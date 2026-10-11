/**
 * .well-known/agent-card.json  ——  A2A v1.0 Agent Card 生成器
 *
 * 为什么有这个脚本（2026-10-08）：
 *   A2A v1.0 于 2026-03 发布并捐给 Linux Foundation 治理，Google/Microsoft/
 *   Salesforce 均已原生支持。它规定 agent 必须在
 *   `/.well-known/agent-card.json` 上放一份自描述清单，供其他 agent 发现并
 *   委派任务。此前本仓只有 `.well-known/agent.json`（A2A v0.2 旧路径，
 *   v0.3 起已废弃），意味着 v1.0 client 根本扫不到我们。
 *
 *   本脚本从两个已存在的单一真相源派生，杜绝手抄：
 *     - skills/skills.meta.json      （人写的散文：name/title/when_to_use/guardrails）
 *     - functions/mcp.js 的 TOOLS    （工具名 + 参数 schema）
 *
 *   A2A v1.0 要求 protocolBinding 只能取 {JSONRPC, GRPC, HTTPJSON}，且 A2A
 *   JSON-RPC 与 MCP Streamable HTTP 都建立在同一底层：JSON-RPC 2.0 over HTTPS。
 *   我们把 RoboParts MCP 端点作为 JSONRPC 接口声明出去，同时**在 description
 *   与 supportedInterfaces 的 note 里如实标注**「当前实现为 MCP Streamable
 *   HTTP；A2A SendMessage 语义的桥接端点将在 v0.2 上线」——不谎报能力，也不
 *   让 v1.0 client 扫不到我们。
 *
 * 用法：
 *   node scripts/gen_agent_card.mjs          写入
 *   node scripts/gen_agent_card.mjs --check  只校验，有漂移则退出码 1
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(path.resolve(fileURLToPath(import.meta.url))));
const CHECK = process.argv.includes('--check');
const OUT = path.join(ROOT, '.well-known', 'agent-card.json');

const META = JSON.parse(fs.readFileSync(path.join(ROOT, 'skills', 'skills.meta.json'), 'utf8'));
const SERVER = JSON.parse(fs.readFileSync(path.join(ROOT, 'server.json'), 'utf8'));
const VERSION = SERVER.version || META.version || '0.0.0';

/* 从 functions/mcp.js 拿 TOOLS（唯一真相源） */
const { TOOLS } = await import(pathToFileURL(path.join(ROOT, 'functions', 'mcp.js')).href);
if (!Array.isArray(TOOLS) || !TOOLS.length) {
  console.error('❌ functions/mcp.js 未导出 TOOLS —— 拒绝生成');
  process.exit(1);
}
const BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));

/* ── 校验 meta 里的工具名都在 TOOLS 里存在 ── */
const bogus = META.mcp_skills.filter((s) => !BY_NAME.has(s.tool));
if (bogus.length) {
  console.error(`❌ skills.meta.json 声明了 TOOLS 中不存在的工具：`);
  bogus.forEach((s) => console.error(`   · ${s.tool} (${s.name})`));
  process.exit(1);
}

/* ── 拼装 skills[] ── */
/* tags 采用三级：品类前缀 + 通用标签。所有 skills 共享底层标签，
 *   再由 skill 名称前缀推出更细的标签，让 A2A client 能按标签过滤。 */
const BASE_TAGS = ['robotics', 'robot-parts', 'compatibility', 'vendor-neutral'];

function deriveTags(name) {
  const set = new Set(BASE_TAGS);
  if (name.includes('compat')) set.add('compatibility-check');
  if (name.includes('bom')) set.add('bom');
  if (name.includes('co-mount') || name.includes('compose')) set.add('co-mount');
  if (name.includes('standard') || name.includes('audit')) set.add('standards-audit');
  if (name.includes('urdf')) set.add('urdf');
  if (name.includes('evidence') || name.includes('explain')) set.add('evidence-traceability');
  if (name.includes('research')) set.add('research-progress');
  if (name.includes('recommend') || name.includes('semantic')) set.add('selection');
  return [...set];
}

const skills = META.mcp_skills.map((s) => {
  const tool = BY_NAME.get(s.tool);
  return {
    id: s.name,                       // A2A v1.0 要求 id 稳定，改动视作 breaking
    name: s.title,                    // 人类可读
    description: s.when_to_use,       // A2A client 拿这个判断能不能委派
    tags: deriveTags(s.name),
    inputModes: ['application/json'],
    outputModes: ['application/json'],
    /* examples 是 A2A v1.0 允许的示例文本，帮 client 快速理解 skill 干什么 */
    examples: [s.when_to_use.replace(/：$/, '').slice(0, 100)],
    /* 内部字段：不写进公开 card，仅用于本地验证 */
    _tool: tool.name,
  };
});

/* ── 拼 card ── */
const card = {
  $schema: 'https://spec.agentcard.dev/schema-v1.0.json',
  protocolVersion: '1.0',
  name: 'RoboParts',
  description:
    '厂商中立的机器人零部件兼容性数据层。20 个品类、868 条实体，提供协议/电气/机械/ROS2 四维兼容性判定、BOM 矩阵检查、共装关系判定（A↔宿主↔B）、标准合规审计、URDF 校验与研究进度溯源。既不生产也不转售任何零部件，兼容性结论基于厂商公开声明字段的规则推断，未声明维度显式标为 unknown。',
  version: VERSION,
  provider: {
    organization: 'RoboParts',
    url: 'https://roboparts.cc',
    supportUrl: 'https://roboparts.cc/api/register',
  },
  documentationUrl: 'https://roboparts.cc/llms.txt',
  contactUrl: 'https://github.com/lm203688/roboparts/issues',
  /* supportedInterfaces 是 A2A v1.0 的必填。protocolBinding 枚举
   *   {JSONRPC, GRPC, HTTPJSON}。RoboParts 端点底层是 JSON-RPC 2.0
   *   over HTTPS（MCP Streamable HTTP 与 A2A JSON-RPC 共享这一层），
   *   因此如实声明为 JSONRPC。
   *
   *   【20261008 更新】A2A SendMessage 桥接端点 /a2a 已上线（functions/a2a.js）：
   *   它把 A2A message/send 映射到 MCP tools/call，与 /mcp 共用同一份工具表。
   *   故此处**新增** /a2a 接口，并把 /mcp 的 note 改为「工具调用走 MCP」。
   *   诚实边界保留：本桥接不解析自然语言意图（不引入 LLM），
   *   委派方需在 data part 给出 {tool, arguments}。 */
  supportedInterfaces: [
    {
      url: 'https://roboparts.cc/a2a',
      protocolBinding: 'JSONRPC',
      protocolVersion: '1.0',
      note:
        'A2A v1.0 message/send 桥接端点。把 A2A 委派映射到 MCP tools/call（与 /mcp 共用同一份工具表）。不解析自然语言意图——请在 message 的 data part 给出 {"tool":"<名>","arguments":{...}}；未给 tool 时返回能力清单。',
    },
    {
      url: 'https://roboparts.cc/mcp',
      protocolBinding: 'JSONRPC',
      protocolVersion: '1.0',
      note:
        'MCP Streamable HTTP 端点（底层 JSON-RPC 2.0 over HTTPS）。调用工具走 MCP tools/call；若需 A2A 语义委派，改用 /a2a。',
    },
  ],
  capabilities: {
    /* 诚实标注：不做流式、不做推送、不做状态历史 —— 全部只读、同步返回。 */
    streaming: false,
    pushNotifications: false,
    stateTransitionHistory: false,
  },
  defaultInputModes: ['application/json'],
  defaultOutputModes: ['application/json'],
  skills: skills.map(({ _tool, ...s }) => s), /* 剥掉内部字段 */
  /* security 字段：A2A v1.0 允许为空数组表示无认证（只读场景） */
  securitySchemes: {},
  security: [],
  /* 边界声明：让调用 agent 在委派前就知道本 agent 的责任范围 */
  boundaries: [
    '只读、免鉴权、不设 cookie、不存储调用方数据',
    '兼容性结论基于厂商公开声明字段的规则推断，非实验室实测',
    '厂商未声明的维度记为 unknown（无法判定），不计入兼容也不计入不兼容',
    '与任何零部件厂商无商业绑定；不生产、不代理、不转售任何零部件',
    'A2A message/send 桥接已上线（/a2a），但不解析自然语言意图——委派方需显式给出工具名与参数',
  ],
};

/* ── 输出 ── */
const rendered = JSON.stringify(card, null, 2) + '\n';
if (CHECK) {
  const existing = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8') : null;
  if (existing === rendered) {
    console.log('✓ .well-known/agent-card.json 一致（A2A v1.0 card 无漂移）');
    process.exit(0);
  }
  console.error('❌ .well-known/agent-card.json 有漂移，请运行 gen_agent_card.mjs 刷新');
  process.exit(1);
}
fs.writeFileSync(OUT, rendered);
console.log(`✓ 写入 .well-known/agent-card.json（${skills.length} skills，protocolVersion=1.0）`);
