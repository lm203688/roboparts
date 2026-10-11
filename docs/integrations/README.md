# RoboParts 接入主流 Agent 编排框架

> 目标：让任何支持 MCP 的编排框架在 **3 行内**接上 RoboParts 的 20 个只读工具。
> 端点：`https://roboparts.cc/mcp`（MCP Streamable HTTP，免鉴权只读）。
> 委派语义（A2A）：`https://roboparts.cc/a2a`（`message/send` → 映射到 MCP `tools/call`）。

| 框架 | 接入方式 | 文档 |
|---|---|---|
| LangChain / LangGraph | `langchain-mcp-adapters` | [langchain.md](./langchain.md) |
| CrewAI | `crewai-tools` MCP adapter | [crewai.md](./crewai.md) |
| n8n | MCP Client 节点 | [n8n.md](./n8n.md) |
| Agno | 原生 MCPTools | [agno.md](./agno.md) |

## 通用说明

- **免鉴权**：`/mcp` 默认只读开放，无需 key。
- **工具清单**：`search_components` / `get_component_detail` / `check_compatibility` /
  `check_co_mount` / `bom_compatibility_check` / `semantic_search` / `lint_urdf` /
  `get_research_progress` 等共 20 个。
- **口径隔离**：`check_compatibility`（四维：protocol/electrical/mechanical/software）与
  `check_co_mount` / `explain_*`（研究层三轴/三段）**口径不同，不可混用**。每个研究层工具
  的返回值都带 `caliber` 字段，请据此判断。
- **诚实边界**：厂商未声明的维度返回 `null`（无法判定），不等于不兼容。请勿把 `null` 当作 `false`。

## 一句话选择建议

- 用户问「这两个零件能不能配」→ `check_compatibility`
- 用户问「这台机器人能不能同时装 A 和 B」→ `check_co_mount`
- 用户问「补哪条数据最值 / 这个项目做到几成」→ `explain_*` / `get_research_progress`
