/**
 * functions/mcp.js 未知参数处理 —— 功能性验证（真跑 handler，不是看源码长得像不像）
 *
 * 背景（20260807-08 实测）：
 *   search_components{"query":"harmonic reducer"}  → total_matched=685，首条 ACT-001
 *   search_components{"query":"zzzznonexistentxyz"} → **完全相同**
 * 因为筛选参数叫 keyword，`query` 是未知键，旧实现静默忽略 → 退化成"全库浏览"，
 * 而调用方看到的是「共匹配 685 条」这样一句**读起来像成功**的话。
 *
 * 本脚本直接 import handler 并构造 JSON-RPC 请求跑一遍，断言四条性质：
 *   ① 未知参数被拒（-32602），且带 did_you_mean: query → keyword
 *   ② 合法参数不被误伤（不得返回 -32602）
 *   ③ 不传任何参数的"浏览全库"仍然合法（这是设计意图，不能一并封掉）
 *   ④ 拒绝发生在取数之前（env 为空壳也能拿到 -32602，证明没白跑一趟数据源）
 *
 * 用法：node scripts/verify_mcp_args.mjs
 */
import { onRequestPost } from '../functions/mcp.js';

const ctx = (body) => ({
  request: new Request('https://roboparts.cc/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }),
  env: {},                 // 空壳：未知参数校验必须在取数之前完成
  waitUntil: () => {},
});

const call = async (args, tool = 'search_components') => {
  const res = await onRequestPost(
    ctx({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: tool, arguments: args } }));
  return await res.json();
};

const results = [];
const t = (name, pass, detail) => {
  results.push(pass);
  console.log(`${pass ? '✅' : '❌'} ${name}${detail ? ' —— ' + detail : ''}`);
};

// ① 未知参数被拒 + 给出正确的参数名
const r1 = await call({ query: 'harmonic reducer' });
t('未知参数 query 被拒为 -32602',
  r1?.error?.code === -32602,
  `实得 code=${r1?.error?.code ?? '无 error'}，message=${(r1?.error?.message || '').slice(0, 40)}`);
const dym = r1?.error?.data?.did_you_mean || [];
t('错误里给出 did_you_mean: query → keyword',
  dym.some((s) => String(s).includes('query') && String(s).includes('keyword')),
  `实得 ${JSON.stringify(dym)}`);
t('错误里列出全部可接受参数',
  (r1?.error?.data?.accepted_parameters || []).includes('keyword'),
  `实得 ${JSON.stringify(r1?.error?.data?.accepted_parameters)}`);

// ①b 关键：拒绝时**绝不能**顺带把全库结果一起返回
const raw1 = JSON.stringify(r1);
t('拒绝时未返回任何数据（不得出现 total_matched / ACT-001）',
  !raw1.includes('total_matched') && !raw1.includes('ACT-001'));

// ② 合法参数不被误伤（env 为空会在取数阶段失败，但那不该是 -32602）
const r2 = await call({ keyword: 'harmonic', limit: 2 });
t('合法参数 keyword/limit 不被误判为未知参数',
  r2?.error?.code !== -32602,
  `实得 code=${r2?.error?.code ?? '(无 error，已进入取数阶段)'}`);

// ③ 无参数浏览全库仍然合法 —— 这是设计意图，修 ① 时不能顺手封死
const r3 = await call({});
t('无参数调用不被拒（浏览全库是合法用法）',
  r3?.error?.code !== -32602,
  `实得 code=${r3?.error?.code ?? '(无 error，已进入取数阶段)'}`);

// ④ 其他工具同样受保护（校验挂在派发层，不是只给 search 打补丁）
const r4 = await call({ component_id: 'ACT-001' }, 'get_component_detail');
t('get_component_detail 的未知参数同样被拒（校验在派发层，非单点补丁）',
  r4?.error?.code === -32602,
  `实得 code=${r4?.error?.code ?? '无 error'}`);

const passed = results.filter(Boolean).length;
console.log(`\n${passed}/${results.length} 通过`);
process.exit(passed === results.length ? 0 : 1);
