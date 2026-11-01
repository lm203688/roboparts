#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""confidence_tier 调和（P0-9）—— 让 entities.json 的 confidence_tier 与
schemas/entities.schema.json 文档化区间**一致**（此前 476 条冲突）。

背景：normalize_categories.confidence_tier_rule() 旧实现按 source_tier 定档、
覆盖 confidence 值域，产物 100% 匹配该规则却与 schema 区间冲突。本脚本用**修复后
的规则**（confidence_tier 只由 confidence 值域决定）重派生所有实体的 confidence_tier。

不跑整条生成管线（避免连带重生成其它派生产物），只改 confidence_tier 字段本身 ——
它是**标签**（供 Agent 判据使用），不参与 compose/compatibility 判定（quarantine 才
是参与闸），故改动语义安全。

用法：
    python scripts/reconcile_confidence_tier.py          # 就地调和，打印变更数
    python scripts/reconcile_confidence_tier.py --check  # 只报告不写入；非零退出=有违规
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'api', 'entities.json')

# 与 normalize_categories.py 修复后的规则保持一致（此处独立实现以便 --check 无依赖运行）
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
    changed = []
    for e in ents:
        cur = e.get('confidence_tier')
        new = corrected_tier(e)
        if cur != new:
            changed.append((e.get('id'), cur, new))
            if not check_only:
                e['confidence_tier'] = new

    if check_only:
        if changed:
            print('confidence_tier 区间违规: %d 条' % len(changed))
            for eid, cur, new in changed[:8]:
                print('  %s  %s -> %s' % (eid, cur, new))
            return 1
        print('confidence_tier 区间一致: 0 违规')
        return 0

    if not changed:
        print('confidence_tier 已一致，无需写入')
        return 0

    # 原子写入
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DATA), suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print('confidence_tier 调和: %d 条变更（%d 实体）' % (len(changed), len(ents)))
    for eid, cur, new in changed[:8]:
        print('  %s  %s -> %s' % (eid, cur, new))
    return 0


if __name__ == '__main__':
    sys.exit(main())
