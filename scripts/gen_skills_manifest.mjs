/**
 * skills/manifest.json + skills/README.md 表格 + agent-discovery.json 的 skills.items
 *   —— 全部从 functions/mcp.js 的 TOOLS 生成，不许手写第二份。
 *
 * 为什么有这个脚本（20260807-12 实测）：
 *   11:00 手写的 skills/manifest.json 对外声明了 5 个 mcp_tool 技能，
 *   按它写的参数**逐个真跑线上端点，5 个全部失败**：
 *     roboparts-search            query            → -32602 未知参数（真名 keyword）
 *     roboparts-compat-check      components:[]    → -32602 缺 component1_id/component2_id
 *     roboparts-recommend         count_per_category → -32602 未知参数（真名 count）
 *     roboparts-parameter-semantics parameter_semantics → -32602 未知工具（真名 get_parameter_semantics）
 *     roboparts-dataset-discovery  dataset_discovery   → -32602 未知工具（根本不存在）
 *   而这份文件正是我们请外部 Agent 框架「直接解析并自动注册工具」的机读契约。
 *   同一天 08:00 刚在 mcp.js 内部把白名单改成从 schema 推导（"杜绝两处各写一份而漂移"），
 *   三小时后就在另一个文件里手抄了第三份。闸门只锁住了一个文件，病在"任何手抄的复述"。
 *
 * 用法：
 *   node scripts/gen_skills_manifest.mjs          写入三处
 *   node scripts/gen_skills_manifest.mjs --check  只校验，有漂移则退出码 1
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CHECK = process.argv.includes('--check');

const { TOOLS } = await import(pathToFileURL(path.join(ROOT, 'functions', 'mcp.js')).href);
if (!Array.isArray(TOOLS) || !TOOLS.length) {
  console.error('❌ functions/mcp.js 未导出 TOOLS —— 真相源缺失，拒绝生成');
  process.exit(1);
}
const BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));

const META = JSON.parse(fs.readFileSync(path.join(ROOT, 'skills', 'skills.meta.json'), 'utf8'));

/* ── 1. 校验散文文件没有编造工具 ───────────────────────────────────────── */
const bogus = META.mcp_skills.filter((s) => !BY_NAME.has(s.tool));
if (bogus.length) {
  console.error('❌ skills.meta.json 声明了端点上不存在的工具，拒绝生成调不通的技能：');
  for (const b of bogus) {
    console.error(`   - ${b.name} → ${b.tool}（可用工具：${[...BY_NAME.keys()].join(', ')}）`);
  }
  process.exit(1);
}

/* ── 2. 覆盖率：端点有的工具不该在对外清单里凭空消失 ────────────────────── */
const declared = new Set(META.mcp_skills.map((s) => s.tool));
const missing = TOOLS.map((t) => t.name).filter((n) => !declared.has(n));
if (missing.length) {
  console.error(`❌ 端点提供的工具未出现在 skills.meta.json：${missing.join(', ')}`);
  console.error('   对外少报会让调用方以为没有这个能力；要么补上，要么在 meta 里显式说明。');
  process.exit(1);
}

/* ── 3. 参数从 inputSchema 推导（与运行时白名单同源） ────────────────────── */
const paramsOf = (tool) => {
  const schema = tool.inputSchema || {};
  const props = schema.properties || {};
  const required = new Set(schema.required || []);
  return Object.entries(props).map(([name, spec]) => {
    const p = {
      name,
      type: spec.type || 'string',
      required: required.has(name),
      desc: String(spec.description || '').replace(/\s+/g, ' ').trim(),
    };
    if (Array.isArray(spec.enum)) p.enum = spec.enum;
    return p;
  });
};

const oneLine = (s) => String(s || '').replace(/\s+/g, ' ').trim();

const mcpSkills = META.mcp_skills.map((s) => {
  const tool = BY_NAME.get(s.tool);
  return {
    name: s.name,
    title: s.title,
    type: 'mcp_tool',
    tool: s.tool,
    description: oneLine(tool.description),
    when_to_use: s.when_to_use,
    // 【GOAI J1】guardrails：技能的显式拒绝条件，非 Prompt。缺失则 agent 易越界。
    // 从 meta 透传，不在此处编造。
    ...(s.guardrails ? { guardrails: s.guardrails } : {}),
    params: paramsOf(tool),
  };
});

const nonMcp = META.non_mcp_skills.map((s) => {
  const { local_path, ...rest } = s;
  if (rest.datasets) rest.datasets = rest.datasets.map(({ local_path: _lp, ...d }) => d);
  return rest;
});

const manifest = {
  schema_version: '1.1',
  generated_by: 'scripts/gen_skills_manifest.mjs（从 functions/mcp.js 的 TOOLS 生成，勿手改）',
  provider: META.provider,
  summary: META.summary,
  mcp_server: META.mcp_server,
  mcp_registry_name: META.mcp_registry_name,
  skills: [...mcpSkills, ...nonMcp],
};

/* ── 4. README 表格（同源生成，避免文档与清单各说各话） ──────────────────── */
const rows = [
  ...mcpSkills.map((s) => `| \`${s.name}\` | mcp_tool | \`${s.tool}\` | ${s.when_to_use} |`),
  ...nonMcp.map((s) => `| \`${s.name}\` | ${s.type} | \`${s.endpoint.replace('https://roboparts.cc', '')}\` | ${s.when_to_use} |`),
];
const table = [
  '<!-- SKILLS-TABLE:BEGIN 由 scripts/gen_skills_manifest.mjs 生成，勿手改 -->',
  '| Skill | 类型 | 绑定 | 何时用 |',
  '|---|---|---|---|',
  ...rows,
  '<!-- SKILLS-TABLE:END -->',
].join('\n');

/* ── 5. agent-discovery.json 的 skills.items（第三处复述） ───────────────── */
const adItems = [
  ...mcpSkills.map((s) => ({ name: s.name, type: 'mcp_tool', tool: s.tool, when_to_use: s.when_to_use, ...(s.guardrails ? { guardrails: s.guardrails } : {}) })),
  ...nonMcp.map((s) => ({ name: s.name, type: s.type, endpoint: s.endpoint, when_to_use: s.when_to_use, ...(s.guardrails ? { guardrails: s.guardrails } : {}) })),
];

/* ── 6. 写入 / 校验 ─────────────────────────────────────────────────────── */
const targets = [];

targets.push({
  file: 'skills/manifest.json',
  next: JSON.stringify(manifest, null, 2) + '\n',
});

const readmePath = path.join(ROOT, 'skills', 'README.md');
let readme = fs.readFileSync(readmePath, 'utf8');
const TB = /<!-- SKILLS-TABLE:BEGIN[\s\S]*?<!-- SKILLS-TABLE:END -->/;
if (TB.test(readme)) {
  readme = readme.replace(TB, table);
} else {
  // 首次接管：替换掉原手写表格（以表头定位）
  const legacy = /\| Skill \| 类型 \| 绑定 \| 何时用 \|\n\|[-|]+\|\n(?:\|.*\|\n)+/;
  if (!legacy.test(readme)) {
    console.error('❌ skills/README.md 找不到技能表格锚点，无法接管');
    process.exit(1);
  }
  readme = readme.replace(legacy, table + '\n');
}
targets.push({ file: 'skills/README.md', next: readme });

const adPath = path.join(ROOT, 'agent-discovery.json');
const ad = JSON.parse(fs.readFileSync(adPath, 'utf8'));
if (!ad.skills) {
  console.error('❌ agent-discovery.json 缺 skills 段');
  process.exit(1);
}
// 【20260818-W2 收尾加固】total_entities 与 ai_agent_instructions 散文里的实体数是
// 静态字段，gen 只重写 skills.items，故计数漂移（710→729）曾只更新结构化字段、漏掉散文
// 「query 710 entities」，而回归 L2 又只校 total_entities 字段 → 假绿。这里从 entities.json
// 真相源现算并回写两处，regen 即保鲜，杜绝再次漂移。
{
  // 现算两样：total 与 categories 明细。
  // 明细此前是脚本不改、靠手工同步的——见下方 N13 注释。
  let truth = null;
  let counts = null;
  try {
    const doc = JSON.parse(fs.readFileSync(path.join(ROOT, 'api', 'entities.json'), 'utf8'));
    truth = doc.meta && doc.meta.total_entities;
    const arr = Array.isArray(doc.entities) ? doc.entities : [];
    // 【20260829-12】categories 明细此前只靠手工同步（本轮手工现算过一次），
    // 下次新增/迁移实体会再次脱节。闸门 regression L2 的判据是「直接对
    // entities[].category 计数」（ents_by_cat），所以这里必须现算同一量——
    // 不读派生的 meta.category_counts，避免「修好了数据、却拿派生副本写回」。
    if (arr.length) {
      counts = {};
      for (const e of arr) {
        const c = e && e.category;
        if (!c) continue;
        counts[c] = (counts[c] || 0) + 1;
      }
    }
  } catch { /* 缺真相源不阻断 regen */ }
  if (counts && Object.keys(counts).length) {
    // 保留既有键序（读起来稳定），真相源里新出现的类目追加到末尾。
    const ordered = {};
    for (const k of Object.keys(ad.categories || {})) {
      if (counts[k] !== undefined) ordered[k] = counts[k];
    }
    for (const k of Object.keys(counts)) {
      if (ordered[k] === undefined) ordered[k] = counts[k];
    }
    ad.categories = ordered;
  }
  if (typeof truth === 'number' && truth > 0) {
    ad.total_entities = truth;
    if (typeof ad.ai_agent_instructions === 'string') {
      ad.ai_agent_instructions = ad.ai_agent_instructions.replace(/\b\d+\s+entities\b/i, `${truth} entities`);
    }
  }
}
ad.skills.items = adItems;
ad.skills.generated_by = 'scripts/gen_skills_manifest.mjs（勿手改 items）';
targets.push({ file: 'agent-discovery.json', next: JSON.stringify(ad, null, 2) + '\n' });

/* ── 5.5 .well-known/agent.json（A2A Agent Card，第四处复述） ─────────────
 * 【20260807-17】404 归因埋点上线后第一批可定位死链里，`/.well-known/agent.json`
 * 赫然在列 —— 有 Agent 框架照 A2A 规范来我们门口敲门，敲的是空门。
 * 我们花了很多轮做"让 Agent 发现我们"（llms.txt / agent-discovery / MCP Registry），
 * 却漏了 Agent 侧最标准的那一个入口。
 * 生成而非手写的理由同 L1.43：这是工具清单的第四处对外复述，
 * 手抄一次就会漂移一次 —— 8/7 12:41 已经用三处手抄付过一次学费。
 */
const agentCard = {
  $comment: '由 scripts/gen_skills_manifest.mjs 从 functions/mcp.js 的 TOOLS 生成，勿手改',
  protocolVersion: '0.2.0',
  name: META.provider,
  description: oneLine(META.summary),
  url: META.mcp_server,
  preferredTransport: 'JSONRPC',
  provider: { organization: META.provider, url: 'https://roboparts.cc' },
  version: '1.1.0',
  documentationUrl: 'https://roboparts.cc/llms.txt',
  capabilities: { streaming: false, pushNotifications: false, stateTransitionHistory: false },
  securitySchemes: {},
  security: [],
  defaultInputModes: ['application/json', 'text/plain'],
  defaultOutputModes: ['application/json', 'text/plain'],
  skills: [
    ...mcpSkills.map((s) => ({
      id: s.name,
      name: s.title || s.name,
      description: oneLine(s.when_to_use),
      tags: ['robotics', 'compatibility', 'mcp'],
      inputModes: ['application/json'],
      outputModes: ['application/json'],
      ...(s.guardrails ? { guardrails: s.guardrails } : {}),
    })),
    ...nonMcp.map((s) => ({
      id: s.name,
      name: s.title || s.name,
      description: oneLine(s.when_to_use),
      tags: ['robotics', s.type],
      inputModes: ['application/json'],
      outputModes: ['application/json'],
      ...(s.guardrails ? { guardrails: s.guardrails } : {}),
    })),
  ],
};
targets.push({
  file: '.well-known/agent.json',
  next: JSON.stringify(agentCard, null, 2) + '\n',
});

let drift = 0;
for (const t of targets) {
  const abs = path.join(ROOT, t.file);
  const cur = fs.existsSync(abs) ? fs.readFileSync(abs, 'utf8') : '';
  const same = cur.replace(/\r\n/g, '\n') === t.next.replace(/\r\n/g, '\n');
  if (same) {
    console.log(`✅ ${t.file} 与真相源一致`);
    continue;
  }
  drift += 1;
  if (CHECK) {
    console.error(`❌ ${t.file} 与 functions/mcp.js 的 TOOLS 已漂移（运行 node scripts/gen_skills_manifest.mjs 重新生成）`);
  } else {
    fs.writeFileSync(abs, t.next, 'utf8');
    console.log(`✍️  ${t.file} 已重新生成`);
  }
}

if (CHECK && drift) process.exit(1);
console.log(`\n共 ${manifest.skills.length} 个技能（mcp_tool ${mcpSkills.length} / 其它 ${nonMcp.length}），全部绑定到真实存在的工具。`);
