# RoboParts MCP Server

RoboParts MCP (Model Context Protocol) Server 是一个标准化接口，允许 AI Agent（如 Claude、GPT 等）通过 MCP 协议查询机器人零部件数据。AI Agent 可以搜索零部件、获取详细信息、检查兼容性、获取应用推荐并导出 BOM 清单。

> **请按包名甄别**：本包是 roboparts.cc 官方发布的 MCP Server，包名
> **`roboparts-mcp-server`**，主页 https://roboparts.cc 。
> npm 上另有一个名为 `roboparts-mcp` 的第三方包（作者 Crawde，指向 robopartsai.com），
> 与本项目无关。

## 项目介绍

本 MCP Server 基于 `@modelcontextprotocol/sdk` 构建，使用 stdio 传输协议，
启动时从 **https://roboparts.cc/api** 拉取全部数据（**868 条实体 / 20 个品类**），
为 AI Agent 提供结构化的机器人零部件查询能力。

数据实时取自线上，不随包版本过期。若数据源不可达，服务会**明确报错退出**，
而不是以空库启动、对每次查询都回「未找到」—— 静默失败比崩溃更难排查。
内网或离线环境可用环境变量 `ROBOPARTS_API_BASE` 指向自建镜像。

> 📖 **完整工具文档：** [docs/mcp-tools.md](../docs/mcp-tools.md)（含 26 个生产工具的
> 完整参数、返回、示例与口径纪律）。本 README 仅列本地子集（16 个），桥接层工具
> （`explain_*` / `check_co_mount` / `get_body_binding` 等）仅在生产端点提供。

### 支持的数据品类（20 类 / 868 条，与官网口径一致）

| 品类 | 标识 | 条数 |
|------|------|------|
| 执行器 | actuators | 222 |
| 芯片 | chips | 108 |
| 机器人平台 | platforms | 106 |
| 传感器 | sensors | 95 |
| 通信协议 | protocols | 64 |
| 机器人 AI 模型 | robot_ai_models | 44 |
| 数据采集 | data_acquisition | 43 |
| 大语言模型 | llms | 42 |
| 接口 | interfaces | 37 |
| 柔性执行器 | flexible_actuators | 21 |
| 夹爪 | grippers | 23 |
| 仿生机构 | bionic_mechanisms | 17 |
| 减速器 | reducers | 14 |
| 控制器 | controllers | 4 |
| 结构件 | structural | 3 |
| 线缆 | cables | 2 |
| 电源 | power | 2 |
| PCB | pcb | 2 |
| 连接器 | connectors | 2 |
| 一体化关节 | integrated_joints | 1 |

（条数为 `api/entities.json` 现算，以真相源为准。真相源会漂移，本表随数据刷新可能滞后；
`npm run` 与 `npx roboparts-mcp-server` 启动时都从线上拉最新数据。）

### 我们不隐瞒的三件事

1. **参数为厂商公开声明值，未经我方实测复现**，请勿当作实测值用于最终选型。
2. **跨厂商可直接横向比较的 A 级条目目前为 0 条。** 各家参数口径（如转速的定义方式）
   尚不统一，我们宁可如实标注，也不做一个看起来整齐、实则不可比的排行榜。
3. **机械接口有明确线索的占少数。** 这是行业普遍未公开的部分，我们在补，但目前确实很少。
   详见 `get_standard_audit` 与 `check_compatibility` 的 verdict_reason。

**中立声明**：RoboParts 不生产、不销售、不代理任何零部件，与所收录厂商无销售利益关系。

## 安装说明

### 前置条件

- Node.js >= 18.0.0（需要原生 `fetch`）
- 可访问 https://roboparts.cc（或自建镜像）

### 安装

**推荐：远程接入，零安装、无需 API Key。** 无须本包即可使用全部工具：

```json
{
  "mcpServers": {
    "roboparts": { "url": "https://roboparts.cc/mcp" }
  }
}
```

Claude Desktop 暂不原生支持远程 MCP，经开源桥接包转接：

```bash
npx -y mcp-remote https://roboparts.cc/mcp
```

> ⚠️ **`npx roboparts-mcp-server` 目前不可用**：该包尚未发布到 npm
> （registry 实测返回 404），请勿按旧版说明操作。需本地运行见下方「从源码运行」。

### 从源码运行（离线 / 二次开发）

```bash
git clone https://github.com/lm203688/roboparts.git
cd roboparts/mcp-server
node index.js
```

## 配置说明

### 在 Claude Desktop 中配置

编辑 Claude Desktop 配置文件：

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

添加以下配置：

```json
{
  "mcpServers": {
    "roboparts": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://roboparts.cc/mcp"]
    }
  }
}
```

离线 / 内网镜像场景（从源码运行，指向自建镜像）：

```json
{
  "mcpServers": {
    "roboparts": {
      "command": "node",
      "args": ["/path/to/roboparts/mcp-server/index.js"],
      "env": { "ROBOPARTS_API_BASE": "https://your-mirror.example/api" }
    }
  }
}
```

> 如果使用 npx，也可以配置为：
> ```json
> {
>   "mcpServers": {
>     "roboparts": {
>       "command": "npx",
>       "args": [
>         "C:\\Users\\xing\\Desktop\\robopart\\mcp-server\\index.js"
>       ]
>     }
>   }
> }
> ```

配置完成后重启 Claude Desktop，即可在对话中使用 RoboParts 工具。

### 在其他 MCP 客户端中配置

任何支持 MCP 协议的客户端均可通过 stdio 方式连接本 Server。启动命令：

```bash
node index.js
# 或
npm start
```

## 可用工具列表

### 1. search_components - 搜索机器人零部件

搜索零部件，支持按品类、关键词、数量筛选。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| category | string | 否 | 品类：actuators/sensors/chips/protocols/platforms/llms/interfaces |
| keyword | string | 否 | 搜索关键词（匹配名称、厂商、类型、描述等） |
| limit | number | 否 | 返回数量限制，默认 10 |

**返回：** 零部件数组（id, name, category, manufacturer, key_specs）

### 2. get_component_detail - 获取零部件详情

获取单个零部件的完整规格信息。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 零部件 ID，如 "ACT-001" |
| category | string | 是 | 品类 |

**返回：** 完整的零部件数据对象

### 3. check_compatibility - 检查兼容性

检查两个零部件之间的兼容性，基于协议、接口、电压等维度。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| component1_id | string | 是 | 零件 1 ID |
| component1_category | string | 是 | 零件 1 品类 |
| component2_id | string | 是 | 零件 2 ID |
| component2_category | string | 是 | 零件 2 品类 |

**兼容性检查规则：**

- **执行器 + 芯片**：检查协议匹配（如 DYNAMIXEL Protocol 需要 RS485/TTL 接口）+ 电压范围
- **芯片 + 传感器**：检查接口兼容（如 I2C/SPI/UART/USB）
- **协议 + 接口**：检查物理层兼容性（如 EtherCAT 需要以太网接口）
- **通用检查**：应用场景匹配、ROS2 支持情况

**返回：** 兼容性报告（compatible: boolean, reasons: string[], warnings: string[]）

### 4. recommend_for_application - 应用场景推荐

根据应用场景和预算推荐最优零部件组合。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| application | string | 是 | 应用场景：humanoid/quadruped/robot_arm/amr/industrial |
| budget | number | 否 | 预算上限（CNY） |
| count | number | 否 | 每个品类推荐数量，默认 3 |

**返回：** 推荐组合（actuators, sensors, chips, controllers 各自 top 推荐）

### 5. export_bom - 导出 BOM 清单

从选定的零部件列表导出 BOM（Bill of Materials）清单，计算总成本并提供供应商建议。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_name | string | 是 | 项目名称 |
| items | array | 是 | 零部件列表，每项包含 {id, category, quantity} |

**返回：** BOM 对象（项目名、总成本 USD/CNY、总模块数、items 详情、供应商建议）

### 6-11. MCP 双版本 + Trace 回放（v1.2.0 新增）

审计报告 §4.4 要求：「MCP 要做双版本适配与可回放任务……工具输入输出全部引用
project_id + revision + evidence_version；长任务返回任务句柄、进度、可取消状态和
最终结果；把'为什么 unknown''哪条证据导致冲突'作为标准工具，而非仅靠自然语言解释；
为每次外部 Agent 调用保存可去敏回放的评估轨迹」。本节六个工具对应这一要求。

| # | 工具 | 用途 | 三态诚实边界 |
|---|---|---|---|
| 6 | `explain_unknown` | 结构化解释「为什么 unknown」：给 component_id 返回 evidence_gaps / null 字段清单；给 verdict_id 反查当前会话；不给参数返回全库 unknown 覆盖率摘要 | 字段级扫描，非因果归因；跨会话需靠 `trace_export` 落盘后重放 |
| 7 | `start_long_task` | 启动长任务并立即返回 task_id，任务体异步执行 | stdio 无中断通道，取消不是硬终止 |
| 8 | `get_task_status` | 查询任务 status / progress / result | 环形缓冲 200 条上限，最老任务被淘汰 |
| 9 | `cancel_task` | 置任务取消标志位 | 依赖任务体在 checkpoint 检查；对已结束任务返回 `task_already_<status>` |
| 10 | `trace_export` | 导出本会话调用轨迹（默认去敏） | 只回当前 stdio 会话；服务端无持久化；`ROBOPARTS_TRACE_FILE` 环境变量可落盘 |
| 11 | `trace_replay` | 从 JSONL 文本重放：结构校验 + 计数 | 只验证"记录可解析、字段完整"，不重算 verdict（属于 P3 语义重放范畴） |

**协议版本协商**：Server 声明支持 `2024-11-05` / `2025-03-26` / `2025-11-25` 三个版本。
基础 10 个工具在任意版本可用；上述 6 个扩展工具在 `2025-11-25+` 声明可用。
客户端在 `initialize` 请求里传的 `protocolVersion` 会被 SDK 自动协商到共同版本；
本 server 另在 `capabilities.experimental.roboparts` 里显式列出
`protocol_versions_supported` 和 `capabilities_by_version`，方便新客户端程序化判断。

**evidence_version 注入**：每次工具调用返回都挂 `trace_id` 和 `evidence_version`
（当前 = 包版本 `1.2.0`），让调用方可以引用某个数据快照做对账。

**三态诚实边界**（`capabilities.experimental.roboparts.honest_limits`）：

- `no_server_side_persistence` — stdio 单进程，客户端断线 trace 就丢
- `no_hard_cancel` — 无中断通道，cancel 只置标志位
- `no_multi_tenant_isolation` — 单会话，无 user_id 隔离

## 使用示例

### 示例 1：搜索舵机

```
用户：帮我搜索 DYNAMIXEL 舵机
AI Agent 调用：search_components({ category: "actuators", keyword: "DYNAMIXEL", limit: 5 })
```

### 示例 2：获取零部件详情

```
用户：查看 ACT-001 的详细参数
AI Agent 调用：get_component_detail({ id: "ACT-001", category: "actuators" })
```

### 示例 3：检查兼容性

```
用户：DYNAMIXEL XM540-W270-T 和 NVIDIA Jetson Orin NX 兼容吗？
AI Agent 调用：check_compatibility({
  component1_id: "ACT-001",
  component1_category: "actuators",
  component2_id: "CHIP-001",
  component2_category: "chips"
})
```

### 示例 4：应用推荐

```
用户：我要做一个人形机器人，预算 50000 元，推荐零部件
AI Agent 调用：recommend_for_application({
  application: "humanoid",
  budget: 50000,
  count: 3
})
```

### 示例 5：导出 BOM

```
用户：帮我导出一个项目的 BOM，包括 2 个 ACT-001 舵机和 1 个 CHIP-001 芯片
AI Agent 调用：export_bom({
  project_name: "人形机器人手臂原型",
  items: [
    { id: "ACT-001", category: "actuators", quantity: 2 },
    { id: "CHIP-001", category: "chips", quantity: 1 }
  ]
})
```

## 数据来源

数据文件位于 `../api/` 目录（本地开发回退），生产环境从 `https://roboparts.cc/api` 拉取。
完整品类清单与条数见 `api/entities.json` 的 `meta.categories`（真相源，本表随时会漂移）：

- 20 个品类实体：actuators / sensors / chips / protocols / platforms / llms / interfaces /
  flexible_actuators / robot_ai_models / data_acquisition / grippers / bionic_mechanisms /
  reducers / controllers / structural / cables / power / pcb / connectors / integrated_joints
- 派生产物：compatibility_matrix / evidence_ledger / co_mount / morphology_graph /
  standard-audit / compose_semantics / reachability_gap 等（详见 `api/` 目录）

## 技术架构

```
┌─────────────────┐     stdio      ┌──────────────────┐
│   AI Agent      │◄──────────────►│  MCP Server      │
│ (Claude/GPT)    │   MCP Protocol │  (index.js)      │
└─────────────────┘                └────────┬─────────┘
                                            │ readFileSync
                                            ▼
                                   ┌──────────────────┐
                                   │  Local JSON Data │
                                   │  (../api/*.json) │
                                   └──────────────────┘
```

## 许可证

MIT License
