// =============================================================================
// RoboParts · ROSRuntimeProfile 端点 (P2-3, 2026-10-27)
//
// 审计报告 § 9.3 P2-3 "ROSRuntimeProfile 与启动测试"
// 验收：参考构建在目标 ROS 2 环境实际启动，驱动/消息/QoS 可追。
//
// 三态诚实边界（本端点不越界）：
//   - validation_status = 'inferred_from_metadata' 是**当前唯一路径**：
//     基于 library.js 现有的 license / author / robot_type 生成推断，
//     不假装做过真实 ROS 2 环境测试。
//   - validated = false 默认；未来若有真跑 Docker + ros2 launch 的记录，
//     才允许改 'tested' 并附 evidence URL。
//   - evidence_gaps 字段**必须**显式登记"未实测"这一事实，
//     让调用方区分"知道没有测试"与"根本不知道"。
//
// 与 asset-class（L0-L4）的关系：
//   - asset_class 说"几何资产是什么等级"（仿真/视觉可用度）
//   - runtime_profile 说"运行时契约在什么等级"（ROS 2 启动/消息/QoS 可追度）
//   两套契约正交，独立评级。
//
// 契约版本：X-RoboParts-ProfileSchema: 1.0
// =============================================================================

// 注意：不 import cloudflare:workers —— 本函数只使用 onRequest*(context) 参数
// 拿 env，与 functions/api/urdf/library.js 等其他端点保持一致。
// 如果误 import { env, context } 会导致 Wrangler 部署期 SyntaxError：
// "The requested module 'cloudflare:workers' does not provide an export named 'context'"。

// 从 library.js 复用同一份预置 60 模型，避免 fallback 时数据不一致。
import { PRESET_URDF_MODELS } from "./library.js";

const PROFILE_SCHEMA_VERSION = "1.0";
const KV_MODELS_KEY = "urdf_models"; // 与 library.js 共用同一 KV key

// ROS 2 版本枚举（与 library.js 的 SIMULATION_COMPAT / getROS2Compat 对齐）
const SUPPORTED_DISTROS_BY_LEVEL = {
  full: ["humble", "jazzy", "iron"],   // 2022-2024 主线发行
  partial: ["humble"],                 // 保守只标已确认长期支持的
  community: ["humble"],               // 社区维护，只保最低
  unknown: [],                         // 空数组 = 明确"不承诺"，比空字符串诚实
};

// 按 robot_type 推断默认控制器列表（对齐 library.js getControllerCompat）
const CONTROLLERS_BY_ROBOT_TYPE = {
  humanoid: ["ros2_control", "joint_trajectory_controller", "whole_body_controller"],
  quadruped: ["ros2_control", "joint_trajectory_controller", "legged_locomotion"],
  arm: ["ros2_control", "joint_trajectory_controller", "moveit2_kinematics"],
  hand: ["ros2_control", "joint_trajectory_controller", "gripper_action"],
  gripper: ["ros2_control", "gripper_action"],
  amr: ["nav2", "ros2_control", "diff_drive_controller"],
};

// 按控制器类型推断 ROS 消息类型（三态诚实：只是"控制器通常订阅/发布什么"）
const MESSAGE_TYPES_BY_ROBOT_TYPE = {
  humanoid: ["control_msgs/JointTrajectoryControllerCommand", "geometry_msgs/WrenchStamped"],
  quadruped: ["control_msgs/JointTrajectoryControllerCommand", "std_msgs/Float32MultiArray"],
  arm: ["trajectory_msgs/JointTrajectory", "control_msgs/JointTrajectoryControllerCommand"],
  hand: ["trajectory_msgs/JointTrajectory", "control_msgs/SetCompressedDepthImageROI"],
  gripper: ["control_msgs/GripperCommand", "std_msgs/Float64"],
  amr: ["geometry_msgs/TwistStamped", "nav_msgs/Odometry", "sensor_msgs/Imu"],
};

// QoS 模板（三档：command / state / telemetry）
// 注意：QoS 是"建议值"，不是"实测值"，evidence_gaps 会标注。
const QOS_PROFILES = {
  command: {
    reliability: "RELIABLE",
    durability: "VOLATILE",
    history: "KEEP_LAST",
    depth: 10,
    note: "指令通道：丢包会导致动作中断，需要可靠性保证",
  },
  state: {
    reliability: "BEST_EFFORT",
    durability: "TRANSIENT_LOCAL",
    history: "KEEP_LAST",
    depth: 5,
    note: "状态通道：允许丢包，保留最后一帧给订阅者",
  },
  telemetry: {
    reliability: "BEST_EFFORT",
    durability: "VOLATILE",
    history: "KEEP_LAST",
    depth: 1,
    note: "遥测通道：实时优先，允许丢弃历史帧",
  },
};

// 已知有社区驱动包的机器人厂商（对齐 library.js knownBrands）
const DRIVER_PACKAGE_BY_AUTHOR = {
  "KUKA": "kuka_driver",
  "Universal Robots": "universal_robot_description + ur_robot_driver",
  "Universal Robots / Robotiq": "universal_robot_description + robotiq_gripper",
  "Franka Emika": "franka_description + franka_hardware",
  "Unitree Robotics": "unitree_description + unitree_sdk2",
  "ROBOTIS / Open Robotics": "dynamixel_driver + diffbot_description",
  "ROBOTIS": "dynamixel_driver + diffbot_description",
  "Willow Garage / Open Robotics": "pr2_description + pr2_mechanism_model",
};

function getROS2CompatFromLicense(license, author) {
  const lic = (license || "").toUpperCase();
  if (lic.includes("MIT") || lic.includes("APACHE") || lic.includes("BSD")) return "full";
  if (lic.includes("GPL")) return "partial";
  if (lic.includes("PROPRIETARY") || lic.includes("CUSTOM")) {
    const knownBrands = ["Unitree", "ROBOTIS", "Franka", "Universal Robots", "Boston Dynamics", "Figure AI"];
    if (knownBrands.some((b) => (author || "").includes(b))) return "community";
    return "unknown";
  }
  return "unknown";
}

function buildRuntimeProfile(model) {
  const ros2Level = getROS2CompatFromLicense(model.license, model.author);
  const robotType = model.robot_type;
  const author = model.author || "";

  return {
    profile_schema_version: PROFILE_SCHEMA_VERSION,
    meta: {
      id: model.id,
      name: model.name,
      author: author,
      robot_type: robotType,
      license: model.license || "unknown",
    },
    ros2: {
      compat_level: ros2Level,
      supported_distros: SUPPORTED_DISTROS_BY_LEVEL[ros2Level] || [],
      controllers: CONTROLLERS_BY_ROBOT_TYPE[robotType] || [],
      message_types: MESSAGE_TYPES_BY_ROBOT_TYPE[robotType] || [],
      driver_package: DRIVER_PACKAGE_BY_AUTHOR[author] || null,
      details:
        ros2Level === "full" ? "原生支持 ROS 2 Humble/Jazzy，许可证允许" :
        ros2Level === "partial" ? "部分支持（GPL 许可证），需社区适配包" :
        ros2Level === "community" ? "社区维护 ROS 2 适配包，非官方" :
        "无已知 ROS 2 支持路径，需自行验证",
    },
    qos: QOS_PROFILES,
    validated: false,
    validation_status: "inferred_from_metadata",
    validation_evidence: null,
    evidence_gaps: [
      "no_runtime_test_performed",
      "qos_inferred_from_controller_type",
      "driver_package_from_author_heuristic",
    ],
    honest_limits: {
      not_tested_in_docker: true,
      not_tested_on_real_hardware: true,
      schema_version: PROFILE_SCHEMA_VERSION,
    },
  };
}

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Content-Type": "application/json; charset=utf-8",
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const modelId = url.searchParams.get("id");

  // 数据源：从 KV 读整块 urdf_models 数组（与 library.js 同一 key），
  // 再从数组 find 目标 ID。KV 不可用/为空则 fallback 到 PRESET_URDF_MODELS
  // （复用 library.js 的同一份预置，保证"同 id 不同端点"给出同一模型）。
  let model = null;
  if (context.env.URDF_LIBRARY) {
    try {
      const raw = await context.env.URDF_LIBRARY.get(KV_MODELS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          model = parsed.find((m) => m.id === modelId) || null;
        }
      }
    } catch (e) { /* KV 读取失败视为无模型 */ }
  }
  // KV 无数据（或 KV 绑定缺失）→ fallback 到预置模型
  if (!model) {
    model = PRESET_URDF_MODELS.find((m) => m.id === modelId) || null;
  }

  // 单模型模式
  if (modelId) {
    if (!model) {
      return new Response(
        JSON.stringify({
          error: "model_not_found",
          id: modelId,
          hint: "Model ID not found. Try /api/urdf/library to list available IDs.",
          profile_schema_version: PROFILE_SCHEMA_VERSION,
        }, null, 2),
        { status: 404, headers: { ...corsHeaders, "X-RoboParts-ProfileSchema": PROFILE_SCHEMA_VERSION } }
      );
    }
    const profile = buildRuntimeProfile(model);
    return new Response(JSON.stringify(profile, null, 2), {
      status: 200,
      headers: {
        ...corsHeaders,
        "X-RoboParts-ProfileSchema": PROFILE_SCHEMA_VERSION,
        "X-Data-Version": "2026-10-27",
        "Cache-Control": "public, max-age=300",
      },
    });
  }

  // 批量模式：返回所有已知 profile（无 id 时）
  // 这里只生成一个"契约样例"，不批量枚举——避免让下游误以为所有 URDF 都有 profile
  return new Response(
    JSON.stringify({
      profile_schema_version: PROFILE_SCHEMA_VERSION,
      meta: {
        endpoint: "/api/urdf/runtime-profile",
        requires_id_param: true,
        description: "Query a specific model's ROS 2 runtime profile. Pass ?id=URDF-XXX.",
      },
      schema_summary: {
        profile_schema_version: PROFILE_SCHEMA_VERSION,
        fields: [
          "meta (id, name, author, robot_type, license)",
          "ros2 (compat_level, supported_distros, controllers, message_types, driver_package, details)",
          "qos (command, state, telemetry — 建议值，非实测)",
          "validated (boolean, currently always false)",
          "validation_status (inferred_from_metadata | community_verified | tested)",
          "evidence_gaps (explicit list of what was NOT done)",
          "honest_limits (schema_version + not_tested flags)",
        ],
        honest_boundary: "当前唯一路径 inferred_from_metadata；不声称做过 Docker 或真机测试。",
      },
    }, null, 2),
    {
      status: 200,
      headers: {
        ...corsHeaders,
        "X-RoboParts-ProfileSchema": PROFILE_SCHEMA_VERSION,
        "X-Data-Version": "2026-10-27",
        "Cache-Control": "public, max-age=600",
      },
    }
  );
}

export async function onRequestHead(context) {
  return new Response(null, {
    status: 200,
    headers: {
      ...corsHeaders,
      "X-RoboParts-ProfileSchema": PROFILE_SCHEMA_VERSION,
      "X-Data-Version": "2026-10-27",
    },
  });
}
