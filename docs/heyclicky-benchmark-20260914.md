# heyclicky（Clicky / ClickyX）调研与 RoboParts 借鉴方案

> 调研日期：2026-09-14 · 目的：把 heyclicky 系列开源项目里对 RoboParts 有用的能力借鉴过来
> 结论先行：**已落地 2 项核心借鉴（Copilot 上下文感知 + “指给你看”结构化引用）；另有 3 项高价值借鉴列为路线，其中 1 项（厂商规格书 → 自动声明）直接打 P0 数据缺口。**

---

## 一、heyclicky 到底是什么（事实锚定）

“heyclicky” 指 Farza Majeed（farzaa，YC W26）做的 **Clicky** 桌面 AI 助手生态，及其开源/重实现分支：

| 项目 | 形态 | 一句话 | 关键技术 |
|---|---|---|---|
| **farzaa/clicky**（原版，macOS） | Swift 菜单栏 App | “住在光标旁的老师，能看屏、会说话、**能指着东西**” | ScreenCaptureKit 截屏 + 推话 + OpenAI/Anthropic 流式；模型回文内嵌 `[POINT:x,y:label:screenN]` 让光标飞到指定 UI 元素 |
| **unn-Known1/clickyX** | Rust + Tauri + React 跨平台重实现 | “零云依赖、用户自有的 AI 运行时” | localhost:32123 本地 HTTP bridge（REST+SSE、token 鉴权、MCP 路由，25+ 端点）、63 个内置 skill、Codex agent 运行时、computer-use 引擎（enigo 点击/输入）、多屏 overlay 标注 |
| **Bitshank-2338/clicky-windows** 等 | 各平台移植 | 把 clicky 搬到 Win/Linux | 标注语法 `[ARROW]`/`[CIRCLE]`/`[LABEL]`、OCR 兜底（Tesseract 读小字）、**文档拖入即作为上下文**、SM-2 间隔复习、课程录制 |

**两个对 RoboParts 最关键的设计纪律：**

1. **密钥代理模式**：Clicky 用一个小巧的 **Cloudflare Worker 持有 API Key**，App 只跟 Worker 说话，Key 永不进客户端二进制。
   → **RoboParts 的 `/api/copilot` 已经是同一范式**（CF Pages Function 代理 Agnes/ECS，Key 只在 CF secret）。这条我们不缺，只是被 Clicky 证实了是行业标准隐私做法。
2. **“AI 能看见你正在看的东西 + 精准指向那个东西”**：Clicky 不是“通用问答”，而是把**当前屏幕上下文**带进模型，再用 `[POINT]`/`[CIRCLE]` 标签把答案**锚定到具体界面元素**。这是它体验远超普通 Chatbot 的核心。

---

## 二、已经借鉴过来的 2 项（本轮回填）

### 借鉴 A：Copilot 上下文感知（“AI 看见你正在看的东西”）
**改动**：`functions/api/copilot.js`
- 新增 `contextBlock(ctx)`：把前端传来的「当前判定的两个法兰 + 规则裁决（ok/need）+ 用户提到的品牌/型号」拼进 system prompt 的【当前上下文】块。
- 前端 `copilot.html` 的 `explainWithAI()` 现在附带 `context`（法兰 PCD/孔数/螺纹、verdict、mentions、adapterUrl）。
- 效果：AI 解释不再复述通用规则，而是针对**这一例**给出（例如“你这两个 A80 和 A50 因为 PCD 不同才要转接板”，而非泛泛而谈 ISO 9409-1）。

### 借鉴 B：“指给你看”的结构化引用（Web 原生的 `[POINT]` 等价物）
**改动**：`functions/api/copilot.js` + `copilot.html`
- 新增 `buildReferences(ctx, entities)`：生成可点击引用链——命中法兰的 canonical 梯级、ISO 9409-1 速查页、转接件生成器（带本例参数）、以及**按用户提到的品牌/型号反查命中的真实实体**（缓存 `entities.json` 5 分钟，失败降级不阻断）。
- 前端把 `references` 渲染成「🔗 指给你看」的 chip 行。
- 效果：Clicky 用“光标飞到按钮上”解决的事，在 Web 上等价成“答案下方直接挂可点数据链接”——用户看完解释顺手就能跳到法兰库/转接件/对应零件页。这比截图光标更适合 RoboParts 的数据型场景。

> 修复伴随：原 `no_backend_configured` 分支在 `references` 声明前引用它（TDZ 运行时报错），已把 `context/references/system` 计算整体前置到后端可用性判断之前；成功分支与降级分支现在都携带 `references`。

---

## 三、高价值借鉴路线（建议，未落地）

| 优先级 | 借鉴点 | 对 RoboParts 的价值 | 工作量 | 阻塞 |
|---|---|---|---|---|
| **P0 路线** | **厂商规格书拖入 → 自动填机械接口声明**（对应 clicky-windows 的“文档即上下文 + OCR 兜底”） | 直接攻击 **P0 真实 BOM 机械接口声明缺口**（当前 declared 仅 15 条）。用户拖一份 OnRobot/Schunk 规格书 PDF，平台 OCR+解析出孔位尺寸，自动生成带 `source_url` 官域出处的 `declared` 条目 | 中（需加一个解析/抽取管道 + 落库校验，必须满足 L1.78 白名单纪律） | 无（纯前端+Function，可零成本做） |
| P1 | **SSE 流式输出**（对应 Clicky 流式 Responses） | 长解释不再“转圈”整段返回，逐字流出，体验对齐 Clicky | 低（copilot.js 改 ReadableStream；前端 fetch + 增量渲染） | 依赖 P2 后端上线 |
| P1 | **可视化标注 verdict**（对应 `[CIRCLE]`/`[ARROW]`） | 在 `compatibility-viewer` 的法兰图上**圈出不匹配的螺栓圆**，把“需要转接”画出来而非只写文字 | 中（SVG overlay） | 无 |
| P2 | **本地优先 / 隐私护栏**（对应 ClickyX 零云、clicky-windows 隐私守卫） | RoboParts 已是云端 SaaS，但可加“不把用户输入发任何第三方”明示；与现有 `roboparts.cc` 同源策略一致 | 低（文案+策略） | 无 |
| 观察 | **skill / agent 运行时**（对应 clickyX 63 skill + 后台 agent） | RoboParts 已有 `functions/` 端 10 工具 + npm 端 8 工具 + `agent-discovery.json`；概念同“能力注册表”。可把“能力清单”做成用户可见的 registry 页 | 低 | 无 |

**不借鉴**（明确说明，避免邯郸学步）：
- **桌面端语音/TTS/唤醒词**：RoboParts 是 Web 工程工具，不需要常驻语音助手。
- **computer-use / 跨屏光标**：Web 无 ScreenCaptureKit 等价物，且 RoboParts 的价值在“数据判定”而非“操作桌面”。
- **本地优先零云**：与 CF Pages 部署模型冲突，不采纳。

---

## 四、落地后的体验对比

| 维度 | 借鉴前 | 借鉴后 |
|---|---|---|
| Copilot 解释 | 只知“解释这两个法兰”，零上下文，常答泛泛 | 带本例法兰/裁决/品牌，针对这一例解释 |
| 答案可追索 | 纯文本，看完无下文 | 挂「指给你看」chip：法兰梯级 / ISO 速查 / 转接件（带本例参数）/ 命中真实零件 |
| 后端维护中 | 仍可解释（已降级），但无引用 | 降级响应也带引用，用户照样能跳去查证 |
| 隐私 | CF Worker 代理 Key（已具备） | 沿用，未退步 |

---

## 五、下一步建议（待你拍板）

1. **最该做**：P0 路线“规格书 → 自动 declared”管道。这是唯一能同时补产品数据缺口（P0）又直接源自 clicky 借鉴的动作，且零成本可做。要我出方案/原型吗？
2. P1 的 SSE 流式 + 法兰图可视化标注，可在 P2 后端（ECS_API_KEY）敲定后一起做。
3. 本次借鉴的 copilot 改进已随本仓 commit 推送并部署（见发布记录）。
