# RoboParts — 全面性 / 实用性 / 使用性 / 互动性 / 前沿性 五维调查与全面提升报告

> 调查时点：2026-10-22 | 依据：全仓静态扫描（602 commits / 41 页面 / 82 产物 / 57 文档 / 22 文章）+ 产物现算 + 2026 技术与市场趋势联网核实
> 结论先行：**引擎层（判定/形式化/Agent 面）已达 A− 级；产品外壳（导航/端到端流/资产）仍在 C 级。下一阶段的胜负手不是再加引擎，而是把"一堆强能力"收束成"一个连贯产品"。**

---

## 0. 一句话判定与五维评分

| 维度 | 评分 | 一句话诊断 |
|---|---|---|
| **全面性** | **B** | 广度够（20 品类 / 41 页 / 82 产物），但深度严重偏科：执行器 222 条，而连接器/线缆/电源/PCB/结构件各仅 1–3 条 |
| **实用性** | **B−** | 单点工具真实可用（转接件真出 STL、BOM 真校验），但**五步流水线仍是孤岛**，`composed=0` 让核心判定几乎总返回 unknown |
| **使用性** | **C+** | **41 页零共享导航，25 页连 `<nav>` 都没有**；页面是"死胡同"，用户进得来出不去 |
| **互动性** | **B−** | MCP 21 工具 + A2A + 23 Skills 领先，但缺 AG-UI / Agent 原生交易，反馈闭环偏薄 |
| **前沿性** | **A−** | 三值形式化 + 3 定理 + MCP/A2A + ISO 22166 已站前沿；但**未接 VLA/世界模型、无仿真就绪导出（MJCF/Isaac）** |
| **综合** | **B** | 技术底盘优秀，产品化与资产化是最大欠账 |

**核心判断**：这个项目现在像"一台装好了发动机、但没有仪表盘和方向盘的车"。发动机（判定引擎、形式化、Agent 接口）确实领先；但用户坐进去，找不到路。

---

## 1. 全面性：广度达标，深度偏科

### 1.1 实测覆盖

| 层 | 实测 | 评价 |
|---|---|---|
| 实体库 | 868 条 / 20 品类 / 113 条隔离 | 规模可信，隔离率 13% 偏高 |
| 页面 | 41 个根页面 + 22 篇文章 | 功能覆盖面广 |
| API 端点 | **57 个**（含 MCP/A2A/搜索/推荐/供应商/支付） | 相当完整 |
| 派生产物 | 82 个 `api/*.json` | 数据管线成熟 |
| 文档 | 57 篇 md | 工程文档密度罕见 |
| 论文 | arXiv / Mechatronics / KBS / TII 四套投稿包 | 学术输出充足 |

### 1.2 结构性偏科（最该补的洞）

```
actuators            222  ██████████████████████
chips                108  ██████████
platforms            106  ██████████
sensors               95  █████████
protocols             64  ██████
robot_ai_models       46  ████
data_acquisition      46  ████
interfaces            44  ████
llms                  42  ████
grippers              26  ██
flexible_actuators    22  ██
bionic_mechanisms     17  █
reducers              14  █
controllers            4  ▌
structural             3  ▌
connectors             2  ▌
cables                 2  ▌
power                  2  ▌
pcb                    2  ▌
integrated_joints      1  ▌
```

**问题**：一个"机器人零件兼容性"平台，最需要打通的是**连接器 / 线缆 / 电源 / PCB / 结构件**——它们恰恰是兼容性事故的高发区，却各只有 1–3 条。执行器再多，也拼不出一台能上电的机器人。

**另一个硬缺口**：
- `urdf-library.html` 存在，但全仓只有 **2 个 `sample.urdf`**（且在 scripts/ 与部署暂存里）——**URDF 库是空壳**。
- `cad/` 与 `3d/` 目录已空——转接件生成虽能出 STL，但没有沉淀任何真实 CAD 资产。

**建议**：把"深度"指标从"实体总数"换成 **"可组装覆盖率"**——即每个品类中，能凑出一条完整机械+电气链路的比例。当前这个数字接近 0。

---

## 2. 实用性：单点真、链路断

### 2.1 真实可用的部分（值得肯定）

| 能力 | 证据 | 状态 |
|---|---|---|
| 法兰转接件生成 | `adapter-generator.html` 真出 STL / OpenSCAD，浏览器内 3D 预览 | ✅ 真可用 |
| BOM 兼容校验 | `functions/api/bom/check.js` 三源加载 + 免费额度 | ✅ 真可用 |
| 兼容判定 | 三套引擎、三态 fail-closed、变异评分 1.00 | ✅ 严谨 |
| Agent 接入 | 21 hosted MCP 工具 + 8 npm 工具 + A2A | ✅ 领先 |
| 供应商询价 | `suppliers/{register,inquiry,quote,approve}.js` | ⚠️ 端点全，但闭环薄 |

### 2.2 致命断点：五步流水线仍是孤岛

实测页面互链（去重后）：

| 页面 | 指向下一步的链接数 |
|---|---|
| `selection` → `build-planner` | 1（弱） |
| `build-planner` → `designer` | 2（弱） |
| **`designer` → `bom-checker`** | **0（断链）** |
| `bom-checker` → `adapter-generator` | 1（弱） |
| `assembly` → `bom-checker` | 1 |

**这意味着**：用户选完型，要自己记住"下一步该去哪个页面"，再手动找入口。**没有一个"项目"对象贯穿五步**——`selection` 用 `localStorage`（7 处），`build-planner` 完全不读写状态，`designer` 只用 `URLSearchParams`，`bom-checker` 用 `localStorage`。**四套状态，互不相认。**

**这是"实用性"最贵的一条**：工具都在，但用户走不完一条路。

### 2.3 `composed = 0` 的产品副作用

研究上，`composed=0` 是诚实（覆盖地图）；产品上，它是**劝退**——用户问"这个能不能装"，99.94% 得到 `unknown`。需要一层**"最接近可行路径"兜底**：
- 若 `type_error` → 给出"需要哪种转接件/改哪个接口"
- 若 `unknown` → 给出"缺哪一轴的哪个字段"（Bottleneck Necessity 定理已经证明了这个方向）
- 永远给一个**可执行的下一步**，而不是一个"不知道"。

---

## 3. 使用性：41 个页面，零共享导航

### 3.1 最刺眼的一条

| 指标 | 实测 |
|---|---|
| 有 `<nav>` 链接的页面 | **16 / 41**（其中 25 页 nav 链接数 = 0） |
| 有 `<header>` 的页面 | **5 / 41** |
| 共享导航脚本 | **不存在**（无 nav.js / injectNav / site-nav） |
| 首页 → 其他页 | 38 / 41 可达（单向） |
| 其他页 → 首页/其他页 | **基本不可达（死胡同）** |

**后果**：用户从搜索引擎落到 `selection.html`，做完选型，**没有任何入口去 BOM 校验或转接件生成**，只能按浏览器后退。这直接杀死了"五步流水线"的产品价值。

### 3.2 其余使用性问题

| 问题 | 实测 | 影响 |
|---|---|---|
| 单体页面 | `designer.html` **121KB / 2187 行内联 JS** | 首屏慢、难维护 |
| 无 PWA | 无 `manifest.json` / `sw.js` | 不可安装、无离线 |
| 埋点覆盖低 | 仅 8 页有 analytics | 无法做转化漏斗 |
| 国际化名不副实 | 40 页 `zh-CN`，仅 1 页 `en`；hreflang 多指向自身 | "国际化定位"缺英文入口 |
| 无全局搜索 | 仅 16 页有搜索框 | 41 页内容难发现 |
| 第三方依赖裸挂 | three.js **r128（2021 年版本）**、xlsx 0.18.5，走 CDN 无 SRI | 安全与兼容风险 |
| 定价页缺价格锚 | `pricing.html` 未匹配到 `¥/$` 金额 | 商业化说服力弱 |

### 3.3 一个高杠杆动作

**给 41 个页面注入统一 shell（nav + footer + 面包屑 + "下一步"CTA）**，工作量约 3–5 天，但能把"使用性"从 C+ 直接拉到 B+。这是全报告 ROI 最高的一项。

---

## 4. 互动性：Agent 面领先，人机面偏薄

### 4.1 领先的部分

- **MCP**：21 个 hosted 工具（`search_components` / `check_compatibility` / `plan_assembly` / `preflight_check` / `explain_compose_frontier` 等）+ 8 个 npm 工具。
- **A2A**：`functions/a2a.js` + Agent Card + `agent-discovery.json`（23 skills）。
- **工作流即工具**：`plan_assembly` 与 `preflight_check` 已落地——这是"Agent 原生预言机"的关键一步。
- **Copilot**：`functions/api/copilot.js` 412 行，真实实现。
- **反馈端点**：`demand-signal` / `waitlist` / `contributors` / `recommend-feedback` / `adapter-feedback` 五个。

### 4.2 与 2026 协议栈的差距

2026 年的 Agent 协议栈已成形为四层：

| 层 | 标准 | RoboParts 状态 |
|---|---|---|
| 上下文连接 | **MCP** | ✅ 已实现（21 工具） |
| Agent 间通信 | **A2A**（Linux Foundation AAIF 托管） | ✅ 已实现 |
| 人机交互 | **AG-UI** | ❌ 缺失 |
| 交易支付 | **ACP / AP2 / UCP**（OpenAI+Stripe、Visa 已接入） | ❌ 缺失（现为 Creem 人类支付） |

**机会**：RoboParts 已经是"机器人硬件的 MCP 服务端"，但还没有"Agent 能直接下单买零件"的闭环。2026 年 Agentic Commerce 正在爆发（AI 供应链市场 2025 年 $34B → 2030 年 $189B，CAGR 41%），**"让采购 Agent 直接调用 RoboParts 询价/下单"是一个可占的生态位**。

### 4.3 人机互动偏薄

- 无实时协作、无流式 UI（copilot 是请求-响应）。
- BOM 仍以 `localStorage` 为主，跨设备不连续。
- 反馈闭环：`demand-signal` 读的是**静态 JSON**，不是实时 KV。
- 23 个 Skills 无版本化/市场页。

---

## 5. 前沿性：已站前沿，但缺两个 2026 风口

### 5.1 已经站住的前沿

| 前沿点 | 状态 |
|---|---|
| 三值形式化 + 3 定理 + 性质/变异测试 | ✅ 领先（多数竞品停在二值） |
| reflexivity boundary（同型号公头不互补） | ✅ 独有洞察 |
| MCP + A2A 双协议 | ✅ 已实现 |
| ISO 22166-201/-202 对齐 | ✅ 已做条款映射 |
| 工作流即工具（plan_assembly / preflight_check） | ✅ 已落地 |
| 可信性工程（64 闸门 / 负结果 / 反模式） | ✅ 可迁移的方法论 |

### 5.2 两个必须补的风口

**风口一：仿真就绪（Simulation-Ready）**
2026 年机器人开发已是"Simulation First"：Isaac Sim 支持 URDF/MJCF/CAD 导入，MuJoCo 是 RL 主力，PhysX-Anything 能从单图生成仿真就绪模型。RoboParts 有 `urdf-library` 页面和 `lint_urdf` 工具，但**只有 2 个示例 URDF，无 MJCF，无物理参数（质量/惯量/摩擦/关节限位）**。
→ **机会**：做"兼容性判定 → 仿真资产导出"的直链，让用户判定完直接拿到可跑 Isaac/MuJoCo 的模型。这是竞品没有的。

**风口二：VLA / 世界模型的数据接口**
2026 年 VLA 与世界模型（Genie Envisioner 2.0、交互式世界模拟器）成为具身智能主线。RoboParts 不训练模型，但**可以是"VLA 训练所需的硬件本体/接口数据源"**——把 868 实体的关节参数、传感器规格、接口语义导出为 VLA/仿真可消费的结构化格式。
→ **机会**：从"零件兼容层"升格为"具身智能的硬件本体数据层"。

### 5.3 语义检索仍是"零模型"方案

`semantic-search.js` 用**哈希 TF-IDF 向量 + 预计算索引**，零外发、零成本——工程上聪明，但 2026 年用户对"语义搜索"的预期是 embedding 级。建议：保留 TF-IDF 作为降级路径，主路径换小 embedding（Workers AI 或本地量化模型）。

---

## 6. 2026 技术与市场趋势对标

| 趋势 | 2026 事实 | RoboParts 的位置 | 动作 |
|---|---|---|---|
| **Agent 协议栈四层化** | MCP + A2A + AG-UI + ACP/AP2 | 占前两层 | 补 AG-UI + Agent 交易 |
| **Agentic Commerce 爆发** | OpenAI+Stripe ACP、Visa×ChatGPT | 未占 | 让 Agent 可直接询价/下单 |
| **仿真优先** | Isaac Sim / MuJoCo / PhysX-Anything | 仅 URDF 壳 | MJCF + 物理参数导出 |
| **VLA / 世界模型** | Genie Envisioner 2.0、交互式世界模拟器 | 未接 | 导出 VLA 可消费的本体数据 |
| **人形机器人供应链收敛** | 硬件趋同、接口标准化需求上升 | ISO 9409/22166 已对齐 | 抢"标准参考实现"位 |
| **AI 供应链市场高增长** | $34B(2025)→$189B(2030)，CAGR 41% | 有数据、无交易 | 补交易闭环 |

---

## 7. 全面提升方案（按杠杆排序）

### P0 — 一周内：把"死胡同"变成"可导航产品"

1. **统一 shell 注入**（3–5 天）
   - 新建 `_shell.js` 或构建期注入：统一 `<nav>`（选型 / 规划 / 设计 / BOM / 转接件 / 数据 / Agent）+ `<footer>` + 面包屑。
   - 覆盖 41 页；验收：每页 nav 链接 ≥ 8，任意页可 1 跳回到首页与相邻功能页。
2. **补 `designer → bom-checker` 断链**，并在五页各加"下一步"CTA。
3. **修 `pricing.html` 价格锚**与 `promo-poster` 孤儿页。

**验收**：从 `selection` 出发，仅靠页面内点击可走完 selection → build-planner → designer → bom-checker → adapter-generator。

### P1 — 一个月内：端到端"项目"对象

4. **统一项目状态**：定义 `project` schema（选型结果 + 构型 + BOM + 转接件参数），用 URL + KV 双写，五页共享。
5. **`unknown` 兜底可执行化**：每个 unknown 返回"缺哪一轴哪个字段 + 补哪个数据源"，复用 Bottleneck Necessity 定理。
6. **URDF/MJCF 真实资产**：先覆盖 top 50 实体，补质量/惯量/关节限位；`urdf-library` 从壳变库。

**验收**：一个用户能在 10 分钟内，从"我要一个六轴臂 + 夹爪"走到"拿到 BOM + 转接件 STL + 可跑 MuJoCo 的 MJCF"。

### P2 — 一个季度内：占住 2026 生态位

7. **AG-UI 流式交互**：copilot 改为流式，支持"边判定边解释"。
8. **Agent 原生交易**：对接 ACP/AP2 风格协议，让采购 Agent 直接询价/下单（先做 sandbox）。
9. **仿真/VLA 数据导出**：新增 `/api/export/sim`（URDF/MJCF/物理参数）与 `/api/export/vla`（关节/传感/接口语义）。
10. **embedding 语义检索**：主路径换小 embedding，TF-IDF 降级。
11. **PWA + 全站埋点 + 英文版 top10 页**。

### P3 — 持续：数据深度

12. 补齐 **connectors / cables / power / pcb / structural** 五个品类，各目标 ≥ 20 条。
13. 把"实体总数"KPI 换成 **"可组装覆盖率"**（能凑出完整机械+电气链路的品类比例）。

---

## 8. 优先级矩阵

| 动作 | 影响 | 成本 | 优先级 |
|---|---|---|---|
| 统一 shell 导航 | ★★★★★ | 3–5 天 | **P0** |
| 补 designer→bom 断链 + 下一步 CTA | ★★★★ | 1 天 | **P0** |
| 统一 project 状态 | ★★★★★ | 2 周 | **P1** |
| URDF/MJCF 真实资产 | ★★★★ | 3 周 | **P1** |
| unknown 可执行兜底 | ★★★★ | 1 周 | **P1** |
| AG-UI 流式 | ★★★ | 2 周 | P2 |
| Agent 原生交易 | ★★★★ | 4 周 | P2 |
| 仿真/VLA 导出 | ★★★★★ | 3 周 | P2 |
| embedding 检索 | ★★★ | 1 周 | P2 |
| 补五个弱品类 | ★★★★ | 持续 | P3 |

---

## 9. 诚实边界

1. 本报告基于**静态扫描与产物现算**，未做真实用户可用性测试（无埋点漏斗、无 A/B）。
2. "25 页无 nav"是 `<nav>` 标签口径；部分页面可能用 `<div class="nav">` 手写导航，但**无共享机制**这一结论成立。
3. 市场数据来自公开报告（The Business Research Company 等），非一手调研。
4. 趋势判断（AG-UI / ACP / 仿真优先）基于 2026 年公开资料，具体标准演进仍需持续跟踪。
5. "可组装覆盖率接近 0"是结构性推断（弱品类实体数 1–3），未逐条验证装配可行性。
6. 转接件生成"真出 STL"已核实文案与按钮，未实际下载验证几何正确性。

---

*附：本报告与 `docs/RoboParts-SCI达标核验-20261019.md` 互补——前者管"学术可信"，本报告管"产品可用"。两条线不冲突：学术贡献靠形式化与诚实，产品价值靠连贯与深度。*
