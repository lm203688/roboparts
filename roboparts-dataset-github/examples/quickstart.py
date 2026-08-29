"""
RoboParts Dataset — Quick Start Examples
=========================================
Python examples for working with the RoboParts structured dataset.

Dataset: https://github.com/roboparts/roboparts-dataset
Website: https://roboparts.cc
"""

import json
from pathlib import Path

# Load the dataset
DATA_PATH = Path(__file__).parent.parent / "data" / "roboparts_full.json"

with open(DATA_PATH, "r", encoding="utf-8") as f:
    DB = json.load(f)

print(f"Loaded {sum(len(v) for v in DB.values())} entities across {len(DB)} categories\n")


# ── Example 1: List all actuator manufacturers ──────────────────────────────
def list_actuator_manufacturers():
    """Get unique manufacturers from actuators."""
    mfrs = {a.get("manufacturer", "Unknown") for a in DB.get("actuators", [])}
    print("Actuator Manufacturers:")
    for m in sorted(mfrs):
        print(f"  - {m}")
    print()


# ── Example 2: Find high-torque actuators for humanoid joints ───────────────
def find_high_torque_actuators(min_torque_nm: float = 80.0):
    """Find actuators suitable for knee/hip joints (torque > threshold)."""
    results = []
    for a in DB.get("actuators", []):
        specs = a.get("specs", {})
        torque_str = specs.get("额定扭矩", specs.get("最大扭矩", "0"))
        # Extract numeric value from strings like "120Nm" or "85 Nm"
        import re
        match = re.search(r"[\d.]+", str(torque_str))
        if match:
            torque = float(match.group())
            if torque >= min_torque_nm:
                results.append({
                    "name": a["name"],
                    "manufacturer": a.get("manufacturer", "N/A"),
                    "torque": torque,
                    "price": specs.get("价格区间", "N/A"),
                    "protocol": specs.get("通信协议", "N/A"),
                })

    results.sort(key=lambda x: x["torque"], reverse=True)
    print(f"High-Torque Actuators (≥{min_torque_nm}Nm) — {len(results)} found:")
    for r in results[:10]:
        print(f"  {r['name']:30s} | {r['manufacturer']:15s} | {r['torque']:6.1f}Nm | {r['protocol']}")
    print()


# ── Example 3: Filter bionic / SEA actuators ────────────────────────────────
def find_bionic_actuators():
    """Find actuators with bionic features (SEA, series elastic, etc.)."""
    bionic = [
        a for a in DB.get("actuators", [])
        if a.get("bionic_features") and len(a["bionic_features"]) > 0
    ]
    print(f"Bionic Actuators — {len(bionic)} found:")
    for a in bionic[:10]:
        feats = ", ".join(a.get("bionic_features", []))
        print(f"  {a['name']:30s} | Features: {feats}")
    print()


# ── Example 4: Cross-reference protocols with chips ─────────────────────────
def protocol_chip_compatibility():
    """Find chips that support CAN FD protocol."""
    can_chips = []
    for chip in DB.get("chips", []):
        specs = chip.get("specs", {})
        interfaces = str(specs.get("接口", specs.get("外设接口", "")))
        if "CAN" in interfaces.upper():
            can_chips.append({
                "name": chip["name"],
                "manufacturer": chip.get("manufacturer", "N/A"),
                "interfaces": interfaces,
            })
    print(f"CAN/CAN-FD Capable Chips — {len(can_chips)} found:")
    for c in can_chips[:10]:
        print(f"  {c['name']:30s} | {c['manufacturer']:15s} | {c['interfaces']}")
    print()


# ── Example 5: ROS2-compatible platforms ────────────────────────────────────
def ros2_platforms():
    """List platforms with ROS2 support."""
    platforms = [
        p for p in DB.get("platforms", [])
        if p.get("specs", {}).get("ros2_compatible") == True
        or "ROS2" in str(p.get("specs", {}).get("支持框架", ""))
    ]
    print(f"ROS2-Compatible Platforms — {len(platforms)} found:")
    for p in platforms:
        specs = p.get("specs", {})
        print(f"  {p['name']:25s} | Type: {specs.get('类型', 'N/A'):15s} | Open Source: {specs.get('开源', 'N/A')}")
    print()


# ── Example 6: Sensor selection by type ─────────────────────────────────────
def sensors_by_type(sensor_type: str = "IMU"):
    """Find sensors by type (IMU, force, vision, etc.)."""
    matches = [
        s for s in DB.get("sensors", [])
        if sensor_type.lower() in str(s.get("specs", {}).get("类型", s.get("type", ""))).lower()
    ]
    print(f"{sensor_type} Sensors — {len(matches)} found:")
    for s in matches[:10]:
        specs = s.get("specs", {})
        print(f"  {s['name']:30s} | Range: {specs.get('量程', 'N/A'):15s} | Accuracy: {specs.get('精度', 'N/A')}")
    print()


# ── Example 7: Export simplified CSV ────────────────────────────────────────
def export_actuators_csv(output_path: str = "actuators_summary.csv"):
    """Export actuator summary to CSV for spreadsheet analysis."""
    import csv

    rows = []
    for a in DB.get("actuators", []):
        specs = a.get("specs", {})
        rows.append({
            "name": a["name"],
            "manufacturer": a.get("manufacturer", ""),
            "type": specs.get("类型", ""),
            "torque": specs.get("额定扭矩", ""),
            "voltage": specs.get("额定电压", ""),
            "protocol": specs.get("通信协议", ""),
            "weight": specs.get("重量", ""),
            "price": specs.get("价格区间", ""),
            "bionic": "Yes" if a.get("bionic_features") else "No",
            "ros2": "Yes" if a.get("ros2_compatible") else "No",
        })

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} actuators to {output_path}\n")


# ── Run all examples ────────────────────────────────────────────────────────
if __name__ == "__main__":
    list_actuator_manufacturers()
    find_high_torque_actuators(min_torque_nm=80.0)
    find_bionic_actuators()
    protocol_chip_compatibility()
    ros2_platforms()
    sensors_by_type("IMU")
    sensors_by_type("力")
    export_actuators_csv()
