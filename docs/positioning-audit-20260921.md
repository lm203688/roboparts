# RoboParts 市场定位偏差诊断与优化方案 · 2026-09-21

> 诊断对象：全站对外定位表述（HTML / README / llms.txt / agent-discovery / 定价页 / 供应商页）
> 方法：逐文件抓取原文 → 与 `api/entities.json` 现算数字对账 → 与竞品一手核实结果对账
> **原则**：只诊断"表述与事实的偏差"，不做品牌美化；每条偏差附原文与证据。

---

## 一、现状盘点：一共几套定位口径？

抓取全站定位表述，得到 **5 套互不一致的口径**：

| # | 出现位置 | 定位表述 | 目标用户表述 |
|---|---|---|---|
| 1 | `index.html` H1 + title | **开源机器人兼容性平台** | 构建者（Builder）、Agent 与开发者 |
| 2 | `README.md` / `llms.txt` / `agent-discovery.json` / `suppliers.html` | **仿生机器人生态平台** / 仿生机器人模块化选型与设计生态平台 | 工程师 |
| 3 | `index.html` meta description | 中文圈稀缺的开源机器人兼容性平台 | 中文圈 |
| 4 | `api-pricing.html` title | **RobotParts DB**（错名） | — |
| 5 | `waitlist.html` | 零部件兼容性数据底座与匹配引擎 | Builder / 投资人 / 供应商（三类） |
| 6 | **GitHub repo description**（最高曝光位置） | 仿生机器人零部件兼容性平台 \| **688** 条零部件 | — |

**核心疑问**：这 6 套表述里，**没有一套被任何外部信号验证过**（GitHub 0 star / 0 issue / 0 注册）。

### 1.1 一个更刺眼的对照：机器可读清单比人类页面更懂我们的定位

同一份定位，在**两个受众面前质量倒挂**：

| 面向 | 文件 | 描述 | 质量 |
|---|---|---|---|
| **AI / 机器** | `server.json` | `798 humanoid/bionic robot parts, 20 categories, 4-dimension compatibility checking.` **`Vendor-neutral.`** | ✅ 数字现算 + 差异点在前 |
| **AI / 机器** | `lhm.plugin.json` | `Vendor-neutral compatibility data layer… Query 798 parts across 20 categories…` **`We neither manufacture nor resell any part.`** | ✅ 中立性写进描述 |
| **AI / 机器** | `smithery.yaml` | `中立数据层：既不生产也不转售任何零部件；…未声明维度显式标为「无法判定」` | ✅ 中立 + 诚实都写了 |
| **AI / 机器** | `.well-known/mcp.json` | `798 条实体…中立数据层 —— 既不生产也不转售任何零部件` | ✅ 现算 |
| **人** | **GitHub description** | `仿生机器人零部件兼容性平台 \| **688** 条零部件` | ❌ **落后 110 条** |
| **人** | `index.html` | `开源机器人兼容性平台` + `中文圈稀缺` + `对标 TraceParts` + `133+/325 矛盾` | ❌ 差异点埋在页脚 |
| **人** | `README.md` | `仿生机器人生态平台` + actuators `217`（实 220） | ❌ 漂移 |
| **人** | `llms.txt` | `仿生机器人生态平台` | ❌ 品类词挂错 |

> **结论**：**给 AI 看的那份更懂我们的定位，给人看的那份不懂。**
> 机器可读四件套（`server.json` / `smithery.yaml` / `lhm.plugin.json` / `.well-known/mcp.json`）已被 `gen_public_manifests.py` 治理到"现算 + 中立性入描述"；
> 人类可读页面（GitHub description / index.html / README / llms.txt / 定价页）仍停在 8 月的旧口径。
> **这直接定义了整改方向：以机器可读清单为定位真相源，反向同步人类页面。**

---

## 二、偏差诊断（6 条）

### 偏差 1 · 品类词挂错：把 2% 的"仿生"当第一定位词

| 项 | 内容 |
|---|---|
| **宣称** | 站名 `RoboParts — 仿生机器人生态平台`（README / llms.txt / agent-discovery / suppliers 四处） |
| **事实** | `bionic_mechanisms` 仅 **17 条 / 798（2.1%）**；`flexible_actuators` 22 条（2.8%）。主体是 actuators 220 + chips 108 + sensors 95（合计 53%） |
| **证据** | `api/entities.json` → `meta.category_counts` 现算 |
| **危害** | **① 自我窄化**：搜索引擎与 AI 会把 RoboParts 归到"仿生机器人"长尾，错失"机器人零件兼容性"主关键词。**② 用户误判**：做工业臂/AGV 选型的工程师看到"仿生"直接关页，而他们才是 ISO 9409-1 法兰判定（我们的独占能力）的真实用户。**③ 与独占能力脱节**：ISO 9409-1 是**工业法兰标准**，不是仿生概念。 |

### 偏差 2 · 目标受众有 7 种说法，0 个验证

| 说法 | 出处 |
|---|---|
| 工程师 | README § 贡献 |
| 构建者（Builder） | index.html 卡片"构建者免费的日常工具" |
| Agent 与开发者 | index.html"把本页数据接进你的程序 / AI Agent" |
| 免费版 / Starter / Pro / 企业版 | pricing.html（4 档，隐含 4 类客户） |
| 供应商 + 采购方 | suppliers.html"连接人形机器人零部件供应商与采购方" |
| Builder / 投资人 / 供应商 | waitlist.html（3 类） |
| AI Agent | llms.txt `for_ai_assistants` / agent-discovery |

**危害**：**7 种画像 = 没有画像**。产品页同时在向终端开发者、B 端企业、供应商、投资人、AI agent 说话，导致：
- CTA 分散（"领 API key" / "候补登记" / "供应商入驻" / "积分充值" 并列，无主次）
- 每个受众都觉得"这不是给我的"
- 无法定向做增长（不知道该往哪个社区投放）

### 偏差 3 · 差异化错位：对标 TraceParts，掩盖真正的差异

| 项 | 内容 |
|---|---|
| **宣称** | index.html「免费 BOM 兼容性检查器……构建者免费的日常工具（**对标 TraceParts**）」 |
| **事实** | TraceParts 是全球最大零件 CAD 库之一（供应商付费上架，零件量千万级；具体数字本轮未一手核实）；RoboParts 798 实体，机械声明率 5.75% —— **不在同一量级，且它们只提供 CAD 下载，不做兼容性判定** |
| **真实差异（未被量化表述）** | index.html 底部其实写了最好的差异——「**RoboParts 不生产、不销售、不代理任何零部件，因此没有把选型结果导向自家产品的动机。这是关节厂商自建选型器无法复制的一条差异——卖家不适合同时当裁判**」 |
| **危害** | **把最强的差异埋在页脚**，把最弱的比较摆在主位。对标 TraceParts 是拿自己的短板去比别人的长板（零件量差 3-4 个数量级），而"中立第三方判定"是我们唯一没人能抄的位置——厂商自建选型器永远做不到中立。 |

### 偏差 4 · 地域圈层自相矛盾：说"中文圈"，全部动作在国际圈

| 项 | 内容 |
|---|---|
| **宣称** | index.html meta description「**中文圈稀缺**的开源机器人兼容性平台」 |
| **事实** | 所有挂载点与渠道都是**国际英文圈**：官方 MCP Registry / Glama / LobeHub（英/越语镜像）/ Tnkr（伦敦） / RoboInfra / urdf_validator / UrdfArchitect / Onshape / ROS Discourse。`llms.txt` + `agent-discovery.json` 也是按国际 AI agent 标准写的 |
| **危害** | **① 与增长动作方向矛盾**——准备投的 URDF 工具群合作、三态博客、Tnkr PR 全是英文圈，但定位说中文圈，话术不对路。**② "中文圈稀缺"不是护城河**——稀缺≠愿意付费（历史实测 29 次 API 调用 0 注册）。**③ 白白放弃真实优势**——ISO 9409-1 是国际标准，跨厂商兼容判定天然无国界，我们却给自己画了个中文圈。 |

### 偏差 5 · 品牌名漂移 + 开源身份在自己的 GitHub 页不可见

| 项 | 内容 |
|---|---|
| **漂移** | `api-pricing.html` title 写 **RobotParts DB**（应为 RoboParts）——多了一个字母 t |
| **风险** | Amazon 西班牙站已有 **Roboparts®** 品牌（Cecotec 扫地机配件）；另有 `roboparts-premium-bmyr.getsite.online/` 假冒页。品牌名在机器人零部件采购真实场景**已被占** |
| **开源身份不可见** | 真实许可为**代码 MIT / 数据 CC BY 4.0**（双轨），但 GitHub repo `license` 字段返回 **`NOASSERTION`**（GitHub 未识别自定义 LICENSE 文件）⇒ **"开源"这个定位在自己的 GitHub 页上显示不出来**，直接影响开源圈信任与收录 |
| **危害** | 品牌漂移会稀释 SEO 与 AI 检索；`NOASSERTION` 会让开源社区与 AI 爬虫降低信任权重（同时搜"RoboParts"永远输给 Amazon 的 Roboparts 配件）。 |

### 偏差 6 · 数字在最高曝光位置落后 110 条（硬伤级）

| 项 | 内容 |
|---|---|
| **GitHub description（最高曝光）** | `RoboParts — 仿生机器人零部件兼容性平台 \| **688** 条零部件的接口/总线/ROS2 兼容性数据，含 MCP Server 与开放 API`（API 实测 2026-09-21）。**实际 798 ⇒ 落后 110 条** |
| **同页矛盾** | `index.html` 同一页面出现 **「133+ 开源机器人组件」**（"开源兼容性数据层"卡片）与 **「325 个开源组件」**（"三步找到能用的零件"段落）。二者无任何口径说明 |
| **跨文件漂移** | `README.md` 第 34 行仍写 **actuators 217 条**，`entities.json` 现算 **220**；README 顶部说"最后更新 2026-09-17"，但品类明细是 8-03 的旧快照 |
| **危害** | ① GitHub description 是搜索结果摘要与仓库页第一行，**访客第一眼看到"688"**，点进去发现 798 ⇒ 直接怀疑数据新鲜度；② 一个以"可核验性优先于数量宣称"为核心价值的项目，**首页自己就有两个互斥数字**，比数字小更伤；③ 讽刺的是 `smithery.yaml` 注释里已明确记录"曾长期停在 688，真值已是 798"——**说明这个坑被修过一次，但只修了机器可读那份，人类可读那份漏了**（见 §1.1 倒挂）。 |

---

## 三、目标受众精准定义（回答"如何更精准"）

### 3.1 分层原则

**不要按身份分层（工程师/企业/供应商），要按"任务 + 可付费性 + 可触达性"分层。**

### 3.2 三层受众（按优先级）

#### T1 · 主受众：开源机器人构建者（Open-source robot builder）— 唯一已验证存在的群体

| 项 | 内容 |
|---|---|
| **具体是谁** | 在 ROS / URDF 生态里做整机的个人与小团队：hobbyist 升级人形/四足、高校实验室复现开源整机（天工 / LeRobot / Unitree / OpenArm / ToddlerBot / Open Duck Mini）、小型机器人创业团队打样 |
| **他们的任务** | "我手上这个电机（法兰 ISO 9409-1-A50-4-M6）能不能装到这条腿的关节模组上？不能的话有没有转接件？" |
| **为什么是 T1** | ① 已在库的 133+ 开源组件与 URDF 模型库**就是为他们建的**；② 与 Tnkr / UrdfArchitect / RoboInfra 的挂载点完全重合；③ 他们会 star、会提 issue、会写博客——**唯一能产生外部交互痕迹的群体** |
| **判据（可验证）** | GitHub star / issue / PR 数；ROS Discourse 提及；URDF 工具群 issue 回应 |
| **触达** | ROS Discourse、GitHub URDF 生态、Tnkr 承载项目、LobeHub / Glama / 官方 MCP Registry |

#### T2 · 高价值受众：机器人集成商的接口工程师（Integration engineer）

| 项 | 内容 |
|---|---|
| **具体是谁** | 做人形/复合机器人集成的小型集成商，需要在跨厂商零件间做**批量 BOM 可装性筛查** |
| **他们的任务** | "这版 BOM 的 12 个跨厂商接口里，有几个需要转接盘？给我一张表" |
| **为什么是 T2** | ① **唯一有付费动机**（一次判错 = 打样返工成本）；② 对应"API 数据订阅"模式（Octopart 式 ¥200/月起）；③ 但**触达成本高于 T1**，需要等 T1 有社区信号后才有说服力 |
| **判据** | API 订阅转化数；批量 BOM 检查调用量 |
| **触达** | T1 的口碑外溢 + 行业媒体 + 供应链公众号 |

#### T3 · 生态受众：AI Agent / MCP 客户端（不是人）

| 项 | 内容 |
|---|---|
| **具体是谁** | 读 `llms.txt` / 调 MCP 端点的 AI 助手与 IDE 插件 |
| **他们的任务** | "用户问零件兼容 → 我调 check_compatibility → 引用并转述领 key 命令" |
| **为什么是 T3 而不是 T1** | ① **agent 流量当前实测为 0**（`stat:src:agent = 0`）；② 但 MCP 通道是**零边际成本的曝光面**，且国际标准（LobeHub/Glama/Registry）已铺好；③ 定位表述要**同时为人和 agent 写**，但**优先级不能高于 T1** |
| **判据** | `stat:src:agent` 非 0；MCP 端点调用量 |

#### 明确排除的受众（重要）

| 排除对象 | 理由 |
|---|---|
| 终端消费者 / 爱好者买家 | 不买零件、不做 BOM，与判定能力无关 |
| 大型 OEM 采购部门 | 有自己的供应商体系与 PDMLink，不会用第三方数据层 |
| 投资人（作为受众） | waitlist.html 的"我是投资人"选项是**噪音**——投资人不是用户，不该出现在产品候补表单里 |
| 供应商（作为受众） | suppliers.html 的"供应商入驻"是**佣金中介模式的残留**（29 次调用 0 注册已证该模式无效）；供应商不会为"被查到"付费 |

> **一句话**：**砍掉供应商页与投资人选项，聚焦"开源机器人构建者"这一个群体。**

### 3.3 受众定义的一句话版本（可直接用于文案）

> **RoboParts 为开源机器人构建者而生——那些在 ROS/URDF 生态里拼整机、需要确认"这两个零件能不能装到一起"的工程师。**

---

## 四、独特价值主张（UVP）提炼（回答"如何提炼"）

### 4.1 候选 UVP（3 个）

| # | 候选 | 支撑证据 | 强度 |
|---|---|---|---|
| **U1** | **唯一能做"能不能拧到一起"判定的开放数据层** | ISO 9409-1 结构化判定，WebSearch 只返 2 个非官方页面（industrialroboticshub 教学向 / roboticscenter.ai 教学向），**我们是唯一开放源** | ⭐⭐⭐ 独占但市场小 |
| **U2** | **不卖零件的第三方裁决——卖家不适合同时当裁判** | index.html 页脚已写，但埋在底部；厂商自建选型器结构性做不到中立 | ⭐⭐⭐⭐ 结构性差异，竞品无法复制 |
| **U3** | **三态诚实判定：不可判定就说"不知道"，不填 0 假装有数据** | `confirmed/unclassified/noise` 三态 + `not_declared` 显式缺口 + 0 条跨厂商可比公开登记 | ⭐⭐⭐⭐⭐ 业内没人认真做，是内容营销唯一强差异化资产 |

### 4.2 选择：U3 为主，U2 为轴，U1 为落地能力

**为什么以 U3 为主**：
- U1 的"独占"没有变现价值——**因为没人在找这个**（除教学场景）。独占 ≠ 需求。
- U2 很好但**需要对方先知道我们存在**才能感受到"中立"的价值。
- U3 是**别人不会写的东西**：所有竞品都在堆数量（千万级零件库），只有我们公开登记"我们答不出来"。
  - 这个哲学在业内（Moltbook 那篇"数据缺失不是失败，是不确定性"）**没人认真写过**。
  - 它是**最便宜的病毒式传播种子**——一篇讲"为什么我们拒绝编数据"的工程博客，比任何功能列表都容易被转发。
  - 而且它与 T1 受众的**真实痛点精准咬合**：工程师被虚标参数坑过，最信任"敢说不知道"的数据源。

### 4.3 UVP 的一句话版本

> **RoboParts 是唯一会告诉你"我不知道"的机器人零件兼容性数据层——我们公开登记答不出来的部分，因为我们不卖零件，所以没有理由骗你选一个。**

（三句话结构：**独占性**"唯一会告诉你我不知道" + **诚实性**"公开登记答不出来" + **中立性**"不卖零件所以没理由骗你"）

### 4.4 支撑 U3 的三个可验证事实（写文案时必须带）

1. **0 条**跨厂商可直接横向比较的 A 级条目——行业普遍不声明测试条件，我们公开登记这一事实
2. **5.75%** 机械声明率（25/435）——其余如实标 `not_declared`，未作猜测填充
3. **不生产、不销售、不代理任何零部件**——无导流动机，这是厂商自建选型器无法复制的一条差异

---

## 五、定位表述改写（回答"如何调整"）

### 5.1 改写总原则

1. **以机器可读清单为基准反向同步**（见 §1.1）——`server.json` / `lhm.plugin.json` 的描述**已经写对了**，人类页面照它抄即可，不要重新发明
2. **统一到一套**：全站（GitHub description + HTML + README + llms.txt + agent-discovery + 定价页）用同一句定位
3. **品类词归位**："仿生"从第一定位词降级为品类标签之一
4. **受众收窄**：从 7 种说法收到 1 种（开源机器人构建者）
5. **把最强差异提到主位**："中立第三方 + 三态诚实"从页脚提到 H1 下方
6. **地域去圈层**：删"中文圈"，改无国界表述
7. **数字单一来源**：全部走 `onboarding_block.facts()` 现算，GitHub description 也纳入巡检（它是唯一还在手写数字的高曝光位）

### 5.2 逐文件改写对照表

| 文件 | 现状 | 改为 |
|---|---|---|
| **GitHub repo description** | RoboParts — 仿生机器人零部件兼容性平台 \| **688** 条零部件… | **RoboParts — 机器人零部件兼容性判定层（vendor-neutral，开源）\| 798 条实体 / 20 品类 / ISO 9409-1 法兰判定与四维兼容检查**（数字走 `facts()` 注入） |
| `index.html` `<title>` | RoboParts — 开源机器人兼容性平台 | **RoboParts — 机器人零件兼容性判定层（开源）** |
| `index.html` H1 | 开源机器人兼容性平台 | **机器人零件能不能装到一起？我们给你可核验的答案** |
| `index.html` meta desc | 中文圈稀缺的开源机器人兼容性平台：归一化天工 / roboto_origin / LeRobot… | **面向开源机器人构建者的兼容性判定层：ISO 9409-1 法兰判定、BOM 可装性筛查、转接件生成。我们公开登记答不出来的部分——因为不卖零件，所以没理由骗你选一个。** |
| `index.html` 页脚差异声明 | 埋在底部 | **提到 H1 下方第二段**（中立性是最强差异） |
| `README.md` 标题 + §1 定位 | RoboParts — 仿生机器人生态平台 / 仿生机器人模块化选型与设计生态平台 | **RoboParts — 机器人零件兼容性判定层** / 定位：跨厂商零件接口兼容性判定与开源数据层 |
| `llms.txt` 首行 + 概述定位 | 仿生机器人生态平台。配件模块化、接口标准化、协议标准化、大模型产业化、用户数据集成化 | **机器人零件兼容性判定层。** 提供 ISO 9409-1 法兰判定、四维兼容矩阵（机械/电气/协议/ROS）、三态诚实判定与开源数据 API（798 实体） |
| `agent-discovery.json` `site_name` / `tagline` | RoboParts — 仿生机器人生态平台 / 仿生机器人模块化选型与设计生态平台… | **RoboParts — 机器人零件兼容性判定层** / 跨厂商零件接口兼容性判定与开源数据层（798 实体 / ISO 9409-1 法兰登记 / 三态诚实判定） |
| `suppliers.html` | 供应商中心（供应商入驻/目录/询价） | **下线或改为"数据贡献者"页**——把"供应商入驻"改为"贡献机械接口声明"（与我们真正需要的 5.75% 缺口对齐） |
| `waitlist.html` | Builder / 投资人 / 供应商 | 删"投资人"与"供应商"选项，只留**"我是构建者"** |
| `api-pricing.html` `<title>` | API Pricing - **RobotParts** DB | API Pricing - **RoboParts** |
| 全站"仿生" | 作为第一定位词 | 降级为**品类标签**（如"含仿生执行器品类"），不再出现在 title/H1/tagline |

### 5.3 统一后的定位陈述（按长度分三版，各就各位）

**① 一句话版**（GitHub description / title / MCP 目录 / tagline）

```
RoboParts — 机器人零部件兼容性判定层 · vendor-neutral
```
英文对齐（直接沿用 `lhm.plugin.json` 已验证措辞）：
```
RoboParts — Vendor-neutral compatibility judgment layer for robot components
```

**② 标准版**（meta description / README §1 / llms.txt 概述 / agent-discovery tagline）

```
面向开源机器人构建者的兼容性判定层：确认电机、关节、传感器、控制器能不能装到一起、
能不能互相替换；ISO 9409-1 法兰判定 + 机械/电气/协议/ROS 四维兼容检查。
798 实体 / 20 品类，数据 CC BY 4.0 开源。
```

**③ 带差异版**（首页 H1 下方第二段 / README 顶部 / 项目介绍）

```
我们公开登记答不出来 94.25% 的机械接口，不填 0 假装有数据。
RoboParts 不生产、不销售、不代理任何零部件 —— 因此没有把选型结果导向自家产品的动机。
卖家不适合同时当裁判，这是厂商自建选型器无法复制的一条差异。
```

> **关键**：这三版**必须同时替换**，任一处漏改就会出现新的口径分裂（当前 6 套口径就是这么来的）。

---

## 六、落地清单（可执行，按 ROI 排序）

| # | 动作 | 成本 | 修的是什么偏差 |
|---|---|---|---|
| **0** | **改 GitHub repo description**：688 → 798，删"仿生"改"兼容性判定层"，加 vendor-neutral | 5 分钟 | 偏差 6（最高曝光位置的 110 条落差） |
| **1** | 删 `suppliers.html`（或改为"数据贡献"页），`waitlist.html` 删投资人与供应商选项 | 1 小时 | 偏差 2（受众收窄） |
| **2** | `api-pricing.html` title 改 RoboParts DB → RoboParts | 5 分钟 | 偏差 5（品牌漂移） |
| **3** | index.html 删"133+ 开源机器人组件"，统一用 `facts()` 现算值 | 30 分钟 | 偏差 6（同页矛盾） |
| **4** | README § 数据分类改为脚本注入（走 `inject_readme_stats.py`），消 217/220 漂移 | 1 小时 | 偏差 6（跨文件漂移） |
| **5** | 全站 title/H1/tagline 按 §5.2 改写，统一到一套定位 | 半天 | 偏差 1/2/4 |
| **6** | 页脚"中立性"声明提到 H1 下方第二位 | 30 分钟 | 偏差 3（差异化错位） |
| **7** | LICENSE 改为 GitHub 可识别格式（或加 `LICENSE-MIT` + `LICENSE-CC-BY-4.0` 双文件），让 repo `license` 字段不再 `NOASSERTION` | 1 小时 | 偏差 5（开源身份） |
| **8** | 写 3 篇 U3 博客（英文 + 中文 + ROS Discourse），标题围绕"为什么我们拒绝编数据" | 3 天 | UVP 落地（U3） |
| **9** | GEO 全名差异化：所有对外文案统一 "RoboParts.cc"，SEO 标题带"兼容性"以避免与 Amazon Roboparts 相撞 | 半天 | 偏差 5 |

**验收判据**（全部为 grep 可判定）：
- 仓内：`仿生机器人生态平台` = 0 · `RobotParts` = 0 · `中文圈` = 0 · `133+` = 0 · `对标 TraceParts` = 0
- 远端：GitHub repo description 不含 `688`；`server.json` 与 `lhm.plugin.json` 的一句定位与人类页面一致

---

## 七、一句话总结

> **当前定位的核心问题不是"说得不够好"，是"同时说了 6 套，且没有一套被验证过"。**

最该做的三件事：

1. **受众从 7 种收到 1 种**——开源机器人构建者（唯一已验证存在、且能产生外部交互痕迹的群体）；砍掉供应商页与投资人选项
2. **把最强差异从页脚提到主位**——"不卖零件所以没理由骗你选一个"+"公开登记 94.25% 答不出来"，这两条是厂商自建选型器结构性做不到的
3. **以机器可读清单为基准反向同步人类页面**——`server.json` / `lhm.plugin.json` 已经写对了（798 / vendor-neutral / 中立数据层），人类页面照抄即可；同时删掉"仿生""中文圈""对标 TraceParts"这三个与事实不符的定位锚点，并把 GitHub description 的 688 补齐到 798

**一句话**：我们给 AI 写的自我介绍比给人写的更准确——先把人看的那份对齐到 AI 看的那份。

---

## 附录：诊断证据来源

| 类别 | 来源 |
|---|---|
| 定位原文 | `index.html` / `README.md` / `llms.txt` / `agent-discovery.json` / `api-pricing.html` / `suppliers.html` / `waitlist.html` / `server.json` / `smithery.yaml` / `lhm.plugin.json` / `.well-known/mcp.json` 逐个抓取 |
| 数字对账 | `api/entities.json` → `meta.category_counts` / `meta.mechanical_interface_coverage` / `meta.provenance_coverage` 现算 |
| 竞品状态 | `ops/results/_MARKET_POSITIONING-20260918.md` + `docs/tnkr-increment-20260920.md` |
| GitHub 信号 | api.github.com REST（2026-09-21 实测：0 star / 0 fork / 0 issue / license `NOASSERTION` / description 含 688） |
| 受众现状 | `docs/phase2-plan-20260921.md` §3.2（三类受众分层） |
