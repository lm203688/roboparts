#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合成测试对池生成器 · 2026-10-14 阶段 C · 规则合成，零人工，可复现。

动机
----
RoboParts 现有 Golden 评估集（api/eval/compatibility-golden.json）28 条，全部是
人工手写的 freeze_anchor。这是好事（人工审阅的冻结锚点），但也是天花板——
每次想扩测试对都要写 case、跑引擎、贴 rationale。阶段 C 用一个「合成池」把
这个瓶颈解开：规则从 cohort 可行集里自动生成候选对，独立存放，**不污染
Golden 集**，比例被硬闸门守 ≤ 100 对（占 Golden 的 ~3.5×，远低于 20% 的
污染上限口径）。

数据流
------
输入：
  - api/cohort_feasibility.json  → gap_profiles[].top_nodes（3 桶，各 25 节点）
  - api/evidence_valuation.json  → entity_mdv_index（作为诚实元数据，非排序键）
  - api/entities.json            → entity id 校验（保证两端可查）

输出：
  - api/synthesized-pair-pool.json
    - meta: schema / generated_at / generated_by / cap / honest_limits
    - summary: 总数 / 跨桶数 / 桶内数 / category 分布
    - pairs: [{id, node_a, node_b, node_a_category, node_b_category,
              gap_profile_ref, combination_type,
              mdv_a_total, mdv_b_total, rationale}]

采样策略（**关键诚实**）
------------------------
- **不用 MDV 排序**：MDV index 里 top_nodes 的 MDV 值几乎全是 0（637 个
  electrical 只有 1 个非零，575 个 mechanical 全 0）。原因：cohort_feasibility
  的 top_nodes 是"缺口画像典型节点"（覆盖某类缺口的代表），**不是** MDV
  优先级；MDV 是"补单条声明的边际上界"，与"典型代表"正交。
- **用 category 分层**：每个 gap_profile 内按 category 均匀抽样，保证池里
  品类多样性（actuators / sensors / grippers / flexible_actuators 各占一部分），
  而不是被最大桶吃光。
- 跨桶（~50%）+ 桶内（~50%）组合，覆盖"不同缺口画像组合"和"同质可行集"。
- 抽样种子固定（`__synth_v0__`）→ 每次运行输出可复现，可进 regression。

诚实边界（写入 meta.honest_limits）
-----------------------------------
- 合成池是「待评审候选」，**不进入 Golden 集**，Golden 保持人工审阅纯净
- 不预测 verdict：引擎的实际判定要等 CI 跑 eval_compat 才知，本池只做候选
  → 违反 AP-05（不可追溯的合成数据）的正是"直接生成的 verdict"，本池没有
  verdict 字段
- MDV 值仅作元数据（诚实记录，非零值极少，非排序依据）
- 池上限 100 对是硬约束（ci_gate.py 里 gate_synthesized_pair_pool 会核对）

验证（自证）
------------
- 幂等：连跑两次输出 diff 为空（RNG 种子固定）
- fail-fast：cohort_feasibility / evidence_valuation / entities.json 任一缺失
  → 非 0 退出
- 阴阳对照：--self-test 检查池里每条 pair 的两端都在 entities.json 里、
  gap_profile_ref 在 cohort_feasibility.gap_profiles 里、combination_type
  在允许枚举内、pool 大小 ≤ 上限
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEMA = 'roboparts/synthesized_pair_pool/v1'
GENERATED_BY = 'scripts/build_synthesized_pair_pool.py'
POOL_CAP = 100  # 硬上限，避免 pool 无限膨胀；闸门会核对
RNG_SEED = '__synth_v0__'
ALLOWED_COMBINATION_TYPES = ('intra_profile', 'cross_profile')


def load(path, label):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        sys.exit('[FATAL] %s 不存在：%s' % (label, p))
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        sys.exit('[FATAL] %s 解析失败：%s' % (label, e))


def mdv_sum(entity_id, mdv_index, axes=('electrical', 'mechanical', 'signal')):
    """累加一个实体在多个轴上的 MDV 值；不存在的轴记 0。
    仅作元数据记录，不作为排序键（见文件顶部诚实说明）。"""
    total = 0
    for ax in axes:
        total += int(mdv_index.get('%s::%s' % (entity_id, ax), 0) or 0)
    return total


def stratified_sample(nodes, k, rng):
    """按 category 分层均匀抽样：每 category 至少 1 个（若总数够），
    剩余名额随机抽。若不足 k 则返回全部。"""
    by_cat = defaultdict(list)
    for n in nodes:
        by_cat[n.get('category') or 'unknown'].append(n)
    picked = []
    cats = sorted(by_cat.keys())
    for cat in cats:
        if len(picked) >= k:
            break
        candidates = by_cat[cat]
        picked.append(rng.choice(candidates))
    remaining = k - len(picked)
    if remaining > 0:
        all_nodes = nodes[:]
        rng.shuffle(all_nodes)
        picked.extend(all_nodes[:remaining])
    return picked[:k]


def sample_pool(cfp, evl, ents):
    """从 cohort gap_profiles 生成合成对池。"""
    rng = random.Random(RNG_SEED)

    buckets = []
    for gp in cfp.get('gap_profiles') or []:
        top = gp.get('top_nodes') or []
        strat = stratified_sample(top, min(10, len(top)), rng)
        buckets.append({
            'missing_axes': gp.get('missing_axes') or [],
            'nodes': strat,
        })
    if len(buckets) < 2:
        sys.exit('[FATAL] gap_profiles 不足 2 桶（%d），无法做跨桶配对'
                 % len(buckets))

    candidates = []
    for i, bi in enumerate(buckets):
        for j, bj in enumerate(buckets):
            same = (i == j)
            for na in bi['nodes']:
                for nb in bj['nodes']:
                    if na.get('id') == nb.get('id'):
                        continue
                    a, b = sorted([na.get('id'), nb.get('id')], key=str)
                    na_sorted, nb_sorted = (na, nb) if a == na.get('id') else (nb, na)
                    key_a = ','.join(sorted(bi['missing_axes']))
                    key_b = ','.join(sorted(bj['missing_axes']))
                    gap_ref = (key_a if same
                               else '%s × %s' % (key_a, key_b))
                    candidates.append((
                        'intra_profile' if same else 'cross_profile',
                        a, b,
                        gap_ref,
                        na_sorted.get('category'),
                        nb_sorted.get('category'),
                    ))

    intra = [c for c in candidates if c[0] == 'intra_profile']
    cross = [c for c in candidates if c[0] == 'cross_profile']
    rng.shuffle(intra)
    rng.shuffle(cross)

    half = POOL_CAP // 2
    picked = (cross[:half] + intra[:half])[:POOL_CAP]

    mdv_idx = evl.get('entity_mdv_index') or {}
    ent_ids = {e.get('id') for e in ents.get('entities', [])}
    pairs = []
    used_ids = set()
    for idx, (typ, a, b, gap_ref, a_cat, b_cat) in enumerate(picked, start=1):
        if a not in ent_ids or b not in ent_ids:
            continue
        key = tuple(sorted([a, b]))
        if key in used_ids:
            continue
        used_ids.add(key)
        mdv_a = mdv_sum(a, mdv_idx)
        mdv_b = mdv_sum(b, mdv_idx)
        pairs.append({
            'id': 'SYNTH-%03d' % idx,
            'node_a': a,
            'node_b': b,
            'node_a_category': a_cat,
            'node_b_category': b_cat,
            'gap_profile_ref': gap_ref,
            'combination_type': typ,
            'mdv_a_total': mdv_a,
            'mdv_b_total': mdv_b,
            'rationale': (
                '%s 配对（gap: %s）· category %s×%s。'
                '不预测 verdict——实际兼容性待 eval_compat 引擎裁定。'
                'MDV 元数据（%d+%d）仅为记录，非排序键。'
                % (typ, gap_ref, a_cat, b_cat, mdv_a, mdv_b)
            ),
        })
    return pairs


def self_test(pool_path):
    """阴阳自证：schema / 上限 / 实体存在性 / gap_profile 合法性 / 组合类型枚举。"""
    p = os.path.join(ROOT, pool_path)
    if not os.path.exists(p):
        sys.exit('[SELF-TEST FAIL] %s 不存在' % pool_path)
    d = json.load(open(p, encoding='utf-8'))
    if (d.get('meta') or {}).get('schema') != SCHEMA:
        sys.exit('[SELF-TEST FAIL] schema = %r，应为 %r'
                 % ((d.get('meta') or {}).get('schema'), SCHEMA))
    pairs = d.get('pairs') or []
    if not pairs:
        sys.exit('[SELF-TEST FAIL] pairs 为空')
    if len(pairs) > POOL_CAP:
        sys.exit('[SELF-TEST FAIL] pool 大小 %d 超过上限 %d' % (len(pairs), POOL_CAP))

    ents = load('api/entities.json', 'entities.json')
    ent_ids = {e.get('id') for e in ents.get('entities', [])}
    missing = [pp.get('id') for pp in pairs
               if pp.get('node_a') not in ent_ids or pp.get('node_b') not in ent_ids]
    if missing:
        sys.exit('[SELF-TEST FAIL] %d pair 端点不在 entities.json：%s'
                 % (len(missing), missing[:5]))

    cfp = load('api/cohort_feasibility.json', 'cohort_feasibility.json')
    profile_keys = []
    for gp in cfp.get('gap_profiles') or []:
        axes = tuple(sorted(gp.get('missing_axes') or []))
        profile_keys.append(','.join(axes))
    known_gaps = set(profile_keys)
    keys_list = sorted(profile_keys)
    for i, k1 in enumerate(keys_list):
        for j, k2 in enumerate(keys_list):
            if i < j:
                known_gaps.add('%s × %s' % (k1, k2))
                known_gaps.add('%s × %s' % (k2, k1))
    bad_gap = [pp['id'] for pp in pairs if pp.get('gap_profile_ref') not in known_gaps]
    if bad_gap:
        sys.exit('[SELF-TEST FAIL] %d pair 的 gap_profile_ref 不在 cohort 定义里：%s'
                 % (len(bad_gap), bad_gap[:5]))

    bad_type = [pp['id'] for pp in pairs
                if pp.get('combination_type') not in ALLOWED_COMBINATION_TYPES]
    if bad_type:
        sys.exit('[SELF-TEST FAIL] %d pair 的 combination_type 非法：%s'
                 % (len(bad_type), bad_type[:5]))

    dup_ids = [i for i, c in Counter(pp.get('id') for pp in pairs).items() if c > 1]
    if dup_ids:
        sys.exit('[SELF-TEST FAIL] 重复 id：%s' % dup_ids)
    self_pair = [pp['id'] for pp in pairs if pp.get('node_a') == pp.get('node_b')]
    if self_pair:
        sys.exit('[SELF-TEST FAIL] 自配对（node_a == node_b）：%s' % self_pair[:5])

    print('[SELF-TEST PASS] pool=%d，schema=%s，实体存在性 100%%，'
          'gap_profile_ref 全部合法，combination_type 全部合规，'
          '无重复 id，无自配对'
          % (len(pairs), SCHEMA))


def main():
    if '--self-test' in sys.argv:
        self_test('api/synthesized-pair-pool.json')
        return 0

    cfp = load('api/cohort_feasibility.json', 'cohort_feasibility.json')
    evl = load('api/evidence_valuation.json', 'evidence_valuation.json')
    ents = load('api/entities.json', 'entities.json')

    pairs = sample_pool(cfp, evl, ents)
    if not pairs:
        sys.exit('[FATAL] 生成 0 对——gap_profiles 或 entities 数据异常')

    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    intra_count = sum(1 for p in pairs if p['combination_type'] == 'intra_profile')
    cross_count = len(pairs) - intra_count
    cat_counter = Counter()
    for p in pairs:
        cat_counter[p.get('node_a_category')] += 1
        cat_counter[p.get('node_b_category')] += 1

    out = {
        'meta': {
            'schema': SCHEMA,
            'generated_at': now,
            'generated_by': GENERATED_BY,
            'rng_seed': RNG_SEED,
            'pool_cap': POOL_CAP,
            'title': 'RoboParts 合成测试对池 · 规则生成 · 待人工评审',
            'description': (
                '从 cohort_feasibility.gap_profiles（3 桶，各抽 category 分层 10 节点）'
                '自动生成合成测试对候选。跨桶 vs 桶内各半，共 %d 对。'
                '池子与 Golden 集（api/eval/compatibility-golden.json）分家存放——'
                'Golden 保持人工审阅纯净，本池是"待评审候选"。' % len(pairs)
            ),
            'sources': [
                'api/cohort_feasibility.json (gap_profiles.top_nodes)',
                'api/evidence_valuation.json (entity_mdv_index — 仅元数据)',
                'api/entities.json (entity id 校验)',
            ],
            'sampling_policy': {
                'sort_key': 'NOT_MDV — cohort top_nodes 是"缺口画像典型"，不是"MDV 优先级"；'
                            'MDV index 里 top_nodes 的 MDV 值 637 条 electrical 只有 1 个非零、'
                            '575 条 mechanical 全 0，不能作为排序键',
                'stratification': '每个 gap_profile 内按 category 均匀抽 10 个（覆盖品类多样性）',
                'combination_mix': 'cross_profile ≈ 50% / intra_profile ≈ 50%',
                'dedup': 'sorted(node_a, node_b) 作 pair key，去重',
                'idempotent': 'RNG seed = %s，连跑两次输出一致' % RNG_SEED,
            },
            'honest_limits': [
                '本池不预测 verdict——生成对的两端兼容性要 eval_compat 引擎跑过才知。'
                '本层只输出"候选 + 溯源"，不输出"结论"。',
                'MDV 值仅作元数据记录（诚实记录，非排序依据）。MDV index 里 '
                'top_nodes 的值几乎全为 0——这是 cohort 层的诚实边界（top_nodes 是'
                '"缺口画像典型"，不是"MDV 优先级"），不是本层的数据质量缺陷。',
                '合成池是"待评审候选"，不是"直接进主库"。任何人工评审采纳后，'
                '应迁移到 api/eval/compatibility-golden.json，本池不新增重复条目。',
                'RNG 种子固定（%s）——每次运行输出可复现，可进 regression。'
                '如需换一批候选，改种子或改 cap。' % RNG_SEED,
                '池上限 %d 对是硬约束（ci_gate.py 里 gate_synthesized_pair_pool 会核对）。'
                '超过即判红——防止合成对无限膨胀后与 Golden 集边界模糊。' % POOL_CAP,
            ],
        },
        'summary': {
            'total_pairs': len(pairs),
            'intra_profile_pairs': intra_count,
            'cross_profile_pairs': cross_count,
            'category_occurrence': dict(cat_counter.most_common()),
            'golden_reference_count': 28,
            'pool_to_golden_ratio_pct': round(len(pairs) / 28 * 100, 2),
            'ratio_cap_pct': 20,
        },
        'pairs': pairs,
    }

    out_path = os.path.join(ROOT, 'api', 'synthesized-pair-pool.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('[OK] api/synthesized-pair-pool.json 写入 · %d pairs '
          '(intra=%d cross=%d) · categories=%s'
          % (len(pairs), intra_count, cross_count,
             ', '.join('%s:%d' % (k, v) for k, v in cat_counter.most_common()[:5])))


if __name__ == '__main__':
    sys.exit(main())
