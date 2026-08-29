"""
数据层增强：P0-RP-ID + P0-relationship_type + P1-protocol_bridges + P1-deterministic_labels
基于竞品扫描（RoP/NMPA-MedDevice/MedEdge-Gateway）的借鉴价值落地
2026-08-26
"""
import json, hashlib, os
from collections import Counter

BASE = r"C:\Users\xing\Desktop\robopart"
OUT_OPS = os.path.join(BASE, "ops")
os.makedirs(OUT_OPS, exist_ok=True)

# ─── 1. 读取并分配 RP-ID ───

with open(os.path.join(BASE, "api", "entities.json")) as f:
    entities_data = json.load(f)

entities = entities_data.get("entities", entities_data if isinstance(entities_data, list) else [])
print(f"Total entities: {len(entities)}")

# 按 category 分组计数
cat_counter = Counter()
entity_rpid_map = {}

for ent in entities:
    cat = ent.get("category", "other")
    cat_counter[cat] += 1
    # RP-ID 格式: RP-{CATEGORY}-{SEQUENCE}
    # category 取前三字母大写缩写
    prefix = cat[:3].upper().ljust(3, 'X')
    seq = cat_counter[cat]
    rp_id = f"RP-{prefix}-{seq:04d}"
    ent["rp_id"] = rp_id
    entity_rpid_map[ent["id"]] = rp_id

print(f"RP-IDs assigned: {len(entity_rpid_map)}")

# ─── 2. 兼容性关系类型扩展 ───

with open(os.path.join(BASE, "api", "compatibility.json")) as f:
    compat_data = json.load(f)

rules = compat_data.get("rules", [])
print(f"\nCompatibility rules: {len(rules)}")

# 新增关系类型（借鉴 Medical-Equipment-Lifecycle-KG）
NEW_RELATION_TYPES = {
    "compatible": "直接兼容（原有 mounts_to/compatible 语义）",
    "incompatible": "不兼容（原有 incompatible 语义）",
    "adapter_available": "需转接件（有现成转接方案）",
    "supersedes": "型号替代关系（B 型号可替代 A 型号）",
    "same_lineage": "同厂商代际关系",
    "uses_consumable": "依赖耗材/备件",
    "same_standard": "符合同一标准",
    "partial_compatible": "部分兼容（有限制条件）",
}

# 根据现有规则内容推断补充关系类型
enriched_rules = []
for rule in rules:
    rule_type = rule.get("type", "mounts_to")
    enriched = dict(rule)
    if rule_type == "mounts_to":
        enriched["relationship_type"] = "compatible"
    elif rule_type == "compatible":
        enriched["relationship_type"] = "compatible"
    elif rule_type == "incompatible":
        enriched["relationship_type"] = "incompatible"
    else:
        enriched["relationship_type"] = "compatible"  # default

    # 根据 from/to 实体属性推断额外关系
    from_id = rule.get("from", "")
    to_id = rule.get("to", "")
    # 查找 from 和 to 的制造商
    from_ent = next((e for e in entities if e["id"] == from_id), None)
    to_ent = next((e for e in entities if e["id"] == to_id), None)

    extra_rels = []
    if from_ent and to_ent:
        if from_ent.get("manufacturer") == to_ent.get("manufacturer"):
            extra_rels.append("same_lineage")
        # 如果有 interface 字段且包含 "adapter" 语义
        interface = rule.get("interface", "")
        if "ISO 9409" in interface and rule_type != "mounts_to":
            extra_rels.append("same_standard")

    if extra_rels:
        enriched["extra_relationships"] = extra_rels

    # 增加 RP-ID 引用
    enriched["from_rp_id"] = entity_rpid_map.get(from_id, from_id)
    enriched["to_rp_id"] = entity_rpid_map.get(to_id, to_id)
    enriched_rules.append(enriched)

# 更新 statistics
compat_data["rules"] = enriched_rules
compat_data["meta"] = compat_data.get("meta", {})
compat_data["meta"]["relationship_types"] = NEW_RELATION_TYPES
compat_data["meta"]["rp_id_enabled"] = True
compat_data["meta"]["rp_id_note"] = "RP-ID 格式: RP-{CATEGORY前三字母}-{SEQUENCE:04d}"

with open(os.path.join(BASE, "api", "compatibility.json"), "w", encoding="utf-8") as f:
    json.dump(compat_data, f, ensure_ascii=False, indent=2)
print(f"Compatibility rules enriched: relationship_type added to all {len(enriched_rules)} rules")

# ─── 3. 确定性标签推导规则 ───
# 借鉴 NMPA-MedDevice：从已知字段确定性推导兼容属性（非主观标注）

DERIVATION_RULES = {
    "manufacturer_ecosystem": {
        "description": "根据 manufacturer 确定性推导生态兼容属性",
        "rules": [
            {"manufacturer": "Universal Robots", "ecosystem": ["ros_control", "URCap", "Polyscope", "eSeries", "OPC UA"]},
            {"manufacturer": "ABB Robotics", "ecosystem": ["ROS Industrial", "RobotStudio", "RAPID", "EtherNet/IP", "OPC UA"]},
            {"manufacturer": "KUKA", "ecosystem": ["ROS Industrial", "KRL", "KSS", "EtherCAT", "OPC UA"]},
            {"manufacturer": "Fanuc", "ecosystem": ["ROS Industrial", "FANUC roboguide", "EtherNet/IP", "Focas", "OPC UA"]},
            {"manufacturer": "Doosan Robotics", "ecosystem": ["ROS2", "Doosan SDK", "EtherCAT"]},
            {"manufacturer": "Dobot", "ecosystem": ["ROS", "Dobot Studio", "USB"]},
            {"manufacturer": "Unitree Robotics", "ecosystem": ["ROS2", "Unitree SDK", "UDP"]},
            {"manufacturer": "Xarm", "ecosystem": ["ROS", "xArm SDK", "TCP/IP"]},
        ]
    },
    "category_inferred_props": {
        "description": "根据 category 确定性推导默认属性",
        "rules": [
            {"category": "actuators", "default_props": {"has_power_input": True, "has_feedback": True, "has_controller_interface": True}},
            {"category": "sensors", "default_props": {"has_data_output": True, "supports_polling": True, "typical_protocol": "I2C/SPI/CAN"}},
            {"category": "end_effectors", "default_props": {"requires_flange": True, "has_suction": False, "has_gripper_jaw": False}},
            {"category": "controllers", "default_props": {"supports_ros": False, "has_ethernet": True, "supports_rtos": True}},
        ]
    },
    "age_based_tier_decay": {
        "description": "根据 last_updated 时间自动降级 evidence_tier",
        "rule": "last_updated 距今 >3年 → tier 降一级（A→B, B→C）；>5年 → 标记 stale=true",
        "applied": False  # 此规则需结合时间判断，在运行时执行
    }
}

# 将推导规则写入 entities.json 的 meta
if isinstance(entities_data, dict) and "meta" in entities_data:
    entities_data["meta"]["derivation_rules"] = DERIVATION_RULES
else:
    entities_data["meta"] = entities_data.get("meta", {})
    entities_data["meta"]["derivation_rules"] = DERIVATION_RULES

# 执行：对每个实体应用确定性推导
for ent in entities:
    mfr = ent.get("manufacturer", "")
    cat = ent.get("category", "")

    # 制造商生态推导
    for rule in DERIVATION_RULES["manufacturer_ecosystem"]["rules"]:
        if rule["manufacturer"].lower() in mfr.lower():
            ent["derived_ecosystem"] = rule["ecosystem"]
            # 更新 confidence（有确定性推导后置信度提升）
            if ent.get("confidence", 0) < 0.7:
                ent["confidence"] = min(ent.get("confidence", 0) + 0.1, 0.7)
            ent["confidence_basis"] = (ent.get("confidence_basis", "") + "+manufacturer_ecosystem").lstrip("+")
            break

    # 品类属性推导
    for rule in DERIVATION_RULES["category_inferred_props"]["rules"]:
        if rule["category"] == cat:
            ent["derived_properties"] = rule["default_props"]
            break

with open(os.path.join(BASE, "api", "entities.json"), "w", encoding="utf-8") as f:
    json.dump(entities_data, f, ensure_ascii=False, indent=2)

# 统计推导覆盖情况
eco_derived = sum(1 for e in entities if e.get("derived_ecosystem"))
prop_derived = sum(1 for e in entities if e.get("derived_properties"))
print(f"\nDeterministic derivation:")
print(f"  Ecosystem derived: {eco_derived} entities")
print(f"  Properties derived: {prop_derived} entities")

# ─── 4. 协议桥接表 ───

PROTOCOL_BRIDGES = {
    "meta": {
        "description": "跨协议桥接方案——当机器人控制器与零部件使用不同通信协议时的转换方案",
        "source_inspiration": "MedEdge-Gateway (Modbus→MQTT→FHIR)",
        "version": "1.0.0",
        "updated": "2026-08-26",
        "bridge_count": 0
    },
    "bridges": [
        {
            "id": "BRIDGE-001",
            "from_protocol": "EtherCAT",
            "to_protocol": "CAN Bus",
            "bridge_solution": "Beckhoff TwinCAT XAE + CANopen Master",
            "typical_use_case": "EtherCAT 总线机器人 + CAN Bus 传感器/执行器",
            "latency_overhead_ms": 5,
            "evidence_tier": "B",
            "evidence_source": "Beckhoff documentation"
        },
        {
            "id": "BRIDGE-002",
            "from_protocol": "EtherCAT",
            "to_protocol": "Modbus TCP",
            "bridge_solution": "Beckhoff TwinCAT Modbus Master / EL2004",
            "typical_use_case": "EtherCAT 控制器 + Modbus TCP 变频器/电源",
            "latency_overhead_ms": 3,
            "evidence_tier": "B",
            "evidence_source": "Beckhoff / IEA Motion"
        },
        {
            "id": "BRIDGE-003",
            "from_protocol": "EtherCAT",
            "to_protocol": "OPC UA",
            "bridge_solution": "Beckhoff OPC UA Server (TwinCAT 3)",
            "typical_use_case": "EtherCAT 现场总线 → 上层 MES/SCADA 系统集成",
            "latency_overhead_ms": 2,
            "evidence_tier": "B",
            "evidence_source": "Beckhoff / OPC Foundation"
        },
        {
            "id": "BRIDGE-004",
            "from_protocol": "ROS 2 (DDS)",
            "to_protocol": "EtherCAT",
            "bridge_solution": "ros2_control + EtherCAT master (soem/ignition)",
            "typical_use_case": "ROS 2 上层控制 + EtherCAT 驱动器",
            "latency_overhead_ms": 50,
            "evidence_tier": "A",
            "evidence_source": "ros2_control documentation"
        },
        {
            "id": "BRIDGE-005",
            "from_protocol": "ROS 2 (DDS)",
            "to_protocol": "CAN Bus",
            "bridge_solution": "ros2_control + socketcan / can_msgs",
            "typical_use_case": "ROS 2 控制 + CAN Bus 关节电机（如 Dynamixel, ODrive）",
            "latency_overhead_ms": 10,
            "evidence_tier": "A",
            "evidence_source": "ros2_control documentation"
        },
        {
            "id": "BRIDGE-006",
            "from_protocol": "OPC UA",
            "to_protocol": "MQTT",
            "bridge_solution": "node-opcua + mqtt.js 或 KEPServerEX",
            "typical_use_case": "工业机器人 OPC UA 数据 → IoT 云平台",
            "latency_overhead_ms": 50,
            "evidence_tier": "B",
            "evidence_source": "OpenOPC / node-opcua"
        },
        {
            "id": "BRIDGE-007",
            "from_protocol": "Modbus TCP",
            "to_protocol": "OPC UA",
            "bridge_solution": "Kepware / Ignition / FreeOpcUa",
            "typical_use_case": "Modbus 设备接入 OPC UA 集成层",
            "latency_overhead_ms": 10,
            "evidence_tier": "B",
            "evidence_source": "Kepware documentation"
        },
        {
            "id": "BRIDGE-008",
            "from_protocol": "CAN Bus",
            "to_protocol": "ROS 2 (DDS)",
            "bridge_solution": "ros2_control + can_msgs / socketcan_bridge",
            "typical_use_case": "CAN Bus 关节 → ROS 2 控制框架",
            "latency_overhead_ms": 10,
            "evidence_tier": "A",
            "evidence_source": "ros2_control documentation"
        },
        {
            "id": "BRIDGE-009",
            "from_protocol": "EtherCAT",
            "to_protocol": "PROFINET",
            "bridge_solution": "Beckhoff PROFINET Master / Siemens PLC + ET 200",
            "typical_use_case": "跨厂商总线集成（Beckhoff + Siemens 产线）",
            "latency_overhead_ms": 3,
            "evidence_tier": "C",
            "evidence_source": "Beckhoff / Siemens documentation"
        },
        {
            "id": "BRIDGE-010",
            "from_protocol": "ROS 2 (DDS)",
            "to_protocol": "OPC UA",
            "bridge_solution": "ROS 2 → custom middleware → OPC UA SDK",
            "typical_use_case": "ROS 2 机器人数据 → 工业 SCADA/MES",
            "latency_overhead_ms": 20,
            "evidence_tier": "C",
            "evidence_source": "社区方案"
        }
    ]
}
PROTOCOL_BRIDGES["meta"]["bridge_count"] = len(PROTOCOL_BRIDGES["bridges"])

with open(os.path.join(BASE, "api", "protocol_bridges.json"), "w", encoding="utf-8") as f:
    json.dump(PROTOCOL_BRIDGES, f, ensure_ascii=False, indent=2)
print(f"\nProtocol bridges created: {len(PROTOCOL_BRIDGES['bridges'])} bridges")

# ─── 5. 生成增强报告 ───

# 统计推导效果
confidence_before = []
confidence_after = []
for ent in entities:
    # 读取原始 confidence（在写入之前，需要重建）
    pass

# 按 category 统计
print(f"\nCategory distribution:")
for cat, count in sorted(cat_counter.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count}")

print("\nDone. Verify JSON files:")
for fname in ["entities.json", "compatibility.json", "protocol_bridges.json"]:
    with open(os.path.join(BASE, "api", fname)) as f:
        json.load(f)
    print(f"  ✅ {fname} valid")
