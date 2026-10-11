/**
 * P0 安全修复：API Key 从 query 参数迁移到 Header
 * 函数名：resolveAuthState (functions/_lib/upstream.js)
 */

const fs = require('fs');
const path = require('path');

const upstreamPath = path.join(__dirname, '..', 'functions', '_lib', 'upstream.js');
let code = fs.readFileSync(upstreamPath, 'utf8');

// === 修改 1：resolveAuthState 增加 use_header 标记 ===
const oldBlock = `export async function resolveAuthState(request, env) {
  const auth = request.headers.get('Authorization') || '';
  const url = new URL(request.url);
  const qk = url.searchParams.get('key') || '';
  const provided = auth.startsWith('Bearer ') ? auth.slice(7).trim() : qk.trim();

  if (!provided) return { tier: 'free', auth_state: 'anonymous', auth_failure: null, key: '' };`;

const newBlock = `export async function resolveAuthState(request, env) {
  const auth = request.headers.get('Authorization') || '';
  const url = new URL(request.url);
  const qk = url.searchParams.get('key') || '';
  const fromHeader = auth.startsWith('Bearer ') ? auth.slice(7).trim() : '';
  const useHeader = !!fromHeader;
  const provided = fromHeader || qk.trim();

  if (!provided) return { tier: 'free', auth_state: 'anonymous', auth_failure: null, key: '', use_header: useHeader };`;

if (!code.includes(oldBlock)) {
  console.error('ERROR: Could not find target block in upstream.js');
  // Show what's there
  const lines = code.split('\n');
  console.log('Lines 77-90:', lines.slice(76, 90).join('\n'));
  process.exit(1);
}
code = code.replace(oldBlock, newBlock);

// === 修改 2：所有 return 对象加 use_header ===
const returnReplacements = [
  // verified_free (KV)
  [/{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key: '' };/g,
   /{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key: '', use_header: useHeader };/],
  // verified_free (Creem 404/400)
  [/{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key_status: 'not_found', key: '' };/g,
   /{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key_status: 'not_found', key: '', use_header: useHeader };/],
  // verified_free (Creem inactive)
  [/{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key_status: d.status \|\| 'inactive', key: '' };/g,
   /{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key_status: d.status || 'inactive', key: '', use_header: useHeader };/],
  // verified_pro (KV)
  [/{ tier: 'pro', auth_state: 'verified_pro', auth_failure: null, key: provided };/g,
   /{ tier: 'pro', auth_state: 'verified_pro', auth_failure: null, key: provided, use_header: useHeader };/],
  // verified_pro (Creem active)
  [/{ tier: 'pro', auth_state: 'verified_pro', auth_failure: null, key: provided };/g,
   /{ tier: 'pro', auth_state: 'verified_pro', auth_failure: null, key: provided, use_header: useHeader };/],
];

for (const [old, new_] of returnReplacements) {
  const count = (code.match(old) || []).length;
  code = code.replace(old, new_);
  console.log(`  Replaced ${count} occurrence(s): ${old.toString().slice(0, 60)}...`);
}

// === 修改 3：unverified returns ===
code = code.replace(
  /{ tier: 'free', auth_state: 'unverified', auth_failure: \{ source: 'kv', kind: 'no_user_credits_binding' \}, key: '' }/,
  `{ tier: 'free', auth_state: 'unverified', auth_failure: { source: 'kv', kind: 'no_user_credits_binding' }, key: '', use_header: useHeader }`
);
code = code.replace(
  /{ tier: 'free', auth_state: 'unverified', auth_failure: \{ source: 'kv', kind: 'lookup_failed'/g,
  `{ tier: 'free', auth_state: 'unverified', auth_failure: { source: 'kv', kind: 'lookup_failed'`
);
code = code.replace(
  /{ tier: 'free', auth_state: 'unverified', auth_failure: \{ source: 'creem', kind: 'no_api_key_configured' \}, key: '' }/,
  `{ tier: 'free', auth_state: 'unverified', auth_failure: { source: 'creem', kind: 'no_api_key_configured' }, key: '', use_header: useHeader }`
);
code = code.replace(
  /{ tier: 'free', auth_state: 'unverified', auth_failure: \{ source: 'creem', kind: 'upstream_status_' \+ r.status \}, key: '' }/g,
  `{ tier: 'free', auth_state: 'unverified', auth_failure: { source: 'creem', kind: 'upstream_status_' + r.status }, key: '', use_header: useHeader }`
);
code = code.replace(
  /{ tier: 'free', auth_state: 'unverified', auth_failure: \{ source: 'creem', kind: 'validate_failed'/g,
  `{ tier: 'free', auth_state: 'unverified', auth_failure: { source: 'creem', kind: 'validate_failed'`
);

// === 修改 4：在 tierMessage 后添加 deprecationHeaders ===
const deprecationFn = `\n\n/** 生成 deprecation 提示头（当 API Key 仍通过 query 参数传递时） */\nexport function deprecationHeaders(useHeader) {\n  if (useHeader) return {};\n  return {\n    'Deprecation': 'true',\n    'Sunset': '2026-10-01',\n    'X-Auth-Migration': 'API Key should be passed via Authorization: Bearer header, not as query parameter ?key=',\n  };\n}`;

if (!code.includes('deprecationHeaders')) {
  code = code.replace(
    "export function authHeaders(authState, upgradeUrl) {",
    deprecationFn + "\n\nexport function authHeaders(authState, upgradeUrl) {"
  );
}

fs.writeFileSync(upstreamPath, code);
console.log('\n✅ upstream.js 安全修复完成');
