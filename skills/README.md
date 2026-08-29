# RoboParts Skills（Agent 技能包）

把 RoboParts 的机器人零部件兼容性能力封装成可被其它 Agent 框架一键接入的 Skills。
底层统一走 **免鉴权只读 MCP 端点** `https://roboparts.cc/mcp`（已收录官方 Registry `cc.roboparts/roboparts`），零安装、零 API Key。

## 机器可读清单

- `skills/manifest.json` —— 全部 skill 的结构化定义（名称 / 触发条件 / 绑定工具 / 参数）。其它 Agent 框架可直接解析此文件自动注册工具。
- **该文件与下方表格由 `scripts/gen_skills_manifest.mjs` 从 `functions/mcp.js` 的工具定义自动生成，勿手改**。
  回归闸门 L1.43 会照清单声明的参数真跑一遍每个技能，调不通即阻断发布 —— 保证你读到的参数名与线上端点逐字一致。

## Skills 一览

<!-- SKILLS-TABLE:BEGIN 由 scripts/gen_skills_manifest.mjs 生成，勿手改 -->
| Skill | 类型 | 绑定 | 何时用 |
|---|---|---|---|
| `roboparts-search` | mcp_tool | `search_components` | 用户想找某类机器人零件（执行器/传感器/芯片/协议/平台），或给出型号片段需要补全信息时。 |
| `roboparts-component-detail` | mcp_tool | `get_component_detail` | 已经拿到零部件 ID（如 ACT-001），需要完整规格、厂商、证据等级与数据缺口时。 |
| `roboparts-compat-check` | mcp_tool | `check_compatibility` | 用户问「A 和 B 能不能装一起」「这两个零件兼容吗」「选型有没有冲突」时。 |
| `roboparts-recommend` | mcp_tool | `recommend_for_application` | 用户要「给某类机器人配一套零件」「预算 X 元怎么选」时。 |
| `roboparts-parameter-semantics` | mcp_tool | `get_parameter_semantics` | 用户问「这个扭矩参数靠谱吗」「不同厂商参数怎么比」「单位怎么换算」时。 |
| `roboparts-adapter-generate` | web_resource | `/adapter-generator` | 兼容性判定为不兼容、且根因是机械法兰不匹配时，直接产出解决方案而非只给结论。 |
| `roboparts-dataset-discovery` | dataset | `/agent-discovery.json` | 用户想下载/引用原始数据、做二次分析、或确认数据来源时。 |
<!-- SKILLS-TABLE:END -->

## 接入方式

### 1) 直接连 MCP（推荐）
```json
{ "mcpServers": { "roboparts": { "url": "https://roboparts.cc/mcp" } } }
```
连上后即拥有上述 5 个 `mcp_tool` 类 skill（检索 / 详情 / 兼容 / 推荐 / 参数口径）。
数据集发现不是 MCP 工具，走静态 JSON 直接 GET（见表中 `roboparts-dataset-discovery`）。

### 2) 把 skill manifest 喂给框架
解析 `https://roboparts.cc/skills/manifest.json`，按 `skills[].when_to_use` 决定自动调用哪个工具；
`roboparts-adapter-generate` 为 `web_resource` 类，按 `endpoint` + `params` 拼接 URL 打开转接件生成器。

### 3) 自然语言兜底
用户说「我手腕 A80-4-M8，夹爪 A50-4-M6，能直接用吗」时，可路由到
[兼容性 Copilot](https://roboparts.cc/copilot) 或本地用 `roboparts-compat-check` 判定。

## 诚实性约定（Skill 调用方请遵守）
- 兼容性结论基于厂商**已声明**字段，未声明维度记为「无法判定」，不折算成分数。
- RoboParts 不生产/不销售/不代理任何零部件，选型无导向自家产品的动机。
- 转接件生成器产物为几何建议，非认证；量产前请样机实测。
