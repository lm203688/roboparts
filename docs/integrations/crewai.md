# CrewAI 接入 RoboParts MCP

> 依赖：`pip install crewai crewai-tools[mcp]`

```python
from crewai import Agent, Task, Crew
from crewai_tools import MCPServerAdapter

# 用 with 语句管理 MCP 连接生命周期
with MCPServerAdapter({
    "url": "https://roboparts.cc/mcp",
    "transport": "streamable-http",
}) as tools:                       # tools 即 RoboParts 的 20 个工具

    engineer = Agent(
        role="机器人集成工程师",
        goal="确认跨厂商零件能否装配到一起",
        backstory="你负责在打样前排除接口不兼容风险",
        tools=tools,
        verbose=True,
    )

    task = Task(
        description=(
            "查询 UR5e 工具侧能否同时装夹爪 ACT-028 与传感器 SENS-047；"
            "若装不下，说明是工程约束（port_exhausted）还是数据不足（unknown），"
            "并给出替代建议。"
        ),
        expected_output="裁决结论 + 判据 + 证据出处 + 替代建议",
        agent=engineer,
    )

    crew = Crew(agents=[engineer], tasks=[task])
    print(crew.kickoff())
```

## 要点

- `MCPServerAdapter` 必须用 `with` 上下文（连接随退出释放）。
- 工具名与 LangChain 侧一致，模型据描述选择。
- 需要「能不能共装」类答案时，明确要求用 `check_co_mount` 并转述 `verdict` 四态
  （mountable / port_exhausted / type_error / unknown）。
