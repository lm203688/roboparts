#!/usr/bin/env node
/**
 * validate_mjcf.mjs —— MJCF 真加载验证器（① 融合点，2026-11-19）
 *
 * 目的：scripts/smoke_prod.mjs 的 checkMjcfDownload 只做正则/字符串断言
 * （<mujoco 根 + <worldbody> 存在），从没在 MuJoCo 里真加载过。本脚本把
 * 「生成了 MJCF」升级为「MuJoCo 真能吃」：
 *
 *   阶段一（纯 node，无依赖）：结构校验
 *     · 根元素必须是 <mujoco>
 *     · 必须有 <worldbody>
 *     · 每个 <joint body="X"> 引用的 body 必须存在
 *     · 每个 <pair geom1=.. geom2=..> 引用的 geom 必须存在
 *     · <joint> 上的 body 属性、body 与 joint 的父子关系做结构审查
 *
 *   阶段二（env-gated，走 MUJOCO_PY）：真加载
 *     · 用 mujoco.MjModel.from_xml_string() 编译
 *     · mj_step() 跑 100 步验证动力学能推进
 *     · 绑定缺失 → SKIP（诚实报告，不假绿）
 *
 * 用法：
 *   node scripts/validate_mjcf.mjs                       # 默认打生产 URDF-001..005
 *   node scripts/validate_mjcf.mjs --target http://127.0.0.1:8787
 *   node scripts/validate_mjcf.mjs --ids URDF-001,URDF-002 --json
 *   MUJOCO_PY=C:\...\python.exe node scripts/validate_mjcf.mjs   # 指定绑定
 *   node scripts/validate_mjcf.mjs --local sample.mjcf   # 验本地文件
 *
 * 输出：每项 { id, structural, load, note }；--json 机读。
 */

import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2);
const TARGET = (process.env.SMOKE_TARGET || args.find((a) => a.startsWith('http')) || 'https://roboparts.cc').replace(/\/$/, '');
const JSON_OUT = args.includes('--json');
const LOCAL = args.includes('--local') ? args[args.indexOf('--local') + 1] : null;
const IDS = (args.includes('--ids') ? args[args.indexOf('--ids') + 1] : 'URDF-001,URDF-002,URDF-003,URDF-004,URDF-005').split(',');

// 阶段二绑定：默认用 %TEMP%\roboparts-mujoco-venv，可用 MUJOCO_PY 覆盖
const DEFAULT_VENV = path.join(
  process.env.TEMP || 'C:\\Users\\xing\\AppData\\Local\\Temp',
  'roboparts-mujoco-venv',
  'Scripts',
  'python.exe',
);
const MUJOCO_PY = process.env.MUJOCO_PY || DEFAULT_VENV;

// ===================== 阶段一：结构校验 =====================

/** 提取所有 body 名（含嵌套） */
function extractBodyNames(xml) {
  const names = new Set();
  const re = /<body\b[^>]*\bname="([^"]+)"/g;
  let m;
  while ((m = re.exec(xml))) names.add(m[1]);
  return names;
}

/** 提取所有 geom 名 */
function extractGeomNames(xml) {
  const names = new Set();
  const re = /<geom\b[^>]*\bname="([^"]+)"/g;
  let m;
  while ((m = re.exec(xml))) names.add(m[1]);
  return names;
}

/** 结构校验：返回 { ok, reasons[], warnings[] } */
export function structuralCheck(xml) {
  const reasons = [];
  const warnings = [];
  const bodyNames = extractBodyNames(xml);
  const geomNames = extractGeomNames(xml);

  if (!/<mujoco\b/.test(xml)) reasons.push('根元素不是 <mujoco>');
  if (!/<worldbody\b/.test(xml)) reasons.push('缺少 <worldbody>');
  if (bodyNames.size === 0) reasons.push('没有声明任何 <body>');

  // joint 的 body 属性引用
  const jointRe = /<joint\b([^>]*)\/?>/g;
  let m;
  while ((m = jointRe.exec(xml))) {
    const attrs = m[1];
    const b = /body="([^"]+)"/.exec(attrs);
    const nm = /name="([^"]+)"/.exec(attrs);
    if (b && !bodyNames.has(b[1])) {
      reasons.push(`joint "${nm ? nm[1] : '?'}" 引用不存在的 body "${b[1]}"`);
    }
    if (b) {
      // 标准 MJCF：<joint> 没有 body 属性；关节应声明为子 body 的孩子。
      // 此处 body="link_i" 说明作者想让关节连到 link_i，但挂载在父 body 上。
      warnings.push(`joint "${nm ? nm[1] : '?'}" 使用非标准 body 属性（MJCF 中 <joint> 无 body 属性，应作为目标 body 的孩子声明）`);
    }
  }

  // contact pair 的 geom 引用
  const pairRe = /<pair\b[^>]*geom1="([^"]+)"[^>]*geom2="([^"]+)"/g;
  while ((m = pairRe.exec(xml))) {
    if (!geomNames.has(m[1])) reasons.push(`pair geom1 "${m[1]}" 引用不存在的 geom`);
    if (!geomNames.has(m[2])) reasons.push(`pair geom2 "${m[2]}" 引用不存在的 geom`);
  }

  return { ok: reasons.length === 0, reasons, warnings };
}

// ===================== 阶段二：真加载 =====================

/** 用 venv python + mujoco 真编译并 step。返回 { ok, skip?, note } */
export function realLoad(xml) {
  if (!MUJOCO_PY) return { ok: false, skip: true, note: '未指定 MUJOCO_PY' };
  const py = [
    'import sys, mujoco',
    '# stdin 显式按 UTF-8 解码：中文 Windows 上 sys.stdin 默认用 locale 编码（cp936），',
    '# 会把 UTF-8 字节解成乱码，pybind 再转回 UTF-8 时报 "incompatible function arguments" TypeError。',
    'xml = sys.stdin.buffer.read().decode("utf-8")',
    'try:',
    '    m = mujoco.MjModel.from_xml_string(xml)',
    'except Exception as e:',
    '    print("LOAD_FAIL", repr(e)); sys.exit(2)',
    'd = mujoco.MjData(m)',
    'for _ in range(100): mujoco.mj_step(m, d)',
    'print("LOAD_OK", "nbody=%d njnt=%d ngeom=%d" % (m.nbody, m.njnt, m.ngeom))',
  ].join('\n');
  const r = spawnSync(MUJOCO_PY, ['-c', py], { input: xml, encoding: 'utf8', timeout: 30000 });
  if (r.error) {
    const ENOENT = r.error.code === 'ENOENT';
    return { ok: false, skip: ENOENT, note: ENOENT ? `绑定不存在: ${MUJOCO_PY}` : `执行错误: ${r.error.message}` };
  }
  const out = (r.stdout || '').trim();
  const err = (r.stderr || '').trim();
  if (r.status === 0 && out.startsWith('LOAD_OK')) {
    return { ok: true, note: out };
  }
  // 绑定存在但 mujoco 模块未装（例如安装还没完成）：诚实报告 SKIP，不是 FAIL
  if (/No module named ['"]mujoco['"]/.test(err) || /ModuleNotFoundError/.test(err)) {
    return { ok: false, skip: true, note: 'mujoco 模块未安装（绑定存在但未装包），真加载 SKIP' };
  }
  return { ok: false, note: out || err || `exit ${r.status}` };
}

// ===================== 主流程 =====================

async function fetchMjcf(id) {
  const url = `${TARGET}/api/urdf/download?id=${encodeURIComponent(id)}&format=mjcf`;
  const r = await fetch(url, { headers: { 'X-RoboParts-Selftest': '1' } });
  const text = await r.text();
  return { status: r.status, text, headers: Object.fromEntries(r.headers.entries()), url };
}

async function main() {
  const results = [];

  const sources = LOCAL
    ? [{ id: 'LOCAL', fetch: async () => ({ status: 200, text: readFileSync(LOCAL, 'utf8'), headers: {} }) }]
    : IDS.map((id) => ({ id, fetch: () => fetchMjcf(id) }));

  for (const { id, fetch: f } of sources) {
    let r;
    try {
      r = await f();
    } catch (e) {
      results.push({ id, error: `fetch: ${e.message}`, structural: null, load: null });
      continue;
    }
    const rec = { id, http: r.status, url: r.url };
    if (r.status !== 200) {
      rec.error = `HTTP ${r.status}`;
      rec.structural = { ok: false, reasons: [`HTTP ${r.status}（非 200）`], warnings: [] };
      results.push(rec);
      continue;
    }
    rec.assetClass = r.headers['x-roboparts-assetclass'] || '(无头)';
    rec.structural = structuralCheck(r.text);
    rec.load = realLoad(r.text);
    results.push(rec);
  }

  const anyLoadFail = results.some((x) => x.load && !x.load.ok && !x.load.skip);
  const anyStructFail = results.some((x) => x.structural && !x.structural.ok);
  const anySkip = results.some((x) => x.load && x.load.skip);

  const summary = {
    total: results.length,
    structuralOk: results.filter((x) => x.structural && x.structural.ok).length,
    loadOk: results.filter((x) => x.load && x.load.ok).length,
    loadSkip: results.filter((x) => x.load && x.load.skip).length,
    loadFail: results.filter((x) => x.load && !x.load.ok && !x.load.skip).length,
    verdict: anyLoadFail || anyStructFail ? 'FAIL' : anySkip ? 'PARTIAL (load skipped)' : 'PASS',
  };

  if (JSON_OUT) {
    console.log(JSON.stringify({ summary, results }, null, 2));
  } else {
    console.log(`\n[validate_mjcf] target=${TARGET}  verdict=${summary.verdict}`);
    for (const x of results) {
      console.log(`\n-- ${x.id} (HTTP ${x.http})${x.url ? `  ${x.url}` : ''}`);
      if (x.error) { console.log(`   ERROR: ${x.error}`); continue; }
      console.log(`   assetClass: ${x.assetClass}`);
      console.log(`   结构: ${x.structural.ok ? 'PASS' : 'FAIL'}`);
      for (const r of x.structural.reasons) console.log(`     ✗ ${r}`);
      for (const w of x.structural.warnings) console.log(`     ⚠ ${w}`);
      console.log(`   加载: ${x.load.ok ? 'PASS' : x.load.skip ? 'SKIP' : 'FAIL'}`);
      if (x.load.note) console.log(`     ${x.load.note}`);
    }
    console.log('');
  }

  process.exit(summary.verdict === 'PASS' ? 0 : 1);
}

// 仅在直接运行（node scripts/validate_mjcf.mjs）时执行 main；被 smoke_prod 导入时不自动跑。
import { pathToFileURL } from 'node:url';
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => {
    console.error(e);
    process.exit(2);
  });
}
