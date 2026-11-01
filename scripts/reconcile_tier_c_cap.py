#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tier-C 上限调和（P0-10）—— 无溯源实体不得声称高置信度。

规则（govern_tier_c.py tier_definition）：
    C = 无溯源（历史导入，待补来源，**confidence 上限 0.30**）。
此前 299 条 C 实体中 252 条 confidence ∈ [0.42, 0.90]，远超 0.30 上限 ——
「无溯源却声称高置信」正是「同一事实两处定义」的漂移形态，且无闸门看住。

本脚本：
    ① 对 source_tier='C' 且 confidence>0.30 的实体：confidence 压到 0.30，
       并把 confidence_basis 记为 'tier_c_cap'（若此前有别的 basis 则追加说明）。
    ② 重派生 confidence_tier（修复后的 confidence_tier_rule —— 只由值域决定）。
    ③ 原子写回。

不跑整条管线，只改这两个字段（都是**标签/元信息**，不参与 compose 判定）。

用法：
    python scripts/reconcile_tier_c_cap.py            # 就地调和
    python scripts/reconcile_tier_c_cap.py --check    # 只查不改；非零退出=有违规
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'api', 'entities.json')
CAP = 0.30


def corrected_tier(e):
    conf = e.get('confidence')
    src = e.get('source') or e.get('sources')
    q = bool(e.get('quarantine', False))
    if not src and not q:
        return 'unverified'
    if q:
        return 'unverified'
    if isinstance(conf, (int, float)):
        if conf >= 0.9:
            return 'verified'
        if conf >= 0.7:
            return 'observed'
        if conf >= 0.5:
            return 'derived'
        if conf >= 0.3:
            return 'inferred'
    return 'unverified'


def main() -> int:
    check_only = '--check' in sys.argv
    with open(DATA, encoding='utf-8') as f:
        doc = json.load(f)
    ents = doc.get('entities', [])
    capped = []
    tier_changed = []
    for e in ents:
        # ① C 上限
        if e.get('source_tier') == 'C' and isinstance(e.get('confidence'), (int, float)) and e['confidence'] > CAP:
            if not check_only:
                basis = e.get('confidence_basis')
                e['confidence'] = CAP
                e['confidence_basis'] = (basis + '; tier_c_cap') if basis else 'tier_c_cap'
            capped.append(e.get('id'))
        # ② tier 重派生（无论是否 cap，统一按修复后规则）
        cur = e.get('confidence_tier')
        new = corrected_tier(e)
        if cur != new:
            if not check_only:
                e['confidence_tier'] = new
            tier_changed.append((e.get('id'), cur, new))

    if check_only:
        if capped or tier_changed:
            print('Tier-C 上限违规: %d 条（confidence>%.2f）' % (len(capped), CAP))
            print('confidence_tier 需重派生: %d 条' % len(tier_changed))
            return 1
        print('Tier-C 上限一致（0 违规）')
        return 0

    if not capped and not tier_changed:
        print('Tier-C 上限已一致，无需写入')
        return 0

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DATA), suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print('Tier-C 上限调和: %d 条压到 %.2f · confidence_tier 重派生 %d 条（%d 实体）'
          % (len(capped), CAP, len(tier_changed), len(ents)))
    for eid in capped[:8]:
        print('  cap:', eid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
