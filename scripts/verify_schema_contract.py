#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""entities.json ↔ entities.schema.json 结构契约闸门（P0-8）。

此前 **entities.schema.json 从未被任何闸门加载** —— 契约文件写好了但没人校验，
「schema 变了」或「产物违反 schema」都不会让任何机器响。schema_contract.py 只查
5 个核心字段，其余契约形同虚设。

本闸门：
  ① 加载 schemas/entities.schema.json（证明契约文件真实存在且是合法 JSON Schema）。
  ② 用 jsonschema 校验 api/entities.json 的 entities[] 逐条。
  ③ 任何违规 → 判红（fail-closed）。按 error path 归类输出，便于修复。
  ④ 自证（--self-test）：用最小破坏样本验证校验器能抓 4 类违规
     （缺 required / 枚举越界 / 类型错 / confidence 越界），防「闸门没在看东西」。

依赖：jsonschema（已加入 requirements-dev.txt —— build_field_provenance 曾 import
但未声明，本地/CI 依赖不一致）。

用法：
    python scripts/verify_schema_contract.py           # 校验，非零退出 = 判红
    python scripts/verify_schema_contract.py --self-test
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, 'schemas', 'entities.schema.json')
DATA = os.path.join(ROOT, 'api', 'entities.json')


def load():
    with open(SCHEMA, encoding='utf-8') as f:
        schema = json.load(f)
    with open(DATA, encoding='utf-8') as f:
        data = json.load(f)
    return schema, data


def validate_entities(schema, entities):
    """返回 [(实体id, 字段路径, 消息)]。

    逐条实体必须满足 **$defs.Entity**（顶层 schema 是 {meta, entities, count,...}
    文档契约，不能拿整份文档 schema 去验单条实体 —— 那会全员报缺 meta）。
    """
    from jsonschema import Draft202012Validator
    defs = (schema or {}).get('$defs') or {}
    ent_schema = defs.get('Entity')
    if ent_schema is None:
        raise ValueError('schema 缺 $defs.Entity')
    # evolve 保留**完整 schema 作为 $ref 解析根**（否则 Entity 里
    # `$ref:'#/$defs/ConfidenceTier'` 会 PointerToNowhere —— Entity 子 schema 没有 $defs）。
    v = Draft202012Validator(schema).evolve(schema=ent_schema)
    errs = []
    for i, ent in enumerate(entities):
        eid = (ent or {}).get('id', f'<#{i}>')
        for e in v.iter_errors(ent):
            path = '.'.join(str(p) for p in e.absolute_path) or '<root>'
            errs.append((eid, path, e.message))
    return errs


def main() -> int:
    try:
        schema, data = load()
    except Exception as e:
        print('!! 加载失败: %s' % e)
        return 1

    ents = data.get('entities') if isinstance(data, dict) else data
    if not isinstance(ents, list):
        print('!! entities.json 无 entities[] 数组（数据形状异常）')
        return 1

    errs = validate_entities(schema, ents)
    if errs:
        print('entities.json ↔ entities.schema.json 契约: FAIL（%d 条违规 / %d 实体）'
              % (len(errs), len(ents)))
        # 按 字段路径 归类
        by_path = {}
        for eid, path, msg in errs:
            by_path.setdefault(path, []).append((eid, msg))
        for path, items in sorted(by_path.items()):
            print('  ❌ %s ×%d  例: %s' % (path, len(items), items[0][1][:120]))
        return 1
    print('entities.json ↔ entities.schema.json 契约: ✅ %d 实体全合规（schema=%s）'
          % (len(ents), schema.get('schema_version') or schema.get('$id') or '?'))
    return 0


def self_test() -> int:
    """阴阳对照：4 类最小破坏必须被校验器抓到。"""
    schema, data = load()
    ents = data['entities']
    base = ents[0]

    def mk(mut):
        import copy
        e = copy.deepcopy(base)
        mut(e)
        return e

    cases = [
        ('缺 required id', lambda e: e.pop('id', None), 'id'),
        ('枚举越界 data_quality', lambda e: e.__setitem__('data_quality', 'bogus'), 'data_quality'),
        ('类型错 confidence', lambda e: e.__setitem__('confidence', 'high'), 'confidence'),
        ('confidence 越界 >1', lambda e: e.__setitem__('confidence', 1.5), 'confidence'),
    ]
    fails = 0
    print('schema 契约自证:')
    for name, mut, needle in cases:
        errs = validate_entities(schema, [mk(mut)])
        caught = any(needle in path or needle in msg for _, path, msg in errs)
        print('  %s %s（%s）' % ('✅' if caught else '❌', name, '被抓' if caught else '漏检!'))
        if not caught:
            fails += 1
    # 阴性：原始基座不应违规
    errs = validate_entities(schema, [base])
    print('  %s 阴性: 原始实体不违规' % ('✅' if not errs else '❌'))
    if errs:
        fails += 1
    return 1 if fails else 0


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    sys.exit(main())
