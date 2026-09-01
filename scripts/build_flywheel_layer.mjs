#!/usr/bin/env node
/**
 * RoboParts 数据飞轮 · 贡献层构建器（P0）
 *
 * 把「真实开源机器人 BOM 摄取产物」+「用户/开源项目提交的 BOM」统一合成为一份
 * 贡献层 api/entities.contrib.json，由运行时引擎（compat_engine.loadEntityMap）
 * 合并进主实体表，使开源/用户贡献的零件也能参与兼容性裁决。
 *
 * 诚实性纪律（与 ingest_oss_bom.mjs 同源，不可放宽）：
 *   - OSS 零件来源于 URDF 抓取，protocol/voltage/ros_support 是真实可核实的；
 *     但 URDF 不含机械接口事实，故 mechanical_interface 一律留空（不编造）。
 *   - 用户 BOM（ops/seed-bom.json 或 /api/bom/import 提交）若含机械接口声明，
 *     须带 source_url 方可采信，否则仅作协议/电气层补充。
 *   - 贡献层不污染主库数字（api/entities.json 的 708 不变），仅作为运行时增强层。
 *
 * 用法：
 *   node scripts/build_flywheel_layer.mjs            # 合并 OSS + ops/seed-bom.json → api/entities.contrib.json
 *   node scripts/build_flywheel_layer.mjs --dry-run  # 仅预览统计
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const OSS = path.join(ROOT, 'api', 'oss_components.json');
const SEED = path.join(ROOT, 'ops', 'seed-bom.json');
const OUT = path.join(ROOT, 'api', 'entities.contrib.json');
const FLYWHEEL_STATE = path.join(ROOT, 'scripts', 'flywheel_state.py');

/** 输入指纹：OSS + seed-bom 原始内容拼接待，供「输入未变则跳过重建」判定。 */
function fingerprintOf(parts) {
  const h = createHash('sha256');
  for (const p of parts) h.update(typeof p === 'string' ? p : '<<null>>');
  return h.digest('hex').slice(0, 16);
}

// OSS 的 category schema（actuators/sensors/controllers/communication/structural/power）
// 映射到主库 11 类；structural/power 无标准接口，跳过（join 后恒 null，无价值）。
const CAT_MAP = {
  actuators: 'actuators',
  sensors: 'sensors',
  controllers: 'chips',
  communication: 'protocols',
};

function hasDeclare(e) {
  const p = e.protocol && String(e.protocol).toUpperCase() !== 'N/A';
  const v = e.voltage && String(e.voltage).toUpperCase() !== 'N/A';
  const r = typeof e.ros_support === 'boolean';
  return !!(p || v || r);
}

function fromOss(e) {
  const cat = CAT_MAP[e.category];
  if (!cat) return null;                 // structural/power 跳过
  if (!hasDeclare(e)) return null;       // 无任何可裁决维度声明的跳过
  return {
    id: e.id,
    name: e.name,
    name_en: e.name_en || e.name,
    category: cat,
    manufacturer: e.manufacturer || null,
    type: e.type || null,
    protocol: e.protocol && String(e.protocol).toUpperCase() !== 'N/A' ? e.protocol : null,
    interface: e.interface && String(e.interface).toUpperCase() !== 'N/A' ? e.interface : null,
    voltage: e.voltage && String(e.voltage).toUpperCase() !== 'N/A' ? e.voltage : null,
    ros_support: typeof e.ros_support === 'boolean' ? e.ros_support : undefined,
    compatibility: Array.isArray(e.compatibility) ? e.compatibility : [],
    applications: Array.isArray(e.applications) ? e.applications : [],
    entity_kind: 'component',
    source_tier: 'C',
    confidence: 'low',
    flywheel_source: 'oss_urdf:' + (e.source_robot || 'unknown'),
    source_url: e.source_url || e.source_repo || null,
    oss: true,
  };
}

/** 用户/开源 BOM 条目 → 贡献实体。机械接口须带 source_url 才采信。 */
function fromBom(b, srcLabel) {
  if (!b || !b.id || !b.category) return null;
  const cat = CAT_MAP[b.category] || b.category;
  const mech = b.mechanical_interface;
  let mechanical_interface = undefined;
  if (mech && mech.standard) {
    if (!b.source_url) return { _warn: `跳过 ${b.id} 的机械接口：缺 source_url（不可核实）` };
    mechanical_interface = {
      status: 'declared',
      standard: Array.isArray(mech.standard) ? mech.standard : [mech.standard],
      source: b.source_url,
      source_url: b.source_url,
      confidence: 'medium',
    };
  }
  return {
    id: b.id,
    name: b.name || b.id,
    name_en: b.name_en || b.name || b.id,
    category: cat,
    manufacturer: b.manufacturer || null,
    type: b.type || null,
    protocol: b.protocol || null,
    interface: b.interface || null,
    voltage: b.voltage || null,
    ros_support: typeof b.ros_support === 'boolean' ? b.ros_support : undefined,
    mechanical_interface,
    compatibility: Array.isArray(b.compatibility) ? b.compatibility : [],
    applications: Array.isArray(b.applications) ? b.applications : [],
    entity_kind: 'component',
    source_tier: 'B',
    confidence: 'medium',
    flywheel_source: srcLabel,
    source_url: b.source_url || null,
  };
}

function main() {
  const dry = process.argv.includes('--dry-run');
  const force = process.argv.includes('--force');
  const warnings = [];
  const out = [];
  const seen = new Set();

  // 先读原始内容（既用于合并，也用于「输入指纹」）
  let ossRaw = null;
  try { ossRaw = fs.readFileSync(OSS, 'utf8'); }
  catch { console.warn(`⚠️ 读取 ${path.relative(ROOT, OSS)} 失败`); }
  let seedRaw = null;
  if (fs.existsSync(SEED)) {
    try { seedRaw = fs.readFileSync(SEED, 'utf8'); }
    catch { console.warn(`⚠️ 读取 ${path.relative(ROOT, SEED)} 失败`); }
  } else {
    console.log(`ℹ️ 未发现 ops/seed-bom.json（用户 BOM 入口待提交；管道已就绪）`);
  }

  const inputFp = fingerprintOf([ossRaw, seedRaw]);
  // 可恢复/幂等：输入未变且上一轮 candidate 阶段 OK → 跳过整个重建
  if (!force && !dry) {
    try {
      const r = spawnSync(process.execPath,
        [FLYWHEEL_STATE, 'should-run', 'candidate', inputFp],
        { encoding: 'utf8', timeout: 30000 });
      if ((r.stdout || '').trim() === 'skip') {
        console.log('♻️ candidate 阶段输入未变且上次 OK → 跳过重建（幂等/可恢复）');
        return 0;
      }
    } catch { /* python 不可用则照常重建，不阻塞 */ }
  }

  // 1) OSS 真实反喂
  if (ossRaw) {
    try {
      const oss = JSON.parse(ossRaw);
      const arr = oss.data || oss.entities || [];
      let added = 0, skipped = 0;
      for (const e of arr) {
        const c = fromOss(e);
        if (!c) { skipped++; continue; }
        if (seen.has(c.id)) continue;
        seen.add(c.id); out.push(c); added++;
      }
      console.log(`📥 OSS 反喂：解析 ${arr.length} 条，纳入贡献层 ${added} 条，跳过 ${skipped} 条（structural/power 或无声明）`);
    } catch (e) {
      console.warn(`⚠️ 解析 ${path.relative(ROOT, OSS)} 失败: ${e.message}`);
    }
  }

  // 2) 用户/开源 BOM 种子
  if (seedRaw) {
    try {
      const bom = JSON.parse(seedRaw);
      const items = Array.isArray(bom) ? bom : (bom.components || bom.entities || []);
      let added = 0;
      for (const b of items) {
        const c = fromBom(b, 'seed-bom');
        if (!c) continue;
        if (c._warn) { warnings.push(c._warn); continue; }
        if (seen.has(c.id)) continue;
        seen.add(c.id); out.push(c); added++;
      }
      console.log(`📥 seed-bom：纳入 ${added} 条`);
    } catch (e) {
      console.warn(`⚠️ 解析 ${path.relative(ROOT, SEED)} 失败: ${e.message}`);
    }
  }

  if (warnings.length) warnings.forEach(w => console.warn('   ⚠️ ' + w));

  const byCat = {};
  for (const e of out) byCat[e.category] = (byCat[e.category] || 0) + 1;
  const mechDeclared = out.filter(e => e.mechanical_interface && e.mechanical_interface.standard).length;
  const protoDeclared = out.filter(e => e.protocol).length;
  const rosDeclared = out.filter(e => typeof e.ros_support === 'boolean').length;
  console.log(`📊 贡献层合计 ${out.length} 条；按类目 ${JSON.stringify(byCat)}`);
  console.log(`   协议声明 ${protoDeclared} | ROS 布尔 ${rosDeclared} | 机械接口声明 ${mechDeclared}（机械维度仍稀缺，待真实 BOM 贡献流入）`);

  if (dry) {
    console.log('\n🧪 --dry-run：未写入。');
    return 0;
  }
  const doc = {
    meta: {
      layer: 'flywheel-contrib',
      generated_at: new Date().toISOString(),
      description: '数据飞轮贡献层：开源机器人 BOM(URDF 摄取) + 用户/开源项目提交 BOM。由 compat_engine 运行时合并进主实体表，不修改主库 api/entities.json。',
      curated_baseline: 708,
      contributions: out.length,
    },
    entities: out,
  };
  fs.writeFileSync(OUT, JSON.stringify(doc, null, 2));
  console.log(`\n✅ 已写入 ${path.relative(ROOT, OUT)}：+${out.length} 贡献实体`);

  // 记录 candidate 阶段状态（飞轮幂等/可恢复台账）
  try {
    spawnSync(process.execPath,
      [FLYWHEEL_STATE, 'record', 'candidate', '--file', OUT, '--ok', '1'],
      { encoding: 'utf8', timeout: 30000 });
  } catch { /* 记录失败不阻塞主流程 */ }
  return 0;
}

main();
