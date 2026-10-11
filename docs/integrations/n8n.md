# n8n 接入 RoboParts MCP

> 节点：**MCP Client**（n8n ≥ 1.6x，内置）

## 配置

1. 新建 **MCP Client** 节点 → Credential 选 **HTTP Streamable**。
2. URL 填 `https://roboparts.cc/mcp`（免鉴权，Header 留空）。
3. Node 选 **List Tools** → 执行，可见 20 个工具。
4. 把 Node 切到 **Execute Tool**，选 `check_compatibility`，参数：
   - `a` = `ACT-001`，`b` = `ACT-002`

## 示例工作流（JSON 导入）

```json
{
  "nodes": [
    { "parameters": { "resource": "tool", "operation": "listTools" },
      "name": "RoboParts 工具清单", "type": "n8n-nodes-base.mcpClient", "typeVersion": 1,
      "position": [240, 300] },
    { "parameters": {
        "resource": "tool", "operation": "executeTool",
        "toolName": "check_co_mount",
        "toolParameters": "={{ { \"host\": \"HUB-031\", \"a\": \"ACT-028\", \"b\": \"SENS-047\" } }}"
      },
      "name": "共装查询", "type": "n8n-nodes-base.mcpClient", "typeVersion": 1,
      "position": [480, 300] }
  ]
}
```

## 要点

- n8n 侧无需代码；工具返回 JSON 可直接进后续节点（判断 `verdict` 走分支）。
- 典型场景：**定时巡检** —— 每天拉取 `get_research_progress`，把完成度写入告警/看板。
- 若返回 `error_kind`，说明参数或数据问题；`unknown` 是**有效答案**（数据不足），不是错误。
