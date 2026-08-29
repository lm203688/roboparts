#!/usr/bin/env python3
"""
URDF Auto-Extractor - parse public URDF/XACRO files
Extract mechanical interface data (joints, links, flanges)
Target: auto-populate mechanical declarations from open-source robots
"""
import os, sys, json, re, xml.etree.ElementTree as ET
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_BOM = os.path.join(ROOT, "ops", "seed-bom.json")
NEEDS_USER = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")

# Public URDF sources (downloaded on demand)
URDF_SOURCES = [
    {"name": "UR5e", "url": "https://raw.githubusercontent.com/UniversalRobots/Universal_Robots_ROS_Description/kinetic/ur_description/urdf/ur5.urdf.xacro", "type": "xacro"},
    {"name": "Franka FR3", "url": "https://raw.githubusercontent.com/franka_emika/franka_ros/main/franka_description/robots/fr3/fr3.urdf.xacro", "type": "xacro"},
    {"name": "Kinova Gen3", "url": "https://raw.githubusercontent.com/Kinovarobotics/kinova-ros/master/kinova_description/robots/gen3.urdf.xacro", "type": "xacro"},
    {"name": "Trossen ViperX", "url": "https://raw.githubusercontent.com/Interbotix/interbotix_ros_manipulators/main/interbotix_xsarm_descriptions/urdf/viperx_660.urdf.xacro", "type": "xacro"},
    {"name": "Unitree Go2", "url": "https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/go2_description/urdf/go2.urdf", "type": "urdf"},
]


def download_urdf(url, timeout=30):
    """Download URDF content from URL"""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoboParts-Extractor/1.0"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None


def parse_urdf_joints(content):
    """Extract joint info from URDF content"""
    joints = []
    try:
        root = ET.fromstring(content)
        for joint in root.findall(".//joint"):
            name = joint.get("name", "unknown")
            jtype = joint.get("type", "unknown")
            parent = joint.find("parent")
            child = joint.find("child")
            parent_link = parent.get("link", "") if parent is not None else ""
            child_link = child.get("link", "") if child is not None else ""

            joints.append({
                "name": name,
                "type": jtype,
                "parent_link": parent_link,
                "child_link": child_link,
            })
    except ET.ParseError:
        pass
    return joints


def classify_flange_type(joints):
    """Heuristic: detect if robot uses ISO 9409-1 flange based on joint structure"""
    revolute_count = sum(1 for j in joints if j["type"] in ["revolute", "continuous"])
    has_gripper = any("gripper" in j["name"].lower() or "hand" in j["name"].lower() for j in joints)

    if revolute_count >= 6 and has_gripper:
        return "ISO 9409-1-50-4-M6 (6+ DOF arm with gripper)"
    elif revolute_count >= 5:
        return "ISO 9409-1-50-4-M6 (5+ DOF arm)"
    elif revolute_count >= 3:
        return "unknown (lightweight arm)"
    elif any("leg" in j["name"].lower() or "hip" in j["name"].lower() for j in joints):
        return "proprietary (legged robot)"
    else:
        return "unknown"


def extract_mechanical_data(name, content):
    """Extract mechanical interface data from URDF"""
    joints = parse_urdf_joints(content)
    if not joints:
        return None

    flange = classify_flange_type(joints)
    revolute = [j for j in joints if j["type"] in ["revolute", "continuous"]]
    prismatic = [j for j in joints if j["type"] == "prismatic"]

    return {
        "entity_name": name,
        "source_type": "urdf",
        "joint_count": len(joints),
        "revolute_joints": len(revolute),
        "prismatic_joints": len(prismatic),
        "mechanical_interface": {
            "standard": flange,
            "status": "declared" if "ISO" in flange else "not_declared",
            "source_evidence": f"URDF joint analysis ({len(joints)} joints)",
        },
    }


def main():
    print(f"[URDF-EXTRACTOR] {datetime.now().isoformat()}")

    results = []
    for source in URDF_SOURCES:
        print(f"  Downloading {source['name']}...")
        content = download_urdf(source["url"])
        if content is None:
            print(f"    SKIP: download failed")
            continue

        data = extract_mechanical_data(source["name"], content)
        if data:
            data["source_url"] = source["url"]
            results.append(data)
            status = data["mechanical_interface"]["status"]
            print(f"    OK: {data['joint_count']} joints, flange={status}")
        else:
            print(f"    SKIP: parse failed")

    if results:
        existing = []
        if os.path.exists(SEED_BOM):
            with open(SEED_BOM, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing = existing_data.get("entries", [])

        existing_names = {e.get("entity_name") for e in existing}
        new_entries = [r for r in results if r["entity_name"] not in existing_names]

        all_entries = existing + new_entries
        with open(SEED_BOM, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "source": "urdf_auto_extractor",
                "entries": all_entries,
            }, f, ensure_ascii=False, indent=2)

        print(f"\n  Total entries: {len(all_entries)} ({len(new_entries)} new from URDF)")
    else:
        print("\n  No data extracted")

    return 0


if __name__ == "__main__":
    sys.exit(main())
