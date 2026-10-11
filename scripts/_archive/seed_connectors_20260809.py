# -*- coding: utf-8 -*-
"""
connectors 类目首批种子（20260809-07）。

背景：全库 706 条实体里，entity_kind=component 的连接器 **0 条**（已独立复现：
按 connector/连接器/接插件/端子 全字段搜到 29 条提及，无一条是 component；
manufacturer 含 Molex/TE/Amphenol/JAE/Hirose/JST/Harting 的 0 条）。
平台主张「接口兼容」，而连接器就是接口的物理载体 —— 这是品类空洞，不是覆盖不足。

录入纪律（本文件所有断言的唯一来源）：
  · 全部来自 Molex 官方发布（2026-08-05，PRNewswire 302843651）；
  · 只录**厂商自己给出的数值**。凡新闻稿里的比较级/营销表述一律不录：
    "industry's smallest"、"up to 50% less routing area" 均属未经独立验证的
    厂商主张（inelectronics 亦明确指出该比较未被独立验证），因此不进字段。
  · 厂商发布**未披露**的项目照实留空并写进 gap：降额曲线、接触电阻、
    插拔寿命、IP 等级、振动/弯折试验数据、对接尺寸与引脚定义。
  · 因此 MiniMix 记 partial（有 5.65mm 走线开口与对接方向，但无对接尺寸），
    Mirror Mezz 记 not_declared（只有接口角色，无任何物理量）——
    **不允许**因为"想让新类目好看"而把 not_declared 写成 declared。

幂等：以 id 为准，存在即按本文件内容覆盖，不重复插入。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')

SOURCE = 'Molex 官方发布《Molex Introduces MiniMix Hybrid Power and Signal Connectors》2026-08-05'
SOURCE_URL = ('https://www.prnewswire.com/news-releases/molex-introduces-minimix-hybrid-'
              'power-and-signal-connectors-to-accelerate-humanoid-robotics-mass-production-'
              'scaling-302843651.html')

COMMON = {
    'category': 'connectors',
    'manufacturer': 'Molex',
    'source': SOURCE,
    'source_tier': 'A',
    'source_url': SOURCE_URL,
    'confidence_basis': 'vendor_official_announcement',
    'last_verified': '2026-08-09',
    'verified': True,
    'data_quality': 'ok',
    'quarantine': False,
    'oss': False,
}

SEEDS = [
    {
        'id': 'CONN-molex-minimix',
        'name': 'Molex MiniMix 混装电源信号连接器',
        'name_en': 'Molex MiniMix Hybrid Power and Signal Connectors',
        'type': 'hybrid_connector',
        'description': (
            '面向人形机器人关节/执行器的线对板混装连接器：单一接口内集成最高 15.0A '
            '电源触点与 1Gbps 1000BASE-T1 单对以太网，最小可穿过 5.65mm 开口；'
            '提供垂直与直角两种对接方向，含预端接线缆组件。'
            '样品与功能评估组件现已可取，规模量产排期 2026 年末。'),
        # 物理量：仅厂商明确给出的数值
        'current': '15.0A',
        'data_rate': '1Gbps',
        'protocol': '1000BASE-T1',
        'routing_opening': '5.65mm',
        'mating_orientations': ['vertical', 'right_angle'],
        'form_factor': 'wire_to_board',
        'availability': 'samples_now_mass_production_late_2026',
        'applications': ['humanoid_joint', 'actuator', 'amr', 'industrial_automation'],
        'confidence': 0.8,
        'mechanical_interface': {
            'status': 'partial',
            'mount_type': 'wire_to_board',
            'standard': None,
            'flange': None,
            'declared_note': '最小走线开口 5.65mm；提供垂直/直角两种对接方向（厂商发布）',
            'source': SOURCE,
            'confidence': 0.7,
            'gap': ('缺对接尺寸与引脚定义、插拔寿命、接触电阻、IP 等级、降额曲线与'
                    '振动/弯折试验数据 —— 厂商发布明确未披露，无法做互换判定'),
        },
    },
    {
        'id': 'CONN-molex-mirror-mezz',
        'name': 'Molex Mirror Mezz 夹层连接器',
        'name_en': 'Molex Mirror Mezz Mezzanine Connectors',
        'type': 'mezzanine_connector',
        'description': (
            '高密度板对板夹层连接器。据 Molex 官方发布，它是 NVIDIA Jetson Thor 等'
            '业界标准 AI 计算平台的主要高速接口。'),
        'form_factor': 'board_to_board',
        'applications': ['ai_compute_module', 'humanoid_robot'],
        # 与库内既有实体的关系：这是本条目的主要价值（可判定的接口边）
        'mates_with': ['CHIP-008'],
        'mates_with_note': 'Molex 官方发布称其为 NVIDIA Jetson Thor 模组的主要高速接口',
        'confidence': 0.7,
        'mechanical_interface': {
            'status': 'not_declared',
            'mount_type': 'board_to_board',
            'standard': None,
            'flange': None,
            'source': SOURCE,
            'confidence': 0.5,
            'gap': ('厂商发布只给出接口角色，未给堆叠高度、排距、引脚数与对接尺寸；'
                    '不足以做孔位级/堆高级互换判定'),
        },
    },
]


def main():
    with open(ENT, encoding='utf-8') as f:
        doc = json.load(f)
    ents = doc['entities']
    by_id = {e.get('id'): i for i, e in enumerate(ents)}

    added = updated = 0
    for seed in SEEDS:
        rec = dict(COMMON)
        rec.update(seed)
        if rec['id'] in by_id:
            ents[by_id[rec['id']]].update(rec)
            updated += 1
        else:
            ents.append(rec)
            added += 1

    with open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print('connectors 种子：新增 %d 条 / 更新 %d 条 / 全库 %d 条'
          % (added, updated, len(ents)))
    print('提醒：本脚本只写 entities.json。必须接着跑 '
          'normalize_categories.py → govern_entity_kind.py → add_mechanical_interface.py')


if __name__ == '__main__':
    main()
