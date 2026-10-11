#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0: 为 api/entities.json（真相源）中**可一手核实**的 actuators 补 connector 字段。

纪律：
- 只写**已核实**的连接器型号，不臆造、不推断同厂其他型号。
- 只使用已存在的字段（connector / last_verified），不新增字段，
  避免触发 regression「分类 JSON 与真相源字段级零差异」门禁。
- 本脚本改真相源，之后必须跑 add_mechanical_interface.py + regen_derived.py 派生。

核实来源（检索 2026-09-08）：
- ROBOTIS e-Manual XM430-W210 / XM540-W150：TTL 版 Housing JST EHR-03、PCB Header JST B3B-EH-A、
  Crimp JST SEH-001T-P0.6、21AWG；RS-485 版 Housing JST EHR-04、Header JST B4B-EH-A。
- robotis.us 官方技术提示：型号以 T 结尾 = TTL 3-pin；以 R 结尾及 P 系列 = RS-485 4-pin。
- CubeMars AK80-9 V3.0 官方商品页 + OpenELAB wiki：黑色口 XT30（2+2，电源+CAN 合一），
  白色口 CJT 3-pin（UART 调试）；规格表列 Power connector XT30PW-M、UART connector A1257WR-S-3P。
  ⚠ 来源差异：OpenELAB 另列 CAN connector A1257WR-S-4P，官网文案称 CAN 已并入 XT30 2+2。
  故本脚本只写两处一致的（电源 XT30PW-M / UART A1257WR-S-3P），差异记入文档不在实体内断言。
"""
import json
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'api', 'entities.json')
VERIFY_DATE = '2026-09-08'

# id -> connector 字符串（仅一手核实项）
PATCH = {
    'ACT-001': 'JST EHR-03（TTL 3-pin；PCB header B3B-EH-A）',
    'ACT-002': 'JST EHR-03（TTL 3-pin；PCB header B3B-EH-A）',
    'ACT-003': 'JST EHR-04（RS-485 4-pin；PCB header B4B-EH-A）',
    'ACT-016': 'XT30PW-M（电源/CAN）+ A1257WR-S-3P（UART 调试）',
}

# 未纳入的自由说明（写报告用，不写进实体）
SKIPPED = [
    ('ACT-006 T-Motor AK80-64', '同属 T-Motor/CubeMars AK 家族，但本型号连接器未见官方规格表明确列出，不臆断'),
    ('ACT-007 T-Motor AK10-9', '同上'),
    ('ACT-015 CubeMars GL40', '同上'),
    ('ACT-011/012 Unitree', '厂商 proprietary，无公开连接器规格'),
    ('ACT-013/014 Tesla/Figure', 'classified / proprietary'),
    ('其余 200+ 条', '多为工业级伺服/气动/专有总线，连接器需逐个查规格书，非本轮可批量核实'),
]


def main():
    with io.open(SRC, encoding='utf-8') as f:
        data = json.load(f)
    ents = data['entities']
    by_id = {e['id']: e for e in ents}

    acts = [e for e in ents if e.get('category') == 'actuators']
    before = sum(1 for e in acts if e.get('connector'))

    applied, missing = [], []
    for eid, conn in PATCH.items():
        e = by_id.get(eid)
        if not e:
            missing.append(eid)
            continue
        if e.get('category') != 'actuators':
            missing.append(eid + ' (非 actuators)')
            continue
        e['connector'] = conn
        e['last_verified'] = VERIFY_DATE
        applied.append((eid, e.get('name'), conn))

    after = sum(1 for e in acts if e.get('connector'))
    total_conn = sum(1 for e in ents if e.get('connector'))

    with io.open(SRC, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print('=== connector 补丁（真相源 api/entities.json）===')
    print(f'actuators 覆盖：{before} → {after} / {len(acts)}')
    print(f'全库 connector：{total_conn} / {len(ents)}')
    print()
    print('已写入：')
    for eid, name, conn in applied:
        print(f'  {eid} | {name} | {conn}')
    if missing:
        print()
        print('未找到：', missing)
    print()
    print('未纳入（不臆造）：')
    for k, why in SKIPPED:
        print(f'  {k}: {why}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
