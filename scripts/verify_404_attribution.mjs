#!/usr/bin/env node
/**
 * L1.44 真跑验证：404 归因分类器必须「能定位我方死链」且「键空间有界」。
 *
 * 两个要求天然对立 —— 记得越细越好定位，也越容易被扫描器撑爆 KV。
 * 所以不能只测其中一半：只测"能定位"会放过键爆炸，只测"有界"会放过
 * 把所有路径都归成 other 的假修复（那样闸门全绿而问题原样存在）。
 *
 * 用法：node scripts/verify_404_attribution.mjs
 */
import { classify404 } from '../functions/_middleware.js';

let pass = 0;
const fails = [];
function eq(actual, expect, why) {
  if (actual === expect) { pass++; return; }
  fails.push(`${why}｜期望 ${expect}，实得 ${actual}`);
}
function ok(cond, why) {
  if (cond) { pass++; return; }
  fails.push(why);
}

// ① 我方死链必须逐条可定位 —— 这是本闸门存在的全部理由
const MINE = [
  '/iso-9409-flanges',          // 复数错写，站内互链常见错法
  '/articles/robot-joint-guide',
  '/api/entities',              // 少了 .json
  '/data-hub/',                 // 尾斜杠
  '/MCP-Guide',                 // 大小写
];
for (const p of MINE) {
  const v = classify404(p);
  ok(v !== 'scan' && v !== 'other',
    `我方死链必须独立成键，不得被聚合吞掉: ${p} → ${v}`);
}
eq(classify404('/data-hub/'), '/data-hub', '尾斜杠归一（否则同一条链算两处）');
eq(classify404('/MCP-Guide'), '/mcp-guide', '大小写归一（否则同一条链算两处）');

// ② 扫描器噪声必须聚合成一个桶，不给它们开键
const SCANS = [
  '/wp-login.php', '/wordpress/wp-admin/setup-config.php', '/.env',
  '/.git/config', '/phpmyadmin/index.php', '/admin/login',
  '/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php',
  '/backup.sql', '/config.yml', '/.ssh/id_rsa', '/cgi-bin/luci',
  '/actuator/env', '/xmlrpc.php', '/site.zip',
];
for (const p of SCANS) eq(classify404(p), 'scan', `扫描器路径应聚合: ${p}`);

// ③ 键空间有界：500 条随机长尾路径不得产出 500 个键
const bucket = new Set();
for (let i = 0; i < 500; i++) {
  bucket.add(classify404(`/${Math.random().toString(36).slice(2)}/`
    + `${Math.random().toString(36).slice(2)}/`
    + `${Math.random().toString(36).slice(2)}/`
    + `${Math.random().toString(36).slice(2)}`));            // 4 段，超界
  bucket.add(classify404('/' + 'x'.repeat(60) + i));          // 超长
  bucket.add(classify404(`/搜索?q=${i}<script>`));            // 异形字符
}
ok(bucket.size <= 3,
  `长尾路径必须收敛到有界桶（实得 ${bucket.size} 个键：${[...bucket].slice(0, 6)}）`);

// ④ 阳性对照：分类器不得退化成"全归 other"（那是假修复的典型形态）
const distinct = new Set(MINE.map(classify404));
ok(distinct.size === MINE.length,
  `5 条不同死链必须产出 5 个不同键（实得 ${distinct.size}，退化即失去定位能力）`);
ok(!MINE.map(classify404).includes('other'),
  '我方死链不得被判为 other（判成 other 就等于回到"只有总数"的老问题）');

// ⑤ 边界：根路径与空输入不得抛异常（遥测永不能影响主流程）
try {
  classify404('/'); classify404(''); classify404(undefined);
  pass += 1;
} catch (e) {
  fails.push(`异常输入不得抛错（遥测不能影响主流程）: ${e.message}`);
}

const total = pass + fails.length;
if (fails.length) {
  for (const f of fails) console.log('❌ ' + f);
  console.log(`❌ 404 归因验证失败 ${fails.length}/${total}`);
  process.exit(1);
}
console.log(`✅ 404 归因验证全部通过 ${pass}/${total}`);
