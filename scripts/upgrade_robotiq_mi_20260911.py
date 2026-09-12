# -*- coding: utf-8 -*-
"""【20260911】Robotiq 夹爪/力传感器 mechanical_interface 升 declared（真相源派生）。

背景
----
`add_mechanical_interface.py` 的机械可耦合类目白名单原不含 `grippers`，导致库内
4 条 Robotiq 夹爪与 1 条 FT 300-S 力传感器全部停在 not_declared，gap 被写成
"未归类类目 grippers"（= 我们没判过，不是厂商没公开）。而 Robotiq 官方对这套
耦合件有**逐型号、逐 SKU** 的公开声明，属可一手核实的 declared 级数据。

本轮一次性核实并升级 4 条；其余无公开法兰级声明的保持 not_declared，不臆造。

一手出处（检索日 2026-09-11）
----------------------------
A. Robotiq 官方知识库《Integrating Robotiq Products on Non-Supported Robots》
   —— 明确「For grippers (2F-85, 2F-140, Hand-E, Hand-E C10, and EPick)」共用
      同一张耦合件对照表，并单列 FT-300-S 的表：
      https://blog.robotiq.com/knowledge/integration-on-non-supported-robot-5-1736280738706
B. Robotiq 官方手册《Hand-E Instruction Manual》§6.1.1 Couplings（逐耦合件尺寸与销孔）
   https://assets.robotiq.com/website-assets/support_documents/document/online/Hand-E_Instruction_Manual_Web_20190306.zip/Hand-E_Instruction_Manual_Web/Content/6.%20Specifications.htm
C. Robotiq 官方手册《2F-85 & 2F-140 Instruction Manual》§6.1.1 Couplings
   https://assets.robotiq.com/website-assets/support_documents/document/2F-85_2F-140_TM-OMRON_InstructionManual_20190206.pdf

为何是 declared 而非 partial
----------------------------
官方给出的不是"怎么装"的描述，而是**带 ISO 9409-1 编码的孔位**（PCD / 孔数 /
螺纹 / 定位销全部明确），可直接进入法兰互换比对集合 → declared。

纪律
----
- 只写上述出处逐字可见的内容；手册未给出的止口/厚度等几何一律不写。
- 幂等：重复运行产物一致。
- 写入后自动调用 add_mechanical_interface.main() 重算覆盖率（该脚本对已有
  declared/partial 条目原样保留，不会抹掉本轮数据）。
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')
REGISTRY_REF = '/api/mechanical_interfaces.json'
RETRIEVED = '2026-09-11'

KB_URL = ('https://blog.robotiq.com/knowledge/'
          'integration-on-non-supported-robot-5-1736280738706')
HANDE_MANUAL = ('https://assets.robotiq.com/website-assets/support_documents/document/'
                'online/Hand-E_Instruction_Manual_Web_20190306.zip/'
                'Hand-E_Instruction_Manual_Web/Content/6.%20Specifications.htm')

# 夹爪通用耦合表（出处 A + B + C，三处一致）
_GRIPPER_STD = [
    'ISO 9409-1-50-4-M6',
    'ISO 9409-1-31.5-4-M5',
    'ISO 9409-1-40-4-M6',
]
_GRIPPER_NOTE = (
    '孔位随官方耦合件可变，非单一法兰：GRP-CPL-062=ISO 9409-1-50-4-M6（PCD Ø50，'
    '4×M6-1.0，配 1×Ø6 定位销）、GRP-CPL-063=ISO 9409-1-31.5-4-M5（PCD Ø31.5，'
    '4×M5-0.8，配 1×Ø5 定位销）、GRP-CPL-064=ISO 9409-1-40-4-M6（PCD Ø40，'
    '4×M6-1.0，配 1×Ø6 定位销）；另有 AGC-CPL-065-002（PCD Ø56，8×M4-0.7，'
    '62 mm 内嵌）、AGC-CPL-066-002（PCD Ø56，6×M4，42 mm 外嵌）、'
    'AGC-CPL-067-002（PCD Ø60，4×M5，34 mm 外嵌）与 AGC-CPL-068-002'
    '（PCD Ø63，6×M6 + 2×Ø6 销）为非 ISO 编码孔位；'
    '非标法兰可用 GRP-CPL-BLANK 空白耦合件自加工，或标准耦合件配 AGC-APL-XXX-002 转接盘。'
    '耦合件为必需件（集成电子与电触点），故「可装」的前提是选配对应型号耦合件。'
)
_GRIPPER_SRC = (
    'Robotiq 官方知识库《Integrating Robotiq Products on Non-Supported Robots》'
    '（适用于 2F-85 / 2F-140 / Hand-E / Hand-E C10 / EPick，检索 %s）'
    '＋《Hand-E Instruction Manual》§6.1.1 Couplings ｜ %s ｜ %s'
    % (RETRIEVED, KB_URL, HANDE_MANUAL)
)
_GRIPPER_GAP = (
    'AGC-CPL-066/067/068 的 PCD56(6×M4) / PCD60(4×M5) / PCD63(6×M6) 无 ISO 9409-1 编码，'
    '未纳入自动比对集合；夹爪本体与耦合件之间的止口配合尺寸未单列为可比对标识。'
    '【已知厂商命名分歧】AGC-CPL-065 在 2019 版手册 §6.1.1 记作「P.C.D. 56, 8×M4」'
    '（无 ISO 编码），Robotiq 现行知识库记作「ISO 9409-1-56-8-M4」；'
    '本条按**保守口径**只收录三处出处一致给出 ISO 编码的 3 个标号。'
)

# FT-300-S 力传感器耦合表（出处 A，FT-300-S 单列）
_FT300_NOTE = (
    '孔位随官方耦合件可变，非单一法兰：FTS-300-S-CPL-014=ISO 9409-1-50-4-M6、'
    'FTS-300-S-CPL-029=ISO 9409-1-31.5-4-M5、FTS-300-S-CPL-030=ISO 9409-1-40-4-M6、'
    'FTS-300-S-CPL-031=PCD Ø39 上 8×M3；非标法兰可用 FTS-300-S-CPL-BLANK 空白耦合件'
    '自加工，或标准耦合件配 AGC-APL-XXX-002 转接盘。'
)
_FT300_SRC = (
    'Robotiq 官方知识库《Integrating Robotiq Products on Non-Supported Robots》'
    'FT-300-S 耦合件对照表（检索 %s）｜ %s' % (RETRIEVED, KB_URL)
)
_FT300_GAP = (
    'PCD Ø39 上 8×M3 无 ISO 9409-1 编码，未纳入自动比对集合；'
    '传感器两侧（机器人侧/工具侧）孔位是否相同未在知识库单列，需对照官方 Drawing。'
)

UPGRADES = {
    # 注意：GRIP-002 与 ACT-028（Robotiq 2F-85 Gripper）是同一产品的跨品类重复条目，
    # 本轮按同一份出处补齐，重复本身另立待办，不在本脚本内合并（避免误删）。
    'GRIP-002': {  # Robotiq 2F-85
        'standard': _GRIPPER_STD,
        'declared_note': _GRIPPER_NOTE,
        'source': _GRIPPER_SRC,
        'gap': _GRIPPER_GAP,
    },
    'GRIP-006': {  # Robotiq Hand-E
        'standard': _GRIPPER_STD,
        'declared_note': _GRIPPER_NOTE,
        'source': _GRIPPER_SRC,
        'gap': _GRIPPER_GAP,
    },
    'GRIP-014': {  # Robotiq EPick 真空抓具
        'standard': _GRIPPER_STD,
        'declared_note': _GRIPPER_NOTE,
        'source': _GRIPPER_SRC,
        'gap': _GRIPPER_GAP,
    },
    'SENS-855': {  # Robotiq FT 300-S（与 SENS-31「FT 300」为同产品重复条目）
        'standard': [
            'ISO 9409-1-50-4-M6',
            'ISO 9409-1-31.5-4-M5',
            'ISO 9409-1-40-4-M6',
        ],
        'declared_note': _FT300_NOTE,
        'source': _FT300_SRC,
        'gap': _FT300_GAP,
    },
}


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
            'status': 'declared',
            'mount_type': 'flange',
            'standard': u['standard'],
            'flange': None,
            'declared_note': u['declared_note'],
            'source': u['source'],
            'source_url': KB_URL,
            'confidence': 0.95,
            'retrieved': RETRIEVED,
            'registry_ref': REGISTRY_REF,
            'gap': u['gap'],
        }
        changed.append(eid)

    with io.open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print('Robotiq mi 升级完成（%d 条 → declared）：%s' % (len(changed), ', '.join(changed)))

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import add_mechanical_interface  # noqa: E402
    add_mechanical_interface.main()


if __name__ == '__main__':
    main()
