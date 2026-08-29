# -*- coding: utf-8 -*-
"""
机械接口人工采编（20260810 批次）—— 让机械维度第一次出现「可比对的一对」。

背景与上一批次（20260809）的区别：
  上一批次把第一条尺寸级 declared（ACT-028 Robotiq 2F-85）灌进库里，机械维度从
  「引擎好、油箱空」变成「有一滴油」。但**一条声明是配不出对的** —— 兼容判定要
  两侧都有可比对的孔位集合才会产出一次真实的 true positive。也就是说上一批次之后，
  机械维度的判定路径在真实数据上**仍然一次都没走通**。

本批次补的 SENS-31（Robotiq FT 300 / FT 300-S 力/力矩传感器）与 ACT-028 共享同一族
ISO 9409-1 耦合件孔位，落库后二者构成**全库第一对孔位级可互换实体**（同一机器人法兰
上可互换安装），机械维度的集合求交路径第一次跑在两条真实数据之间。

采编纪律（与 L1.64/L1.70/L1.74 一致）：
  1. 只录一手出处的**深链**（厂商官方手册 PDF / 官方知识库），不录二手软文；
  2. 出处里没有的尺寸一律不补，缺什么写进 gap；
  3. 接口「随耦合件可变」的如实录成**集合**，不塌缩成单值（塌缩产生假红，见 L1.74）；
  4. **厂商简写不当 ISO 编码用**：见下方 ACT-028 的孔位命名分歧处置。

幂等：可重复运行，结果一致。
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')
REGISTRY_REF = '/api/mechanical_interfaces.json'

# ---------------------------------------------------------------------------
# SENS-31 Robotiq FT 300 / FT 300-S 力-力矩传感器
#
# 出处一（现行型号 FT 300-S 官方手册，Spare Parts and Kits 表逐项给出 PCD 与螺纹）：
#   FTS-300-S-CPL-014 → "Coupling for ISO 9409-1-50-4-M6"   (50 mm PCD, 4×M6, 1×6mm M6 定位销；用于 UR / TM / Omron)
#   FTS-300-S-CPL-029 → "Coupling for ISO 9409-1-31.5-4-M5" (31.5 mm PCD, 4×M5, 1×5mm M5 定位销)
#   FTS-300-S-CPL-030 → "Coupling for ISO 9409-1-40-4-M6"   (40 mm PCD, 4×M6, 1×6mm M6 定位销)
#   FTS-300-S-CPL-031 → "Coupling for P.C.D. 39 and 8 x M3" （**无 ISO 编码**，不进比对集合）
#   FTS-300-S-CPL-BLANK → 空白盘，可自行加工孔位
# 出处二（前代 FT 300 官方手册 §3.3 Mechanical Connections）：
#   "You must use a coupling to attach the Sensor to a robot."
#   "Our couplings are listed according to ISO 9409-1 and this covers most bolt patterns."
#   → 耦合件为**必需件**这一条对两代都成立，与 ACT-028 的建模口径一致。
#
# 因此 standard 录成三值集合，而不是"UR 专用"这种单值 —— 单值会让引擎对
# 31.5/40 法兰的机器人输出假红。
# ---------------------------------------------------------------------------
FT300_MANUAL = (
    'https://assets.robotiq.com/website-assets/support_documents/document/'
    'FT300-S_Sensor_Manual_OMRON_TM_PDF_20210301.pdf'
)
FT300_LEGACY_MANUAL = (
    'https://assets.robotiq.com/website-assets/support_documents/document/online/'
    'FT_Sensor_Instruction_Manual_Web_20190322.zip/FT_Sensor_Instruction_Manual_Web/'
    'Content/Installation.htm'
)
ROBOTIQ_KB = (
    'https://blog.robotiq.com/knowledge/'
    'integration-on-non-supported-robot-5-1736280738706'
)

CURATION = {
    'SENS-31': {
        'mechanical_interface': {
            'status': 'declared',
            'mount_type': 'flange_mount',
            'standard': [
                'ISO 9409-1-50-4-M6',
                'ISO 9409-1-31.5-4-M5',
                'ISO 9409-1-40-4-M6',
            ],
            'flange': None,
            'declared_note': (
                '孔位随官方耦合件可变，非单一法兰：FTS-300-S-CPL-014=ISO 9409-1-50-4-M6'
                '（PCD Ø50，4×M6，配 Ø6 M6 定位销，用于 UR / Techman / Omron TM）、'
                'FTS-300-S-CPL-029=ISO 9409-1-31.5-4-M5（PCD Ø31.5，4×M5）、'
                'FTS-300-S-CPL-030=ISO 9409-1-40-4-M6（PCD Ø40，4×M6）；'
                '另有 FTS-300-S-CPL-031=PCD Ø39 + 8×M3（无 ISO 编码）与空白盘 '
                'FTS-300-S-CPL-BLANK 可自定义孔位。'
                '前代 FT 300 官方手册 §3.3 载明「必须使用耦合件把传感器装到机器人上」'
                '且「Robotiq 耦合件按 ISO 9409-1 编列」，故「可装」的前提同样是选配'
                '对应型号耦合件——与 Robotiq 夹爪族（见 ACT-028）同一建模口径。'
            ),
            'source': 'Robotiq 官方手册《FT 300-S Instruction Manual》Spare Parts and Kits '
                      '耦合件清单（逐项标注 PCD 与螺纹规格）；前代口径见 FT 300 手册 '
                      '§3.3 Mechanical Connections',
            'source_url': FT300_MANUAL,
            'confidence': 0.92,
            'registry_ref': REGISTRY_REF,
            'gap': (
                'PCD39(8×M3) 无 ISO 编码，未纳入自动比对集合；'
                'FT 300（前代）耦合件 SKU 族为 FTS-300-CPL-xxx，与现行 -S 的 '
                'FTS-300-S-CPL-xxx 不同，本条未逐一核对前代 SKU 编号，'
                'ISO 编码族两代一致但 SKU 不可互引；'
                '传感器本体与耦合件之间的对接面（M4 螺钉 + 碟形垫圈压 O 型圈）'
                '未单列为可比对标识。'
            ),
        },
        'provenance': {
            'source': 'Robotiq 官方产品手册（FT 300-S Instruction Manual，含耦合件 PCD/螺纹清单）：'
                      + FT300_MANUAL,
            'source_tier': 'A',
            'source_url': FT300_MANUAL,
            'confidence': 0.92,
            'confidence_basis': 'vendor_official_manual_with_coupling_bolt_pattern_table',
            'verification_note': (
                '2026-08-10 核验：FT 300-S 官方手册备件表逐项给出各耦合件的 ISO 9409-1 '
                '编码、PCD 与螺纹；前代 FT 300 官方手册 §3.3 佐证「耦合件必需 + 按 ISO 9409-1 编列」。'
                '两份出处均为 robotiq.com 官方资产域，实测 HTTP 200。'
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# ACT-028 Robotiq 2F-85：**只订正 gap 措辞，不动比对集合**。
#
# 发现：2019 版官方手册 §6.1.1 把 AGC-CPL-065 的孔位写作 "P.C.D. 56, 8 × M4"（无编码），
# 而 Robotiq 现行官方知识库把同一件写作 "ISO 9409-1-56-8-M4"。两处出处对同一孔位
# 给了**不同命名**。
#
# 处置：**不**把 'ISO 9409-1-56-8-M4' 加进 standard 集合。理由不是"证据不足"，
# 而是"加错了代价更高"：若 56-8-M4 实为厂商借用 ISO 命名格式的简写而非 ISO 9409-1
# 收录尺寸，把它当 ISO 编码对外发布会有两个后果——(a) 我方数据集凭空造出一个
# ISO 编码并被 AI 爬虫抄走；(b) 其他厂商对同一孔位用别的写法时产生命名不一致的
# 假阴。按 L1.77 之后立的纪律：**没读到标准原文就不替标准发明条目**。
# 该分歧作为已知缺口写进 gap，等拿到 ISO 9409-1 原文条款再决定是否入集合。
# ---------------------------------------------------------------------------
ACT028_GAP = (
    'PCD56(6×M4)/PCD60(4×M5) 无 ISO 编码，未纳入自动比对集合；'
    '夹爪本体与耦合件之间的接口（Ø63 F8 止口）未单列为可比对标识。'
    '【20260810 新增分歧】AGC-CPL-065 的孔位在 2019 版手册 §6.1.1 记作 '
    '「P.C.D. 56, 8×M4」（无编码），而 Robotiq 现行官方知识库记作 '
    '「ISO 9409-1-56-8-M4」；两处厂商出处命名不一致，且未核到 ISO 9409-1 标准原文'
    '是否收录 56-8-M4 尺寸，故暂不进比对集合——把厂商简写当 ISO 编码发布，'
    '既可能凭空造出一个编码被爬虫抄走，也会与他方写法产生假阴。'
    '待核 ISO 9409-1 原文后再定。出处：' + ROBOTIQ_KB
)


def main():
    with io.open(ENT, encoding='utf-8') as f:
        doc = json.load(f)

    by_id = {e.get('id'): e for e in doc['entities']}
    changed, missing = [], []

    for eid, spec in CURATION.items():
        ent = by_id.get(eid)
        if ent is None:
            missing.append(eid)
            continue
        before = json.dumps(ent, ensure_ascii=False, sort_keys=True)
        ent['mechanical_interface'] = json.loads(
            json.dumps(spec['mechanical_interface'], ensure_ascii=False))
        ent.update(json.loads(json.dumps(spec.get('provenance', {}), ensure_ascii=False)))
        if json.dumps(ent, ensure_ascii=False, sort_keys=True) != before:
            changed.append(eid)

    # ACT-028：仅订正 gap，不改 standard 集合
    act = by_id.get('ACT-028')
    if act is None:
        missing.append('ACT-028')
    else:
        mi = act.get('mechanical_interface') or {}
        if mi.get('status') != 'declared':
            raise SystemExit(
                'ACT-028 的 mechanical_interface 已不是 declared，'
                '本批次的 gap 订正前提被推翻，拒绝盲写')
        if mi.get('gap') != ACT028_GAP:
            mi['gap'] = ACT028_GAP
            changed.append('ACT-028(gap)')

    if missing:
        raise SystemExit('采编目标不存在于实体库，拒绝静默跳过: %s' % missing)

    with io.open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print('机械接口采编完成（20260810 批次）：changed=%d' % len(changed))
    for eid in changed:
        print('  ✏️ ', eid)

    # 落库后自检：机械维度是否真的出现了"可比对的一对"
    declared = [e for e in doc['entities']
                if (e.get('mechanical_interface') or {}).get('status') == 'declared'
                and (e.get('mechanical_interface') or {}).get('standard')]
    pairs = 0
    for i in range(len(declared)):
        for j in range(i + 1, len(declared)):
            a = set(declared[i]['mechanical_interface']['standard'])
            b = set(declared[j]['mechanical_interface']['standard'])
            if a & b:
                pairs += 1
    print('  ✅ declared(带尺寸) = %d 条，孔位集合有交集的实体对 = %d 对' % (len(declared), pairs))
    if len(declared) >= 2 and pairs == 0:
        raise SystemExit('两条以上 declared 却配不出任何一对，与本批次目标矛盾，请复核')


if __name__ == '__main__':
    main()
