# RoboParts MCP Server

RoboParts MCP (Model Context Protocol) Server 是一个标准化接口，允许 AI Agent（如 Claude、GPT 等）通过 MCP 协议查询机器人零部件数据。AI Agent 可以搜索零部件、获取详细信息、检查兼容性、获取应用推荐并导出 BOM 清单。

> **请按包名甄别**：本包是 roboparts.cc 官方发布的 MCP Server，包名
> **`roboparts-mcp-server`**，主页 https://roboparts.cc 。
> npm 上另有一个名为 `roboparts-mcp` 的第三方包（作者 Crawde，指向 robopartsai.com），
> 与本项目无关。

## 项目介绍

本 MCP Server 基于 `@modelcontextprotocol/sdk` 构建，使用 stdio 传输协议，
启动时从 **https://roboparts.cc/api** 拉取全部数据（688 条实体），
为 AI Agent 提供结构化的机器人零部件查询能力。

数据实时取自线上，不随包版本过期。若数据源不可达，服务会**明确报错退出**，
而不是以空库启动、对每次查询都回「未找到」—— 静默失败比崩溃更难排查。
内网或离线环境可用环境变量 `ROBOPARTS_API_BASE` 指向自建镜像。

### 支持的数据品类（10 类 / 688 条，与官网口径一致）

| 品类 | 标识 | 条数 | 说明 |
|------|------|------|------|
| 执行器 | actuators | 199 | 舵机、电机控制器等 |
| 芯片 | chips | 108 | 计算芯片、MCU 等 |
| 传感器 | sensors | 90 | LiDAR、IMU、触觉传感器等 |
| 通信协议 | protocols | 64 | EtherCAT、CANopen 等 |
| 机器人 AI 模型 | robot_ai_models | 44 | RT-2、π0 等具身智能模型 |
| 数据采集 | data_acquisition | 43 | 遥操作、动捕等数采方案 |
| 大语言模型 | llms | 42 | GPT-4o、Claude、VLA 模型等 |
| 机器人平台 | platforms | 40 | 人形、四足等机器人平台 |
| 接口 | interfaces | 37 | USB、MIPI CSI、PCIe 等 |
| 柔性执行器 | flexible_actuators | 21 | 气动人工肌肉、SMA 等 |

### 我们不隐瞒的三件事

1. **参数为厂商公开声明值，未经我方实测复现**，请勿当作实测值用于最终选型。
2. **跨厂商可直接横向比较的 A 级条目目前为 0 条。** 各家参数口径（如转速的定义方式）
   尚不统一，我们宁可如实标注，也不做一个看起来整齐、实则不可比的排行榜。
3. **机械接口有明确线索的仅占 0.57%。** 这是行业普遍未公开的部分，我们在补，但目前确实很少。

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

数据文件位于 `../api/` 目录，包含以下 JSON 文件：

- `actuators.json` - 执行器数据（147 条）
- `sensors.json` - 传感器数据（42 条）
- `chips.json` - 芯片数据（95 条）
- `protocols.json` - 通信协议数据（64 条）
- `platforms.json` - 机器人平台数据（23 条）
- `llms.json` - 大语言模型数据（27 条）
- `interfaces.json` - 接口数据（14 条）
- `compatibility_matrix.json` - 兼容性规则矩阵

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
