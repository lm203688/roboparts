#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts T5 数据实体扩展 - 批次合并器
扫描 ops/entity-expansion/batch-*.json 并合并进 api/entities.json

准入门禁：id/name/category + source/confidence/last_verified 六字段缺一不入库。
幂等：按 id + 同名去重，已存在则跳过。

【20260805 修复】此前 glob 硬编码为 'batch-20260805-*.json'，换到下一个周期后
新分片会被静默忽略、脚本照样 exit 0 —— 正是 T5 此前"零产出静默死亡"的同款死法。
现改为通配全部日期的 'batch-*.json'，历史分片靠幂等跳过，无副作用。
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES = os.path.join(ROOT, 'api', 'entities.json')
BATCH_DIR = os.path.join(ROOT, 'ops', 'entity-expansion')
BATCH_GLOB = 'batch-*.json'   # 通配全部日期，勿改回硬编码日期（见文件头 20260805 修复说明）
CANONICAL = {
    'actuators', 'sensors', 'chips', 'interfaces', 'protocols',
    'llms', 'platforms', 'flexible_actuators', 'robot_ai_models', 'data_acquisition',
}
GATE = ['id', 'name', 'category', 'source', 'confidence', 'last_verified']


def main():
    doc = json.load(open(ENTITIES, encoding='utf-8'))
    candidates = []
    for p in sorted(glob.glob(os.path.join(BATCH_DIR, BATCH_GLOB))):
        part = json.load(open(p, encoding='utf-8'))
        candidates.extend(part['entities'])
        print('载入分片:', os.path.basename(p), len(part['entities']), '条')
    batch = {'entities': candidates}
    existing = {e['id'] for e in doc['entities']}
    existing_names = {(e.get('name') or '').strip().lower() for e in doc['entities']}

    accepted, rejected, skipped = [], [], []
    for e in batch['entities']:
        miss = [k for k in GATE if not e.get(k)]
        if miss:
            rejected.append((e.get('id', '?'), '缺字段: ' + ','.join(miss)))
            continue
        if e['category'] not in CANONICAL:
            rejected.append((e['id'], '非标准类目: ' + str(e['category'])))
            continue
        if e['id'] in existing:
            skipped.append((e['id'], 'id 已存在'))
            continue
        if (e.get('name') or '').strip().lower() in existing_names:
            skipped.append((e['id'], '同名实体已存在'))
            continue
        accepted.append(e)
        existing.add(e['id'])
        existing_names.add(e['name'].strip().lower())

    doc['entities'].extend(accepted)
    json.dump(doc, open(ENTITIES, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(ENTITIES, 'a', encoding='utf-8').write('\n')

    print('=== T5 实体扩展门禁结果 ===')
    print('批次候选 :', len(batch['entities']))
    print('入库     :', len(accepted))
    print('拒绝     :', len(rejected), rejected)
    print('跳过重复 :', len(skipped), skipped)
    print('实体总数 :', len(doc['entities']))
    for e in accepted:
        print('  + %-34s %-12s %s' % (e['id'], e['category'], e['name']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
