# -*- coding: utf-8 -*-
"""
机械接口人工采编（20260809 批次）—— 把有一手出处的孔位级规格写进实体库。

背景：截至本批次，全库 mechanical_interface 里 standard/flange 非空的条目为 **0**，
fill_pct 1.12% 全部由 4 条只有 mount_type 的 partial 撑着。也就是说兼容判定引擎
在机械维度上从未拿到过一次可比对的孔位规格 —— 引擎是好的，油箱是空的。

本批次的作用是把第一条**尺寸级 declared** 灌进去，让 hole-pattern 级互换判定
第一次跑在真实数据上。

采编纪律（与 L1.64/L1.70 一致）：
  1. 只录一手出处（厂商官方手册/datasheet 的**深链**），不录首页、不录二手软文；
  2. 出处里没有的尺寸一律不补，缺什么在 gap 里说清楚；
  3. 厂商把接口做成"随耦合件可变"的，就如实录成**集合**，不塌缩成单值 ——
     塌缩会让引擎对集合内的其它孔位输出"无交集"这种**假红**。

幂等：可重复运行，结果一致。
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')
REGISTRY_REF = '/api/mechanical_interfaces.json'

# Robotiq 2F-85：官方手册《2F-85 & 2F-140 Instruction Manual》第 6.1.1 节 Couplings
# 明确「耦合件是必需件（集成电子与电触点）」，并逐个给出各耦合件的螺栓孔位：
#   AGC-CPL-062-002 → ISO 9409-1-50-4-M6   (PCD Ø50, 4×M6-1.0 过孔, 1×M6 定位销)
#   AGC-CPL-063-002 → ISO 9409-1-31.5-4-M5 (PCD Ø31.5, 4×M5-0.8, 1×M5 定位销)
#   AGC-CPL-064-002 → ISO 9409-1-40-4-M6   (PCD Ø40, 4×M6-1.0)
#   AGC-CPL-065-002 → PCD Ø56, 8×M4-0.7    （非 ISO 编码孔位）
#   AGC-CPL-066-002 → PCD Ø56, 6×M4-0.7    （非 ISO 编码孔位）
#   AGC-CPL-067-002 → PCD Ø60, 4×M5-0.8    （非 ISO 编码孔位）
#   AGC-CPL-BLANK-002 → 空白盘，可自定义孔位
#
# standard 只放能被 ISO 9409-1 编码、因而可与他方直接比对的三种；PCD56/PCD60
# 这三种没有通行的规范编码，硬造 token 只会造成两边命名不一致的假阴，故记在
# declared_note 里供人读，不进比对集合。
ROBOTIQ_MANUAL = (
    'https://assets.robotiq.com/website-assets/support_documents/document/'
    '2F-85_2F-140_TM-OMRON_InstructionManual_20190206.pdf'
)

CURATION = {
    'ACT-028': {
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
                '孔位随官方耦合件可变，非单一法兰：AGC-CPL-062-002=ISO 9409-1-50-4-M6、'
                'AGC-CPL-063-002=ISO 9409-1-31.5-4-M5、AGC-CPL-064-002=ISO 9409-1-40-4-M6；'
                '另有非 ISO 编码孔位 PCD56(8×M4)/PCD56(6×M4)/PCD60(4×M5) 及空白盘 '
                'AGC-CPL-BLANK-002 可自定义。耦合件为必需件（集成电子与电触点），'
                '故「可装」的前提是选配对应型号耦合件。'
            ),
            'source': 'Robotiq 官方手册《2F-85 & 2F-140 Instruction Manual》§6.1.1 Couplings',
            'source_url': ROBOTIQ_MANUAL,
            'confidence': 0.95,
            'registry_ref': REGISTRY_REF,
            'gap': (
                'PCD56/PCD60 三种孔位无 ISO 编码，未纳入自动比对集合；'
                '夹爪本体与耦合件之间的接口（Ø63 F8 止口）未单列为可比对标识。'
            ),
        },
        # 出处升级：此前记为「厂商目录声明值（无原始链接，未核验）」tier B / 0.5。
        # 现已取得厂商官方手册深链且含带尺寸的工程图，符合 Tier A 判据
        # （具体文档深链，非厂商首页）。
        'provenance': {
            'source': 'Robotiq 官方产品手册（含尺寸工程图）：%s' % ROBOTIQ_MANUAL,
            'source_url': ROBOTIQ_MANUAL,
            'source_tier': 'A',
            'confidence': 0.95,
            'confidence_basis': 'vendor_official_manual_with_dimensioned_drawings',
            'verification_note': (
                '2026-08-09 核验：官方手册 §6.1.1 逐一列出各耦合件孔位与螺纹规格，'
                '含 P.C.D. 标注工程图。'
            ),
        },
    },
}


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

    if missing:
        raise SystemExit('采编目标不存在于实体库，拒绝静默跳过: %s' % missing)

    with io.open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print('机械接口采编完成：changed=%d unchanged=%d'
          % (len(changed), len(CURATION) - len(changed)))
    for eid in changed:
        print('  ✏️ ', eid)


if __name__ == '__main__':
    main()
