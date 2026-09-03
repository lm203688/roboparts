#!/usr/bin/env python3
"""
Add bionic/biomimetic entities and 3D printing support
Core specialty: 仿生机械 (Bionic Mechanisms)
"""
import json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_FILE = os.path.join(ROOT, "api", "entities.json")

BIONIC_ENTITIES = [
    # === 仿生关节 ===
    {
        "id": "BIONIC-JOINT-001",
        "name": "球窝仿生关节",
        "name_en": "Ball-and-Socket Bionic Joint",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_joints",
        "manufacturer": "RoboParts",
        "type": "bionic_joint",
        "description": "仿人类肩关节/髋关节的球窝关节，3自由度，适用于仿人机器人上肢/下肢。",
        "biomimetic_target": "human_shoulder_hip",
        "dof": 3,
        "load_capacity": "50N",
        "range_of_motion": "360° rotation",
        "applications": ["humanoid_upper_limb", "humanoid_lower_limb", "prosthetics"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "dof": 3,
            "joint_type": "ball_and_socket",
            "load_capacity": "50N",
            "rotation_range": "360°",
            "friction_torque": "0.5 Nm",
            "materials": ["PEEK", "titanium_alloy", "carbon_fiber"]
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "flange",
            "standard": "ISO 9409-1",
            "flange": "64mm",
            "confidence": 0.8,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": True,
        "stl_files": [
            {"name": "ball_socket_housing", "url": "/3d/bionic_joint/ball_socket_housing.stl", "scale": "1:1"},
            {"name": "socket_insert", "url": "/3d/bionic_joint/socket_insert.stl", "scale": "1:1"}
        ],
        "print_settings": {
            "material": ["PETG", "ABS", "Nylon"],
            "infill": "40%",
            "layer_height": "0.15mm",
            "support": True,
            "print_time": "4.5 hours"
        },
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_ball_joint.step"},
            {"format": "STL", "url": "/cad/bionic_ball_joint.stl"}
        ],
        "compatibility": {
            "mounts_to": ["FRAME-001", "FRAME-002"],
            "connects_to": ["BIONIC-ACTUATOR-001"],
            "compatible_with": ["BIONIC-SENSOR-001"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    {
        "id": "BIONIC-JOINT-002",
        "name": "铰链仿生关节",
        "name_en": "Hinge Bionic Joint",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_joints",
        "manufacturer": "RoboParts",
        "type": "bionic_joint",
        "description": "仿人类膝关节/肘关节的铰链关节，1自由度，高负载，适用于仿人机器人膝/肘部。",
        "biomimetic_target": "human_knee_elbow",
        "dof": 1,
        "load_capacity": "200N",
        "range_of_motion": "0-135° flexion",
        "applications": ["humanoid_knee", "humanoid_elbow", "exoskeleton"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "dof": 1,
            "joint_type": "hinge",
            "load_capacity": "200N",
            "flexion_range": "0-135°",
            "locking_mechanism": "bi-stable",
            "materials": ["aluminum_alloy", "PEEK", "steel"]
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "flange",
            "standard": "ISO 9409-1",
            "flange": "80mm",
            "confidence": 0.8,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": True,
        "stl_files": [
            {"name": "hinge_housing", "url": "/3d/bionic_joint/hinge_housing.stl", "scale": "1:1"},
            {"name": "hinge_pin", "url": "/3d/bionic_joint/hinge_pin.stl", "scale": "1:1"}
        ],
        "print_settings": {
            "material": ["PETG", "ABS", "Nylon"],
            "infill": "50%",
            "layer_height": "0.15mm",
            "support": True,
            "print_time": "3.5 hours"
        },
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_hinge_joint.step"},
            {"format": "STL", "url": "/cad/bionic_hinge_joint.stl"}
        ],
        "compatibility": {
            "mounts_to": ["FRAME-001", "FRAME-002"],
            "connects_to": ["BIONIC-ACTUATOR-002"],
            "compatible_with": ["BIONIC-SENSOR-002"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    {
        "id": "BIONIC-JOINT-003",
        "name": "滑车仿生关节",
        "name_en": "Gliding Bionic Joint",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_joints",
        "manufacturer": "RoboParts",
        "type": "bionic_joint",
        "description": "仿人类指关节的滑车关节，2自由度，轻量化，适用于灵巧手指。",
        "biomimetic_target": "human_finger_knuckle",
        "dof": 2,
        "load_capacity": "20N",
        "range_of_motion": "0-90° flexion",
        "applications": ["dexterous_hand", "prosthetic_finger", "micro_manipulation"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "dof": 2,
            "joint_type": "gliding",
            "load_capacity": "20N",
            "flexion_range": "0-90°",
            "size": "15mm x 8mm x 6mm",
            "materials": ["titanium_alloy", "PEEK"]
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "press_fit",
            "standard": "custom",
            "flange": "8mm",
            "confidence": 0.7,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": True,
        "stl_files": [
            {"name": "gliding_joint", "url": "/3d/bionic_joint/gliding_joint.stl", "scale": "1:1"}
        ],
        "print_settings": {
            "material": ["Resin", "PEEK"],
            "infill": "100%",
            "layer_height": "0.05mm",
            "support": True,
            "print_time": "1.5 hours"
        },
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_gliding_joint.step"},
            {"format": "STL", "url": "/cad/bionic_gliding_joint.stl"}
        ],
        "compatibility": {
            "mounts_to": ["BIONIC-ACTUATOR-003"],
            "connects_to": ["TENDON-001"],
            "compatible_with": ["BIONIC-SENSOR-003"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    # === 仿生驱动器 ===
    {
        "id": "BIONIC-ACTUATOR-001",
        "name": "肌腱驱动仿生驱动器",
        "name_en": "Tendon-Driven Bionic Actuator",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_actuators",
        "manufacturer": "RoboParts",
        "type": "bionic_actuator",
        "description": "仿人体肌腱的柔性驱动器，通过缆绳传递力，适用于灵巧手和柔性关节。",
        "biomimetic_target": "human_tendon_muscle",
        "drive_type": "tendon",
        "force_output": "50N",
        "stroke": "30mm",
        "applications": ["dexterous_hand", "flexible_manipulator", "prosthetics"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "drive_type": "tendon",
            "force_output": "50N",
            "stroke": "30mm",
            "tension_sensing": True,
            "backdrivable": True,
            "materials": ["steel_cable", "PEEK_housing"]
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "flange",
            "standard": "custom",
            "flange": "40mm",
            "confidence": 0.7,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": True,
        "stl_files": [
            {"name": "tendon_actuator_housing", "url": "/3d/bionic_actuator/tendon_housing.stl", "scale": "1:1"}
        ],
        "print_settings": {
            "material": ["PETG", "Nylon"],
            "infill": "30%",
            "layer_height": "0.2mm",
            "support": True,
            "print_time": "2.5 hours"
        },
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_tendon_actuator.step"}
        ],
        "compatibility": {
            "mounts_to": ["BIONIC-JOINT-001", "BIONIC-JOINT-003"],
            "connects_to": ["CTRL-001"],
            "compatible_with": ["TENDON-001"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    {
        "id": "BIONIC-ACTUATOR-002",
        "name": "人工肌肉驱动器",
        "name_en": "Artificial Muscle Actuator",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_actuators",
        "manufacturer": "RoboParts",
        "type": "bionic_actuator",
        "description": "仿骨骼肌的人工肌肉驱动器，高功率密度，适用于仿人机器人全身。",
        "biomimetic_target": "human_skeletal_muscle",
        "drive_type": "artificial_muscle",
        "force_output": "100N",
        "contraction": "40%",
        "applications": ["humanoid_body", "exoskeleton", "rehabilitation"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "drive_type": "artificial_muscle",
            "force_output": "100N",
            "contraction_ratio": "40%",
            "response_time": "50ms",
            "power_density": "100W/kg",
            "materials": ["SMA_wire", "polymer_actuator"]
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "surface_mount",
            "standard": "custom",
            "confidence": 0.6,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": False,
        "print_settings": None,
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_artificial_muscle.step"}
        ],
        "compatibility": {
            "mounts_to": ["BIONIC-JOINT-001", "BIONIC-JOINT-002"],
            "connects_to": ["CTRL-001"],
            "compatible_with": ["BIONIC-SENSOR-001"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    # === 仿生传感器 ===
    {
        "id": "BIONIC-SENSOR-001",
        "name": "电子皮肤传感器",
        "name_en": "Electronic Skin Sensor",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_sensors",
        "manufacturer": "RoboParts",
        "type": "bionic_sensor",
        "description": "仿人类皮肤的多模态传感器，集成触觉、温度、压力感知，适用于机器人全身覆盖。",
        "biomimetic_target": "human_skin",
        "sensing_modalities": ["tactile", "temperature", "pressure"],
        "spatial_resolution": "1mm",
        "applications": ["humanoid_skin", "prosthetic_sensory", "collaborative_robot"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "sensing_modalities": ["tactile", "temperature", "pressure"],
            "spatial_resolution": "1mm",
            "response_time": "10ms",
            "flexible": True,
            "stretchable": True,
            "materials": ["conductive_polymer", "silicone_elastomer"]
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "adhesive",
            "standard": "custom",
            "confidence": 0.7,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": False,
        "print_settings": None,
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_eskin.step"}
        ],
        "compatibility": {
            "mounts_to": ["BIONIC-JOINT-001", "BIONIC-JOINT-002", "BIONIC-JOINT-003"],
            "connects_to": ["CTRL-001"],
            "compatible_with": ["BIONIC-ACTUATOR-001", "BIONIC-ACTUATOR-002"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    {
        "id": "BIONIC-SENSOR-002",
        "name": "仿生本体感觉传感器",
        "name_en": "Bionic Proprioception Sensor",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_sensors",
        "manufacturer": "RoboParts",
        "type": "bionic_sensor",
        "description": "仿人体关节感受器的位置/力传感器，集成于关节内部，提供本体感觉。",
        "biomimetic_target": "human_proprioceptor",
        "sensing_modalities": ["position", "force", "velocity"],
        "applications": ["joint_control", "force_feedback", "balance_control"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "sensing_modalities": ["position", "force", "velocity"],
            "accuracy": "0.1°",
            "force_resolution": "0.1N",
            "integrated": True,
            "miniaturized": True
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "integrated",
            "standard": "custom",
            "confidence": 0.7,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": False,
        "print_settings": None,
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_proprioceptor.step"}
        ],
        "compatibility": {
            "mounts_to": ["BIONIC-JOINT-001", "BIONIC-JOINT-002", "BIONIC-JOINT-003"],
            "connects_to": ["CTRL-001"],
            "compatible_with": ["BIONIC-ACTUATOR-001", "BIONIC-ACTUATOR-002"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    # === 仿生结构件 ===
    {
        "id": "BIONIC-FRAME-001",
        "name": "仿生骨骼框架",
        "name_en": "Bionic Skeleton Frame",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_structures",
        "manufacturer": "RoboParts",
        "type": "bionic_frame",
        "description": "仿人类骨骼的轻量化框架，拓扑优化设计，适用于仿人机器人躯干。",
        "biomimetic_target": "human_skeleton",
        "material": "carbon_fiber_composite",
        "weight": "2.5kg",
        "load_capacity": "500N",
        "applications": ["humanoid_torso", "robot_frame", "exoskeleton"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "material": "carbon_fiber_composite",
            "weight": "2.5kg",
            "load_capacity": "500N",
            "design_method": "topology_optimization",
            "biomimetic_accuracy": "85%"
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "flange",
            "standard": "ISO 9409-1",
            "flange": "120mm",
            "confidence": 0.8,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": True,
        "stl_files": [
            {"name": "torso_frame", "url": "/3d/bionic_frame/torso_frame.stl", "scale": "1:1"}
        ],
        "print_settings": {
            "material": ["Carbon_Fiber_Nylon", "PETG"],
            "infill": "60%",
            "layer_height": "0.2mm",
            "support": True,
            "print_time": "12 hours"
        },
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_skeleton_frame.step"}
        ],
        "compatibility": {
            "mounts_to": ["BIONIC-JOINT-001", "BIONIC-JOINT-002"],
            "connects_to": ["BIONIC-ACTUATOR-001", "BIONIC-ACTUATOR-002"],
            "compatible_with": ["BIONIC-SENSOR-001", "BIONIC-SENSOR-002"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    {
        "id": "BIONIC-SKIN-001",
        "name": "仿生皮肤覆盖层",
        "name_en": "Bionic Skin Cover",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_skin",
        "manufacturer": "RoboParts",
        "type": "bionic_skin",
        "description": "仿人类皮肤的柔性覆盖层，集成传感器，提供触觉反馈和外观仿真。",
        "biomimetic_target": "human_skin_appearance",
        "material": "silicone_elastomer",
        "thickness": "2mm",
        "applications": ["humanoid_appearance", "prosthetic_cover", "social_robot"],
        "source": "RoboParts bionic design library",
        "source_tier": "C",
        "confidence": 0.6,
        "specs": {
            "material": "silicone_elastomer",
            "thickness": "2mm",
            "color_options": ["skin_tone_1", "skin_tone_2", "skin_tone_3"],
            "stretchable": True,
            "sensor_integrated": True
        },
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "adhesive",
            "standard": "custom",
            "confidence": 0.7,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "3d_printable": False,
        "print_settings": None,
        "cad_files": [
            {"format": "STEP", "url": "/cad/bionic_skin_cover.step"}
        ],
        "compatibility": {
            "mounts_to": ["BIONIC-FRAME-001"],
            "connects_to": ["BIONIC-SENSOR-001"],
            "compatible_with": ["BIONIC-JOINT-001", "BIONIC-JOINT-002"]
        },
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial"
    },
    # === 真实肌纤维人形手（竞品差异化情报：公开领先者）===
    {
        "id": "BIONIC-HAND-001",
        "rp_id": "RP-BIO-0010",
        "name": "Clone Hand",
        "name_en": "Clone Hand (myofiber anthropomorphic hand)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Clone Robotics",
        "type": "bionic_hand",
        "description": "肌纤维驱动仿人灵巧手：37 根 McKibben Myofiber 水驱人工肌肉、24 DOF，单指负载约 7kg，650k 次作动寿命，Neural Joint V2 神经网络关节控制器。公开资料未声明任何机械接口标准（腱锚点 / 肌挂载点 / 软套接口 / 带供电法兰通信均无 ISO）。",
        "biomimetic_target": "human_hand_myofiber",
        "dof": 24,
        "actuators": 37,
        "load_capacity": "7kg per finger (vendor-stated)",
        "cycle_life": "650000 actuation cycles (vendor-stated)",
        "controller": "Neural Joint V2 (neural-network joint controller)",
        "actuation_type": "hydraulic_mckibben_muscle",
        "applications": ["humanoid_hand", "android", "prosthetics_research"],
        "source": "Clone Robotics 官方产品页（公开厂商声明）",
        "source_url": "https://www.clonerobotics.com/hand",
        "source_tier": "A",
        "confidence": 0.7,
        "confidence_basis": "vendor_public_claims_unverified_independent",
        "mechanical_interface": {
            "status": "n_a",
            "note": "no public ISO standard for tendon_anchor_pattern / muscle_mount_pattern / soft_socket / powered_flange_comms; all proprietary, unstandardized"
        },
        "bionic_interface": {
            "actuation_type": "hydraulic_mckibben_muscle",
            "tendon_anchor_pattern": "proprietary_unnamed (non-standard, no ISO)",
            "muscle_mount_pattern": "integrated_proprietary",
            "soft_socket": "silicone_skin_socket_proprietary",
            "powered_flange_comms": "proprietary (no standard)"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "vendor_official_product_page",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    },
    # === 真实开源腱驱人形手（标准法兰 + 非标准腱锚，差异化样本）===
    {
        "id": "BIONIC-HAND-002",
        "rp_id": "RP-BIO-0011",
        "name": "Yeah Robotic Hand (formerly Rebelia)",
        "name_en": "Yeah Robotic Hand (formerly Rebelia)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Vittorio Lumare (Yeah Robotics) / Public Invention",
        "type": "bionic_hand",
        "description": "低成本开源腱驱灵巧手：5 个 WaveShare ST3215HS 伺服 + 腱绳（Hercules 8 股 0.75mm）屈伸，15 DOF，单指扭矩 20 kg·cm，指根扭矩传感。挂载声明 ISO 9409-1-50-4-M6（UR3 同款法兰），但腱锚点布局为自有开源设计（非标准）；硅胶指垫（Dragon Skin）。CERN-OHL-S-2.0，V1 已 OSHWA 认证。",
        "biomimetic_target": "human_hand_tendon",
        "dof": 15,
        "actuators": 5,
        "torque_per_finger": "20 kg*cm (vendor-stated)",
        "sensors": ["torque_per_finger"],
        "applications": ["humanoid_hand", "manipulator", "prosthetic_transradial", "research"],
        "source": "Hackaday.io 开源项目页（含 BOM / 装配说明）",
        "source_url": "https://hackaday.io/project/204373-rebelia-robotic-hand",
        "source_tier": "B",
        "confidence": 0.6,
        "confidence_basis": "community_open_source_project_bom",
        "mechanical_interface": {
            "status": "declared",
            "mount_type": "flange",
            "standard": "ISO 9409-1",
            "flange": "50mm",
            "confidence": 0.8,
            "registry_ref": "/api/mechanical_interfaces.json"
        },
        "bionic_interface": {
            "actuation_type": "servo_tendon_driven",
            "tendon_anchor_pattern": "proprietary spool + M3 bolts (open-source, non-standard)",
            "muscle_mount_pattern": "servo-mounted spools (replaceable)",
            "soft_socket": "silicone finger pads (Dragon Skin 10)",
            "powered_flange_comms": "none (servo bus + external ESP32 driver board)"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "community_open_source_project",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    },
    # === 真实灵巧手（差异化情报：研究级 + 商业级 + 工业级样本）===
    {
        "id": "BIONIC-HAND-003",
        "rp_id": "RP-BIO-0012",
        "name": "Shadow Dexterous Hand",
        "name_en": "Shadow Dexterous Hand (research-grade anthropomorphic hand)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Shadow Robot Company",
        "type": "bionic_hand",
        "description": "研究级仿人灵巧手：24 DOF（20 主动），腱驱（Shadow Air Muscle），5 指，指端标配压力触觉。重 4.3kg，标称负载 5kg，被视为灵巧手领域黄金基准。腕部为厂商专有接口，无 ISO 法兰声明；腱锚点/肌挂载/软套/带供电通信均无开放标准。",
        "biomimetic_target": "human_hand_tendon",
        "dof": 24,
        "actuators": 20,
        "load_capacity": "5kg (vendor-stated)",
        "tactile_sensors": "pressure_tactile_per_fingertip",
        "weight": "4.3kg",
        "applications": ["research", "in_hand_manipulation", "humanoid_hand", "teleoperation"],
        "source": "Shadow Robot Company 官方产品页（公开厂商声明）",
        "source_url": "https://www.shadowrobot.com/dexterous-hand-series/",
        "source_tier": "A",
        "confidence": 0.7,
        "confidence_basis": "vendor_public_claims_unverified_independent",
        "mechanical_interface": {
            "status": "n_a",
            "note": "proprietary wrist mount; no ISO 9409-1; tendon_anchor_pattern / muscle_mount_pattern / soft_socket / powered_flange_comms all proprietary, unstandardized"
        },
        "bionic_interface": {
            "actuation_type": "tendon_driven",
            "tendon_anchor_pattern": "proprietary cable routing (non-standard, no ISO)",
            "muscle_mount_pattern": "forearm-mounted Shadow Air Muscle actuators",
            "soft_socket": "n/a (rigid fingers)",
            "powered_flange_comms": "n/a"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "vendor_official_product_page",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    },
    {
        "id": "BIONIC-HAND-004",
        "rp_id": "RP-BIO-0013",
        "name": "Psyonic Ability Hand",
        "name_en": "Psyonic Ability Hand (myoelectric bionic hand)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Psyonic",
        "type": "bionic_hand",
        "description": "肌电仿生手（原为假肢，后开放给机器人研究）：6 无刷直流电机、6 DOF，32 种抓取模式，功率抓取 66N，指端触压传感 + 振动触觉反馈（首个商售带触觉反馈的仿生手）。重约 490g，开放 API（BLE/I2C/UART/RS485）。残肢 EMG 解码驱动。腕部为残肢/专有接口，无 ISO 法兰。",
        "biomimetic_target": "human_hand_myoelectric",
        "dof": 6,
        "actuators": 6,
        "load_capacity": "79 lbs max (vendor-stated, ~36kg axial)",
        "grasp_force": "66N power grasp (vendor-stated)",
        "grip_patterns": 32,
        "tactile_sensors": "pressure_tactile_thumb_index_pinky",
        "weight": "490g",
        "applications": ["prosthetics", "humanoid_hand", "research", "teleoperation"],
        "source": "Psyonic 官方产品页（公开厂商声明）",
        "source_url": "https://www.psyonic.io/",
        "source_tier": "A",
        "confidence": 0.7,
        "confidence_basis": "vendor_public_claims_unverified_independent",
        "mechanical_interface": {
            "status": "n_a",
            "note": "prosthetic/robot wrist, no ISO 9409-1; mounts via proprietary quick-disconnect or short wrist option"
        },
        "bionic_interface": {
            "actuation_type": "brushless_dc_motor_myoelectric",
            "tendon_anchor_pattern": "n/a (direct-drive finger joints)",
            "muscle_mount_pattern": "n/a (EMG decoded to motor commands)",
            "soft_socket": "silicone overmolded fingertips (compliant, impact-tolerant)",
            "powered_flange_comms": "n/a (prosthetic wrist; BLE/I2C/UART/RS485 to host)"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "vendor_official_product_page",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    },
    {
        "id": "BIONIC-HAND-005",
        "rp_id": "RP-BIO-0014",
        "name": "Open Bionics Hero PRO",
        "name_en": "Open Bionics Hero PRO (myoelectric bionic hand)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Open Bionics",
        "type": "bionic_hand",
        "description": "肌电仿生手（假肢消费级）：多抓握模式、全无线、防水，2025-04 发布的 Hero RGD(Rugged)/Hero PRO 主打更快交付与耐用。残肢 EMG 驱动，定制 3D 打印接受腔。腕部为残肢专有接口，无 ISO 法兰；软套为定制硅胶接受腔。",
        "biomimetic_target": "human_hand_myoelectric",
        "dof": 6,
        "actuators": 6,
        "grip_patterns": "multi-grip (vendor-stated)",
        "ip_rating": "waterproof (vendor-stated)",
        "applications": ["prosthetics", "humanoid_hand", "research"],
        "source": "Open Bionics 官方产品页（公开厂商声明）",
        "source_url": "https://openbionics.com/",
        "source_tier": "A",
        "confidence": 0.65,
        "confidence_basis": "vendor_public_claims_unverified_independent",
        "mechanical_interface": {
            "status": "n_a",
            "note": "prosthetic wrist, no ISO 9409-1"
        },
        "bionic_interface": {
            "actuation_type": "brushless_dc_motor_myoelectric",
            "tendon_anchor_pattern": "n/a",
            "muscle_mount_pattern": "n/a (EMG electrodes on residual limb)",
            "soft_socket": "custom silicone socket liner (3D-printed)",
            "powered_flange_comms": "n/a (prosthetic wrist, wireless)"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "vendor_official_product_page",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    },
    {
        "id": "BIONIC-HAND-006",
        "rp_id": "RP-BIO-0015",
        "name": "Unitree Dex5",
        "name_en": "Unitree Dex5 (dexterous robot hand)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Unitree Robotics",
        "type": "bionic_hand",
        "description": "高自由度灵巧手：20 DOF（16 主动 + 4 被动），直驱 + 减速，94 个触觉传感器，可反向驱动。用于 Unitree 人形机器人（G1/H2 等），该生态采用 NVIDIA 栈（Cosmos/GR00T）。腕部为厂商专有总线，无 ISO 法兰。",
        "biomimetic_target": "human_hand_dexterous",
        "dof": 20,
        "actuators": 16,
        "tactile_sensors": "94 tactile sensors (vendor-stated)",
        "weight": "~1.0kg",
        "backdrivable": True,
        "applications": ["humanoid_hand", "dexterous_manipulation", "research"],
        "source": "Unitree 官方产品页（公开厂商声明）",
        "source_url": "https://www.unitree.com/",
        "source_tier": "A",
        "confidence": 0.7,
        "confidence_basis": "vendor_public_claims_unverified_independent",
        "mechanical_interface": {
            "status": "n_a",
            "note": "proprietary wrist bus, no ISO 9409-1"
        },
        "bionic_interface": {
            "actuation_type": "direct_drive_gear",
            "tendon_anchor_pattern": "n/a (integrated joint motors)",
            "muscle_mount_pattern": "n/a",
            "soft_socket": "n/a (rigid links; 94 tactile sensors)",
            "powered_flange_comms": "n/a (proprietary wrist bus)"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "vendor_official_product_page",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    },
    {
        "id": "BIONIC-HAND-007",
        "rp_id": "RP-BIO-0016",
        "name": "Inspire RH56 Series",
        "name_en": "Inspire RH56 Series (dexterous robot hand)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Inspire-Robots",
        "type": "bionic_hand",
        "description": "高性价比灵巧手：6 主动 DOF、12 关节，连杆/直线驱动，指端力控。2025 年出货约 10,000 台（按台数计为最大量供应商）。腕部为厂商专有接口，无 ISO 法兰。",
        "biomimetic_target": "human_hand_dexterous",
        "dof": 12,
        "actuators": 6,
        "grip_force": "4N (RH56BFX) / 10N (RH56DFX) (vendor-stated)",
        "weight": "540g",
        "applications": ["humanoid_hand", "dexterous_manipulation", "industrial"],
        "source": "Inspire-Robots 官方产品页（公开厂商声明）",
        "source_url": "https://www.inspire-robots.com/",
        "source_tier": "A",
        "confidence": 0.65,
        "confidence_basis": "vendor_public_claims_unverified_independent",
        "mechanical_interface": {
            "status": "n_a",
            "note": "proprietary wrist mount, no ISO 9409-1"
        },
        "bionic_interface": {
            "actuation_type": "linkage_linear",
            "tendon_anchor_pattern": "n/a",
            "muscle_mount_pattern": "n/a",
            "soft_socket": "n/a",
            "powered_flange_comms": "n/a (proprietary wrist bus)"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "vendor_official_product_page",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    },
    {
        "id": "BIONIC-HAND-008",
        "rp_id": "RP-BIO-0017",
        "name": "Allegro Hand",
        "name_en": "Allegro Hand (Wonik Robotics dexterous hand)",
        "category": "bionic_mechanisms",
        "subcategory": "bionic_hands",
        "manufacturer": "Wonik Robotics",
        "type": "bionic_hand",
        "description": "四指灵巧手：16 DOF，直驱电机，轻量（约 1.0kg），广泛用作机器人操作研究基准平台。腕部为厂商专有接口，无 ISO 法兰。",
        "biomimetic_target": "human_hand_dexterous",
        "dof": 16,
        "actuators": 16,
        "weight": "1.0kg",
        "applications": ["research", "dexterous_manipulation", "humanoid_hand"],
        "source": "Wonik Robotics 官方产品页（公开厂商声明）",
        "source_url": "https://www.wonikrobotics.com/allegro-hand",
        "source_tier": "A",
        "confidence": 0.65,
        "confidence_basis": "vendor_public_claims_unverified_independent",
        "mechanical_interface": {
            "status": "n_a",
            "note": "proprietary wrist mount, no ISO 9409-1"
        },
        "bionic_interface": {
            "actuation_type": "direct_drive",
            "tendon_anchor_pattern": "n/a",
            "muscle_mount_pattern": "n/a",
            "soft_socket": "n/a",
            "powered_flange_comms": "n/a (proprietary wrist bus)"
        },
        "compatibility": {"mounts_to": [], "connects_to": [], "compatible_with": []},
        "entity_kind": "component",
        "verified": False,
        "data_quality": "partial",
        "source_tier_basis": "vendor_official_product_page",
        "kind_basis": "category=bionic_mechanisms: bionic hand, physical hardware",
        "entity_kind_basis": "默认归类",
        "quarantine": False,
        "standard_conformance": {
            "assessed": False,
            "bus_class": "unknown",
            "ros2": None,
            "interop_stack_20262893": "unknown",
            "caee060_relevant": False,
            "interop_posture": "unknown",
            "iso22166_relevant": False
        }
    }
]


def main():
    print("[ADD-BIONIC] Adding bionic/biomimetic entities...")
    
    with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    existing_ids = {e["id"] for e in data["entities"]}
    added = 0
    
    for entity in BIONIC_ENTITIES:
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
        for entity in BIONIC_ENTITIES:
            if entity["id"] not in existing_ids:
                cat = entity["category"]
                if cat in data["meta"]["category_counts"]:
                    data["meta"]["category_counts"][cat] += 1
                else:
                    data["meta"]["category_counts"][cat] = 1
                    data["meta"]["categories"].append(cat)
        
        data["meta"]["updated"] = datetime.now().isoformat()
        
        with open(ENTITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[OK] Added {added} bionic entities. Total: {data['meta']['total_entities']}")
        print(f"[INFO] New category: bionic_mechanisms ({added} entities)")

        # 再生全部派生产物（语义索引/页面数字/数据集分发/技能清单/阴性兼容库）
        # —— 杜绝「加实体即崩 35 红」：真相源改了，派生副本必须同刻重生。
        try:
            import subprocess as _sp
            _regen = os.path.join(ROOT, "scripts", "regen_derived.py")
            _r = _sp.run([sys.executable, _regen], cwd=ROOT,
                         capture_output=True, text=True, timeout=600)
            for _ln in (_r.stdout or "").strip().splitlines()[-6:]:
                print("  [REGEN]", _ln)
            if _r.returncode != 0:
                print("  [WARN] 派生产物再生有步骤失败，提交前请跑 ci_gate/regression",
                      file=sys.stderr)
        except Exception as _ex:  # noqa: BLE001
            print(f"  [WARN] 无法调用 regen_derived.py: {_ex}", file=sys.stderr)
    else:
        print("\n[SKIP] No new entities to add")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
