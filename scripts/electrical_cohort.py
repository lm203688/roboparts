#!/usr/bin/env python3
"""scripts/electrical_cohort.py — 电气取证同质集框架（Phase C · L4 证据飞轮）

**背景**（20261013 报告 §8.3 #3）：
    fitness 排序显示电气取证同质集是唯一被推荐的变更（net_gain=1.46）。
    本脚本创建同质集框架，让用户后续填入实际数据。

**MVC 判据**（cohort_feasibility.json）：
    - K=2 即可（双轴 AND 收敛）
    - 缺 ['mechanical', 'electrical'] 的节点每节点只需 2 条声明
    - 涉及 370 个节点，支撑 24,424 对可行配对

**设计纪律**：
    1. 按同质集批量推进，不按单条取证（T2 定理：单声明零收益）
    2. 每条证据必须带出处（Tier A/B/C 溯源）
    3. 批量推送：一次 16 节点，不零散补数

用法：
    python scripts/electrical_cohort.py --plan       # 输出取证计划
    python scripts/electrical_cohort.py --scaffold   # 生成取证骨架文件
    python scripts/electrical_cohort.py --validate   # 校验已填数据
    python scripts/electrical_cohort.py --status     # 显示当前进度
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
OUTPUT_DIR = ROOT / "evidence" / "electrical_cohort"

# 同质集目标节点（从 cohort_feasibility.json 提取）
TARGET_NODES = [
    # Actuators (top MDV)
    {"id": "ACT-004", "label": "Odrive D6374", "category": "actuators", "manufacturer": "ODrive"},
    {"id": "ACT-005", "label": "SimpleFOC Shield", "category": "actuators", "manufacturer": "RobotDyn"},
    {"id": "ACT-006", "label": "T-Motor AK80-64", "category": "actuators", "manufacturer": "T-Motor"},
    {"id": "ACT-007", "label": "T-Motor AK10-9", "category": "actuators", "manufacturer": "T-Motor"},
    {"id": "ACT-008", "label": "Maxon EC Flat 60", "category": "actuators", "manufacturer": "Maxon"},
    {"id": "ACT-009", "label": "Kollmorgen TBM2G", "category": "actuators", "manufacturer": "Kollmorgen"},
    {"id": "ACT-010", "label": "Focbox Unity", "category": "actuators", "manufacturer": "FocBox"},
    {"id": "ACT-011", "label": "Unitree B2 Motor", "category": "actuators", "manufacturer": "Unitree"},
    # Sensors
    {"id": "SEN-001", "label": "ROS Kinect", "category": "sensors", "manufacturer": "Intel"},
    {"id": "SEN-002", "label": "Orbbec Gemini 335", "category": "sensors", "manufacturer": "Orbbec"},
    {"id": "SEN-003", "label": "Intel RealSense D435i", "category": "sensors", "manufacturer": "Intel"},
    {"id": "SEN-004", "label": "Lepton 3.5 Thermal", "category": "sensors", "manufacturer": "FLIR"},
    # Grippers
    {"id": "GRP-001", "label": "Robotiq 2F-85", "category": "grippers", "manufacturer": "Robotiq"},
    {"id": "GRP-002", "label": "Schunk EGP Gripper", "category": "grippers", "manufacturer": "Schunk"},
    {"id": "GRP-003", "label": "Robotiq 2F-140", "category": "grippers", "manufacturer": "Robotiq"},
    {"id": "GRP-004", "label": "Robotiq 2F-85E", "category": "grippers", "manufacturer": "Robotiq"},
]

# 电气取证字段（每条节点需要填）
EVIDENCE_FIELDS = {
    "connector_family": {"type": "string", "required": True, "example": "M8, M12, JST-XH"},
    "connector_pins": {"type": "integer", "required": True, "example": "3, 4, 5, 8"},
    "pinout": {"type": "array", "required": False, "example": ["VCC", "GND", "SIG+"]},
    "voltage_range": {"type": "string", "required": True, "example": "12V DC, 24V DC"},
    "current_max": {"type": "number", "required": False, "example": 5.0},
    "interface_protocol": {"type": "string", "required": True, "example": "CANopen, Modbus, RS485"},
    "source_url": {"type": "string", "required": True, "example": "https://www.odrive.com/products/odrive"},
    "source_tier": {"type": "string", "required": True, "example": "A, B, C"},
    "source_date": {"type": "string", "required": True, "example": "2026-10-16"},
}


def generate_plan() -> Dict[str, Any]:
    """生成取证计划。"""
    return {
        "meta": {
            "version": "electrical_cohort/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_nodes": len(TARGET_NODES),
        },
        "strategy": {
            "batch_size": 16,
            "rounds": 1,
            "axis": "electrical",
            "mvc_K": 2,
            "expected_pairs_unlocked": 15,
            "expected_net_gain": 1.46,
        },
        "nodes": TARGET_NODES,
        "fields": EVIDENCE_FIELDS,
        "validation_rules": [
            "每条节点必须有 connector_family + connector_pins + interface_protocol",
            "source_tier 必须是 A/B/C 之一",
            "source_url 必须是 https 开头",
            "批量推送：16 节点一起提交，不零散补数",
        ],
    }


def generate_scaffold() -> Dict[str, Any]:
    """生成取证骨架文件（空模板，等用户填）。"""
    scaffold = {
        "meta": {
            "version": "electrical_cohort/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "scaffold",
            "instructions": "填写每个节点的电气参数，然后运行 --validate 校验",
        },
        "nodes": {},
    }
    
    for node in TARGET_NODES:
        scaffold["nodes"][node["id"]] = {
            "label": node["label"],
            "category": node["category"],
            "manufacturer": node["manufacturer"],
            "evidence": {},  # 等用户填
        }
    
    return scaffold


def validate_evidence(data: Dict[str, Any]) -> Dict[str, Any]:
    """校验已填证据。"""
    errors = []
    warnings = []
    valid_nodes = 0
    total_nodes = len(data.get("nodes", {}))
    
    for node_id, node_data in data.get("nodes", {}).items():
        evidence = node_data.get("evidence", {})
        
        # 必填字段检查
        for field, spec in EVIDENCE_FIELDS.items():
            if spec.get("required") and field not in evidence:
                errors.append(f"{node_id}: 缺少必填字段 {field}")
        
        # 字段类型检查
        for field, value in evidence.items():
            if field not in EVIDENCE_FIELDS:
                warnings.append(f"{node_id}: 未知字段 {field}")
                continue
            
            spec = EVIDENCE_FIELDS[field]
            expected_type = spec["type"]
            
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"{node_id}.{field}: 应为 string，实际 {type(value).__name__}")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"{node_id}.{field}: 应为 integer，实际 {type(value).__name__}")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"{node_id}.{field}: 应为 number，实际 {type(value).__name__}")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"{node_id}.{field}: 应为 array，实际 {type(value).__name__}")
        
        # 溯源检查
        if "source_tier" in evidence:
            if evidence["source_tier"] not in ["A", "B", "C"]:
                errors.append(f"{node_id}.source_tier: 必须为 A/B/C，实际 {evidence['source_tier']}")
        
        if "source_url" in evidence and not evidence["source_url"].startswith("https://"):
            errors.append(f"{node_id}.source_url: 必须以 https:// 开头")
        
        # 计数
        if not any(e.startswith(node_id) for e in errors):
            valid_nodes += 1
    
    return {
        "ok": len(errors) == 0,
        "total_nodes": total_nodes,
        "valid_nodes": valid_nodes,
        "errors": errors,
        "warnings": warnings,
    }


def get_status() -> Dict[str, Any]:
    """显示当前进度。"""
    scaffold_path = OUTPUT_DIR / "electrical_cohort.json"
    
    if not scaffold_path.exists():
        return {
            "status": "not_started",
            "message": "未开始——运行 --scaffold 生成骨架文件",
            "scaffold_path": str(scaffold_path),
        }
    
    with open(scaffold_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total_nodes = len(data.get("nodes", {}))
    filled_nodes = sum(1 for n in data.get("nodes", {}).values() if n.get("evidence"))
    
    return {
        "status": "in_progress" if filled_nodes < total_nodes else "complete",
        "total_nodes": total_nodes,
        "filled_nodes": filled_nodes,
        "completion_pct": round(filled_nodes / total_nodes * 100, 1) if total_nodes > 0 else 0,
        "scaffold_path": str(scaffold_path),
    }


def main() -> int:
    if "--plan" in sys.argv:
        result = generate_plan()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    elif "--scaffold" in sys.argv:
        scaffold = generate_scaffold()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "electrical_cohort.json"
        output_path.write_text(json.dumps(scaffold, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] scaffold written: {output_path}")
        return 0
    elif "--validate" in sys.argv:
        scaffold_path = OUTPUT_DIR / "electrical_cohort.json"
        if not scaffold_path.exists():
            print("[error] scaffold not found, run --scaffold first")
            return 1
        with open(scaffold_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        result = validate_evidence(data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    elif "--status" in sys.argv:
        result = get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    else:
        print(__doc__)
        return 0


if __name__ == "__main__":
    sys.exit(main())
