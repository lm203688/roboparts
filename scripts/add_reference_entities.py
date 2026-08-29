#!/usr/bin/env python3
"""
Add new entities from reference projects analysis
Adds: Prima1, DexHand021 Pro, NEO Hand, ProHand, ACE-ViDiHand, ZEST
"""
import json, os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_FILE = os.path.join(ROOT, "api", "entities.json")

NEW_ENTITIES = [
    {
        "id": "PRIMA1-HAND-001",
        "name": "Prima1 Dexterous Hand",
        "name_en": "Prima1 Dexterous Hand",
        "category": "grippers",
        "manufacturer": "Xynova",
        "type": "dexterous_hand",
        "description": "22-DoF robotic hand with tactile sensors and high-precision force control. Industrial-grade design for precision manipulation tasks. Showcased at WRC 2026 Beijing.",
        "applications": [
            "precision_manipulation",
            "industrial_assembly",
            "research",
            "humanoid_robotics"
        ],
        "source": "Xynova official announcement (2026-08-18)",
        "source_url": "https://nnets.ru/news/robotizirovannaja-kist-prima1-ot-xynova-poluchila-22-stepeni-svobody",
        "source_tier": "B",
        "confidence": 0.7,
        "confidence_basis": "press_release",
        "needs_provenance": True,
        "specs": {
            "dof": 22,
            "tactile_sensors": True,
            "force_control": True,
            "target_market": "industrial"
        },
        "mechanical_interface": {
            "status": "not_declared",
            "mount_type": "unknown",
            "standard": None,
            "flange": None,
            "confidence": 0,
            "registry_ref": "/api/mechanical_interfaces.json",
            "gap": "厂商未公开机械安装接口规格"
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False
        },
        "teleop_support": ["Isaac Teleop", "Spes Teleop"],
        "ai_frameworks": ["ACE-ViDiHand", "ZEST", "LeRobot"],
        "tactile_feedback": True,
        "force_control": True
    },
    {
        "id": "DEXHAND021PRO-001",
        "name": "DexHand021 Pro",
        "name_en": "DexHand021 Pro",
        "category": "grippers",
        "manufacturer": "DexRobot",
        "type": "dexterous_hand",
        "description": "Flagship dual-tendon driven dexterous hand with 22 DoF, 50N payload, full-palm multi-modal sensing, and 300K+ durability cycles. One-fifth the cost of comparable systems.",
        "applications": [
            "industrial_manipulation",
            "research",
            "humanoid_robotics"
        ],
        "source": "DexRobot Automate 2026 announcement",
        "source_url": "https://www.prnewswire.com/news-releases/dexrobot-unveils-full-dexterous-hand-series-and-new-dextele-teleoperation-system-at-automate-2026-302808579.html",
        "source_tier": "A",
        "confidence": 0.85,
        "confidence_basis": "official_press_release",
        "needs_provenance": False,
        "specs": {
            "dof": 22,
            "payload": "50N",
            "durability_cycles": 300000,
            "sensing": "full_palm_multi_modal",
            "drive_type": "dual_tendon"
        },
        "mechanical_interface": {
            "status": "not_declared",
            "mount_type": "unknown",
            "standard": None,
            "flange": None,
            "confidence": 0,
            "registry_ref": "/api/mechanical_interfaces.json",
            "gap": "厂商未公开机械安装接口规格"
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False
        },
        "teleop_support": ["DexTele"],
        "ai_frameworks": ["ACE-ViDiHand", "ZEST"],
        "tactile_feedback": True,
        "force_control": True
    },
    {
        "id": "NEO-HAND-001",
        "name": "NEO 25-DoF Hand",
        "name_en": "NEO 25-DoF Hand",
        "category": "grippers",
        "manufacturer": "1X Technologies",
        "type": "dexterous_hand",
        "description": "25-DoF tendon-driven hand for NEO humanoid. Near human-level dexterity with force transparency. IP68 waterproof, food-safe. 10K units/year production capacity.",
        "applications": [
            "humanoid_robotics",
            "household_tasks",
            "food_handling",
            "research"
        ],
        "source": "1X Technologies official announcement (2026-07-09)",
        "source_url": "https://www.1x.tech/discover/neos-hands",
        "source_tier": "A",
        "confidence": 0.9,
        "confidence_basis": "official_product_page",
        "needs_provenance": False,
        "specs": {
            "dof": 25,
            "dof_fingers_palm": 22,
            "dof_wrist": 3,
            "peak_torque_thumb": "3.5 Nm",
            "peak_torque_finger": "2.6 Nm",
            "wrist_torque": "17.75 Nm",
            "positioning_accuracy": "±0.2 mm",
            "ip_rating": "IP68",
            "food_safe": True,
            "production_capacity": "10000/year"
        },
        "mechanical_interface": {
            "status": "not_declared",
            "mount_type": "unknown",
            "standard": None,
            "flange": None,
            "confidence": 0,
            "registry_ref": "/api/mechanical_interfaces.json",
            "gap": "厂商未公开机械安装接口规格"
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False
        },
        "teleop_support": ["Isaac Teleop"],
        "ai_frameworks": ["ZEST", "GR00T"],
        "tactile_feedback": True,
        "force_control": True,
        "force_transparency": True
    },
    {
        "id": "PROHAND-001",
        "name": "ProHand 1.0",
        "name_en": "ProHand 1.0",
        "category": "grippers",
        "manufacturer": "Proception",
        "type": "dexterous_hand",
        "description": "22-DoF tendon-driven robotic hand with skin-like sensors. Includes ProGlove wearable for human hand data collection. Shipping June 2026.",
        "applications": [
            "research",
            "data_collection",
            "humanoid_robotics"
        ],
        "source": "Proception official announcement (2026-06)",
        "source_url": "https://www.proception.ai/news/introducing-prohand",
        "source_tier": "A",
        "confidence": 0.85,
        "confidence_basis": "official_product_page",
        "needs_provenance": False,
        "specs": {
            "dof": 22,
            "sensing": "skin_like_contact",
            "wearable_data_collection": True,
            "pro_glove": True
        },
        "mechanical_interface": {
            "status": "not_declared",
            "mount_type": "unknown",
            "standard": None,
            "flange": None,
            "confidence": 0,
            "registry_ref": "/api/mechanical_interfaces.json",
            "gap": "厂商未公开机械安装接口规格"
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False
        },
        "teleop_support": [],
        "ai_frameworks": ["LeRobot"],
        "tactile_feedback": True,
        "force_control": False,
        "wearable_data_collection": True
    },
    {
        "id": "ACE-VIDIHAND-001",
        "name": "ACE-ViDiHand",
        "name_en": "ACE-ViDiHand",
        "category": "data_acquisition",
        "manufacturer": "ACE ROBOTICS",
        "type": "hand_motion_capture",
        "description": "4D bimanual motion reconstruction from egocentric video using video diffusion model. #1 on ARCTIC, HOT3D, HOI4D benchmarks. 0.997 frame-level accuracy.",
        "applications": [
            "data_collection",
            "imitation_learning",
            "robotics_research"
        ],
        "source": "ACE ROBOTICS announcement (2026-07-13)",
        "source_url": "https://www.linkedin.com/posts/acerobotics_embodiedai-robotics-worldmodels-activity-7482290231291863040-GsQp",
        "source_tier": "B",
        "confidence": 0.75,
        "confidence_basis": "linkedin_post",
        "needs_provenance": True,
        "specs": {
            "frame_accuracy": 0.997,
            "benchmarks": ["ARCTIC", "HOT3D", "HOI4D"],
            "model_size": "1.3B",
            "input": "egocentric_video",
            "output": "4D_hand_motion"
        },
        "mechanical_interface": {
            "status": "not_applicable",
            "mount_type": "N/A",
            "standard": None,
            "flange": None,
            "confidence": 1.0,
            "registry_ref": "/api/mechanical_interfaces.json",
            "gap": "软件工具，无机械接口"
        },
        "entity_kind": "software",
        "verified": False,
        "data_quality": "partial",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False
        }
    },
    {
        "id": "ZEST-FRAMEWORK-001",
        "name": "ZEST Framework",
        "name_en": "ZEST: Zero-shot Embodied Skill Transfer",
        "category": "robot_ai_models",
        "manufacturer": "Boston Dynamics / ETH Zurich",
        "type": "whole_body_control",
        "description": "Zero-shot skill transfer framework for humanoid robots. Works with MoCap, video, and animation data. Deployed on Atlas, G1, Spot.",
        "applications": [
            "humanoid_control",
            "motion_imitation",
            "skill_transfer"
        ],
        "source": "arXiv:2602.00401 (2026-01-30)",
        "source_url": "https://arxiv.org/abs/2602.00401",
        "source_tier": "A",
        "confidence": 0.9,
        "confidence_basis": "peer_reviewed_paper",
        "needs_provenance": False,
        "specs": {
            "data_sources": ["MoCap", "video", "animation"],
            "platforms": ["Atlas", "G1", "Spot"],
            "training_time": "10 hours on L4 GPU",
            "zero_shot_deployment": True
        },
        "mechanical_interface": {
            "status": "not_applicable",
            "mount_type": "N/A",
            "standard": None,
            "flange": None,
            "confidence": 1.0,
            "registry_ref": "/api/mechanical_interfaces.json",
            "gap": "软件框架，无机械接口"
        },
        "entity_kind": "software",
        "verified": False,
        "data_quality": "partial",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False
        }
    }
]


def main():
    print("[ADD-ENTITIES] Adding reference project entities...")
    
    with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    existing_ids = {e["id"] for e in data["entities"]}
    added = 0
    
    for entity in NEW_ENTITIES:
        if entity["id"] not in existing_ids:
            data["entities"].append(entity)
            data["meta"]["total_entities"] += 1
            data["meta"]["total"] += 1
            added += 1
            print(f"  [ADDED] {entity['id']}: {entity['name']}")
        else:
            print(f"  [SKIP] {entity['id']} already exists")
    
    # Update category counts
    if added > 0:
        for entity in NEW_ENTITIES:
            if entity["id"] not in existing_ids:
                cat = entity["category"]
                if cat in data["meta"]["category_counts"]:
                    data["meta"]["category_counts"][cat] += 1
                else:
                    data["meta"]["category_counts"][cat] = 1
        
        data["meta"]["updated"] = datetime.now().isoformat()
        
        with open(ENTITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[OK] Added {added} entities. Total: {data['meta']['total_entities']}")
    else:
        print("\n[SKIP] No new entities to add")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
