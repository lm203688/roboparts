"""
P2: 实体 kind 分层（type vs instance）+ 跨标准术语对齐表
借鉴 FHIR DeviceDefinition 模型
2026-08-26
"""
import json, os

BASE = r"C:\Users\xing\Desktop\robopart"

with open(os.path.join(BASE, "api", "entities.json")) as f:
    entities_data = json.load(f)

entities = entities_data.get("entities", [])

# ─── 1. 实体 kind 分层 ───
# FHIR 做法：DeviceDefinition（型号定义）vs Device（具体实例）
# RoboParts 映射：entity_kind: "type" | "instance" | "standard"

for ent in entities:
    existing_kind = ent.get("entity_kind", "component")
    # 已有 entity_kind: "component" → 改为 "type"（因为绝大多数条目是型号级别）
    # 有 serial_number 或 unique_id 的 → "instance"
    if ent.get("serial_number") or ent.get("unique_id") or ent.get("serial"):
        ent["entity_kind"] = "instance"
    elif ent.get("standard") or "standard" in str(ent.get("type", "")).lower():
        ent["entity_kind"] = "standard"
    else:
        ent["entity_kind"] = "type"

# ─── 2. 跨标准术语对齐表 ───
# 借鉴 RoP：同一概念在不同标准体系中的名称映射

TERMINOLOGY_ALIASES = {
    "meta": {
        "description": "机器人零部件术语对齐表——同一概念在不同标准体系/厂商手册中的名称映射",
        "inspiration": "RoP biomedical CDE cross-vocabulary mapping",
        "version": "1.0.0",
        "updated": "2026-08-26"
    },
    "mappings": [
        {
            "canonical_concept": "机器人法兰",
            "aliases": [
                {"standard": "ISO 9409-1", "term": "Robotic manipulators - Flanges"},
                {"standard": "GB/T", "term": "机械手臂法兰"},
                {"standard": "UR手册", "term": "Tool flange"},
                {"standard": "ABB手册", "term": "Tool flange / Wrist flange"},
                {"standard": "KUKA手册", "term": "Werkzeugflansch / Tool flange"},
                {"standard": "Fanuc手册", "term": "Tool flange"},
                {"standard": "ROS工业", "term": "TCP (Tool Center Point)"},
            ],
            "rp_category": "interfaces"
        },
        {
            "canonical_concept": "减速器",
            "aliases": [
                {"standard": "ISO", "term": "Reducer / Harmonic drive"},
                {"standard": "GB/T", "term": "谐波减速器"},
                {"standard": "厂商通用", "term": "Harmonic reducer / Cycloidal reducer / Planetary reducer"},
                {"standard": "ROS", "term": "Joint transmission"},
            ],
            "rp_category": "reducers"
        },
        {
            "canonical_concept": "夹爪/末端执行器",
            "aliases": [
                {"standard": "ISO", "term": "End effector / Gripper"},
                {"standard": "GB/T", "term": "末端执行器"},
                {"standard": "ROS", "term": "Gripper action"},
                {"standard": "工业通用", "term": "Tool / End-of-arm tooling (EOAT)"},
            ],
            "rp_category": "grippers"
        },
        {
            "canonical_concept": "控制器/驱动器",
            "aliases": [
                {"standard": "ISO 10218", "term": "Controller"},
                {"standard": "GB/T", "term": "控制器"},
                {"standard": "ROS", "term": "controller_manager"},
                {"standard": "EtherCAT", "term": "Master / Master controller"},
                {"standard": "工业通用", "term": "Drive / Servo drive / Motion controller"},
            ],
            "rp_category": "controllers"
        },
        {
            "canonical_concept": "工业总线",
            "aliases": [
                {"standard": "IEC 61158", "term": "Fieldbus"},
                {"standard": "IEC 62541", "term": "OPC UA"},
                {"standard": "ROS", "term": "DDS / rosbag"},
                {"standard": "工业通用", "term": "EtherCAT / PROFINET / Modbus / CANopen"},
            ],
            "rp_category": "protocols"
        }
    ]
}

# 写入 standalone 文件
with open(os.path.join(BASE, "api", "terminology_aliases.json"), "w", encoding="utf-8") as f:
    json.dump(TERMINOLOGY_ALIASES, f, ensure_ascii=False, indent=2)

# 在 entities.json 中增加 cross_standard_aliases 索引
entities_data["meta"] = entities_data.get("meta", {})
entities_data["meta"]["terminology_aliases_file"] = "api/terminology_aliases.json"
entities_data["meta"]["entity_kind_values"] = {
    "type": "型号级别定义（用于兼容性判定）",
    "instance": "具体实例（用于库存/维修追踪）",
    "standard": "标准/规范本身"
}

# 写入
with open(os.path.join(BASE, "api", "entities.json"), "w", encoding="utf-8") as f:
    json.dump(entities_data, f, ensure_ascii=False, indent=2)

# 统计
kind_counts = {}
for ent in entities:
    k = ent.get("entity_kind", "unknown")
    kind_counts[k] = kind_counts.get(k, 0) + 1

print("Entity kind distribution:")
for k, c in sorted(kind_counts.items()):
    print(f"  {k}: {c}")
print(f"\nTerminology aliases created: {len(TERMINOLOGY_ALIASES['mappings'])} concept groups")

# 验证
for fname in ["entities.json", "terminology_aliases.json"]:
    with open(os.path.join(BASE, "api", fname)) as f:
        json.load(f)
    print(f"✅ {fname} valid")
