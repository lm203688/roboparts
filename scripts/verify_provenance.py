#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_provenance.py —— 具身跨层溯源闸门（审计 + 阴阳/变异自证）

为什么要这道闸门
----------------
api/provenance.json 的核心输出是**四个布尔**（L1–L4 连接条件是否满足）。
布尔最容易假绿，也最容易假红：

  · 假绿一例（本脚本首版真实踩到）：L3 判据把 robot_ai_models 条目与自己比，
    而该文件是 entities.json 里那 46 条实体的**派生视图**（条目 id 就是实体 id），
    于是"引用自己"被当成了一次跨层引用，产物报 body→policy = true —— 而真实的
    物理零件引用数是 0。若没有这道闸门，"链已闭合"会作为事实对外输出。
  · 假红一例：把 dangling 误判成 complete，或反过来，都会让"缺口追踪"失真。

故本闸门三趟：
  ① 契约校验：产物必须满足 schemas/embodiment_provenance.schema.json 的硬约束
     （枚举、必填、相邻层、link 与 layers 的一致性）。
  ② 不变量（含 fail-closed）：complete ⇒ 四链全满足；satisfied=false ⇒ 必须给出
     blocked_by（**不得"因为不知道所以不满足"却不说原因**）；dangling ⇒ 必须指明断点。
  ③ 自证：阳性（满足即 complete）、阴性（缺条件不得 complete）、
     **回归守卫**（自引用不得被算成跨层引用）。

用法
----
    python scripts/verify_provenance.py             # 审计
    python scripts/verify_provenance.py --self-test # 阴阳/变异自证
    python scripts/verify_provenance.py --quiet
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from build_provenance import (  # noqa: E402
    build, _referenced_ids, LAYER_ORDER, OUT,
)

LAYER_ENUM = set(LAYER_ORDER)
STATUS_ENUM = {'complete', 'partial', 'dangling', 'spec-example'}
AVAIL_ENUM = {'populated', 'partial', 'declared_empty', 'external_not_ingested'}


def check_doc(doc):
    """契约 + 不变量。纯函数，可审真实产物，也可审人为改坏的产物。"""
    P = []
    if doc.get('meta', {}).get('schema') != 'embodiment_provenance/v1':
        P.append('meta.schema 不是 embodiment_provenance/v1')
    inv = doc.get('layer_inventory') or {}
    missing = LAYER_ENUM - set(inv)
    if missing:
        P.append('layer_inventory 缺层: %s' % sorted(missing))
    for k, v in inv.items():
        if v.get('available') not in AVAIL_ENUM:
            P.append('layer %s 的 available 非法: %r' % (k, v.get('available')))
    links = doc.get('links') or []
    # 相邻层必须恰好四条，且顺序正确
    want = list(zip(LAYER_ORDER, LAYER_ORDER[1:]))
    got = [(l.get('from'), l.get('to')) for l in links]
    if got != want:
        P.append('links 不是四个相邻层对（期望 %s，实得 %s）' % (want, got))
    for l in links:
        if not l.get('requires'):
            P.append('link %s→%s 缺机器可判定的 requires' % (l.get('from'), l.get('to')))
        # fail-closed：不满足就必须说清被什么挡住
        if l.get('satisfied') is False and not l.get('blocked_by'):
            P.append('link %s→%s 未满足却未给出 blocked_by（不得静默"不满足"）'
                     % (l.get('from'), l.get('to')))
    for c in doc.get('chains') or []:
        cid = c.get('id')
        if not str(cid or '').startswith('PROVC-'):
            P.append('chain id 必须以 PROVC- 开头: %r' % cid)
        st = c.get('status')
        if st not in STATUS_ENUM:
            P.append('chain %s status 非法: %r' % (cid, st))
        lids = [l.get('id') for l in (c.get('layers') or [])]
        if lids and lids != [x for x in LAYER_ORDER if x in set(lids)]:
            P.append('chain %s 的层顺序错乱: %s' % (cid, lids))
        bad = sorted(set(lids) - LAYER_ENUM)
        if bad:
            P.append('chain %s 含非法层: %s' % (cid, bad))
        for l in c.get('layers') or []:
            if (l.get('prov') or {}).get('source') in (None, ''):
                P.append('chain %s 的层 %s 缺 prov.source（溯源链自身必须可溯源）'
                         % (cid, l.get('id')))
        # 状态与连接的语义一致性
        if st == 'complete' and not all(x.get('satisfied') for x in (c.get('links') or [])):
            P.append('chain %s 标 complete 但有 link 未满足（假绿）' % cid)
        if st == 'dangling' and not c.get('dangling_at'):
            P.append('chain %s 标 dangling 却未给 dangling_at' % cid)
        if st == 'complete' and c.get('dangling_at'):
            P.append('chain %s 标 complete 却又有 dangling_at' % cid)
    s = doc.get('chain_summary') or {}
    chains = doc.get('chains') or []
    if s.get('total') != len(chains):
        P.append('chain_summary.total %s != 实得 %d' % (s.get('total'), len(chains)))
    if s.get('complete') != sum(1 for c in chains if c.get('status') == 'complete'):
        P.append('chain_summary.complete 与 chains 不符（汇总层撒谎）')
    if s.get('links_satisfied') != sum(1 for l in links if l.get('satisfied')):
        P.append('chain_summary.links_satisfied 与 links 不符')
    if s.get('links_total') != len(links):
        P.append('chain_summary.links_total %s != 实得 %d' % (s.get('links_total'), len(links)))
    # honest_limits 必须存在且提到完整链数（防"缺口被删掉一句话就消失"）
    hl = ' '.join((doc.get('meta') or {}).get('honest_limits') or [])
    if '完整链数' not in hl:
        P.append('meta.honest_limits 未披露完整链数（缺口叙述被抹掉）')
    return P


def strip_ts(doc):
    d = copy.deepcopy(doc)
    m = d.get('meta') or {}
    m.pop('generated_at', None)
    # meta.access 是 inject_api_access.py 的受管区（构建器不产出、注入器负责）。
    # 若不剥离，每次注入后的合法比对都会假红 —— 与 verify_morphology_graph 同口径。
    m.pop('access', None)
    return d


def self_test():
    ok, fail = [], []

    def chk(name, cond, detail=''):
        (ok if cond else fail).append(name)
        print('  %s %s%s' % ('✅' if cond else '❌', name,
                             ('  — ' + detail) if detail and not cond else ''))

    good = build(with_timestamp=False)

    # ── 阳性：真实产物通过 ──
    chk('基线：真实产物通过契约 + 不变量', check_doc(good) == [],
        repr(check_doc(good)[:3]))

    # ── 阳性：把四链全设为满足 → complete 合法 ──
    p = copy.deepcopy(good)
    for l in p['links']:
        l['satisfied'] = True
        l['blocked_by'] = None
    for c in p['chains']:
        c['status'] = 'complete'
        c['dangling_at'] = None
        for l in c['links']:
            l['satisfied'] = True
            l['blocked_by'] = None
    p['chain_summary'].update(complete=len(p['chains']),
                              links_satisfied=len(p['links']),
                              first_dangling_at=None)
    chk('阳性① 四链全满足 → complete 合法（判据不是永远判红）',
        check_doc(p) == [], repr(check_doc(p)[:3]))

    # ── 阴性：缺条件不得 complete ──
    n1 = copy.deepcopy(p)
    n1['chains'][0]['links'][0]['satisfied'] = False
    chk('阴性① 标 complete 但有一条 link 不满足 → 判红（假绿被抓）',
        any('假绿' in x for x in check_doc(n1)))

    n2 = copy.deepcopy(good)
    n2['links'][0]['satisfied'] = False
    n2['links'][0]['blocked_by'] = None
    chk('阴性② 不满足却不说被什么挡住 → 判红（不得静默不满足）',
        any('blocked_by' in x for x in check_doc(n2)))

    # ── 变异：汇总层 / 断点被抹 ──
    m1 = copy.deepcopy(good)
    m1['chain_summary']['complete'] = 5
    chk('变异① 汇总层谎报 complete 数 → 判红', any('汇总层撒谎' in x for x in check_doc(m1)))

    m2 = copy.deepcopy(good)
    for c in m2['chains']:
        c['dangling_at'] = None
    chk('变异② dangling 却不给断点 → 判红', any('dangling_at' in x for x in check_doc(m2)))

    m3 = copy.deepcopy(good)
    m3['meta']['honest_limits'] = ['一切正常']
    chk('变异③ 抹掉"完整链数"披露 → 判红（缺口叙述不得消失）',
        any('完整链数' in x for x in check_doc(m3)))

    m4 = copy.deepcopy(good)
    m4['links'] = m4['links'][:3]
    chk('变异④ 抽掉一条相邻层连接 → 判红', any('相邻层' in x for x in check_doc(m4)))

    m5 = copy.deepcopy(good)
    m5['layer_inventory'].pop('behavior', None)
    chk('变异⑤ 抽掉一层 → 判红', any('缺层' in x for x in check_doc(m5)))

    # ── 回归守卫：自引用假阳性（本脚本首版真实踩到的 bug）──
    body_ids = {'ACT-001', 'GRIP-002'}
    # 派生视图条目：自身 id 就是实体 id，且不引用任何别的零件
    derived_view_entry = {'id': 'ACT-001', 'name': '某模型', 'applications': ['humanoid']}
    chk('守卫① 派生视图条目"引用自己"**不得**算成跨层引用',
        _referenced_ids(derived_view_entry, body_ids, skip_keys=('id',)) == set(),
        repr(_referenced_ids(derived_view_entry, body_ids, skip_keys=('id',))))
    # 阳性对照：真的引用了另一个零件必须能被发现
    real_ref = {'id': 'ACT-001', 'targets': ['GRIP-002']}
    chk('守卫② 真正引用别的零件必须被发现（判据不是恒空）',
        _referenced_ids(real_ref, body_ids, skip_keys=('id',)) == {'GRIP-002'},
        repr(_referenced_ids(real_ref, body_ids, skip_keys=('id',))))
    chk('守卫③（反证）**显式**不跳过 id 时才会误命中 —— 证明 skip_keys 真在起作用',
        _referenced_ids(derived_view_entry, body_ids, skip_keys=()) == {'ACT-001'})

    print()
    print('  自证结果：通过 %d / 失败 %d' % (len(ok), len(fail)))
    if fail:
        print('  失败项：')
        for f in fail:
            print('    - ' + f)
    return 1 if fail else 0


def audit(quiet=False):
    if not os.path.exists(OUT):
        print('❌ api/provenance.json 不存在（先跑 scripts/build_provenance.py）')
        return 1
    committed = json.load(open(OUT, encoding='utf-8'))
    fresh = build(with_timestamp=False)
    problems = check_doc(committed)
    if strip_ts(committed) != strip_ts(fresh):
        where = [k for k in ('meta', 'layer_inventory', 'links', 'chains', 'chain_summary')
                 if strip_ts(committed).get(k) != strip_ts(fresh).get(k)]
        problems.append('已提交产物与现算不一致（漂移）: %s' % where)
    if problems:
        print('❌ 溯源闸门未通过（%d 项）' % len(problems))
        for p in problems:
            print('   - ' + p)
        return 1
    s = committed['chain_summary']
    if not quiet:
        print('  ✅ 跨层溯源契约 + 不变量通过')
        print('     层：%s' % ' · '.join('%s=%s(%d)' % (k, v['available'], v['count'])
                                        for k, v in committed['layer_inventory'].items()))
        print('     链 %d 条（完整 %d）· 连接条件满足 %d/%d · 首个断点 %s'
              % (s['total'], s['complete'], s['links_satisfied'], s['links_total'],
                 s['first_dangling_at']))
    print('✅ 跨层溯源通过')
    return 0


def main():
    if '--self-test' in sys.argv:
        return self_test()
    return audit(quiet='--quiet' in sys.argv)


if __name__ == '__main__':
    sys.exit(main())
