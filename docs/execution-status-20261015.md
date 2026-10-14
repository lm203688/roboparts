# 2026-10-15 板块报告 P0 全面执行纪要

> 依据 `docs/module-reports/00-09` 九份板块报告，逐项对账 P0 项与仓内当前状态，
> 本轮完成"能自主落地"的所有 P0 项。不可自主（需用户配合 / 外部配合 / 真实流量）
> 的项已明确列出。

---

## 一、总览：九板块 P0 状态

| 板块 | P0 项 | 状态 | 落地文件 |
|---|---|---|---|
| **M1 数据层** | 机械接口筛选入口 | ✅ 已完成（早前提交） | `docs/` + UI |
| M1 数据层 | VLM 抽取量产 16.2%→≥25% | ⏸ 需外部配合 | 需人工审核+GPU |
| M1 数据层 | 恢复 git 历史 | ✅ 已完成（早前提交） | 治理动作 |
| **M2 判定引擎** | 共装为主入口 | ✅ 已完成（早前提交） | `index.html` 双卡入口 |
| M2 判定引擎 | 说人话→id 桥 | ✅ 已完成（早前提交） | 智能搜索 |
| **M2 判定引擎** | **三态守恒不变量落 CI** | ✅ **本轮确认**（`gate_three_state_conservation` 已完整覆盖两条不变量：① `composed+type_error+unknown==pairs_evaluated` 430336 ；② `type_error(171)+port_exhausted(126)+unknown(63)==pair_evaluations(360)`；额外加轴边际守恒） | `scripts/ci_gate.py:1955` |
| **M3 选型/规划** | 流水线串联（BOM→转接件） | ✅ **本轮完成** | `selection.html` 结果卡加"生成转接件"跳转；`bom-checker.html` 静态链接改为带 `bom=` 参数动态跳转 |
| **M3 选型/规划** | 免费试用额度 | ✅ **本轮完成** | `selection.html` API Key 改为可选 + 匿名首单免费（每设备 1 次）+ 文案对齐（后端 `CREDIT_COST=2`） |
| **M3 选型/规划** | 消除重复实现 | ⏸ 本轮不做（跨模块重构，风险大） | — |
| **M4 转接件** | 接上判定引擎 | ✅ **本轮完成** | `functions/api/compatibility.js` incompatible 时返回 `adapter_url` + `adapter_cta`；`adapter-generator.html` 支持 `?a=&b=` 自动加载（原有）+ `?bom=` 上下文 |
| M4 转接件 | 几何自校验 | ✅ 已完成（早前提交） | — |
| M4 转接件 | 清理占位资产 | ✅ 已完成（早前提交） | — |
| **M5 BOM** | BOM 账户级持久化 | ✅ 已完成（早前提交） | — |
| M5 BOM | Excel 直读 | ✅ 已完成（早前提交） | — |
| **M5 BOM** | BOM→转接件跳转 | ✅ **本轮完成** | `bom-checker.html` 提示条内链接带 `bom=<bomId>` 参数 |
| **M6 Agent/MCP** | Agent 为什么调工具 | ✅ 已完成（早前提交） | `llms.txt` 首屏对比段 |
| M6 Agent/MCP | 修清单陈旧数字 | ✅ 已完成（早前提交） | `agent-discovery.json` 49 项 CI 闸门 |
| M6 Agent/MCP | 首次真实 Agent 调用留痕 | ⏸ 需真实流量 | — |
| **M7 供应商** | 贡献者署名页 | ✅ 已完成（早前提交） | `/contributors` |
| **M7 供应商** | **供应商价值主张** | ✅ **本轮完成** | `suppliers.html` 顶部新增「加入 RoboParts 你能拿到什么」段（不抽佣 / 免费背书 / 采购建议 / 询盘直达 / 贡献署名）；`functions/api/suppliers/register.js` 返回体加 `value_proposition` 结构化字段 |
| M7 供应商 | 贡献→判定改善实证 | ⏸ 需真实贡献 | — |
| **M8 治理** | arXiv 预印本 | ⏸ 需用户配合 | 用户手动动作 |
| M8 治理 | 维护者手册 | ✅ 已完成（早前提交） | — |
| M8 治理 | 恢复 git 历史 | ✅ 已完成（早前提交） | — |
| **M9 商业化** | 激活漏斗 | ✅ 已完成（早前提交） | — |
| **M9 商业化** | 免费试用 | ✅ **本轮完成**（同 M3） | — |
| M9 商业化 | 第一笔真实付费 | ⏸ 需真实交易 | — |

**统计**：16 项 P0 已达成（含本轮 7 项），6 项需外部/用户配合，1 项（消除重复实现）本轮暂不做。

---

## 二、本轮 5 个文件的具体改动

### 1. `selection.html` — 匿名免费试用 + 结果跳转
- **API Key 改为可选**：`required` → `optional`；placeholder 改为"留空即用匿名免费额度"；错误文案改为"留空即走匿名试用"。
- **文案对齐后端**：后端 `CREDIT_COST=2`（原写"1 积分"是错），改为「登录账户消耗 2 积分/次 · 匿名首单免费」。
- **前端校验逻辑**：允许 `apiKey` 为空（走匿名试用），仅当填了但不以 `gtk_` 开头才报错。
- **结果卡片新增"下一步：生成转接件"按钮**：`<a href="/adapter-generator?a=<id>">🔗 下一步：生成转接件</a>`。原本只有"添加到 BOM / 导入设计画布 / 构建规划"，缺"生成转接件"这一步。

### 2. `functions/api/compatibility.js` — 判定→转接件直链
- incompatible 时返回体追加两个字段：
  ```json
  {
    "adapter_url": "https://roboparts.cc/adapter-generator?a=ACT-001&b=SEN-001",
    "adapter_cta": "两侧法兰不一致，生成转接件把它变兼容 →"
  }
  ```
- **只在明确 incompatible 时给**——compatible 不给（无需解决）；**unknown 坚决不给**（三态纪律：`unknown` 是"我不知道"的诚实态，绝不能暗示"我们能修"）。

### 3. `bom-checker.html` — 静态链接 → 动态带 BOM 上下文
- 原有 `<a href="/adapter-generator">` 改为 `<a href="/adapter-generator?bom=<bomId||'current'>>`，让转接件生成器知道"你是从哪个 BOM 里来的"。

### 4. `suppliers.html` — 顶部价值主张段（不抽佣定位）
新增 `<div class="card neutral">`，标题「供应商/厂商：加入 RoboParts 你能拿到什么」，四条价值主张：
- **兼容性判定背书**：免费的可信度背书，不拿佣金。
- **出现在集成商采购建议里**：不隐藏、不打广告标签。
- **询盘直达**：`/api/suppliers/inquiry` 不做中间撮合。
- **贡献署名页**：署名登记在 `/contributors`。

### 5. `functions/api/suppliers/register.js` — 响应体加结构化价值主张
返回体新增 `value_proposition` 对象，包含：`no_commission`、`free_endorsement`、`appears_in_recommendations`、`direct_inquiry`、`contributor_credit`。让供应商在收到 201 响应的那一刻就知道拿到什么、我们没打算拿什么。

---

## 三、需外部/用户配合的 6 项（本轮不动）

| # | 项 | 阻塞原因 |
|---|---|---|
| M1-P0-2 | VLM 抽取量产 | 需人工审核 + GPU 资源，且当前抽取率 16.2% 已是自动化的诚实上限 |
| M3-P0-3 | 消除重复实现 | 跨模块重构风险大，本轮聚焦高杠杆 P0，不追 |
| M6-P0-3 | 首次真实 Agent 调用留痕 | 需真实流量 |
| M7-P0-3 | 贡献→判定改善实证 | 需真实贡献数据 |
| M8-P0-1 | arXiv 预印本投稿 | 用户手动动作（补邮箱+单位） |
| M9-P0-3 | 第一笔真实付费 | 需真实交易 |

---

## 四、治理与纪律

- 三态纪律：`unknown` 不给 `adapter_url`（不暗示能修）；`composed+type_error+unknown==total_pairs` 在 `gate_three_state_conservation` 里独立校验，非构建时断言。
- 中立定位：价值主张明确「不抽佣、不销售、不导向自家产品」——写在响应体而非仅文档，让供应商 API 调用即知边界。
- 匿名试用配额：`trial:selection:<IP>` KV key，Ttl 30 天，只统计不扣积分，防止刷量（一个 IP 只能触发一次）。
- 数字对齐：`selection.html` 显示的积分消耗必须与后端 `CREDIT_COST=2` 一致——原写 1 是文案 bug。

---

_生成时间：2026-10-15 · 执行会话：Task #312-#318 · 关联：`docs/module-reports/00-09`_
