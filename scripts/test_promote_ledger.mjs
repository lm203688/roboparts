#!/usr/bin/env node
/**
 * promote.mjs 纯函数自测（效果台账 / 阶段状态幂等性，不触网、不发请求）。
 * 断言：fingerprintUrls 顺序无关 + 非空；buildPromoEntry 字段完整。
 * 非零退出即判红（被 ci_gate 的「飞轮幂等/可恢复」闸门调用）。
 */
import { fingerprintUrls, buildPromoEntry } from './promote.mjs';

let pass = 0, fail = 0;
function ck(cond, msg) {
  if (cond) { pass++; console.log('  ✅ ' + msg); }
  else { fail++; console.log('  ❌ ' + msg); }
}

// 1 fingerprintUrls 顺序无关 + 确定性
const a = fingerprintUrls(['https://x/1', 'https://x/2']);
const b = fingerprintUrls(['https://x/2', 'https://x/1']);
ck(a === b, 'fingerprintUrls 顺序无关（同一集合同指纹）');
ck(typeof a === 'string' && a.length > 0, 'fingerprintUrls 返回非空串');
const c = fingerprintUrls(['https://x/1']);
ck(a !== c, 'fingerprintUrls 不同集合不同指纹');

// 2 buildPromoEntry 字段完整
const e = buildPromoEntry('https://roboparts.cc', 12, { indexnow: 200, bing: 200, baidu: 'throttled-today' });
ck(e.date && /^\d{4}-\d{2}-\d{2}$/.test(e.date), 'buildPromoEntry.date 为 YYYY-MM-DD');
ck(e.site === 'https://roboparts.cc' && e.url_count === 12, 'buildPromoEntry 基本字段正确');
ck(e.engines.indexnow === 200 && e.engines.baidu === 'throttled-today', 'buildPromoEntry 记录各引擎结果');
ck(typeof e.generated_at === 'string' && e.generated_at.length > 0, 'buildPromoEntry 带 generated_at');

console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
