#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 数据治理脚本（对应报告 N10 Schema 治理 + T6 三副本漂移修复）

职责：
1. 将 entities.json 中 65 种原始 category 值归一化到 10 个标准类目
2. 以 entities.json 为单一真相源，重生成 api/<category>.json（消除分类 JSON 与 entities 漂移）
3. 重生成 data.js（消除前端副本漂移，修正统计数字）
4. 更新 entities.json 的 meta.category_counts / meta.categories
5. 重生成 api/data.json（对外主接口 /api/data.json 的数据源，防止其脱离治理管线）

【N03 20260805 修复】api/data.json 此前不在本脚本产出范围内，导致它长期停留在旧快照
（493 实体 / 65 个未归一化 category），而对外主接口 /api/data.json 正是由它提供。
每日巡检因此把「本地文件陈旧」误判为「待部署」，连续多日无法闭环。现纳入管线。

运行：python scripts/normalize_categories.py
幂等：可重复运行，结果与单次运行一致。
"""
import json
import collections
import datetime
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# RP_ENTITIES_JSON 重定向：闸门可在副本上试算而不碰真实数据（见 ci_gate.py）。
ENTITIES_PATH = (os.environ.get('RP_ENTITIES_JSON')
                 or os.path.join(ROOT, 'api', 'entities.json'))
DATAJS_PATH = os.path.join(ROOT, 'data.js')

CANONICAL = [
    'actuators', 'sensors', 'chips', 'interfaces', 'protocols',
    'llms', 'platforms', 'flexible_actuators', 'robot_ai_models', 'data_acquisition',
    # 【20260809-07】connectors —— 实物互连件（线对板/板对板/混装电源信号连接器）。
    # 为什么不并入 interfaces：interfaces 在 govern_entity_kind 属 SPEC_CATEGORIES，
    # 判据是「类目 + 物理证据否决」。实测同一个 Molex 产品族会被劈成两半 ——
    # MiniMix 带 current=15.0A 触发否决位 → component；Mirror Mezz 只有接口角色
    # 描述、无任何物理量 → 落回 specification 被静默吞掉，且永不进机械声明率分母。
    # 同族产品分类不一致是结构性缺陷，故独立类目，component 语义稳定。
    'connectors',
    # 【20260818】W1 机械骨架类目扩展（飞轮覆盖面缺口，见 ops/roboparts-conformance-review-20260818.md）。
    # 现有 11 类偏"智能/驱动层"，机械/电源/结构/互连骨干从未成为一等类目。
    # 下列类目当前多为 0 种子（诚实留空），由 Matrix 一体化关节模组 BOM 作为起始脚手架。
    'integrated_joints',  # 一体化关节模组（集成丝杠+电机+驱动+减速器+编码器+传感器）
    'reducers',           # 减速器 / 谐波减速器
    'controllers',        # 控制器 / 驱动器（伺服驱动）
    'grippers',           # 夹爪 / 末端执行器
    'structural',         # 结构件 / 机架
    'cables',             # 线缆 / 线束
    'power',              # 电源 / 电池
    'pcb',                # PCB / 电子布线
    # 【20260821】仿生机械品类
    'bionic_mechanisms',  # 仿生机械（仿生关节、仿生驱动器、仿生传感器）
]

# 原始 category 值 -> 标准类目（覆盖全部 65 种取值）
MAPPING = {
    # 执行器集群
    'actuators': 'actuators', 'actuator': 'actuators', 'joint_actuator': 'actuators',
    'servo': 'actuators', 'Servo': 'actuators', 'motor': 'actuators', 'Motor': 'actuators',
    'hand_actuator': 'actuators', '灵巧手': 'actuators', 'gripper': 'actuators',
    'dexterous_hand': 'actuators', 'integrated_actuator': 'actuators',
    'humanoid_actuator': 'actuators', 'humanoid-actuator': 'actuators',
    'full_body_actuator': 'actuators', 'Hydraulic': 'actuators', 'hydraulic': 'actuators',
    'Pneumatic': 'actuators', 'pneumatic': 'actuators', 'Piezo': 'actuators', 'piezo': 'actuators',
    '串联弹性驱动器(SEA)': 'actuators', 'micro_actuator': 'actuators',
    'qdd_actuator': 'actuators', 'frameless_motor': 'actuators',
    'smart-actuator': 'actuators', 'joint_motor': 'actuators',
    '柔性驱动器': 'actuators', '人工肌肉': 'actuators', '仿生脊柱': 'actuators',
    'SMA': 'actuators', 'motor_controller': 'actuators', 'controller': 'actuators',
    # 传感器集群
    'sensors': 'sensors', 'Sensor': 'sensors', 'Vision Sensor': 'sensors',
    '触觉传感器': 'sensors', '六维力传感器': 'sensors', 'IMU': 'sensors',
    # 计算/芯片集群
    'chips': 'chips', 'AI Accelerator': 'chips', 'ai_accelerator': 'chips',
    'compute': 'chips', 'mcu': 'chips', 'sensor_processor': 'chips',
    'dev_board': 'chips', 'ai-processor': 'chips', 'robot_soc': 'chips',
    'desktop_ai_chip': 'chips',
    # 协议集群
    'protocols': 'protocols', 'communication': 'protocols',
    'wireless-protocol': 'protocols', 'industrial-protocol': 'protocols',
    'iot-protocol': 'protocols',
    # 接口
    'interfaces': 'interfaces', 'interface': 'interfaces',
    # 大模型
    'llms': 'llms', 'LLM': 'llms',
    # 机器人 AI 模型
    'robot_ai_models': 'robot_ai_models', 'VLA': 'robot_ai_models', 'ai_model': 'robot_ai_models',
    # 平台
    'platforms': 'platforms', 'market_analysis': 'platforms',
    # 柔性执行器 / 数据采集（保持原类目）
    'flexible_actuators': 'flexible_actuators',
    'data_acquisition': 'data_acquisition',
    # 互连件（实物连接器）
    'connectors': 'connectors', 'connector': 'connectors', '连接器': 'connectors',
    'hybrid_connector': 'connectors', 'board_to_board': 'connectors',
    'wire_to_board': 'connectors', 'mezzanine_connector': 'connectors',
    'circular_connector': 'connectors', 'terminal': 'connectors', '接插件': 'connectors',
    # 【20260818】W1 机械骨架类目别名（原始值 -> 标准类目）
    'integrated_joint': 'integrated_joints', '一体化关节': 'integrated_joints',
    '一体化关节模组': 'integrated_joints', 'joint_module': 'integrated_joints',
    'reducer': 'reducers', '减速器': 'reducers', '谐波减速器': 'reducers',
    'harmonic_drive': 'reducers',
    'controller': 'controllers', '控制器': 'controllers', '驱动器': 'controllers',
    'servo_drive': 'controllers', 'motor_controller': 'controllers',
    'gripper': 'grippers', '夹爪': 'grippers', '末端执行器': 'grippers',
    'end_effector': 'grippers',
    'structural': 'structural', '结构件': 'structural', '机架': 'structural',
    'chassis': 'structural', 'frame': 'structural',
    'cable': 'cables', '线缆': 'cables', '线束': 'cables', 'harness': 'cables',
    'power': 'power', '电源': 'power', '电池': 'power', 'battery': 'power',
    'pcb': 'pcb', 'PCB': 'pcb', '电路板': 'pcb', '电子布线': 'pcb',
    # 【20260821】仿生机械品类
    'bionic_mechanisms': 'bionic_mechanisms', '仿生机械': 'bionic_mechanisms',
    'bionic': 'bionic_mechanisms',
}


class UnmappedCategory(Exception):
    """未知类目不得静默兜底 —— 见 normalize() 注释。"""


def normalize(cat, strict=False):
    """把原始 category 归一化到 CANONICAL。

    【20260809-07】`strict` 的由来：原实现是 `MAPPING.get(cat, 'actuators')`，
    未知类目**静默变成执行器**，只在收尾打印一行 ⚠️ 警告。这条兜底的危险在于
    它对"新增类目"和"拼错类目"给出完全相同的、看起来成功的结果：
    本轮新增 connectors 时若忘了登记，两条 Molex 连接器会被写成 actuators，
    而 217→219 的执行器计数不会让任何闸门失败。
    与 L1.69「新增口径不会让核验器失败 → 加了和漏了在闸门眼里一样」同族。
    默认保持兜底（不改变既有调用方行为），但 main() 一律以 strict 复核，
    有未映射值即中止，绝不把污染写回真相源。
    """
    if cat in CANONICAL:
        return cat
    if cat in MAPPING:
        return MAPPING[cat]
    if strict:
        raise UnmappedCategory(cat)
    return 'actuators'

def main():
    with open(ENTITIES_PATH, encoding='utf-8') as f:
        doc = json.load(f)
    entities = doc['entities']
    updated = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    # 1) 归一化 category，统计变更
    changed = 0
    unmapped = collections.Counter()
    for e in entities:
        raw = e.get('category')
        new = normalize(raw)
        if new != raw:
            changed += 1
        if raw not in CANONICAL and raw not in MAPPING:
            unmapped[raw] += 1
        e['category'] = new

    # 2) 更新 meta
    counts = collections.Counter(e['category'] for e in entities)
    doc['meta']['categories'] = CANONICAL
    doc['meta']['category_counts'] = {c: counts.get(c, 0) for c in CANONICAL}
    doc['meta']['total'] = len(entities)
    doc['meta']['total_entities'] = len(entities)
    doc['meta']['updated'] = updated
    if unmapped:
        # 【20260809-07】此处原为一行 ⚠️ 警告后继续写盘 —— 等于把误分类固化进真相源。
        # 未映射类目只有两种成因：新类目忘了登记，或原始值拼错。两者都必须人来定夺，
        # 不该由脚本替它选"算作执行器"。
        raise SystemExit('!! 未映射的原始类目 %s —— 拒绝写回。'
                         '请先在 CANONICAL/MAPPING 登记，勿让它静默兜底到 actuators'
                         % dict(unmapped))

    # 3) 写回 entities.json
    with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # 4) 重生成各分类 JSON（单一真相源 -> 分类文件）
    for c in CANONICAL:
        items = [e for e in entities if e['category'] == c]
        out = {'count': len(items), 'updated': updated, 'data': items}
        if c == 'robot_ai_models':
            out['category'] = c
        with open(os.path.join(ROOT, 'api', c + '.json'), 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write('\n')

    # 5) 重生成 data.js（DB 格式，消除前端副本漂移）
    stats = {c: counts.get(c, 0) for c in CANONICAL}
    db = {'updated': updated, 'stats': stats}
    for c in CANONICAL:
        db[c] = [e for e in entities if e['category'] == c]
    with open(DATAJS_PATH, 'w', encoding='utf-8') as f:
        f.write('const DB = ')
        json.dump(db, f, ensure_ascii=False, indent=2)
        f.write(';\n')

    # 6) 重生成 api/data.json（对外主接口数据源，保留其既有 meta 扩展字段）
    datajson_path = os.path.join(ROOT, 'api', 'data.json')
    if os.path.exists(datajson_path):
        with open(datajson_path, encoding='utf-8') as f:
            pub = json.load(f)
    else:
        pub = {'meta': {}, 'data': []}
    pub.setdefault('meta', {})
    pub['meta']['updated'] = updated
    pub['meta']['total_entities'] = len(entities)
    pub['meta']['categories'] = CANONICAL
    pub['meta']['category_counts'] = stats
    # 【N10 20260805】把溯源覆盖率摘要一并透出到对外主接口，
    # 让调用方 Agent 无需遍历全量实体即可判断数据可信度分布
    if doc['meta'].get('provenance_coverage'):
        pub['meta']['provenance_coverage'] = doc['meta']['provenance_coverage']
    # 【N10 20260805 周三】数据质量审计结论同步透出，
    # 让调用方 Agent 能直接按 quarantine 过滤掉无法溯源的条目
    if doc['meta'].get('data_quality'):
        pub['meta']['data_quality'] = doc['meta']['data_quality']
    # 【N13 20260805-16】机械互换维度覆盖率透出，
    # 让调用方 Agent 在做装配/选型判定前就知道该维度的填充率与缺口口径
    if doc['meta'].get('mechanical_interface_coverage'):
        pub['meta']['mechanical_interface_coverage'] = doc['meta']['mechanical_interface_coverage']
    pub['data'] = entities
    with open(datajson_path, 'w', encoding='utf-8') as f:
        json.dump(pub, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # 7) 报告
    print('[OK] Normalized: modified category', changed, 'items / total', len(entities), 'items')
    print('[STATS] Category counts:', json.dumps(stats, ensure_ascii=False))
    print('[REGEN] Regenerated: entities.json + category JSONs + data.js + api/data.json')


# --- meta.access 自动重注入 ---
# 【N13 20260805-22】本脚本整体重写 entities.json 与 10 个分类 JSON，
# 而 AI 爬虫 16% 的抓取正落在这些文件上。接入声明若只靠人工补一次，
# 必然在下一次重建中被静默抹掉（与 sitemap 被整段覆盖属同一类事故）。
# 因此把注入挂成生成管线的固定尾巴：谁重写数据，谁负责把入口补回去。
def _reinject_access():
    import subprocess, sys as _s, os as _o
    _r = _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    subprocess.run([_s.executable, _o.path.join(_r, 'scripts', 'inject_api_access.py')],
                   check=False)


if __name__ == '__main__':
    main()
    _reinject_access()
