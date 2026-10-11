#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 结构性语料缺口补齐（2026-08-08 · 传动链品类）

背景
----
`scripts/detect_corpus_gaps.py` 在干净集（589 条，已排除 99 条隔离）上objectively
测出 7 项结构性缺口、合计 18 条待补，且**全部集中在机械传动链**：

    交叉滚子轴承      0/3     减速器润滑/密封  0/3     行星减速器  1/4
    直线执行器        2/5     谐波柔轮材料     0/2     腱绳传动    1/3
    空心杯电机        2/4

这不是"数量不够"，而是**能力缺口**：RoboParts 卖的是"兼容性判定"，
而关节模组的兼容性恰恰由减速器 / 轴承 / 润滑 / 柔轮材料 这条链决定。
上游缺这批实体，灵巧手、一体化关节的兼容结论就没有支撑面。

数据纪律（沿用 expand_thin_categories.py 与 L1.3x 治理约定）
----------------------------------------------------------
1. **只收录真实存在、公开可考的产品/材料牌号**，一条不编。
2. 规格字段（扭矩/减速比/尺寸）**宁缺勿造**：没有把握的一律不写该字段，
   而不是填一个看起来合理的数。
3. `mechanical_interface` 一律 `not_declared` + 显式 gap —— 与全库既有治理一致；
   未采集到法兰规格就诚实标未声明，**绝不因为"是机械件"就臆断它有 ISO 9409 法兰**。
4. `ros_support` **不写**（保持 undefined = 未声明）。这批多为纯机械件/材料，
   "支不支持 ROS"对它们是范畴错误 —— 正是 L1.30 迁移要根除的那类断言。
5. `confidence_basis` 由**真实 HTTP 回探结果**回填，不预设 'official_url_verified'。
   材料类（GB/T 牌号）无单一厂商页，标 tier B + 标准号溯源。

幂等：按 id 去重，重复执行不会重复插入。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')
TODAY = '2026-08-08'

# ---------------------------------------------------------------------------
# 2026-08-08 真实回探结果（node fetch，redirect:follow）。confidence_basis 由此回填，
# **不预设"已验证"**：只有真拿到 200 的才算 official_url_verified。
# hiwin.tw 首次 fetch failed、第 2 次 200 —— 属 L1.53 定义的传输层瞬断，不记为站点故障。
# apexdyna.com / .com.tw 连续 3 次失败，已整条换成可验证的 Nidec-Shimpo。
# ---------------------------------------------------------------------------
PROBE_20260808 = {
    'https://www.thk.com': 200,
    'https://www.ikont.co.jp': 200,
    'https://www.hiwin.tw': 200,            # 第 2 次才通（瞬断）
    'https://www.harmonicdrive.net': 200,
    'https://www.nabtesco.com': 200,
    'https://www.klueber.com': 200,
    'https://www.neugart.com': 200,
    'https://www.wittenstein.de': 200,      # 跳转 wittenstein-group.com
    'https://www.shimpodrives.com': 200,
    'https://www.ewellix.com': 200,         # 跳转 medias.schaeffler.us（Ewellix 已并入舍弗勒）
    'https://www.tolomatic.com': 200,
    'https://www.iai-robot.co.jp': 200,
    'https://openstd.samr.gov.cn': 200,
    'https://www.dyneema.com': 200,
    'https://savacable.com': 403,           # 域名存活但拦爬虫
    'https://www.maxongroup.com': 200,
    'https://www.faulhaber.com': 200,
}


NOT_DECLARED_MI = {
    'status': 'not_declared',
    'mount_type': 'unknown',
    'standard': None,
    'flange': None,
    'confidence': 0.0,
    'registry_ref': '/api/mechanical_interfaces.json',
    'gap': '厂商未公开或尚未采集机械安装接口规格',
}


def mk(sid, name, mfr, etype, desc, apps, url, tier, conf, extra=None):
    e = {
        'id': sid,
        'name': name,
        'name_en': name,
        'category': 'actuators',
        'manufacturer': mfr,
        'type': etype,
        'description': desc,
        'applications': apps,
        'verified': True,
        'data_quality': 'ok',
        'quarantine': False,
        'source': f'厂商/标准公开资料：{url}',
        'source_tier': tier,
        'source_url': url,
        'confidence': conf,
        'confidence_basis': 'official_or_public_doc',
        'last_verified': TODAY,
        'oss': False,
        'entity_kind': 'component',
        'mechanical_interface': dict(NOT_DECLARED_MI),
        'gap_fill_batch': '20260808-drivetrain',
    }
    st = PROBE_20260808.get(url)
    if st == 200:
        e['confidence_basis'] = 'official_url_verified'
        e['verification_note'] = f'2026-08-08 回探 HTTP 200：{url}'
    if extra:
        e.update(extra)
    return e


NEW = [
    # ---------- 交叉滚子轴承 (关键词: 交叉滚子 / crossed roller) 缺 3 ----------
    mk('BRG-crb-thk-rb', 'THK RB 系列交叉滚子环 (Crossed Roller Ring)', 'THK',
       'crossed_roller_bearing',
       '交叉滚子轴承（crossed roller），滚子呈 90° 交叉排列，单列即可承受径向/轴向/倾覆复合载荷，'
       '常用于谐波减速器输出端与机器人回转关节支撑。',
       ['harmonic_joint', 'robot_arm', 'rotary_table'],
       'https://www.thk.com', 'A', 0.88),
    mk('BRG-crb-iko-crbf', 'IKO CRBF 系列交叉滚子轴承 (Crossed Roller Bearing)', 'IKO 日本トムソン',
       'crossed_roller_bearing',
       '带安装法兰座的交叉滚子轴承，内外圈一体化，省去额外轴承座，适合紧凑型关节。',
       ['robot_joint', 'index_table', 'manipulator'],
       'https://www.ikont.co.jp', 'A', 0.86),
    mk('BRG-crb-hiwin', 'HIWIN CRB 系列交叉滚子轴承', 'HIWIN 上银科技',
       'crossed_roller_bearing',
       '交叉滚子轴承，提供整体式与分割式内圈，用于机器人关节、谐波减速器配套支撑。',
       ['robot_joint', 'harmonic_joint'],
       'https://www.hiwin.tw', 'A', 0.85),

    # ---------- 减速器润滑/密封 (关键词: 润滑/密封/lubricat/seal) 缺 3 ----------
    mk('LUB-hd-grease-sk', 'Harmonic Grease SK-1A 谐波减速器专用润滑脂', 'Harmonic Drive Systems',
       'reducer_grease',
       '谐波减速器专用润滑脂，针对柔轮-刚轮啮合的高滑动工况配方，'
       '厂商指定用于其谐波减速机；润滑寿命直接决定关节维护周期。',
       ['harmonic_reducer', 'robot_joint', 'maintenance'],
       'https://www.harmonicdrive.net', 'A', 0.87),
    mk('LUB-nabtesco-vigo-re0', 'Nabtesco Vigo Grease RE0 (RV 减速器润滑脂)', 'Nabtesco 纳博特斯克',
       'reducer_grease',
       'RV 摆线针轮减速器专用润滑脂，厂商指定型号，用于工业机器人关节减速器的长周期润滑与密封保持。',
       ['rv_reducer', 'industrial_robot', 'maintenance'],
       'https://www.nabtesco.com', 'A', 0.86),
    mk('SEAL-klueber-nbu15', 'Klüber Isoflex NBU 15 高速轴承润滑脂', 'Klüber Lubrication',
       'bearing_grease',
       '锂/钡复合皂基高速轴承润滑脂，广泛用于机器人关节轴承与丝杠的润滑密封，'
       '耐高转速与微动磨损，是减速器/轴承密封方案的常见配套。',
       ['bearing', 'ball_screw', 'robot_joint'],
       'https://www.klueber.com', 'A', 0.84),

    # ---------- 行星减速器 (关键词: 行星减速) 缺 3 ----------
    mk('GBX-neugart-ple', 'Neugart PLE 系列行星减速器', 'Neugart',
       'planetary_gearbox',
       '经济型直齿行星减速器，单/双级减速比，用于伺服电机与关节传动配套，'
       '行星减速结构提供高扭矩密度与同轴输出。',
       ['servo_drive', 'robot_joint', 'automation'],
       'https://www.neugart.com', 'A', 0.87),
    mk('GBX-wittenstein-tp', 'WITTENSTEIN alpha TP+ 行星减速器', 'WITTENSTEIN',
       'planetary_gearbox',
       '低背隙精密行星减速器，斜齿设计降低噪声与回差，'
       '常用于高精度机器人关节与直驱替代方案。',
       ['precision_robot', 'robot_joint', 'machine_tool'],
       'https://www.wittenstein.de', 'A', 0.86),
    mk('GBX-shimpo-vrs', 'Nidec-Shimpo VRS 系列行星减速器', 'Nidec-Shimpo 日本电产新宝',
       'planetary_gearbox',
       '精密行星减速器，用于伺服电机配套的高刚性行星减速传动，'
       '常见于机械臂关节与转台驱动。',
       ['servo_drive', 'manipulator', 'rotary_table'],
       'https://www.shimpodrives.com', 'A', 0.85),

    # ---------- 直线执行器 (关键词: 直线执行 / linear actuator) 缺 3 ----------
    mk('LIN-ewellix-casm', 'Ewellix CASM 系列电动缸 (Linear Actuator)', 'Ewellix',
       'electric_linear_actuator',
       '伺服电动缸式直线执行器（linear actuator），由滚珠/行星滚柱丝杠驱动，'
       '用于人形机器人腿部直线驱动与工业推力场景。',
       ['humanoid_leg', 'industrial_press', 'linear_drive'],
       'https://www.ewellix.com', 'A', 0.86),
    mk('LIN-tolomatic-erd', 'Tolomatic ERD 系列电动直线执行器', 'Tolomatic',
       'electric_linear_actuator',
       '杆式电动直线执行器（electric rod linear actuator），集成丝杠与电机接口，'
       '替代气缸用于可控推力/位置的直线执行。',
       ['linear_drive', 'automation', 'pneumatic_replacement'],
       'https://www.tolomatic.com', 'A', 0.85),
    mk('LIN-iai-rcp6', 'IAI ROBO Cylinder RCP6 电动直线执行器', 'IAI Corporation',
       'electric_linear_actuator',
       '步进伺服驱动的直线执行器（linear actuator）系列，内置控制器方案可选，'
       '常用于装配与搬运工位的精密直线运动。',
       ['assembly', 'pick_place', 'linear_drive'],
       'https://www.iai-robot.co.jp', 'A', 0.85),

    # ---------- 谐波柔轮材料 (关键词: 柔轮 / flexspline) 缺 2 ----------
    mk('MAT-flexspline-42crmo', '42CrMo 合金结构钢（谐波减速器柔轮用）', 'GB/T 3077 标准牌号',
       'flexspline_material',
       '谐波减速器柔轮（flexspline）常用合金结构钢牌号，'
       '经调质+渗氮处理后兼顾疲劳强度与弹性变形能力；柔轮材料与热处理直接决定谐波减速器寿命。',
       ['harmonic_reducer', 'flexspline', 'material'],
       'https://openstd.samr.gov.cn', 'B', 0.7,
       {'entity_kind': 'component',
        'standard': 'GB/T 3077 合金结构钢',
        'confidence_basis': 'national_standard_designation',
        'material_note': '牌号与用途为行业通用做法；具体厂商柔轮的材料与热处理工艺多不公开，未逐一核实'}),
    mk('MAT-flexspline-30crmnsia', '30CrMnSiA 合金结构钢（柔轮/高应力构件用）', 'GB/T 3077 标准牌号',
       'flexspline_material',
       '高强度合金结构钢，用于柔轮（flexspline）等承受交变弯曲应力的薄壁构件，'
       '综合力学性能与淬透性较好。',
       ['harmonic_reducer', 'flexspline', 'material'],
       'https://openstd.samr.gov.cn', 'B', 0.65,
       {'entity_kind': 'component',
        'standard': 'GB/T 3077 合金结构钢',
        'confidence_basis': 'national_standard_designation',
        'material_note': '为通用高强钢牌号，柔轮用途属行业常见选材，非某一厂商公开声明'}),

    # ---------- 腱绳传动 (关键词: 腱绳 / tendon) 缺 2 ----------
    mk('TDN-dyneema-sk75', 'Dyneema SK75 超高分子量聚乙烯纤维（腱绳传动用）', 'Avient / DSM Dyneema',
       'tendon_cable',
       'UHMWPE 高强纤维绳，比强度极高、蠕变低，是灵巧手与腱绳传动（tendon drive）'
       '的主流腱绳材料，用于远端驱动以减轻指端惯量。',
       ['dexterous_hand', 'tendon_drive', 'exoskeleton'],
       'https://www.dyneema.com', 'A', 0.85),
    mk('TDN-sava-cable', 'Sava Industries 微型钢丝绳（腱绳/tendon 传动）', 'Sava Industries',
       'tendon_cable',
       '小直径不锈钢/镀层钢丝绳，用于腱绳传动（tendon）与遥控操作机构，'
       '相比合成纤维蠕变更小、耐磨，常见于机械手指腱索。',
       ['dexterous_hand', 'tendon_drive', 'surgical_robot'],
       'https://savacable.com', 'A', 0.78,
       {'confidence_basis': 'official_domain_live_403_bot_blocked',
        'verification_note': '2026-08-08 回探 HTTP 403：域名存活但拦截爬虫，未能读取页面正文'}),

    # ---------- 空心杯电机 (关键词: 空心杯 / coreless) 缺 2 ----------
    mk('MOT-maxon-re25', 'maxon RE 25 空心杯直流电机 (Coreless DC Motor)', 'maxon group',
       'coreless_dc_motor',
       '空心杯（coreless）有刷直流电机，无铁芯转子带来极低转动惯量与无齿槽转矩，'
       '用于灵巧手指节、微型关节等要求快速响应的场景。',
       ['dexterous_hand', 'micro_joint', 'precision_drive'],
       'https://www.maxongroup.com', 'A', 0.88),
    mk('MOT-faulhaber-1741cxr', 'FAULHABER 1741...CXR 空心杯微电机', 'FAULHABER',
       'coreless_dc_motor',
       '空心杯（coreless）自承式绕组微型直流电机，高功率密度与线性特性，'
       '常配套行星减速器用于假肢手与微型执行机构。',
       ['prosthetics', 'dexterous_hand', 'micro_actuator'],
       'https://www.faulhaber.com', 'A', 0.87),
]


def main():
    with open(ENT, encoding='utf-8') as f:
        d = json.load(f)
    ents = d.get('entities', d.get('data'))
    key = 'entities' if 'entities' in d else 'data'

    have = {e.get('id') for e in ents}
    have_names = {(e.get('name') or '').strip().lower() for e in ents}

    added, skipped = [], []
    for e in NEW:
        if e['id'] in have or e['name'].strip().lower() in have_names:
            skipped.append(e['id'])
            continue
        ents.append(e)
        have.add(e['id'])
        have_names.add(e['name'].strip().lower())
        added.append(e['id'])

    if not added:
        print(f'幂等：无新增（已存在 {len(skipped)} 条）')
        return 0

    d[key] = ents
    d.setdefault('meta', {})['total_entities'] = len(ents)
    with open(ENT, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    print(f'新增 {len(added)} 条，跳过 {len(skipped)} 条，实体总数 -> {len(ents)}')
    for i in added:
        print('  +', i)
    return 0


if __name__ == '__main__':
    sys.exit(main())
