#!/usr/bin/env python3
"""
Compatibility Matrix System - manages part-to-part compatibility relationships
Enables "LEGO-like" assembly by validating which parts work together
"""
import json, os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_FILE = os.path.join(ROOT, "api", "entities.json")
COMPAT_FILE = os.path.join(ROOT, "api", "compatibility.json")

# Pre-defined compatibility relationships
COMPATIBILITY_RULES = [
    # === 机械接口兼容 ===
    {"from": "BIONIC-JOINT-001", "to": "BIONIC-FRAME-001", "type": "mounts_to", "interface": "ISO 9409-1 64mm"},
    {"from": "BIONIC-JOINT-002", "to": "BIONIC-FRAME-001", "type": "mounts_to", "interface": "ISO 9409-1 80mm"},
    {"from": "BIONIC-JOINT-003", "to": "BIONIC-ACTUATOR-003", "type": "mounts_to", "interface": "press_fit 8mm"},
    
    # === 驱动兼容 ===
    {"from": "BIONIC-ACTUATOR-001", "to": "BIONIC-JOINT-001", "type": "drives", "interface": "tendon_50N"},
    {"from": "BIONIC-ACTUATOR-001", "to": "BIONIC-JOINT-003", "type": "drives", "interface": "tendon_50N"},
    {"from": "BIONIC-ACTUATOR-002", "to": "BIONIC-JOINT-001", "type": "drives", "interface": "muscle_100N"},
    {"from": "BIONIC-ACTUATOR-002", "to": "BIONIC-JOINT-002", "type": "drives", "interface": "muscle_100N"},
    
    # === 传感器兼容 ===
    {"from": "BIONIC-SENSOR-001", "to": "BIONIC-JOINT-001", "type": "senses", "interface": "eskin_adhesive"},
    {"from": "BIONIC-SENSOR-001", "to": "BIONIC-JOINT-002", "type": "senses", "interface": "eskin_adhesive"},
    {"from": "BIONIC-SENSOR-002", "to": "BIONIC-JOINT-001", "type": "senses", "interface": "proprioceptor_integrated"},
    {"from": "BIONIC-SENSOR-002", "to": "BIONIC-JOINT-002", "type": "senses", "interface": "proprioceptor_integrated"},
    
    # === 皮肤兼容 ===
    {"from": "BIONIC-SKIN-001", "to": "BIONIC-FRAME-001", "type": "covers", "interface": "adhesive"},
    {"from": "BIONIC-SKIN-001", "to": "BIONIC-JOINT-001", "type": "covers", "interface": "flexible"},
    {"from": "BIONIC-SKIN-001", "to": "BIONIC-JOINT-002", "type": "covers", "interface": "flexible"},
    
    # === 已有零件兼容 ===
    {"from": "PRIMA1-HAND-001", "to": "BIONIC-ACTUATOR-001", "type": "uses", "interface": "tendon_interface"},
    {"from": "DEXHAND021PRO-001", "to": "BIONIC-ACTUATOR-001", "type": "uses", "interface": "tendon_interface"},
    {"from": "NEO-HAND-001", "to": "BIONIC-ACTUATOR-001", "type": "uses", "interface": "tendon_interface"},
    
    # === 框架兼容 ===
    {"from": "BIONIC-FRAME-001", "to": "BIONIC-JOINT-001", "type": "supports", "interface": "flange_120mm"},
    {"from": "BIONIC-FRAME-001", "to": "BIONIC-JOINT-002", "type": "supports", "interface": "flange_120mm"},
    {"from": "BIONIC-FRAME-001", "to": "BIONIC-ACTUATOR-001", "type": "mounts", "interface": "surface_mount"},
    {"from": "BIONIC-FRAME-001", "to": "BIONIC-ACTUATOR-002", "type": "mounts", "interface": "surface_mount"},
]


def load_entities():
    with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_compatibility_index(entities):
    """Build a lookup index for entities by ID"""
    return {e["id"]: e for e in entities}


def validate_compatibility(from_id, to_id, index):
    """Check if two parts are compatible"""
    # Check if both entities exist
    if from_id not in index or to_id not in index:
        return {"compatible": False, "reason": "entity_not_found"}
    
    from_entity = index[from_id]
    to_entity = index[to_id]
    
    # Check mechanical interface compatibility
    from_interface = from_entity.get("mechanical_interface", {})
    to_interface = to_entity.get("mechanical_interface", {})
    
    if from_interface.get("status") == "declared" and to_interface.get("status") == "declared":
        if from_interface.get("standard") == to_interface.get("standard"):
            return {"compatible": True, "reason": "same_standard"}
    
    # Check explicit compatibility
    for rule in COMPATIBILITY_RULES:
        if rule["from"] == from_id and rule["to"] == to_id:
            return {"compatible": True, "reason": rule["type"], "interface": rule["interface"]}
        if rule["from"] == to_id and rule["to"] == from_id:
            return {"compatible": True, "reason": rule["type"], "interface": rule["interface"]}
    
    return {"compatible": False, "reason": "no_known_compatibility"}


def find_compatible_parts(part_id, index, direction="both"):
    """Find all parts compatible with a given part"""
    compatible = []
    
    for rule in COMPATIBILITY_RULES:
        if direction in ("both", "outgoing") and rule["from"] == part_id:
            if rule["to"] in index:
                compatible.append({
                    "id": rule["to"],
                    "name": index[rule["to"]]["name"],
                    "type": rule["type"],
                    "interface": rule["interface"]
                })
        if direction in ("both", "incoming") and rule["to"] == part_id:
            if rule["from"] in index:
                compatible.append({
                    "id": rule["from"],
                    "name": index[rule["from"]]["name"],
                    "type": rule["type"],
                    "interface": rule["interface"]
                })
    
    return compatible


def generate_assembly_suggestions(parts, index):
    """Given a list of parts, suggest compatible additions"""
    suggestions = []
    
    for part_id in parts:
        compatible = find_compatible_parts(part_id, index)
        for comp in compatible:
            if comp["id"] not in parts:
                suggestions.append({
                    "add": comp["id"],
                    "name": comp["name"],
                    "connects_to": part_id,
                    "connection_type": comp["type"],
                    "interface": comp["interface"]
                })
    
    # Deduplicate suggestions
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        if s["add"] not in seen:
            seen.add(s["add"])
            unique_suggestions.append(s)
    
    return unique_suggestions


def main():
    print("[COMPAT] Compatibility Matrix System")
    print("=" * 60)
    
    # Load entities
    entities_data = load_entities()
    index = build_compatibility_index(entities_data["entities"])
    
    print(f"\n[INFO] Loaded {len(index)} entities")
    print(f"[INFO] Loaded {len(COMPATIBILITY_RULES)} compatibility rules")
    
    # Save compatibility data
    compat_data = {
        "version": "1.0",
        "updated": datetime.now().isoformat(),
        "rules": COMPATIBILITY_RULES,
        "statistics": {
            "total_rules": len(COMPATIBILITY_RULES),
            "unique_parts": len(set(r["from"] for r in COMPATIBILITY_RULES) | set(r["to"] for r in COMPATIBILITY_RULES)),
            "connection_types": list(set(r["type"] for r in COMPATIBILITY_RULES))
        }
    }
    
    with open(COMPAT_FILE, "w", encoding="utf-8") as f:
        json.dump(compat_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Saved compatibility matrix to {COMPAT_FILE}")
    
    # Demo: Find compatible parts for a bionic joint
    print("\n[DEMO] Compatible parts for BIONIC-JOINT-001:")
    compatible = find_compatible_parts("BIONIC-JOINT-001", index)
    for comp in compatible:
        print(f"  - {comp['name']} ({comp['type']}: {comp['interface']})")
    
    # Demo: Assembly suggestion
    print("\n[DEMO] Assembly suggestion for [BIONIC-JOINT-001, BIONIC-ACTUATOR-001]:")
    suggestions = generate_assembly_suggestions(["BIONIC-JOINT-001", "BIONIC-ACTUATOR-001"], index)
    for s in suggestions:
        print(f"  + Add {s['name']} -> {s['connection_type']} {s['connects_to']}")
    
    # Print statistics
    print("\n[STATS]")
    print(f"  Connection types: {compat_data['statistics']['connection_types']}")
    print(f"  Unique parts in matrix: {compat_data['statistics']['unique_parts']}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
