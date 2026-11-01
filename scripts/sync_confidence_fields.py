#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""confidence / confidence_tier / confidence_basis 单事实源同步（P0-9/P0-10 收尾）。

reconcile_confidence_tier.py / reconcile_tier_c_cap.py 只改了 api/entities.json
（真相源），但同 id 记录**同时嵌在** api/actuators.json、api/sensors.json 等类别产物里。
govern_tier_c.py 早就示范了这套同步（按 id 匹配、逐文件 walk、原子写回）—— 本脚本做
同样的事，只同步三个字段，防「entities.json 说 A、actuators.json 说 B」的跨文件漂移。

用法：
    python scripts/sync_confidence_fields.py          # 就地同步
    python scripts/sync_confidence_fields.py --check  # 只查不改；非零退出=有漂移
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, 'api')
TRUTH = os.path.join(API, 'entities.json')
FIELDS = ('confidence', 'confidence_tier', 'confidence_basis')


def main() -> int:
    check_only = '--check' in sys.argv
    with io.open(TRUTH, encoding='utf-8') as f:
        truth = json.load(f)
    # 真相源映射 id -> {field: value}
    by_id = {e.get('id'): {k: e.get(k) for k in FIELDS} for e in truth['entities'] if e.get('id')}

    drift_files = []
    total_drift = 0
    for fn in sorted(os.listdir(API)):
        if not fn.endswith('.json') or fn in ('entities.json', 'data.json'):
            continue
        p = os.path.join(API, fn)
        try:
            with io.open(p, encoding='utf-8') as f:
                obj = json.load(f)
        except Exception:
            continue

        drift = [0]

        def walk(o):
            if isinstance(o, dict):
                i = o.get('id')
                if isinstance(i, str) and i in by_id and ('name' in o or 'category' in o):
                    t = by_id[i]
                    for k in FIELDS:
                        if o.get(k) != t.get(k):
                            drift[0] += 1
                            if not check_only:
                                o[k] = t.get(k)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(obj)
        if drift[0]:
            drift_files.append(fn)
            total_drift += drift[0]
            if not check_only:
                with io.open(p, 'w', encoding='utf-8') as f:
                    json.dump(obj, f, ensure_ascii=False, indent=2)

    if check_only:
        if total_drift:
            print('confidence 字段跨文件漂移: %d 处 / %d 个文件' % (total_drift, len(drift_files)))
            print('  文件: %s' % ', '.join(drift_files[:8]))
            return 1
        print('confidence 字段单事实源一致（0 漂移）')
        return 0

    if total_drift:
        print('confidence 字段同步: %d 处 / %d 个文件已对齐真相源' % (total_drift, len(drift_files)))
        for f_ in drift_files[:8]:
            print('  synced:', f_)
    else:
        print('confidence 字段已一致，无需同步')
    return 0


if __name__ == '__main__':
    sys.exit(main())
