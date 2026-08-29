/**
 * skills/manifest.json 功能性验证 —— **按清单写的那样，真跑一遍每一个技能**。
 *
 * 判据故意不看源码像不像：20260807-11 手写的 manifest 每一项都"长得对"
 *（有 tool、有 params、有 desc），但按它调用时 5/5 全部 -32602。
 * 唯一靠得住的判据是：把 manifest 里写的参数原样发给 handler，看端点认不认。
 *
 * 断言：
 *   ① manifest 里每个 mcp_tool 的 tool 名都出现在 tools/list 里
 *   ② 按 manifest 声明的参数构造调用，不得返回 -32602
 *      （-32602 = 未知工具 / 未知参数 / 缺必填，三者都意味着"照文档调用会失败"）
 *   ③ manifest 声明的每个参数名都在该工具 inputSchema.properties 里
 *   ④ 该工具的必填参数不得在 manifest 里缺席（否则调用方不知道要传）
 *   ⑤ 阳性对照：故意加一个未知参数必须被拒 —— 证明 ② 不是因为端点根本不校验才绿
 *
 * 用法：node scripts/verify_skills_manifest.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const { onRequestPost } = await import(pathToFileURL(path.join(ROOT, 'functions', 'mcp.js')).href);

const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'skills', 'manifest.json'), 'utf8'));

const ctx = (body) => ({
  request: new Request('https://roboparts.cc/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }),
  env: {},               // 空壳：参数校验必须在取数之前完成
  waitUntil: () => {},
});

const rpc = async (body) => (await onRequestPost(ctx(body))).json();

const results = [];
const t = (name, pass, detail) => {
  results.push(pass);
  console.log(`${pass ? '✅' : '❌'} ${name}${detail ? ' —— ' + detail : ''}`);
};

// 端点自报的工具表（真相源的运行时投影）
const listed = await rpc({ jsonrpc: '2.0', id: 0, method: 'tools/list' });
const tools = listed?.result?.tools || [];
const schemaOf = new Map(tools.map((x) => [x.name, x.inputSchema || {}]));
t('tools/list 可用', tools.length > 0, `实得 ${tools.length} 个工具`);

// 按类型/enum 造一个"形状正确"的最小值；目的是通过参数校验，不是取到真数据
const sample = (p) => {
  if (Array.isArray(p.enum) && p.enum.length) return p.enum[0];
  switch (p.type) {
    case 'number': case 'integer': return 1;
    case 'boolean': return false;
    case 'array': return [];
    case 'object': return {};
    default:
      // 需要真实 ID 的参数给一个库内确实存在的值，避免把"找不到"混进参数校验结论
      return /(^|_)id$/.test(p.name) ? 'ACT-001' : 'test';
  }
};

const mcpSkills = manifest.skills.filter((s) => s.type === 'mcp_tool');
t('manifest 含 mcp_tool 技能', mcpSkills.length > 0, `实得 ${mcpSkills.length} 个`);

for (const s of mcpSkills) {
  const schema = schemaOf.get(s.tool);

  // ① 工具真的存在
  t(`[${s.name}] 绑定的工具 ${s.tool} 存在于 tools/list`, !!schema,
    schema ? '' : `端点可用工具：${[...schemaOf.keys()].join(', ')}`);
  if (!schema) continue;

  const props = schema.properties || {};
  const required = schema.required || [];
  const declaredNames = (s.params || []).map((p) => p.name);

  // ③ 声明的参数名都真实存在
  const unknown = declaredNames.filter((n) => !(n in props));
  t(`[${s.name}] 声明的参数名全部存在于 inputSchema`, unknown.length === 0,
    unknown.length ? `不存在: ${unknown.join(', ')}；真实参数: ${Object.keys(props).join(', ')}` : '');

  // ④ 必填参数不得漏报
  const missReq = required.filter((n) => !declaredNames.includes(n));
  t(`[${s.name}] 必填参数未在清单中漏报`, missReq.length === 0,
    missReq.length ? `漏报必填: ${missReq.join(', ')}` : '');

  // ② 照 manifest 调用，端点必须认
  const args = {};
  for (const p of s.params || []) {
    if (p.required) args[p.name] = sample(p);
  }
  // 无必填参数时也带一个可选参数，确保"清单里写的参数名"真被验证到
  if (!Object.keys(args).length && (s.params || []).length) {
    const p = s.params[0];
    args[p.name] = sample(p);
  }
  const r = await rpc({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: s.tool, arguments: args } });
  t(`[${s.name}] 照清单调用不返回 -32602`, r?.error?.code !== -32602,
    r?.error?.code === -32602 ? `args=${JSON.stringify(args)} → ${r.error.message}` : `args=${JSON.stringify(args)}`);
}

// ⑤ 阳性对照：端点确实在校验（否则 ② 全绿毫无意义）
const guard = await rpc({
  jsonrpc: '2.0', id: 2, method: 'tools/call',
  params: { name: 'search_components', arguments: { __definitely_not_a_param__: 1 } },
});
t('阳性对照：端点确实会拒绝未知参数（否则上面全绿是假绿）',
  guard?.error?.code === -32602, `实得 code=${guard?.error?.code ?? '无 error'}`);

const pass = results.filter(Boolean).length;
console.log(`\n${pass}/${results.length} 通过`);
process.exit(pass === results.length ? 0 : 1);
