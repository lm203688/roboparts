/**
 * A2A (Agent2Agent) 桥接端点 —— 兑现 .well-known/agent-card.json 的 supportedInterfaces 声明。
 *
 *   POST /a2a   （JSON-RPC 2.0，A2A v1.0 语义）
 *
 * 为什么需要它：
 *   MCP 暴露**工具**给 LLM 调用（client-to-tool），A2A 暴露**agent**给另一个 agent 委派
 *   （client-to-agent）。两者互补，不是替代。此前 agent-card 已声明 A2A，但端点是 MCP
 *   （只认 tools/call），外部 agent 想按 A2A 语义委派只能迂回 —— 语义不符。
 *   本端点补上这一层：把 A2A 的 `message/send` 映射到 MCP 的 `tools/call`。
 *
 * 支持的方法：
 *   · message/send （A2A v1.0）／别名 SendMessage
 *   · message/stream → 本 agent 不支持流式（capabilities.streaming=false），如实报错
 *   · 其它 → -32601 Method not found
 *
 * 消息约定（**诚实边界**：本桥接不做自然语言意图解析——那需要 LLM，本层不引入）：
 *   调用方在 message 的 parts 里放一个 data part：{ "tool": "<MCP 工具名>", "arguments": {...} }。
 *   桥接据此转 tools/call。若未给 tool，则返回能力清单（skills + 如何委派），不猜意图。
 *
 * 与 MCP 端点共用**同一份**工具表（从 mcp.js 导入 TOOLS），避免两处各写一份工具名。
 */
import { TOOLS } from './mcp.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

const TOOL_NAMES = new Set(TOOLS.map((t) => t.name));

function rpcResult(id, result) {
  return { jsonrpc: '2.0', id, result };
}
function rpcError(id, code, message, data) {
  return { jsonrpc: '2.0', id, error: { code, message, ...(data ? { data } : {}) } };
}

/** 从 A2A message 的 parts 里抽出结构化工具调用 {tool, arguments}。 */
function extractToolCall(message) {
  const parts = (message && message.parts) || [];
  for (const p of parts) {
    // A2A v1.0 data part：{ kind: 'data', data: {...} }
    const d = p && (p.data !== undefined ? p.data : (p.kind === 'data' ? p.data : null));
    if (d && typeof d === 'object' && typeof d.tool === 'string') {
      return { tool: d.tool, arguments: d.arguments || {} };
    }
  }
  return null;
}

/** 能力清单：未给 tool 时的回退响应（不猜意图，只给可执行的下一步）。 */
function capabilitiesReply() {
  return {
    kind: 'message',
    role: 'agent',
    parts: [
      {
        kind: 'text',
        text:
          'RoboParts A2A 端点已就绪。本 agent 不解析自然语言意图（无内置 LLM）；'
          + '请在 message 的 data part 里给出 {"tool": "<工具名>", "arguments": {...}}。'
          + `可用工具共 ${TOOLS.length} 个，例如 search_components / check_compatibility / check_co_mount。`,
      },
      {
        kind: 'data',
        data: {
          tools: TOOLS.map((t) => ({ name: t.name, description: t.description.slice(0, 120) })),
          mcp_endpoint: 'https://roboparts.cc/mcp',
          note: '也可直接走 MCP tools/call；本端点等价于其 A2A 语义封装。',
        },
      },
    ],
  };
}

export async function onRequestPost(context) {
  const { request } = context;
  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify(rpcError(null, -32700, 'Parse error：请求体不是合法 JSON')),
      { status: 400, headers: corsHeaders },
    );
  }

  const { id = null, method, params } = body || {};

  if (method === 'message/stream') {
    return new Response(
      JSON.stringify(rpcError(id, -32601, '不支持流式：capabilities.streaming=false')),
      { status: 200, headers: corsHeaders },
    );
  }
  if (method !== 'message/send' && method !== 'SendMessage') {
    return new Response(
      JSON.stringify(rpcError(id, -32601, `Method not found: ${method}`)),
      { status: 200, headers: corsHeaders },
    );
  }

  const message = (params && (params.message || params)) || {};
  const call = extractToolCall(message);

  // 未给工具 → 返回能力清单（不猜意图）
  if (!call) {
    return new Response(
      JSON.stringify(rpcResult(id, { kind: 'message', message: capabilitiesReply() })),
      { status: 200, headers: corsHeaders },
    );
  }

  // 给了工具名但不在表内 → 明确报错，不静默
  if (!TOOL_NAMES.has(call.tool)) {
    return new Response(
      JSON.stringify(rpcError(id, -32602, `未知工具: ${call.tool}`,
        { known_tools: [...TOOL_NAMES] })),
      { status: 200, headers: corsHeaders },
    );
  }

  // 转 MCP tools/call（**自请求**同一份实现，杜绝桥接与 MCP 分叉）
  try {
    const mcpUrl = new URL('/mcp', request.url);
    const r = await fetch(mcpUrl.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'tools/call',
        params: { name: call.tool, arguments: call.arguments },
      }),
    });
    const j = await r.json();
    const text = (j && j.result && j.result.content && j.result.content[0] && j.result.content[0].text) || '';
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* 非 JSON 就原样透传文本 */ }
    return new Response(
      JSON.stringify(rpcResult(id, {
        kind: 'message',
        role: 'agent',
        parts: [
          parsed
            ? { kind: 'data', data: parsed }
            : { kind: 'text', text: String(text).slice(0, 8000) },
        ],
        metadata: { bridged_tool: call.tool, source: 'mcp:tools/call' },
      })),
      { status: 200, headers: corsHeaders },
    );
  } catch (e) {
    return new Response(
      JSON.stringify(rpcError(id, -32603, `桥接到 MCP 失败: ${String((e && e.message) || e)}`)),
      { status: 200, headers: corsHeaders },
    );
  }
}
