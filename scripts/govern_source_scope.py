# -*- coding: utf-8 -*-
"""按本仓自己写下的 tier 定义，把「出处只是站点首页」的 Tier A 归位为 Tier B。

【20260809-09 · L1.70 治理动作】
本仓 `tier_definition` 明写「官网首页，无原始链接」= Tier B，
`scripts/quality-baseline.json` 2026-08-05 也已把该规则写进历史记录并当场挤掉 8 条注水。
但那次只跑了一次性脚本、scope 靠手维护的注册表，未落成闸门 —— 于是复发。
本脚本按 `scripts/source_scope.py` 的形状判据全库执行，不依赖任何人工登记表。

同时处理 2 条**出处经实证不存在**的条目（GitHub API 返回 404）：
不是 tier 标错，是出处本身编造，按既有治理约定隔离而非删除。

用法： python scripts/govern_source_scope.py [--dry]
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from govern_tier_c import recompute_meta            # noqa: E402  复用同一套 meta 重算，不另造口径
from source_scope import scope_of, violations       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIMARY = os.path.join(ROOT, 'api', 'entities.json')

CAP_REASON = ('出处仅为站点首页，证明不了该型号/该条目的任何参数；'
              '按 meta.tier_definition「官网首页，无原始链接」= Tier B 归位')

# 出处经 GitHub API 实证不存在（HTTP 404），却曾标 verified=true / tier=A / confidence=0.82。
# 不是分级标错，是引用了一个不存在的仓库 —— 按治理约定隔离，保留条目待补真实出处。
FABRICATED = {
    'XDA-007': 'source_url https://github.com/google-deepmind/puppeteer 经 GitHub API 实证不存在（404）；'
               'manufacturer 标 Google 亦无据。原描述系批量模板生成。',
    'XDA-008': 'source_url https://github.com/google-deepmind/telekinesis 经 GitHub API 实证不存在（404）；'
               'GitHub 全站搜索 telekinesis+teleoperation+robot 命中 0。原描述系批量模板生成。',
}


def main():
    dry = '--dry' in sys.argv
    with io.open(PRIMARY, encoding='utf-8') as f:
        d = json.load(f)
    ents = d['entities']
    by_id = {e['id']: e for e in ents}

    before_a = sum(1 for e in ents if e.get('source_tier') == 'A')

    downgraded = []
    for e in violations(ents):
        e['source_tier_prev'] = 'A'
        e['source_tier'] = 'B'
        e['tier_cap_reason'] = CAP_REASON
        e['source_scope'] = 'vendor'
        downgraded.append(e['id'])

    # 未违规条目也标注 scope，让判据结果对 Agent 可见（否则只有"被罚的"可见）
    for e in ents:
        sc = scope_of(e)
        if sc and e.get('source_scope') != 'vendor':
            e['source_scope'] = sc

    quarantined = []
    for eid, reason in FABRICATED.items():
        e = by_id.get(eid)
        if not e:
            continue
        e['quarantine'] = True
        e['data_quality'] = 'unverifiable_vendor'
        e['verified'] = False
        e['quarantine_reason'] = reason
        e['source_tier'] = 'C'
        e['confidence'] = 0.30
        e['confidence_basis'] = 'source_not_found'
        e['needs_provenance'] = True
        quarantined.append(eid)

    recompute_meta(d)
    pc = d['meta']['provenance_coverage']
    print('Tier A: %d -> %d   traceable_pct -> %.2f%%'
          % (before_a, pc['tier_a_traceable'], pc['traceable_pct']))
    print('首页封顶降级 %d 条；出处证伪隔离 %d 条 %s'
          % (len(downgraded), len(quarantined), quarantined))

    if dry:
        print('[dry] 未写盘')
        return

    with io.open(PRIMARY, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    # 同步 api/*.json 与 data.js 中的同 id 记录（与 govern_tier_c 相同的字段集）
    patched = {}
    for e in ents:
        patched[e['id']] = {k: e[k] for k in
                            ('source_tier', 'confidence', 'confidence_basis',
                             'quarantine', 'data_quality', 'verified', 'source_scope')
                            if k in e}
    api_dir = os.path.join(ROOT, 'api')
    for fn in sorted(os.listdir(api_dir)):
        if not fn.endswith('.json') or fn == 'entities.json':
            continue
        p = os.path.join(api_dir, fn)
        try:
            with io.open(p, encoding='utf-8') as f:
                obj = json.load(f)
        except Exception:
            continue
        hits = [0]

        def walk(o):
            if isinstance(o, dict):
                i = o.get('id')
                if isinstance(i, str) and i in patched and ('name' in o or 'category' in o):
                    for k, v in patched[i].items():
                        if o.get(k) != v:
                            o[k] = v
                            hits[0] += 1
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(obj)
        if hits[0]:
            with io.open(p, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            print('  synced %-26s fields=%d' % (fn, hits[0]))


if __name__ == '__main__':
    main()
