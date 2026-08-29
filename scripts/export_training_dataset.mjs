/**
 * RoboParts → 物理 AI 训练数据底座导出器（v2 · 多模态扩展）
 * ─────────────────────────────────────────────────────────────────────────
 * 目的：把 RoboParts 的兼容性数据层，打包成「物理 AI 训练流水线（MoziSim / NVIDIA
 *       Isaac / 自研仿真器 / TurboVLA 类 V+L→A 策略）可直接消费」的结构化数据集。
 *
 * 三件套（单一真相源，无手写数字）：
 *   1. components          —— 零件目录 + 标准标签 + 多模态暴露(force/tactile/geometric/electrical/vision)
 *   2. compatibility_edges —— 用 compat_engine.judgePair 现算的**有证据**兼容性关系
 *                               + 物理交互类型(interaction_type) + 力觉剖面(force_profile)
 *   3. standards           —— 互操作性标准登记表（来自 entities.json meta）
 *
 * v2 扩展（参考 TurboVLA 的双向跨模态融合架构，arXiv:2607.27205）：
 *   - meta.modalities：定义 5 类模态，并诚实标注 RoboParts 平台「是否提供原始传感流」。
 *   - component.modality_details：每个零件暴露哪些模态、力/触觉相关**真实声明**参数。
 *   - edge.interaction_type / force_profile：让力觉策略知道该边对应"法兰拧紧扭矩 /
 *     接插件插拔力 / 信号耦合"，从 RoboParts 的几何/力先验推导，不编造原始传感。
 *
 * 诚实边界（沿用 L1 系列纪律）：
 *   - 原始触觉/力觉**传感时序**本平台为零。tactile/force 模态只承载「厂商声明级 /
 *     类别级」参数（torque/weight/bionic_features/material_note/data_modalities）。
 *   - 未声明的维度/模态一律标 declared:false / not_provided，绝不填默认值伪装成数据。
 *   - 兼容性判定仍复用 functions/_lib/compat_engine.js 的 judgePair，禁止另写一套。
 *
 * 用法：node scripts/export_training_dataset.mjs
 * 输出：api/training_dataset.json（静态资源，Pages 直接 serve）
 */
import { readFileSync, writeFileSync, statSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { judgePair, parseVoltageRange } from '../functions/_lib/compat_engine.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const entitiesPath = join(root, 'api', 'entities.json');
const outPath = join(root, 'api', 'training_dataset.json');

const raw = JSON.parse(readFileSync(entitiesPath, 'utf8'));
const entities = raw.entities || raw.data || [];
const metaStandards =
  (raw.meta && raw.meta.standard_conformance_spec && raw.meta.standard_conformance_spec.standards) || [];

/** 只有 entity_kind=component（含缺字段老数据）才是「有物理接口的实物零件」。 */
function isComponent(e) {
  return !e.entity_kind || e.entity_kind === 'component';
}
/** 可进训练目录与边的零件：实物 + 未隔离。 */
function isSelectable(e) {
  return isComponent(e) && e.quarantine !== true;
}

// ── 力/触觉参数解析（只在能解析时给数字，否则 null）─────────────────────────
function parseTorqueNm(s) {
  if (!s) return null;
  const m = String(s).match(/([\d.]+)\s*Nm/i);
  return m ? parseFloat(m[1]) : null;
}
function parseWeightKg(s) {
  if (!s) return null;
  const m = String(s).match(/([\d.]+)\s*(g|kg)/i);
  if (!m) return null;
  const v = parseFloat(m[1]);
  return m[2].toLowerCase() === 'g' ? v / 1000 : v;
}
/** 从 bionic_features 文本里抠「力控精度±0.5Nm」这类声明级力控精度。 */
function parseForceControlPrecisionNm(arr) {
  if (!Array.isArray(arr)) return null;
  for (const t of arr) {
    const m = String(t).match(/力控精度[±]?\s*([\d.]+)\s*Nm/i);
    if (m) return parseFloat(m[1]);
  }
  return null;
}

// ── 模态暴露判定（复用真实声明字段，不编造）────────────────────────────────
const TACTILE_MODALITY_TOKENS = ['tactile', 'touch', 'haptic_feedback', 'grasp_force', 'force_torque'];
const VISION_MODALITY_TOKENS = [
  'vision', 'rgb', 'rgb_d', 'depth', 'stereo_rgb', '3d_position', 'pose', 'rigid_body_pose',
  'skeleton', 'hand_pose', 'head_pose', 'fingertip_pose', 'gripper_pose', 'body_pose',
  'joint_angle', 'finger_joints', 'hand_joint_angle', 'body_joint_angle', 'base_odometry',
  'imu', 'human_demonstration', 'whole_body_action', 'state', 'action',
];

function hasToken(list, tokens) {
  if (!Array.isArray(list)) return false;
  return list.some((x) => tokens.includes(String(x).toLowerCase()));
}

function modalityExposure(e) {
  const dm = Array.isArray(e.data_modalities) ? e.data_modalities : [];
  const mi = e.mechanical_interface;
  const miIdentity =
    mi && typeof mi === 'object'
      ? [...(mi.standard ? [mi.standard] : []), ...(mi.flange ? [mi.flange] : [])]
          .filter(Boolean).length > 0 || (mi.tool_side || mi.tool_side_flange)
      : false;

  const force = {
    declared: !!(e.torque || e.weight || (e.bionic_features && e.bionic_features.length) || hasToken(dm, ['force_torque', 'grasp_force'])),
    torque_nm: parseTorqueNm(e.torque),
    weight_kg: parseWeightKg(e.weight),
    force_control_precision_nm: parseForceControlPrecisionNm(e.bionic_features),
    basis: [],
  };
  if (e.torque) force.basis.push('torque');
  if (e.weight) force.basis.push('weight');
  if (e.bionic_features && e.bionic_features.length) force.basis.push('bionic_features');
  if (hasToken(dm, ['force_torque', 'grasp_force'])) force.basis.push('data_modalities');

  const tactile = {
    declared: !!(
      hasToken(dm, TACTILE_MODALITY_TOKENS) ||
      e.material_note ||
      e.category === 'flexible_actuators' ||
      (e.bionic_features && e.bionic_features.length)
    ),
    basis: [],
    note: null,
  };
  if (hasToken(dm, TACTILE_MODALITY_TOKENS)) tactile.basis.push('data_modalities:' + dm.filter((x) => TACTILE_MODALITY_TOKENS.includes(String(x).toLowerCase())).join('/'));
  if (e.material_note) tactile.basis.push('material_note');
  if (e.category === 'flexible_actuators') tactile.basis.push('category:flexible_actuators');
  if (e.bionic_features && e.bionic_features.length) tactile.basis.push('bionic_features');
  tactile.note = '声明级/类别级触觉相关（软体柔顺性、表面材质、抓握力），无原始触觉传感时序';

  const geometric = {
    declared: !!(miIdentity || e.interface || e.flange || e.connector),
    identity: miIdentity ? (mi && typeof mi === 'object' ? [mi.standard, mi.flange, mi.tool_side, mi.tool_side_flange].filter(Boolean) : []) : [],
  };

  const voltage = parseVoltageRange(e.voltage);
  const electrical = {
    declared: !!(e.voltage || e.protocol || e.interface),
    voltage_range: voltage ? [voltage.min, voltage.max] : null,
    protocols: e.protocol ? [String(e.protocol)] : null,
  };

  const vision = {
    declared: hasToken(dm, VISION_MODALITY_TOKENS),
    note: hasToken(dm, VISION_MODALITY_TOKENS)
      ? '该零件/系统自带视觉/位姿观测模态（来自 data_modalities）'
      : 'RoboParts 平台不提供原始图像流，消费方须自备相机/RGB(-D)观测',
  };

  const exposed = [];
  if (geometric.declared) exposed.push('geometric');
  if (electrical.declared) exposed.push('electrical');
  if (force.declared) exposed.push('force');
  if (tactile.declared) exposed.push('tactile');
  if (vision.declared) exposed.push('vision');

  return { exposed, force, tactile, geometric, electrical, vision };
}

// ── 边的物理交互类型 + 力觉剖面（从 judgePair 已判定维度推导）──────────────
function interactionOf(r) {
  const decided = r.dimensions.filter((d) => d.compatible !== null).map((d) => d.dimension);
  const hasMech = decided.includes('mechanical');
  const hasElec = decided.includes('electrical');
  const hasProto = decided.includes('protocol');
  let type;
  if (hasMech && hasElec) type = 'rigid_join';
  else if (hasMech) type = 'flange_mount';
  else if (hasElec) type = 'connector_insert';
  else if (hasProto) type = 'bus_coupling';
  else type = 'unspecified';

  const profiles = {
    flange_mount: {
      force_senses: ['axial_load', 'bolt_torque'],
      guidance: '螺栓法兰对接：力觉策略应关注轴向载荷与拧紧扭矩；参考两侧 component.modality_details.force.torque_nm',
    },
    connector_insert: {
      force_senses: ['insertion_force', 'electrical_contact'],
      guidance: '接插件插拔：关注插入力与接触力；本平台无原始插拔力曲线，需传感采集补充',
    },
    rigid_join: {
      force_senses: ['axial_load', 'bolt_torque', 'insertion_force', 'electrical_contact'],
      guidance: '机械+电气双重约束的刚性连接：同时关注法兰拧紧扭矩与接插件插拔力',
    },
    bus_coupling: {
      force_senses: [],
      guidance: '信号级耦合（协议互通），无显著力学约束',
    },
    unspecified: { force_senses: [], guidance: '无已判定的物理约束维度' },
  };
  return { interaction_type: type, force_profile: profiles[type] };
}

// ── 1. components（v2：加 modality_details）───────────────────────────────
const components = entities.filter(isComponent).map((e) => {
  const mod = modalityExposure(e);
  return {
    id: e.id,
    name: e.name,
    name_en: e.name_en || null,
    category: e.category,
    entity_kind: e.entity_kind || null,
    manufacturer: e.manufacturer || null,
    type: e.type || null,
    specs: {
      torque: e.torque || null,
      speed: e.speed || null,
      weight: e.weight || null,
      voltage: e.voltage || null,
      protocol: e.protocol || null,
      interface: e.interface || null,
      position_resolution: e.position_resolution || null,
    },
    applications: Array.isArray(e.applications) ? e.applications : [],
    price_range: e.price_range || null,
    ros_support: typeof e.ros_support === 'boolean' ? e.ros_support : null,
    modalities: mod.exposed,
    modality_details: mod,
    evidence: {
      source_tier: e.source_tier || null,
      confidence: e.confidence || null,
      verified: e.verified === true,
      quarantine: e.quarantine === true,
      source_url: e.source_url || null,
    },
    standards: e.standard_conformance
      ? {
          caee060_relevant: !!e.standard_conformance.caee060_relevant,
          iso22166_relevant: !!e.standard_conformance.iso22166_relevant,
          bus_class: e.standard_conformance.bus_class || null,
          ros2: typeof e.standard_conformance.ros2 === 'boolean' ? e.standard_conformance.ros2 : null,
          interop_posture: e.standard_conformance.interop_posture || null,
        }
      : null,
  };
});

// ── 2. compatibility_edges（v2：加 interaction_type + force_profile）──────────
const selectable = entities.filter(isSelectable);
const edges = [];
let pairs = 0;
let decided = 0;
let compatible = 0;
let conflict = 0;
const t0 = Date.now();

for (let i = 0; i < selectable.length; i++) {
  for (let j = i + 1; j < selectable.length; j++) {
    pairs++;
    const r = judgePair(selectable[i], selectable[j]);
    if (!r.applicable) continue;
    if (r.decided_dimensions < 1) continue; // 剔除无信号噪声配对
    decided++;
    if (r.overall_compatible === true) compatible++;
    else if (r.overall_compatible === false) conflict++;
    const ix = interactionOf(r);
    edges.push({
      a: r.a.id,
      b: r.b.id,
      dimensions: r.dimensions,
      overall_compatible: r.overall_compatible,
      compatibility_score: r.compatibility_score,
      decided_dimensions: r.decided_dimensions,
      undecided_dimensions: r.undecided_dimensions,
      hard_dimensions_decided: r.hard_dimensions_decided,
      interaction_type: ix.interaction_type,
      force_profile: ix.force_profile,
      verdict_reason: r.verdict_reason,
      evidence_basis: r.evidence_basis,
    });
  }
}

// ── 3. 模态覆盖统计（诚实透出覆盖率，不编造）──────────────────────────────
function countDeclared(getter) {
  return components.filter(getter).length;
}
const modalityCoverage = {
  geometric: countDeclared((c) => c.modality_details.geometric.declared),
  electrical: countDeclared((c) => c.modality_details.electrical.declared),
  force: countDeclared((c) => c.modality_details.force.declared),
  tactile: countDeclared((c) => c.modality_details.tactile.declared),
  vision: countDeclared((c) => c.modality_details.vision.declared),
};
const forceWithNumeric = countDeclared((c) => c.modality_details.force.torque_nm != null || c.modality_details.force.weight_kg != null);

// ── 4. 组装 + 写盘 ────────────────────────────────────────────────────────
const out = {
  meta: {
    schema_version: '2.0',
    generated_at: new Date().toISOString(),
    generator: 'scripts/export_training_dataset.mjs',
    purpose: 'RoboParts 兼容性数据层 → 物理AI训练流水线（MoziSim / NVIDIA Isaac / TurboVLA 类 V+L→A 策略）可直接消费的结构化多模态数据底座',
    source: 'api/entities.json（single source of truth）',
    license: 'CC BY 4.0',
    honesty:
      '兼容性结论基于厂商公开声明字段的规则推断，非实测；未声明的维度记为无法判定，不计入证据。' +
      '本导出已剔除无证据的 undecided 配对，仅保留至少有 1 个维度有双方声明的兼容性关系。' +
      'v2 多模态扩展：force/tactile 模态仅承载「厂商声明级/类别级」参数（torque/weight/bionic_features/material_note/data_modalities），' +
      '原始触觉/力觉传感时序本平台为零，绝不编造。',
    modalities: {
      vision: {
        provided_by_roboparts: false,
        note: '本平台不提供原始图像/RGB(-D)流；仅当零件自身是视觉/位姿系统（data_modalities 含视觉类）时标记 exposed',
      },
      geometric: {
        provided_by_roboparts: true,
        source: 'mechanical_interface(standard/flange/tool_side) / interface / connector',
        note: '机械接口几何与孔位级互换真值（ISO 9409-1 等）',
      },
      electrical: {
        provided_by_roboparts: true,
        source: 'voltage / protocol / interface',
        note: '电压区间与通信协议互通判定',
      },
      force: {
        provided_by_roboparts: 'declared-only',
        source: 'torque / weight / bionic_features / data_modalities(force_torque,grasp_force)',
        note: '声明级力/扭矩/负载参数，非原始六维 F-T 时序；coverage 见 totals.modality_coverage',
      },
      tactile: {
        provided_by_roboparts: 'declared-only',
        source: 'data_modalities(tactile/touch/haptic_feedback/grasp_force) / category(flexible_actuators) / bionic_features / material_note',
        note: '声明级/类别级触觉相关（软体柔顺性、表面材质、抓握力），无原始触觉传感',
      },
    },
    totals: {
      entities_total: entities.length,
      components_total: components.length,
      selectable_components: selectable.length,
      pairs_evaluated: pairs,
      edges_decided: decided,
      edges_compatible: compatible,
      edges_conflict: conflict,
      modality_coverage: modalityCoverage,
      components_with_numeric_force: forceWithNumeric,
    },
    provenance: raw.meta?.provenance_coverage || null,
    data_quality: raw.meta?.data_quality || null,
    consumption: {
      direct_url: 'https://roboparts.cc/api/training_dataset.json',
      format: 'JSON（array-of-records）',
      notes:
        'components[].modalities 列出该零件暴露的模态类；modality_details 给出力/触觉/几何/电气的真实参数。' +
        'compatibility_edges[].interaction_type + force_profile 给出该兼容性关系的物理交互类型与力觉剖面，' +
        '供 TurboVLA 类策略在双向跨注意力融合中接入力觉/触觉编码器流时定位受力维度。' +
        'edge.a / edge.b 对应 components[].id。',
      extension_blueprint: 'docs/modality-extension-blueprint.md',
      collection_roadmap: 'docs/tactile-force-collection-roadmap.md',
    },
  },
  standards: metaStandards,
  components,
  compatibility_edges: edges,
};

writeFileSync(outPath, JSON.stringify(out, null, 2));

// ── 5. 收尾必须真调横切注入器（L1.55 教训）─────────────────────────────────
{
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const inj = spawnSync(py, [join(root, 'scripts', 'inject_api_access.py')], { cwd: root, encoding: 'utf8' });
  if (inj.status !== 0) {
    console.error('❌ meta.access 注入失败，导出视为失败（不许产出缺接入入口的对外 JSON）');
    console.error((inj.stderr || inj.stdout || '').trim().slice(0, 500));
    process.exit(1);
  }
}

const ms = Date.now() - t0;
console.log(
  `✅ v2 导出完成：${outPath}\n` +
    `   components=${components.length}  selectable=${selectable.length}  pairs=${pairs}\n` +
    `   edges(decided)=${decided}  compatible=${compatible}  conflict=${conflict}\n` +
    `   模态覆盖: geometric=${modalityCoverage.geometric} electrical=${modalityCoverage.electrical} ` +
    `force=${modalityCoverage.force}(数值${forceWithNumeric}) tactile=${modalityCoverage.tactile} vision=${modalityCoverage.vision}\n` +
    `   耗时 ${ms}ms  文件大小 ${(statSync(outPath).size / 1024).toFixed(0)} KB`
);
