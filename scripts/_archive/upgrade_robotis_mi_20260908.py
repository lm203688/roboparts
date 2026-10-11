# -*- coding: utf-8 -*-
"""【20260908】ROBOTIS 条目 mechanical_interface 升 partial（真相源派生流程）。

背景
----
四目标深化扫描（docs/opensource-scan-20260908.md）确认：库内 6 条 ROBOTIS
条目 mechanical_interface 全部 not_declared，而 ROBOTIS 官方公开资料对其
安装体系有明确声明。本轮对**有公开出处**的 5 条升 partial；对无公开安装
声明的 ACT-robotis-20dof-hand 保持 not_declared（不臆造）。

纪律
----
- 只写**经一手检索核实**的事实（官方商店页 / e-Manual / 官方 UR 版手册，
  检索日期 2026-09-08），来源逐条落 source 字段。
- 一律不写法兰级几何（PCD/孔数/螺纹）——公开页面未给出，宁可留空，
  不可臆造（与 mechanical_interfaces.json coverage_policy 一致）。
- 写入后须跑 add_mechanical_interface.py 重算覆盖率（本脚本尾部自动调用），
  再跑 regen_derived.py 重生全部派生副本。
- 幂等：重复运行结果一致。

为何是 partial 而非 declared
----------------------------
厂商公开声明了"怎么装"（专有 horn / FRP 专有框架），但未给出法兰级
可互换几何 → 属"有线索、缺尺寸"，即 partial。
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')
REGISTRY_REF = '/api/mechanical_interfaces.json'

# 检索日期（一手核实日），写入 source 以便复核
RETRIEVED = '2026-09-08'

# X 系列（XM430/XM540 等）家族级声明：HN12-N101 Set 官方页明确
# "This horn set can be assembled on the output shaft wheel gear of Dynamixel X"
# —— 即 X 系列输出端为专有 horn 体系；该页同时明示 HN12-N101 不兼容 MX 系列与 XL430。
_X_FAMILY_NOTE = (
    'DYNAMIXEL X 系列专有安装体系：输出端经 ROBOTIS 专有 horn 套装于输出轴轮齿'
    '（XM430 标配 HN12-N101，经 WB M2.5×6 + M2×3 螺栓与止推垫圈装配），'
    '机身经侧/底面螺栓孔与 ROBOTIS 专用框架紧固；官方明示不兼容 MX 系列与 XL430；'
    '非 ISO 9409-1 法兰，对接标准法兰需转接盘'
)
_X_FAMILY_SRC = (
    'ROBOTIS 官方商店 HN12-N101 Set 与 XM430-W350-T 产品页 '
    '(en.robotis.com, 检索 %s)' % RETRIEVED
)
_X_FAMILY_GAP = (
    'horn/框架孔位 PCD、孔数、螺纹的法兰级几何未在公开页面给出，需对照官方 Drawing；'
    '孔位级互换判定不可用'
)

UPGRADES = {
    'ACT-001': {  # DYNAMIXEL XM540-W270-T（X 系列）
        'declared_note': _X_FAMILY_NOTE + '（XM540 属 X 系列同体系）',
        'source': _X_FAMILY_SRC,
        'gap': _X_FAMILY_GAP,
    },
    'ACT-002': {  # DYNAMIXEL XM430-W350-T（X430，标配 HN12-N101，逐字核实）
        'declared_note': (
            '标配 HN12-N101 标准 horn（X430 系列）：horn 经 WB M2.5×6 + M2×3 螺栓'
            '与止推垫圈装配于输出轴轮齿，可与 ROBOTIS 专用框架/适配件（hinge or adapter）'
            '组装；官方明示 HN12-N101 不兼容 MX 系列与 XL430；'
            '非 ISO 9409-1 法兰，对接标准法兰需转接盘'
        ),
        'source': _X_FAMILY_SRC,
        'gap': _X_FAMILY_GAP,
    },
    'ACT-003': {  # DYNAMIXEL PH54-200-S500-R（P 系列，原 PRO Plus）
        'declared_note': (
            'DYNAMIXEL P 系列（原 PRO Plus）专有安装体系：经 ROBOTIS 专有 FRP54 系列'
            '框架装配（随附 WB M3×8 ×20），官方明示 54 系不能用旧 PRO 铰接框架'
            '（不兼容 FRP54-H110/120/210/220）；输出端为 horn；'
            '非 ISO 9409-1 法兰，对接标准法兰需转接盘'
        ),
        'source': (
            'ROBOTIS 官方商店 PH54-200-S500-R 产品页 (en.robotis.com) '
            '+ e-Manual (emanual.robotis.com, 检索 %s)' % RETRIEVED
        ),
        'gap': _X_FAMILY_GAP,
    },
    'CTRL-005': {  # 条目名 ROBOTIS Dynamixel XM540-W270（与 ACT-001 同产品家族）
        'declared_note': _X_FAMILY_NOTE + '（XM540 属 X 系列同体系）',
        'source': _X_FAMILY_SRC,
        'gap': _X_FAMILY_GAP,
    },
    'GRIP-015': {  # ROBOTIS RH-P12-RN 夹爪
        'declared_note': (
            '官方声明可快装于 ROBOTIS Manipulator：标配 FRP42-A110K 专有支架 '
            '+ WB M3×8 螺栓；UR e-Series 变体（RH-P12-RN-UR）经专用 UR 支架'
            '以 M6×8 螺栓安装于 UR 腕部；未声明 ISO 9409-1，'
            '对接标准法兰需转接盘'
        ),
        'source': (
            'ROBOTIS 官方商店 RH-P12-RN 产品页 (en.robotis.com) '
            '+ RH-P12-RN-UR User Manual (cdn.robotshop.com, 检索 %s)' % RETRIEVED
        ),
        'gap': (
            '支架/腕部对接孔位 PCD、孔数、螺纹的法兰级几何未在公开页面给出；'
            '孔位级互换判定不可用'
        ),
    },
}

# 明确不升级（无公开安装声明，保持 not_declared，不臆造）：
#   ACT-robotis-20dof-hand —— ROBOTIS 2026 新品，公开页面未检索到安装接口声明


def main():
    with io.open(ENT, encoding='utf-8') as f:
        doc = json.load(f)

    ents = {e.get('id'): e for e in doc['entities']}
    changed = []
    for eid, u in UPGRADES.items():
        e = ents.get(eid)
        if e is None:
            print('!! 找不到条目 %s，跳过' % eid)
            continue
        e['mechanical_interface'] = {
            'status': 'partial',
            'mount_type': 'direct_mount',
            'standard': None,
            'flange': None,
            'declared_note': u['declared_note'],
            'source': u['source'],
            'confidence': 0.75,
            'registry_ref': REGISTRY_REF,
            'gap': u['gap'],
        }
        changed.append(eid)

    with io.open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print('ROBOTIS mi 升级完成（%d 条 → partial）：%s' % (len(changed), ', '.join(changed)))
    print('注：ACT-robotis-20dof-hand 无公开安装声明，保持 not_declared（不臆造）')

    # 重算覆盖率（add_mechanical_interface 会保留本脚本写入的有据声明）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import add_mechanical_interface  # noqa: E402
    add_mechanical_interface.main()


if __name__ == '__main__':
    main()
