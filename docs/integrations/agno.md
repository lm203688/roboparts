# Agno 接入 RoboParts MCP

> 依赖：`pip install agno openai`

```python
from agno.agent import Agent
from agno.tools.mcp import MCPTools
from agno.models.openai import OpenAIChat
import asyncio

async def main():
    async with MCPTools(
        url="https://roboparts.cc/mcp",   # MCP Streamable HTTP，免鉴权只读
        transport="streamable-http",
    ) as mcp_tools:
        agent = Agent(
            model=OpenAIChat(id="gpt-4o"),
            tools=[mcp_tools],
            instructions=[
                "涉及『A 插 B』用 check_compatibility；",
                "涉及『同时装两个器件』用 check_co_mount；",
                "研究层工具返回的 caliber 字段必须原样转述。",
            ],
            markdown=True,
        )
        await agent.aprint_response(
            "这台 UR3e 能同时装夹爪和力传感器吗？如果不能，是装不下还是数据不足？"
        )

asyncio.run(main())
```

## 要点

- `MCPTools` 支持 `transport="streamable-http"`，与 hosted MCP 端点直连。
- Agno 会把每个 MCP 工具展开为可调用工具；`instructions` 用于约束口径选择。
- 需要把结论接入自有系统时，直接调 REST 更轻：
  `GET /api/co-mount?host=HUB-031&a=ACT-028&b=SENS-047`（与 MCP `check_co_mount` 同一份判定逻辑）。
