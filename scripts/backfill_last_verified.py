#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts last_verified 诚实回填（G-07 · 2026-10-17）

审计实测：868 条实体中 301 条缺 last_verified（34.7%）。

**核心纪律：不伪造日期。** 缺 last_verified 分两类：
  A. 从 verification_note 里能看到 HTTP 探测痕迹（10 条）—— probe 发生过，
     但没落 last_verified。这类补 last_verified = audit date（2026-10-17），
     basis = 'audit_backfill:probed'，同时保留 verification_note 原样。
  B. 从未做过任何探测（291 条）—— 没依据写日期。写 last_verified = null，
     加 last_verified_status = 'never_probed'，让缺口**显式可见**（比沉默更好）。

绝不把 last_verified 填成"数据入库日期"或"随便一个昨天"—— 那是造证据，
和 G-01 的搜索 URL 冒充深链是同一类自欺。

用法：
    python scripts/backfill_last_verified.py [--dry-run]

幂等：可重复运行。
"""
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_PATH = os.path.join(ROOT, 'api', 'entities.json')

# 审计回填日期（= 首次发现缺口、并诚实登记的那天）
AUDIT_DATE = '2026-10-17'

# HTTP 探测痕迹：HTTP 200 / HTTP 403 / HTTP 200 (redirect) 等
PROBE_RE = re.compile(r'HTTP\s+\d{3}', re.I)


def classify_missing(e):
    """对缺 last_verified 的实体做诚实分类。
    返回 (status, basis)。
      status: 'probed' | 'never_probed'
      basis:  简短说明为什么这样分类
    """
    note = str(e.get('verification_note') or '').strip()
    if PROBE_RE.search(note):
        return 'probed', 'audit_backfill:probed'
    # 完全没有探测痕迹
    return 'never_probed', 'never_probed'


def backfill(doc, dry):
    entities = doc['entities']
    changes = {'probed': 0, 'never_probed': 0, 'skipped': 0}
    for e in entities:
        if e.get('last_verified'):
            changes['skipped'] += 1
            continue
        status, basis = classify_missing(e)
        if status == 'probed':
            if not dry:
                e['last_verified'] = AUDIT_DATE
            e['last_verified_basis'] = basis
            changes['probed'] += 1
        else:
            # 不写 last_verified；显式标记状态让缺口可见
            if not dry:
                e['last_verified'] = None
            e['last_verified_basis'] = basis
            changes['never_probed'] += 1
    return changes


def main():
    dry = '--dry-run' in sys.argv
    with open(ENTITIES_PATH, encoding='utf-8') as f:
        doc = json.load(f)

    before_missing = sum(1 for e in doc['entities'] if not e.get('last_verified'))
    changes = backfill(doc, dry)

    if not dry:
        # 同步 meta.last_verified_coverage
        total = len(doc['entities'])
        with_lv = sum(1 for e in doc['entities'] if e.get('last_verified'))
        coverage = round(with_lv / total * 100, 2)
        doc.setdefault('meta', {})['last_verified_coverage'] = {
            'pct': coverage,
            'count': with_lv,
            'total': total,
            'backfilled_probed': changes['probed'],
            'never_probed': changes['never_probed'],
            'backfilled_at': AUDIT_DATE,
            'note': 'probed = 从 verification_note 提取到 HTTP 探测痕迹，回填为审计日；'
                    'never_probed = 从未探测，last_verified=null 且 basis 显式可见',
        }
        with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write('\n')

    print('=== last_verified 诚实回填 ===', '(dry-run)' if dry else '')
    print(f'  回填前缺: {before_missing} 条')
    print(f'  probed（可回填）: {changes["probed"]} 条')
    print(f'  never_probed（不回填，显式标记）: {changes["never_probed"]} 条')
    print(f'  已存在（跳过）: {changes["skipped"]} 条')


if __name__ == '__main__':
    sys.exit(main())
