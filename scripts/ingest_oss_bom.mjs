#!/usr/bin/env node
/**
 * RoboParts OSS BOM/URDF 摄取器（link 维度）
 *
 * 与既有 scripts/ingest_oss.mjs 的关系：
 *   ingest_oss.mjs 走 <joint>（可动关节 = 执行器位点），本脚本走 <link>（连杆 = 候选零件），
 *   两者互补、互不覆盖。为避免污染既有 'urdf' 抽取器分组（regression.py 对该分组有
 *   ros_support 不变式断言），本脚本一律标 extractor='urdf_link'、ID 前缀 'OSS-BOM-'。
 *
 * 诚实性约束（本仓库既有准则，不可放宽）：
 *   1. URDF 的 link 只证明「上游模型里存在这个刚体」，**不证明**它是一个可采购零件，
 *      更不证明其电气能力。故 confidence='low'、declared=false、source_tier='C'。
 *   2. ros_support 一律不落字段（三态：undefined = 未声明）。URDF 出处另以
 *      ros_ecosystem_origin=true 如实记录 —— 出处 ≠ 能力。
 *   3. category 由名称/材质/网格文件名推断；推断不出就是 'unknown'，不做兜底猜测。
 *   4. price/weight/torque 等 URDF 里根本没有的量留空，不填「默认值」冒充数据。
 *
 * 用法：
 *   node scripts/ingest_oss_bom.mjs --dry-run --source sample   # 离线自检（不联网、不写盘）
 *   node scripts/ingest_oss_bom.mjs --dry-run                   # 拉取 SOURCES 全部源，仅预览
 *   node scripts/ingest_oss_bom.mjs --limit 50                  # 真实写入，最多新增 50 条
 *   node scripts/ingest_oss_bom.mjs --source https://raw.../x.urdf
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const OUT = path.join(ROOT, 'api', 'oss_components.json');
const SAMPLE = path.join(HERE, 'sample.urdf');

// ---------------------------------------------------------------- 目标源
// 均为已在 ingest_oss.mjs 中验证过可达的公开 raw URL。新增源照此结构追加即可。
const SOURCES = [
  {
    id: 'UNITREE_GO2',
    name: 'Unitree Go2 (四足)',
    license: 'Apache-2.0',
    repo: 'https://github.com/unitreerobotics/unitree_ros',
    robot_type: 'quadruped',
    url: 'https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/go2_description/urdf/go2_description.urdf',
  },
  {
    id: 'TIENKUNG',
    name: '天工 TienKung (开源人形)',
    license: 'Apache-2.0',
    repo: 'https://github.com/Open-X-Humanoid/TienKung_URDF',
    robot_type: 'humanoid',
    url: 'https://raw.githubusercontent.com/Open-X-Humanoid/TienKung_URDF/main/pro_urdf_publish/pro_urdf_publish/urdf/humanoid.urdf',
  },
];

// 离线夹具：证明「解析 + 归一化 + 合并」逻辑正确，不依赖网络即可复现。
const SAMPLE_SOURCE = {
  id: 'SAMPLE',
  name: 'sample.urdf (本地 dry-run 夹具)',
  license: 'N/A',
  repo: 'local',
  robot_type: 'unknown',
  url: 'file://scripts/sample.urdf',
  file: SAMPLE,
};

// ---------------------------------------------------------------- CLI
function parseArgs(argv) {
  const a = { dryRun: false, limit: Infinity, source: null };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--dry-run') a.dryRun = true;
    else if (t === '--limit') {
      const n = parseInt(argv[++i], 10);
      if (!Number.isFinite(n) || n < 0) throw new Error(`--limit 需要非负整数，收到: ${argv[i]}`);
      a.limit = n;
    } else if (t === '--source') {
      a.source = argv[++i];
      if (!a.source) throw new Error('--source 需要一个 URL、SOURCES 里的 id，或 "sample"');
    } else if (t === '--help' || t === '-h') a.help = true;
    else throw new Error(`未知参数: ${t}`);
  }
  return a;
}

function resolveSources(sel) {
  if (!sel) return SOURCES;
  if (sel === 'sample') return [SAMPLE_SOURCE];
  const byId = SOURCES.find(s => s.id === sel || s.id.toLowerCase() === sel.toLowerCase());
  if (byId) return [byId];
  if (/^https?:\/\//.test(sel)) {
    return [{ id: 'ADHOC', name: sel, license: '', repo: '', robot_type: 'unknown', url: sel }];
  }
  const p = path.resolve(process.cwd(), sel);
  if (fs.existsSync(p)) {
    return [{ id: 'LOCAL', name: path.basename(p), license: '', repo: '', robot_type: 'unknown',
      url: `file://${path.relative(ROOT, p).replace(/\\/g, '/')}`, file: p }];
  }
  throw new Error(`无法解析 --source "${sel}"：既不是 URL、已知 id，也不是存在的本地文件`);
}

// ---------------------------------------------------------------- URDF 解析
// 注：URDF 是 XML，此处用正则做保守抽取（与 ingest_oss.mjs 同口径，避免引入依赖）。
// 抽不到就少抽，绝不猜——解析器宽松化带来的假数据比漏数据更糟。

function stripComments(xml) {
  return xml.replace(/<!--[\s\S]*?-->/g, '');
}

/** 抽取所有 <link name="...">，连同其块内文本（材质名 / mesh 文件名用于类目推断）。 */
function extractLinks(xml) {
  const out = [];
  // 成对标签 <link name="x"> ... </link>
  for (const m of xml.matchAll(/<link\s+[^>]*name="([^"]+)"[^>]*>([\s\S]*?)<\/link>/g)) {
    out.push({ name: m[1], body: m[2] });
  }
  // 自闭合 <link name="x"/>
  for (const m of xml.matchAll(/<link\s+[^>]*name="([^"]+)"[^>]*\/>/g)) {
    out.push({ name: m[1], body: '' });
  }
  // 同名 link 只保留一次（URDF 内理论上唯一，实测有仓库重复引用）
  const seen = new Set();
  return out.filter(l => (seen.has(l.name) ? false : (seen.add(l.name), true)));
}

/** 抽取 <joint>，返回 child link -> {joint 名, 类型, parent} 的映射（连接关系）。 */
function extractJoints(xml) {
  const byChild = new Map();
  const joints = [];
  for (const m of xml.matchAll(/<joint\s+[^>]*name="([^"]+)"[^>]*>([\s\S]*?)<\/joint>/g)) {
    const [, jname, body] = m;
    const type = (/<joint\s+[^>]*type="([^"]+)"/.exec(m[0]) || [])[1] || '';
    const parent = (/<parent\s+link="([^"]+)"/.exec(body) || [])[1] || '';
    const child = (/<child\s+link="([^"]+)"/.exec(body) || [])[1] || '';
    joints.push({ jname, type, parent, child });
    if (child && !byChild.has(child)) byChild.set(child, { jname, type, parent });
  }
  return { byChild, joints };
}

// ---------------------------------------------------------------- 归一化
// 类目取 oss_components.json 现役取值集合（actuators/sensors/controllers/
// communication/structural/power），不引入 entities.json 那套 CANONICAL —— 两文件
// 词表本就不同，混用会让 /api/oss?stats=1 的 by_category 变成两套口径的拼盘。
const CATEGORY_RULES = [
  ['sensors', /lidar|camera|imu|encoder|sensor|vision|depth|tof|radar|sonar|ultrasonic|gyro|accel|microphone|tactile/],
  ['controllers', /mcu|sbc|jetson|raspberry|orin|nuc|controller|control_board|driver_board|pcb|mainboard|compute/],
  ['power', /battery|bms|dcdc|regulator|\bpsu\b|power_pack|powerboard/],
  ['communication', /ethercat|canbus|can_bus|rs485|rs232|ethernet|antenna|wifi|router|\bhub\b|harness|connector/],
  ['actuators', /servo|motor|actuator|gearbox|harmonic|reducer|gripper|\bhand\b|finger|thumb|\bjoint\b|drive/],
  ['structural', /base_link|torso|pelvis|thigh|shank|calf|shoulder|elbow|wrist|ankle|\bhip\b|knee|foot|\bfeet\b|frame|bracket|plate|shell|cover|housing|chassis|\blink\b/],
];

function inferCategory(blob) {
  const t = String(blob || '').toLowerCase();
  for (const [cat, re] of CATEGORY_RULES) if (re.test(t)) return cat;
  return 'unknown';   // 推断不出就说不知道，不兜底
}

/** 仅在名称里出现明确总线关键词时才落 protocol，否则 'N/A'（未声明）。 */
function inferProtocol(blob) {
  const t = String(blob || '').toLowerCase();
  if (/ethercat/.test(t)) return 'EtherCAT';
  if (/can[_-]?fd/.test(t)) return 'CAN FD';
  if (/\bcan\b/.test(t)) return 'CAN';
  if (/rs485|485/.test(t)) return 'RS485';
  if (/ethernet|rj45/.test(t)) return 'Ethernet';
  if (/\busb\b/.test(t)) return 'USB';
  const m = t.match(/\b(i2c|spi|uart|ttl)\b/);
  return m ? m[1].toUpperCase() : 'N/A';
}

/** 归一化名：跨大小写/标点识别同一零件，用于去重。 */
function normKey(s) {
  return String(s || '').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]/g, '');
}

/** 稳定 ID：同源同名每次复算一致 → 可去重、可 diff、可追溯。 */
function stableId(sourceUrl, name) {
  return 'OSS-BOM-' + crypto.createHash('sha1').update(`${sourceUrl}|${name}`).digest('hex').slice(0, 10).toUpperCase();
}

function isPlausibleLink(name) {
  if (!name || name.length < 2 || name.length > 80) return false;
  if (!/[a-z\u4e00-\u9fa5]/i.test(name)) return false;
  return true;
}

/**
 * 一个 link → 一个候选零件实体。
 * 字段严格取自 oss_components.json 现有 schema；URDF 未提供的量留空，不编造。
 */
function normalizeLink(link, joint, src, now) {
  const meshes = [...String(link.body).matchAll(/filename="([^"]+)"/g)].map(m => m[1]).join(' ');
  const materials = [...String(link.body).matchAll(/<material\s+name="([^"]+)"/g)].map(m => m[1]).join(' ');
  const blob = `${link.name} ${meshes} ${materials}`;
  const name = `${src.id} 连杆 ${link.name}`;

  return {
    id: stableId(src.url, name),
    name,
    name_en: name,
    category: inferCategory(blob),
    manufacturer: src.name.replace(/\s*\(.*\)$/, ''),
    type: 'urdf_link',
    protocol: inferProtocol(blob),
    interface: 'N/A',
    voltage: 'N/A',
    // ros_support 刻意不落字段：URDF 不含厂商能力声明，写 true/false 都是伪造。
    // regression.py 对派生抽取器有此不变式断言，勿加。
    ros_ecosystem_origin: true,          // 出处如实记录：该刚体确实出现在 ROS/URDF 模型中
    compatibility: [],
    applications: [src.id.toLowerCase().replace(/_/g, ''), src.robot_type],
    weight: '',                          // URDF 的 <inertial> 是仿真质量，非零件净重，不冒充
    torque: '',
    price_range: '',                     // URDF 无价格信息
    standard: '',
    spec: joint
      ? `URDF link；父连杆 ${joint.parent || 'N/A'}，经关节 ${joint.jname}(${joint.type})`
      : 'URDF link；根连杆或无父关节',
    joint_name: joint ? joint.jname : '',
    joint_type: joint ? joint.type : '',
    source_robot: src.name,
    source_license: src.license,
    source_repo: src.repo,
    source_url: src.url,
    extractor: 'urdf_link',
    oss: true,
    live: true,
    // ---- 证据强度标注（对齐仓库治理词表：A 可复核一手 / B 弱归因 / C 无溯源）----
    source_tier: 'C',
    confidence: 'low',                   // 注：本文件的 confidence 是字符串枚举
    declared: false,                     // 非厂商声明，仅为上游模型文件推断
    needs_provenance: true,
    first_seen: now,
    last_seen: now,
  };
}

// ---------------------------------------------------------------- 取源
async function loadSource(src, warn) {
  if (src.file) {
    try {
      return fs.readFileSync(src.file, 'utf8');
    } catch (e) {
      warn(`${src.id}: 读取本地文件失败 ${src.file} → ${e.message}`);
      return null;
    }
  }
  try {
    const res = await fetch(src.url, { headers: { 'User-Agent': 'roboparts-oss-bom-ingest' } });
    if (!res.ok) { warn(`${src.id}: HTTP ${res.status} ← ${src.url}`); return null; }
    return await res.text();
  } catch (e) {
    // 网络不可用是常态（离线环境 / 上游 404 / 限流），只警告不中断：
    // 摄取器崩掉会让飞轮整轮失败，而部分源成功本身是有价值的。
    warn(`${src.id}: 拉取失败 ${src.url} → ${e.message}`);
    return null;
  }
}

// ---------------------------------------------------------------- 主流程
async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8')
      .split('\n').slice(1, 26).join('\n').replace(/^ \* ?/gm, ''));
    return 0;
  }

  const warnings = [];
  const warn = (m) => { warnings.push(m); console.warn(`⚠️  ${m}`); };
  const sources = resolveSources(args.source);
  const now = new Date().toISOString();

  // 现有库：去重基线（按 归一化名 + source_url）
  let doc = null;
  const existingKeys = new Set();
  const existingIds = new Set();
  try {
    doc = JSON.parse(fs.readFileSync(OUT, 'utf8'));
    for (const e of doc.data || []) {
      existingIds.add(e.id);
      existingKeys.add(`${normKey(e.name)}|${e.source_url || ''}`);
    }
    console.log(`📖 现有库 ${doc.data.length} 条（meta.total_entities=${doc.meta?.total_entities}）`);
  } catch (e) {
    warn(`未能读取 ${path.relative(ROOT, OUT)}（${e.message}）；按空库处理`);
    doc = { meta: {}, data: [] };
  }

  const additions = [];
  const perSource = {};
  let parsedLinks = 0, skippedDup = 0;

  for (const src of sources) {
    const text = await loadSource(src, warn);
    if (!text) { perSource[src.id] = 'FAILED'; continue; }

    const xml = stripComments(text);
    const links = extractLinks(xml);
    const { byChild, joints } = extractJoints(xml);
    parsedLinks += links.length;
    console.log(`🔎 ${src.id}: 解析到 link ${links.length} 个 / joint ${joints.length} 个 ← ${src.url}`);

    let added = 0;
    for (const link of links) {
      if (additions.length >= args.limit) break;
      if (!isPlausibleLink(link.name)) continue;
      const ent = normalizeLink(link, byChild.get(link.name), src, now);
      const key = `${normKey(ent.name)}|${ent.source_url}`;
      if (existingKeys.has(key) || existingIds.has(ent.id)) { skippedDup++; continue; }
      existingKeys.add(key);
      existingIds.add(ent.id);
      additions.push(ent);
      added++;
    }
    perSource[src.id] = added;
    if (additions.length >= args.limit) { console.log(`   已达 --limit ${args.limit}，停止摄取`); break; }
  }

  // 摘要
  const byCat = {};
  for (const e of additions) byCat[e.category] = (byCat[e.category] || 0) + 1;
  console.log(`\n📊 解析 link 合计 ${parsedLinks}；将新增 ${additions.length} 条；跳过重复 ${skippedDup} 条`);
  console.log(`   按类目: ${JSON.stringify(byCat)}`);
  console.log(`   按来源: ${JSON.stringify(perSource)}`);
  if (warnings.length) console.log(`   警告 ${warnings.length} 条（见上）`);

  if (args.dryRun) {
    console.log('\n🧪 --dry-run：未写入任何文件。示例条目：');
    console.log(JSON.stringify(additions[0] || null, null, 2));
    return 0;
  }

  if (!additions.length) {
    console.log('\n✅ 无新增，文件保持不变（不空转改写 last_updated，避免伪造「刚更新过」）');
    return 0;
  }

  doc.data = [...(doc.data || []), ...additions];
  doc.meta = doc.meta || {};
  doc.meta.total_entities = doc.data.length;
  doc.meta.last_updated = now;          // 飞轮 7 天新鲜度判据，regression L1.11 守护此字段
  fs.writeFileSync(OUT, JSON.stringify(doc, null, 2));
  console.log(`\n✅ 已写入 ${path.relative(ROOT, OUT)}：+${additions.length} → total_entities=${doc.data.length}`);
  return 0;
}

main().then(c => process.exit(c)).catch(e => {
  console.error(`❌ ${e.message}`);
  process.exit(1);
});
