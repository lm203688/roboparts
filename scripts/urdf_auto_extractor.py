#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URDF 事实抽取器（原名 URDF Auto-Extractor）。

── 20260915 重写：本脚本此前在**编造机械声明** ──
旧版 classify_flange_type() 的判据是关节数量：

    if revolute_count >= 6 and has_gripper:
        return "ISO 9409-1-50-4-M6 (6+ DOF arm with gripper)"
    elif revolute_count >= 5:
        return "ISO 9409-1-50-4-M6 (5+ DOF arm)"

随后 extract_mechanical_data() 把它写成机械声明状态（只要字符串里有 ISO 就记
为已声明），落进 ops/seed-bom.json。问题不是"不够准确"，而是**范畴错误**：
URDF 描述的是连杆几何与关节运动学，**不含任何法兰/孔位/节圆事实**。
同一管道的 build_flywheel_layer.mjs 开篇就写着「URDF 不含机械接口事实，故
mechanical_interface 一律留空（不编造）」——抽取器违反了管道自己的成文纪律，
而它又是 orchestrator collection 阶段每小时被调用的脚本。

后果：唯一能把 P0 机械声明率抬起来的通道之一，是一台**制造该数字的机器**。
一个 5 关节机械臂的 ISO 法兰是 A50 还是 A63，取决于厂商与型号，不取决于
它有几个关节；把"关节数 ≥ 5"写成 ISO 9409-1-50-4-M6，等于替厂商发布了
一个它从未声明的规格。

── 现在的职责边界 ──
  · 只抽取**可核实**的 URDF 事实：关节清单、类型、父子连杆、轴向。
  · 机械接口一律不产出（留空 + 显式 gap 说明），把缺口写成可查询的"未声明"。
  · 产出物落 ops/urdf_candidates.json —— **不再写入 ops/seed-bom.json**。
    seed-bom.json 是人工/社区 BOM 提交入口（模板 + 审核流），抓取器往里写
    正是"机器产物看起来像人提交"的成因。候选与提交必须物理分离。
  · 任何 declared 授权的唯一来源是 scripts/mech_evidence_contract.json 的判据，
    由 scripts/mech_evidence.mjs 执行；本脚本无权自授。
"""
import os
import sys
import json
import xml.etree.ElementTree as ET
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "ops", "urdf_candidates.json")

# 公开 URDF 源（按需下载）。这些是**事实来源**，不是机械接口来源。
URDF_SOURCES = [
    {"name": "UR5e", "url": "https://raw.githubusercontent.com/UniversalRobots/Universal_Robots_ROS_Description/kinetic/ur_description/urdf/ur5.urdf.xacro", "type": "xacro"},
    {"name": "Franka FR3", "url": "https://raw.githubusercontent.com/franka_emika/franka_ros/main/franka_description/robots/fr3/fr3.urdf.xacro", "type": "xacro"},
    {"name": "Kinova Gen3", "url": "https://raw.githubusercontent.com/Kinovarobotics/kinova-ros/master/kinova_description/robots/gen3.urdf.xacro", "type": "xacro"},
    {"name": "Trossen ViperX", "url": "https://raw.githubusercontent.com/Interbotix/interbotix_ros_manipulators/main/interbotix_xsarm_descriptions/urdf/viperx_660.urdf.xacro", "type": "xacro"},
    {"name": "Unitree Go2", "url": "https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/go2_description/urdf/go2.urdf", "type": "urdf"},
]

# 机械接口缺口的固定说明：措辞是给 agent 读的，必须明确"这是我们的缺口，
# 不是厂商没公开"，也不是"这个零件不需要"。
MECH_GAP = ('URDF 不含机械接口事实（无法兰节圆/孔数/螺纹/定位销），'
            '且本脚本不得由关节数量推断 ISO 编码；'
            '需厂商官方文档或人工/社区带出处提交方可声明')


def download_urdf(url, timeout=30):
    """下载 URDF 内容。失败返回 None（诚实记为未取到，不猜测）。"""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoboParts-Extractor/1.0"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def parse_urdf_joints(content):
    """抽取关节事实。xacro 需先展开，此处对 xacro 仅做尽力而为的 XML 解析。"""
    joints = []
    try:
        root = ET.fromstring(content)
        for joint in root.findall(".//joint"):
            name = joint.get("name", "unknown")
            jtype = joint.get("type", "unknown")
            parent = joint.find("parent")
            child = joint.find("child")
            axis = joint.find("axis")
            joints.append({
                "name": name,
                "type": jtype,
                "parent_link": parent.get("link", "") if parent is not None else "",
                "child_link": child.get("link", "") if child is not None else "",
                "axis": axis.get("xyz", "") if axis is not None else "",
            })
    except ET.ParseError:
        pass
    return joints


def extract_facts(name, url, content):
    """只产出可核实的 URDF 事实；机械接口显式留空。"""
    joints = parse_urdf_joints(content)
    if not joints:
        return None

    revolute = [j for j in joints if j["type"] in ("revolute", "continuous")]
    prismatic = [j for j in joints if j["type"] == "prismatic"]

    return {
        "entity_name": name,
        "source_type": "urdf",
        "source_url": url,
        "joint_count": len(joints),
        "revolute_joints": len(revolute),
        "prismatic_joints": len(prismatic),
        "joints": joints,
        # 机械接口：**不产出**。留空 + 显式 gap，供 agent 查询到明确缺口。
        "mechanical_interface": None,
        "mechanical_interface_gap": MECH_GAP,
        "retrieved_at": datetime.now().isoformat(timespec="seconds"),
    }


def main():
    print(f"[URDF-FACTS] {datetime.now().isoformat()}")

    results = []
    for source in URDF_SOURCES:
        print(f"  Downloading {source['name']}...")
        content = download_urdf(source["url"])
        if content is None:
            print("    SKIP: download failed")
            continue
        data = extract_facts(source["name"], source["url"], content)
        if data:
            results.append(data)
            print(f"    OK: {data['joint_count']} joints (mech interface: omitted by design)")
        else:
            print("    SKIP: parse failed")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "urdf_auto_extractor",
            "note": ("URDF 事实候选层。机械接口一律不产出（URDF 不含该事实）；"
                     "本文件不是 BOM 提交，不得直接合并进 entity 库 —— "
                     "任何声明须过 scripts/mech_evidence_contract.json 判据。"),
            "entries": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  抽取 {len(results)} 条 URDF 事实 → {os.path.relpath(OUT, ROOT)}")
    print("  机械接口声明产出 0 条（URDF 无此事实；不推断、不编造）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
