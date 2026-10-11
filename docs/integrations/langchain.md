# LangChain / LangGraph 接入 RoboParts MCP

> 依赖：`pip install langchain-mcp-adapters langgraph langchain-openai`

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

async def main():
    client = MultiServerMCPClient({
        "roboparts": {
            "url": "https://roboparts.cc/mcp",   # MCP Streamable HTTP，免鉴权只读
            "transport": "streamable_http",
        }
    })
    tools = await client.get_tools()             # 自动拉取 20 个工具
    agent = create_react_agent(ChatOpenAI(model="gpt-4o"), tools)

    out = await agent.ainvoke({
        "messages": [{"role": "user",
                      "content": "UR5e 能不能同时装一个夹爪和六维力传感器？"}]
    })
    print(out["messages"][-1].content)

asyncio.run(main())
```

## 要点

- `get_tools()` 会读取 `tools/list`，工具描述里已写明「何时用哪个」，模型可自行选择。
- 想让模型优先用共装查询：在 system prompt 里写
  「涉及『同时装两个器件』的问题，用 `check_co_mount`；涉及『A 插 B』用 `check_compatibility`」。
- 研究层工具（`explain_*` / `check_co_mount`）返回值带 `caliber` 字段，
  建议在 prompt 里要求模型**转述 caliber**，避免与四维口径混淆。
