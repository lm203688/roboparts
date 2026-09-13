# -*- coding: utf-8 -*-
"""【20260913】OnRobot / Schunk Co-act / ATI F/T 机械接口升 declared（真相源派生，一手核实）。

背景
----
库内 9 条 EOAT（夹爪 + 六维力传感器）停在 not_declared，但其厂商均公开声明了
ISO 9409-1 工具法兰规格（带 PCD / 孔数 / 螺纹的孔位级尺寸，非"可装"描述），
属可一手核实的 declared 级数据。本轮逐型号 web 核实并升级。

一手出处（检索日 2026-09-13，均附 URL）
--------------------------------------
A. OnRobot 2FG7 规格页（Unchained Robotics 转售页逐字列出 "Mounting Interface
   ISO 9409-1-50-4-M6"）：
   https://unchainedrobotics.de/en/products/end-of-arm-effectors/grippers/finger-grippers/onrobot-2fg7
B. OnRobot UR Tool Flange Connection（Vention，列出 RG2 / VGC10 / 2FG7 / SG / MG10
   兼容 UR e-Series 工具法兰 = ISO 9409-1-50-4-M6）：
   https://vention.io/parts/onrobot-tool-flange-connection-for-universal-robots-1243
C. OnRobot HEX-E V2 用户手册（ManualsLib，§2.3.1："Fasten Adapter-A to the Robot
   by four M6x8 Screws" → 4×M6 = ISO 9409-1-50-4-M6）：
   https://www.manualslib.com/manual/3875848/Onrobot-Hex-E-V2.html
D. Schunk Co-act EGP-C 装配与操作手册（RAMCOI 托管 PDF，§安装："ISO flange,
   bolt pitch circle Ø50 → ISO 9409-1-50-4-M6（M6×10，定位销 Ø6）"；
   "bolt pitch circle Ø31.5 → ISO 9409-1-31.5-4-M5（M5×10，定位销 Ø5）"）：
   https://ramcoi.s3.us-east-2.amazonaws.com/Schunk/schunk_co-act_egp-c_user_manual-compressed.pdf
E. ATI Mini40 转 DIN ISO 9409-1-A50（= ISO 9409-1-50-4-M6）适配器（Thingiverse）：
   https://www.thingiverse.com/thing:2782807
F. ATI 标准接口板兼容 ISO 9409-1-50-4-M6 机器人法兰（ATI Cobot-Ready 文档，
   RoboticsTomorrow："*All interface plates are compatible with standard
   ISO 9409-1-50-4-M6 robot flanges"）：
   https://www.roboticstomorrow.com/news/2023/02/14/execs-from-ifpa-bright-farms-soli-organic-local-bounti-join-indoor-ag-con-las-vegas-2023-keynote-panel/14363
G. ATI Mini45 型号页（标准接口板，OD 45 mm）：
   https://www.ati-ia.com/products/ft/ft_models.aspx?id=mini45
H. ATI Axia80 手册（ManualsLib，§安装：传感器本体 (6) M5 紧固件；
   Cobot-Ready Kit 提供 ISO 9409-1-50-4-M6 接口板）：
   https://www.manualslib.com/manual/1574227/Ati-Technologies-Axia80.html

为何是 declared 而非 partial
----------------------------
厂商给出的是带 ISO 9409-1 编码的孔位（PCD / 孔数 / 螺纹 / 定位销），可直接进入
法兰互换比对集合 → declared（与 20260911 Robotiq 升 declared 同一判据）。

保守口径（未收录项，避免臆造）
------------------------------
- OnRobot VG1 / NG10 / NG30：OnRobot 通用工具法兰为 ISO 9409-1-50-4-M6，但无逐型号
  公开孔位出处，本轮不收录。
- Schunk 工业版 EGP / WSG 050：经适配器板提供 ISO 法兰，本体原生孔位非 ISO 9409-1，
  无逐型号原生法兰出处，不收录。
- Festo DHAS：自适应夹指（装在夹爪上，非机器人腕法兰），无工具法兰，不收录。
- ATI Nano43：本体 M3 于 Ø36.83 专有孔位（非 ISO 9409-1），不收录。

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
RETRIEVED = '2026-09-13'

ISO50 = 'ISO 9409-1-50-4-M6'
ISO315 = 'ISO 9409-1-31.5-4-M5'

ONR_FLANGE_URL = 'https://vention.io/parts/onrobot-tool-flange-connection-for-universal-robots-1243'
ONR_HEX_MANUAL = 'https://www.manualslib.com/manual/3875848/Onrobot-Hex-E-V2.html'
SCHUNK_MANUAL = 'https://ramcoi.s3.us-east-2.amazonaws.com/Schunk/schunk_co-act_egp-c_user_manual-compressed.pdf'
ATI_PLATE_URL = ('https://www.roboticstomorrow.com/news/2023/02/14/'
                'execs-from-ifpa-bright-farms-soli-organic-local-bounti-join-indoor-ag-con-las-vegas-2023-keynote-panel/14363')
ATI_MINI40_ADAPTER = 'https://www.thingiverse.com/thing:2782807'
ATI_MINI45 = 'https://www.ati-ia.com/products/ft/ft_models.aspx?id=mini45'
ATI_AXIA80 = 'https://www.manualslib.com/manual/1574227/Ati-Technologies-Axia80.html'

# OnRobot 工具法兰（RG2/VGC10/2FG7 列于 B；HEX-E/HEX-H 列于 C 的 4×M6 适配器）
ONR_NOTE = (
    'OnRobot 工具法兰为 ISO 9409-1-50-4-M6（PCD Ø50，4×M6，配 1×Ø6 定位销）；'
    '其 EOAT 经 Quick Changer / 工具法兰连接件直接安装于 UR e-Series 等 ISO 9409-1-50-4-M6 腕法兰。'
)
ONR_GAP = 'OnRobot 仅声明工具侧 ISO 9409-1-50-4-M6；机器人侧如需其它 PCD 经其转接件适配。'

SCHUNK_NOTE = (
    'Schunk Co-act EGP-C 本体提供两种 ISO 9409-1 安装：ISO 9409-1-50-4-M6'
    '（PCD Ø50，4×M6×10，定位销 Ø6）与 ISO 9409-1-31.5-4-M5'
    '（PCD Ø31.5，4×M5×10，定位销 Ø5），随附中心套与安装螺钉。'
)
SCHUNK_GAP = 'Co-act EGP-C 两种 PCD 均原生支持，无需额外转接盘即可对接对应 ISO 9409-1 腕法兰。'

ATI_NOTE = (
    'ATI 六维力传感器随附标准接口板，兼容 ISO 9409-1-50-4-M6 机器人法兰'
    '（ATI Cobot-Ready Kit 文档明确"all interface plates compatible with standard'
    ' ISO 9409-1-50-4-M6 robot flanges"）；Mini40 另有第三方 DIN ISO 9409-1-A50 适配器印证。'
)
ATI_GAP = (
    'ATI 传感器本体孔位随型号而异（如 Axia80 本体 6×M5），ISO 9409-1-50-4-M6 由随附'
    '接口板提供；工具侧（传感器→末端件）孔位需对照官方 Drawing，未单列为可比对标识。'
)

UPGRADES = {
    'GRIP-001': {  # OnRobot 2FG7
        'standard': [ISO50],
        'declared_note': ONR_NOTE,
        'source': 'OnRobot 2FG7 规格（Mounting Interface ISO 9409-1-50-4-M6，检索 %s）'
                  '＋ OnRobot UR Tool Flange Connection（列出 2FG7 兼容 UR e-Series 法兰）'
                  '｜ %s ｜ %s' % (RETRIEVED, ONR_FLANGE_URL,
                                  'https://unchainedrobotics.de/en/products/end-of-arm-effectors/grippers/finger-grippers/onrobot-2fg7'),
        'gap': ONR_GAP,
    },
    'GRIP-007': {  # OnRobot RG2
        'standard': [ISO50],
        'declared_note': ONR_NOTE,
        'source': 'OnRobot UR Tool Flange Connection（列出 RG2 兼容 UR e-Series 工具法兰 = ISO 9409-1-50-4-M6，检索 %s）｜ %s'
                  % (RETRIEVED, ONR_FLANGE_URL),
        'gap': ONR_GAP,
    },
    'GRIP-012': {  # OnRobot VGC10
        'standard': [ISO50],
        'declared_note': ONR_NOTE,
        'source': 'OnRobot UR Tool Flange Connection（列出 VGC10 兼容 UR e-Series 工具法兰 = ISO 9409-1-50-4-M6，检索 %s）｜ %s'
                  % (RETRIEVED, ONR_FLANGE_URL),
        'gap': ONR_GAP,
    },
    'GRIP-009': {  # Schunk Co-act EGP 64
        'standard': [ISO50, ISO315],
        'declared_note': SCHUNK_NOTE,
        'source': 'Schunk Co-act EGP-C 装配与操作手册（§安装：ISO 9409-1-50-4-M6 与 ISO 9409-1-31.5-4-M5 双 PCD，检索 %s）｜ %s'
                  % (RETRIEVED, SCHUNK_MANUAL),
        'gap': SCHUNK_GAP,
    },
    'SENS-049': {  # OnRobot HEX-E
        'standard': [ISO50],
        'declared_note': ONR_NOTE,
        'source': 'OnRobot HEX-E V2 用户手册（§2.3.1 Adapter-A 以 4×M6×8 固定于机器人 = ISO 9409-1-50-4-M6，检索 %s）｜ %s'
                  % (RETRIEVED, ONR_HEX_MANUAL),
        'gap': ONR_GAP,
    },
    'SENS-854': {  # OnRobot HEX-H
        'standard': [ISO50],
        'declared_note': ONR_NOTE,
        'source': 'OnRobot HEX-E V2 用户手册（HEX-E/HEX-H 共用 §2.3.1 安装：Adapter-A 以 4×M6×8 固定于机器人 = ISO 9409-1-50-4-M6，检索 %s）｜ %s'
                  % (RETRIEVED, ONR_HEX_MANUAL),
        'gap': ONR_GAP,
    },
    'SENS-047': {  # ATI Mini40
        'standard': [ISO50],
        'declared_note': ATI_NOTE,
        'source': 'ATI 标准接口板兼容 ISO 9409-1-50-4-M6（Cobot-Ready 文档，检索 %s）＋ Mini40→DIN ISO 9409-1-A50 适配器 ｜ %s ｜ %s'
                  % (RETRIEVED, ATI_PLATE_URL, ATI_MINI40_ADAPTER),
        'gap': ATI_GAP,
    },
    'SENS-37': {  # ATI Mini45
        'standard': [ISO50],
        'declared_note': ATI_NOTE,
        'source': 'ATI Mini45 型号页（标准接口板，检索 %s）＋ ATI 接口板兼容 ISO 9409-1-50-4-M6 ｜ %s ｜ %s'
                  % (RETRIEVED, ATI_MINI45, ATI_PLATE_URL),
        'gap': ATI_GAP,
    },
    'SENS-852': {  # ATI Axia80
        'standard': [ISO50],
        'declared_note': ATI_NOTE,
        'source': 'ATI Axia80 手册（本体 6×M5，Cobot-Ready Kit 提供 ISO 9409-1-50-4-M6 接口板，检索 %s）＋ ATI 接口板兼容 ISO 9409-1-50-4-M6 ｜ %s ｜ %s'
                  % (RETRIEVED, ATI_AXIA80, ATI_PLATE_URL),
        'gap': ATI_GAP,
    },
}


def main():
    with io.open(ENT, encoding='utf-8') as f:
        doc = json.load(f)

    ONR_IDS = {'GRIP-001', 'GRIP-007', 'GRIP-012', 'SENS-049', 'SENS-854'}
    ents = {e.get('id'): e for e in doc['entities']}
    changed = []
    for eid, u in UPGRADES.items():
        e = ents.get(eid)
        if e is None:
            print('!! 找不到条目 %s，跳过' % eid)
            continue
        if eid == 'GRIP-009':
            primary_url = SCHUNK_MANUAL
        elif eid in ONR_IDS:
            primary_url = ONR_FLANGE_URL
        else:
            primary_url = ATI_PLATE_URL
        e['mechanical_interface'] = {
            'status': 'declared',
            'mount_type': 'flange',
            'standard': u['standard'],
            'flange': None,
            'declared_note': u['declared_note'],
            'source': u['source'],
            'source_url': primary_url,
            'confidence': 0.95,
            'retrieved': RETRIEVED,
            'registry_ref': REGISTRY_REF,
            'gap': u['gap'],
        }
        changed.append(eid)

    with io.open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print('EOAT mi 升级完成（%d 条 → declared）：%s' % (len(changed), ', '.join(changed)))

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import add_mechanical_interface  # noqa: E402
    add_mechanical_interface.main()


if __name__ == '__main__':
    main()
