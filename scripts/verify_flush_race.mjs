/**
 * 功能性验证：遥测 flush 的读-改-写竞态，以及串行化修复是否真的止住丢写。
 *
 * 【为什么必须做这个，而不是只加静态闸门】
 * L1.31 只能证明「源码里写了 promise 链」，证明不了「链真的把写序列化了」。
 * 而本次缺陷的性质恰恰是**看起来一切正常、数字却在无声地少**——
 * 这类缺陷只有把真实代码放到真实竞态里跑一遍才能证伪。
 *
 * 做法：不重写逻辑（重写就等于验证我自己的复制品）。直接从 functions/mcp.js
 * 切出遥测段真实源码，注入 mock KV（get/put 各带异步延迟以放大交错窗口），
 * 分别以「修复版」和「反向注入的旧版」各跑一次，比较落盘计数。
 *
 * 期望：旧版丢写（落盘 < 应记），修复版不丢（落盘 == 应记）。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = fs.readFileSync(path.join(ROOT, 'functions', 'mcp.js'), 'utf8');

// 切出遥测段真实源码：从分片常量到 recordMcp 结束
const START = SRC.indexOf('const SHARDS = 16;');
const END = SRC.indexOf('/* ═══', SRC.indexOf('function recordMcp'));
if (START < 0 || END < 0) {
  console.error('❌ 无法在 functions/mcp.js 中定位遥测段，验证脚本需同步更新');
  process.exit(2);
}
const SEG = SRC.slice(START, END);

/** mock KV：get/put 都带延迟，模拟真实网络往返，放大读-改-写交错窗口 */
function makeKV(delayMs) {
  const store = new Map();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  return {
    store,
    async get(key) { await sleep(delayMs); const v = store.get(key); return v ? JSON.parse(v) : null; },
    async put(key, val) { await sleep(delayMs); store.set(key, val); },
  };
}

async function run(label, segSource) {
  const mod = `${segSource}\nexport { recordMcp, flushMcp };\n`;
  const tmp = path.join(ROOT, `.tmp_flush_${label}.mjs`);
  fs.writeFileSync(tmp, mod, 'utf8');
  try {
    const { recordMcp } = await import(`file://${tmp.replace(/\\/g, '/')}?v=${Date.now()}`);
    const kv = makeKV(8);
    const pending = [];
    const context = {
      env: { USER_CREDITS: kv },
      waitUntil: (p) => pending.push(p),
      request: { headers: { get: () => null } },
    };
    // 复刻线上真实调用形态：一次 tools/call 连续两次 recordMcp
    recordMcp(context, 'tool:check_compatibility');
    recordMcp(context, 'toolsrc:script:check_compatibility');
    await Promise.allSettled(pending);
    await new Promise((r) => setTimeout(r, 120));   // 等尾部 put 落定

    let landed = {};
    for (const v of kv.store.values()) Object.assign(landed, JSON.parse(v));
    delete landed._updated;
    return landed;
  } finally {
    try { fs.unlinkSync(tmp); } catch { /* 清理失败不影响结论 */ }
  }
}

const fixed = SEG;
const legacy = SEG.replace('scheduleFlush(context);',
  'context.waitUntil(flushMcp(context.env).catch(() => {}));');
if (legacy === fixed) {
  console.error('❌ 反向注入失败：源码中未找到 scheduleFlush(context); 调用点');
  process.exit(2);
}

const EXPECT = { 'mcp:tool:check_compatibility': 1, 'mcp:toolsrc:script:check_compatibility': 1 };
const fmt = (o) => Object.entries(o).map(([k, v]) => `${k}=${v}`).join(', ') || '（空）';

const legacyLanded = await run('legacy', legacy);
const fixedLanded = await run('fixed', fixed);

console.log('应记入：', fmt(EXPECT));
console.log('旧版（直接 waitUntil，无串行化）落盘：', fmt(legacyLanded));
console.log('修复版（scheduleFlush 串行化）落盘：', fmt(fixedLanded));

const eq = (a) => Object.keys(EXPECT).every((k) => a[k] === EXPECT[k]);
const legacyLoses = !eq(legacyLanded);
const fixedKeeps = eq(fixedLanded);

console.log('');
console.log(legacyLoses ? '✅ 旧版确实丢写（竞态复现，缺陷为真）'
                        : '⚠️ 旧版未复现丢写：本机调度未撞上交错窗口，本次不足以证伪');
console.log(fixedKeeps ? '✅ 修复版无丢写（串行化生效）'
                       : '❌ 修复版仍丢写（串行化未生效）');

process.exit(fixedKeeps ? 0 : 1);
