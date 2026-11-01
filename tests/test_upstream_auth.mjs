/**
 * resolveAuthState 回归测试（P0-1）
 *
 * 测的判据：`functions/_lib/upstream.js resolveAuthState()` 的每个返回分支必须
 * 返回**普通对象** `{ tier, auth_state, ... }`，**绝不返回 RegExp**。
 *
 * 背景：此函数曾有一个分支写成 `return /{...}/`（正则字面量），运行时整个对象
 * 变成 RegExp，`auth_state`/`tier` 全 undefined，付费墙对合法 Pro 密钥也按免费
 * 放行（fail-open）。修好源码后加本回归测试，防复发（改一次、看住一辈子）。
 */
import { resolveAuthState } from '../functions/_lib/upstream.js';

let pass = 0, fail = 0;
function ok(cond, msg) {
  if (cond) { pass++; console.log('  ✓ ' + msg); }
  else { fail++; console.log('  ✗ ' + msg); }
}

const req = (auth, key) => ({
  url: 'https://roboparts.cc/api/entities.json' + (key ? '?key=' + key : ''),
  headers: { get: (h) => (h === 'Authorization' ? auth : null) },
});

async function run() {
  console.log('resolveAuthState 回归（P0-1：绝不返回 RegExp）');

  // ① 匿名（无 key）→ free/anonymous
  let r = await resolveAuthState(req('', ''), {});
  ok(r && r.tier === 'free' && r.auth_state === 'anonymous', '① 匿名 → free/anonymous');
  ok(!(r instanceof RegExp), '① 返回值不是 RegExp');

  // ② gtk_ KV 查到 pro 用户 → pro/verified_pro
  const kv = { get: async () => JSON.stringify({ plan: 'pro', credits: 500 }) };
  r = await resolveAuthState(req('Bearer gtk_abc', ''), { USER_CREDITS: kv });
  ok(r && r.tier === 'pro' && r.auth_state === 'verified_pro', '② KV pro → pro/verified_pro');
  ok(!(r instanceof RegExp), '② 返回值不是 RegExp');

  // ③ gtk_ KV 查到免费用户 → free/verified_free
  const kv2 = { get: async () => JSON.stringify({ plan: 'starter', credits: 0 }) };
  r = await resolveAuthState(req('', 'gtk_abc'), { USER_CREDITS: kv2 });
  ok(r && r.tier === 'free' && r.auth_state === 'verified_free', '③ KV free → free/verified_free');
  ok(!(r instanceof RegExp), '③ 返回值不是 RegExp');

  // ④ gtk_ KV 查询抛错 → free/unverified（fail-closed）
  const kv3 = { get: async () => { throw new Error('kv down'); } };
  r = await resolveAuthState(req('Bearer gtk_abc', ''), { USER_CREDITS: kv3 });
  ok(r && r.tier === 'free' && r.auth_state === 'unverified', '④ KV 抛错 → free/unverified');
  ok(!(r instanceof RegExp), '④ 返回值不是 RegExp');

  // ⑤ 无 CREEM_API_KEY → free/unverified
  r = await resolveAuthState(req('Bearer creemkey', ''), {});
  ok(r && r.tier === 'free' && r.auth_state === 'unverified', '⑤ 无 CREEM key → free/unverified');
  ok(!(r instanceof RegExp), '⑤ 返回值不是 RegExp');

  // ⑥ Creem 404（查无此 license，是裁决）→ free/verified_free
  global.fetch = async () => ({ status: 404, ok: false });
  r = await resolveAuthState(req('Bearer creemkey', ''), { CREEM_API_KEY: 'ck' });
  ok(r && r.tier === 'free' && r.auth_state === 'verified_free', '⑥ Creem 404 → free/verified_free');
  ok(!(r instanceof RegExp), '⑥ 返回值不是 RegExp');

  // ⑦ Creem 200 active → pro/verified_pro
  global.fetch = async () => ({ status: 200, ok: true, json: async () => ({ status: 'active' }) });
  r = await resolveAuthState(req('Bearer creemkey', ''), { CREEM_API_KEY: 'ck' });
  ok(r && r.tier === 'pro' && r.auth_state === 'verified_pro', '⑦ Creem active → pro/verified_pro');
  ok(!(r instanceof RegExp), '⑦ 返回值不是 RegExp');

  // ⑧ Creem 200 inactive → free/verified_free
  global.fetch = async () => ({ status: 200, ok: true, json: async () => ({ status: 'expired' }) });
  r = await resolveAuthState(req('Bearer creemkey', ''), { CREEM_API_KEY: 'ck' });
  ok(r && r.tier === 'free' && r.auth_state === 'verified_free', '⑧ Creem inactive → free/verified_free');
  ok(!(r instanceof RegExp), '⑧ 返回值不是 RegExp');

  // ⑨ Creem 5xx（真故障）→ free/unverified（fail-closed）
  global.fetch = async () => ({ status: 503, ok: false });
  r = await resolveAuthState(req('Bearer creemkey', ''), { CREEM_API_KEY: 'ck' });
  ok(r && r.tier === 'free' && r.auth_state === 'unverified', '⑨ Creem 5xx → free/unverified');
  ok(!(r instanceof RegExp), '⑨ 返回值不是 RegExp');

  // ⑩ Creem fetch 抛错 → free/unverified
  global.fetch = async () => { throw new Error('network'); };
  r = await resolveAuthState(req('Bearer creemkey', ''), { CREEM_API_KEY: 'ck' });
  ok(r && r.tier === 'free' && r.auth_state === 'unverified', '⑩ Creem 网络异常 → free/unverified');
  ok(!(r instanceof RegExp), '⑩ 返回值不是 RegExp');

  console.log(`\n${fail ? 'FAIL' : 'PASS'}（${pass} 通过 / ${fail} 失败）`);
  process.exit(fail ? 1 : 0);
}

run().catch((e) => { console.error(e); process.exit(1); });
