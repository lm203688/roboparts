# RoboParts 查缺补漏审计报告

> 生成日期：2026-10-17
> 扫描范围：全仓（868 实体 / 41 页面 / 64 闸门 / 50 个 Functions / 80 个 api 产物）
> 审计视角：**只找"漏"** —— 承诺了没做、该有却无、有但坏了、做了但漂了
> 取证方式：全仓静态扫描 + 产物现算 + 源码级根因定位 + 线上回探（不手工改任何产物）

---

## 0. 摘要：这次查出了什么

项目在 10-15~10-16 两轮里补了大量地基（闸门 49→60→64，D1/D2/D5 系列收口），**工程治理层面已经相当扎实**。但本次以"找漏"为唯一目标重扫后，发现**治理闸门的密度，与数据本体质量之间存在明显落差**——闸门管住了"数字对不对齐"，却没有管住"证据是不是真的"。

按严重度分档，共查出 **16 项缺口**：

| 级别 | 数量 | 一句话概括 |
|---|---|---|
| 🔴 **致命** | 3 | Tier A 溯源被搜索引擎链接污染（50.6%）；组合判定 43 万对产出 0；单测实际跑 0 个 |
| 🟠 **严重** | 6 | 37 条占位实体；24 条重复实体；机械可判定率 6.6%；`last_verified` 缺 34.7%；BOM 明文存储；11 页不可达 |
| 🟡 **中等** | 5 | 硬编码数字漂移；无 hreflang；空品类；协议基准覆盖 57.8%；死链 1 条 |
| 🔵 **轻微** | 2 | 无 meta description 11 页；无 og:title 32 页 |

**最需要立刻处理的一条**：
> 239 条实体的溯源 URL 是 `https://www.google.com/search?q=...+datasheet`——这是"我没找到，我搜了一下"，不是数据手册。但它们**全部被判为 Tier A（最高可追溯等级）**，占 Tier A 总数 472 的 **50.6%**。任何人点开 `source_url` 复核，看到的是搜索结果页。

对一个把"可追溯 / 诚实"当唯一卖点的项目，这是**比任何功能缺失都贵的漏洞**。

---

## 1. 方法：四把"找漏"尺子

本次不评价优劣，只回答四个问题：

1. **承诺尺** —— README / docs 里写了什么，代码和数据里是否真的有？
2. **覆盖尺** —— 该有的能力，实际覆盖到多少？（分母是谁，分子的真实含义是什么）
3. **一致尺** —— 同一事实在不同文件里是否漂移？
4. **盲区尺** —— 64 道闸门管住了什么，**没管住什么**？

第四把尺子最关键：**凡是闸门没管的维度，就是漏的温床**。本报告 16 项缺口中，有 11 项落在闸门盲区里。

---

## 2. 🔴 致命缺口（3 项）

### G-01 · Tier A 溯源被搜索引擎链接污染（239 条 / 占 A 级 50.6%）

**现象**

全库 868 条实体中，239 条的 `source_url` 是 Google 搜索链接，形态统一为：

```
https://www.google.com/search?q=MIT%2FCustom%20MIT%20Mini%20Cheetah%20Actuator%20datasheet
https://www.google.com/search?q=RoboDrive%2FKollmorgen%20RoboDrive%20ILM%2070%20datasheet
https://www.google.com/search?q=Dexai%2FWonik%20Robotics%20Dexai%20Allegro%20Hand%20v4%20datasheet
```

这 239 条的 `source_tier` 全部是 **A**，无一例外。

**实测交叉表**（`basis` × `tier`）

| source_tier_basis | A | B | C | 合计 |
|---|---|---|---|---|
| **GOOGLE搜索链接** | **239** | 0 | 0 | **239** |
| deep_link（真深链） | 198 | 0 | 0 | 198 |
| root_url_only | 0 | 158 | 0 | 158 |
| named_vendor_catalog | 0 | 76 | 0 | 76 |
| entity_homepage | 35 | 0 | 0 | 35 |
| aggregation_no_anchor | 0 | 0 | 61 | 61 |
| no_source | 0 | 0 | 61 | 61 |
| named_standard | 0 | 12 | 0 | 12 |
| unattributable_text | 0 | 0 | 25 | 25 |

即：**Tier A 共 472 条 = 239（谷歌搜索）+ 198（真深链）+ 35（实体主页）**。
真正"点开即落到具体产品/文档页"的只有 **233 条（49.4%）**。

**根因（源码级定位）**

`scripts/govern_source_tier.py` 的 `_is_deep()`：

```python
def _is_deep(u):
    ...
    path = (p.path or '').strip('/')
    # 只有 query 也算能定位（如 ?id=xxx 的详情页）
    return bool(path) or bool(p.query)      # ← 问题在这行
```

`google.com/search?q=...` 有 query ⇒ `_is_deep()` 返回 `True` ⇒ `derive_tier()` 直接判 A。

注释里"如 `?id=xxx` 的详情页"这个假设对**详情页**成立，对**搜索查询页**不成立——`?q=` 的语义恰恰是"尚未定位到具体页面"。

**这恰恰是该脚本自己批判过的那个 bug 的同类变种**：

> 脚本头部 docstring 记录：旧实现是 `if e.get('source'): return 'A'`（source 非空就送 A），导致
> "336 条 A 级中真有深链的只有 48 条（14.3%）……对外虚报约 5 倍"。
> 修完之后的新实现，把"非空"换成了"有 query"，**污染率从 85.7% 降到 50.6%，但漏洞类型没变**。

**闸门盲区**

64 道闸门中**没有任何一道**校验"Tier A 的 URL 是否指向具体页面 vs 搜索引擎/聚合站"。
`NO_ANCHOR` 黑名单里其实已有 `'web search'` / `'web_search'`，但它只在**无 URL** 分支的文本判断里生效——有 URL 时根本走不到。

**影响**

- 对外契约字段 `source_tier` 被 MCP/API 消费方用于来源过滤，**A 级语义被稀释一半**
- 与 README §11 的对外话术直接冲突：README 明确写 "All 10 entries were elevated to Tier A via real HTTP verification (200 + page hit)"
- 任何合作方"随机抽 10 条 A 级点开复核"，有一半概率点到搜索页

**修复方案（可直接执行）**

1. 在 `govern_source_tier.py` 增加**搜索引擎/聚合站域名黑名单**（`google.com/search`、`bing.com/search`、`baidu.com/s`、`duckduckgo.com` 等），命中即降级：
   - 有 `?q=` 类搜索参数 ⇒ 判 **C**（无溯源，等同于"我没找到"）
   - 具体判定可复用 `source_tier_basis` 写入 `search_engine_query`
2. 把同名 239 条**批量重算**，预期 Tier A 由 472 降到约 233
3. **新增闸门 G-T1**：`source_tier == 'A'` 的实体，其 URL 域名不得命中搜索/聚合黑名单；违者判红
4. 同步修正 README §11 的"A 级经真实 HTTP 验证"话术——**只对修复后的 233 条成立**

**验收口径**：修复后 `Tier A` 中"点开即具体产品页"占比 = 100%（而不是现在的 49.4%）。

---

### G-02 · 组合判定 43 万对，产出 `composed = 0`

**现象**

`api/compose_semantics.json` 实测：

```
pairs_evaluated : 430,336
overall_counts  : { composed: 0, type_error: 262, unknown: 430,074 }
```

**43 万对里，没有一对判出"能组合"，99.94% 是 unknown。**

分轴边际：

| 轴 | compatible | compatible_via_adapter | incompatible | unknown |
|---|---|---|---|---|
| mechanical | 1,958 | 2,138 | 0 | 426,240 |
| electrical | 35 | 0 | 262 | 430,039 |
| signal | 57,000 | 0 | 0 | 373,336 |

三轴合取后 ⇒ 0。

**这是不是 bug？**

不完全是。项目的三态 fail-closed 设计要求"不可判定就报 unknown"，而机械轴 98.9% 是 unknown（因为孔位数据缺失），所以合取必然是 0。**从"诚实"角度看，这是正确的输出**。

**但从"查缺"角度看，它暴露的真实缺口是**：

> 组合演算这台机器**建好了、跑通了、数字守恒了**，但它**几乎没有可吃的输入**。
> 输入侧的机械接口数据缺口，让这台机器的实际产出是 0。

**与 G-03（机械可判定率 6.6%）是同一个根因的两面。**

**修复方向**

不应去改判定逻辑（那会导致假绿），而应**补输入**：
- 见 G-03 的"可判定实体"扩充方案
- 建议新增对外 KPI：`decidable_pairs`（可判定对数）而非 `pairs_evaluated`（评估对数）——后者现在是个虚荣指标

---

### G-03 · `npm run test:unit` 实际跑 **0 个测试**

**现象**

`package.json` 配置了完整测试链：

```json
"test": "npm run test:unit && npm run test:integration",
"test:unit": "node --test tests/**/*.test.mjs tests/**/*.test.js 2>&1 || node --test tests/*.test.mjs tests/*.test.js",
```

实测运行 `npm run test:unit`：

```
TAP version 13
1..0
# tests 0
# suites 0
# pass 0
# fail 0
```

**0 个测试被执行。**

**根因**

`tests/` 目录下实际文件名是：

```
tests/test_bom_assembly.mjs
tests/test_feedback_loop.mjs
tests/test_p0_multifactor.mjs
tests/test_p1_recommender.mjs
tests/test_promote_ledger.mjs
tests/property/test_compose_lattice.py
```

**没有一个匹配 `*.test.mjs` 模式**（是 `test_*.mjs`，不是 `*.test.mjs`）。
主 glob 落空后，fallback 分支 `tests/*.test.mjs` 同样落空，于是静默跑 0 个并**返回退出码 0**（因为 `||` 右侧成功）。

**为什么这是致命的**

- `npm test` 在 README / CI 语境里是"我有测试"的证据，实际是**空转**
- 更危险的是它**不报错**：退出码 0，任何 CI 都会认为通过
- 这与昨日地基报告里的"测试:代码 ≈ 1:111"是同一个问题的两面——**真实测试量比统计的还少**

**修复方案**

1. 统一命名：把 `test_*.mjs` 重命名为 `*.test.mjs`（与 glob 对齐），或反过来改 glob
2. **必须加"零测试即失败"守卫**：`node --test` 跑出 `tests 0` 时判红，而不是静默通过
3. `test:integration` 分支 `python -m pytest tests/ -x -q 2>/dev/null || python scripts/ci_gate.py` —— `2>/dev/null` 会把 pytest 缺失/失败全部吞掉后**静默降级到 ci_gate**，等于"pytest 没装也看不出来"。建议去掉静默，显式检测
4. 接入 GitHub Actions（当前 `.github/workflows` 未调用 `npm test`）

---

## 3. 🟠 严重缺口（6 项）

### G-04 · 37 条占位 ID 实体仍在生产库中

**现象**

按"字母数字严格交替"模式（`A1B2C3` / `a1b2c3` / `M3N4O5`）检出 **37 条**实体：

| 品类 | 数量 | 样本 |
|---|---|---|
| llms | **20** | `LLM-a1b2c3`、`LLM-d4e5f6`、`LLM-g7h8i9`… |
| actuators | 8 | `ACTUATOR-A1B2C3`、`ACTUATOR-D4E5F6`、`ACTUATOR-M3N4O5`… |
| protocols | 8 | `PROTOCOL-*` 同型 |
| chips | 1 | `CHIP-a1b2c3` |

**`llms` 那 20 条尤其不成立**——它们不是实体，是品类词和常识词：

```
LLM-a1b2c3  墨茵机器人      ← 公司名
LLM-d4e5f6  乐聚机器人      ← 公司名
LLM-g7h8i9  宇树机器人      ← 公司名
LLM-j0k1l2  AI芯片          ← 品类词
LLM-m3n4o5  人形机器人      ← 品类词
LLM-p6q7r8  人形机器人      ← 品类词（且与上一条重复）
LLM-s9t0u1  机器人新技术    ← 概念词
LLM-v2w3x4  辅助驾驶        ← 领域词
LLM-y5z6a7  AR眼镜          ← 品类词
LLM-b8c9d0  消费电子        ← 品类词
LLM-a3b7c9  GPT-4           ← 通用语言模型，非机器人模型
LLM-d4e8f2  BERT            ← 同上
LLM-g5h1j3  LLaMA           ← 同上
LLM-k6m4n5  PaLM / LLM-p7q8r9 Claude / LLM-s2t3u4 Falcon
LLM-v5w6x7  Mistral / LLM-y8z9a1 Gemini / LLM-b2c3d4 XLNet / LLM-e5f6g7 RoBERTa
```

这 20 条**全部** `source_tier=C`、`basis=no_source`、`confidence_tier=unverified`、`verified=False`。

**诚实的部分**：它们**全部 `quarantine=True`**（47 条无 source 实体中 100% 被隔离），D5 闸门是绿的。项目没有藏。

**但仍然是漏**：
- 它们**计入对外播报的 868**（`meta.total_entities=868` 含隔离件）
- 10 条通用语言模型放在 `llms`（机器人 AI 模型）品类，是**分类错误**
- 6 条品类词/概念词根本不是实体

**修复方案**
1. 20 条 `LLM-*` 占位：**建议直接删除**（不是补 source——GPT-4 不需要出处，它不该在这个库里）
2. `ACTUATOR-*`/`PROTOCOL-*`/`CHIP-*` 的 17 条：保留但必须补真实出处，或转 `quarantine`
3. 对外播报增加**双数字**：`868 总条数 / 755 可用条数（已排除 113 条 quarantine）`
4. **新增闸门 G-T2**：实体名不得等于某个品类名的归一化形式（防止"人形机器人"这种品类词入库）

---

### G-05 · 24 条重复实体（16 组），且跨越不同 ID 体系

**现象**

归一化后完全同名的组有 16 组、涉及 24 条实体：

| 归一化名 | 重复 ID |
|---|---|
| shadowdexteroushand | `ACT-030` / `BIONIC-HAND-003` |
| agilityroboticsdigitactuator | `ACT-032` / `ACTUATOR-M3N4O5` |
| 1xneoactuator | `ACT-1x-neo-actuator` / `ACTUATOR-S9T0U1` |
| rockchiprk3588 | `CHIP-007` / `CHIP-099` |
| jetsonorinnx | `CHIP-66` / `CHIP-81` |
| qualcommrb5 | `CHIP-68` / `CHIP-91` |
| qualcommqrb5165 | `CHIP-80` / `CHIP-95` |
| teslaoptimusgen3 | `RPLAT-009` / `RPLAT-010` |
| smolvla | `LLM-029` / `RAI-008` |
| syntouchbiotac仿生触觉传感器 | `sensor-tactile-001` / `SENS-056` |
| ces2026robotinterface | `INTERFACE-pqr678` / `INTERFACE-vwx234` |
| 人形机器人 | `LLM-m3n4o5` / `LLM-p6q7r8` |

按 `name_en` 归一后有 20 组（更多）。

**为什么这是漏**

- 重复跨越了**三套 ID 命名体系**（`ACT-*`/`CHIP-*`/`SENS-*` 早期体系 vs `ACT-*` 语义化体系 vs `ACTUATOR-*` 占位体系），说明**历次批量导入未做跨体系去重**
- 后果：同一物理零件在库里有两条 ⇒ 兼容性判定可能给出**不同结论** ⇒ 868 这个数字虚高

**闸门盲区**：64 道闸门中无"重复实体检测"。

**修复方案**
1. 跑一次全库去重扫描（按 `name_en` 归一 + `manufacturer` 复合键）
2. 对 16 组逐组人工裁决：保留信息更全的一条，另一条标 `duplicate_of` 并 quarantine
3. **新增闸门 G-T3**：归一化 `name_en` + `manufacturer` 唯一性约束，违者判红

---

### G-06 · 机械接口"真实可判定率"仅 **6.6%**，且分布极端畸形

**现象**

README 对外播报"机械接口声明率 16.2%（81/500）"。本次按更严格的口径复核：

`mechanical_interface.status` 分布：

| status | 数量 |
|---|---|
| not_declared | 419 |
| **n_a**（不适用） | 368 |
| declared | 67 |
| partial | 14 |

真正能用于法兰判定的口径是「`standard` 与 `flange` **同时非空**」：

```
57 / 868 = 6.6%
```

**按品类看，分布极端畸形**：

| 品类 | 可判定数 |
|---|---|
| platforms | **55** |
| bionic_mechanisms | 1 |
| grippers | 1 |
| **actuators** | **0** |
| 其他所有品类 | 0 |

**即：868 条里真正能做机械装配判定的只有 57 条，其中 55 条是整机平台；占库 25.6% 的执行器品类，可判定数为 0。**

**为什么这是严重缺口**

- 项目自称"最大缺口是机械声明率"，但**真实数字（6.6%）比公开数字（16.2%）严峻 2.5 倍**——两个数字分母不同（868 vs 500），口径未对外统一
- 更关键的是**结构问题**：可判定能力集中在"整机平台"，而组合判定的主战场（执行器↕减速器↕法兰）几乎全空
- 这直接解释了 G-02 为什么 `composed=0`

**修复方案**
1. **对外统一口径并同时播报两个数**：`声明率 16.2%（81/500，含 partial）` + `可判定率 6.6%（57/868，standard+flange 俱全）`
2. 把补齐方向从"广撒网"改成**定向**：优先补 `actuators`（222 条，当前 0 条可判定）
3. 建议新增 KPI：`decidable_entities_by_category`，按品类追踪，避免"platforms 撑起全部指标"

---

### G-07 · `last_verified` 缺失 301 条（34.7%），与 README 硬承诺冲突

**现象**

README §4 明确写：

> 📋 **Data quality labeling** — every entity labeled with **source / confidence / last_verified**

实测：

| 字段 | 缺失数 | 缺失率 |
|---|---|---|
| `last_verified` | **301** | **34.7%** |
| `source_url` | 287 | 33.1% |
| `description` | 254 | 29.3% |
| `manufacturer` | 227 | 26.2% |
| `standard_conformance` | 53 | 6.1% |
| `source` | 47 | 5.4% |
| `confidence` | 0 | 0% |

`last_verified` 缺失集中在：actuators 74 / chips 55 / protocols 35 / robot_ai_models 24 / grippers 23。

**这是"承诺尺"下的直接违约**：README 说"每个实体都有"，实际三分之一没有。

**修复方案**
1. 二选一，且必须自洽：
   - **方案 A（推荐）**：把 301 条的 `last_verified` 补成"入库日期"并标注 `verified=False`（承认未复核）
   - **方案 B**：修改 README 话术为"标注了 source / confidence，last_verified 覆盖 65.3%"
2. 建议选 A——因为 `last_verified` 缺失会让消费方无法判断数据新鲜度，而这正是本项目的核心卖点
3. **新增闸门 G-T4**：`last_verified` 覆盖率必须 ≥ 上次运行值（棘轮，只增不减）

---

### G-08 · 核心目标 5「端到端加密」实际是明文存储

**现象**

README §2 Core Goal 5：

> **User data integration** — **end-to-end encryption** of selection plans / BOM / design files, protecting user habits and privacy

实测存储链路：

```javascript
// functions/api/bom/store.js:113
await env.USER_CREDITS.put(bomKey, JSON.stringify(boms));   // ← 明文 JSON 直存 KV

// bom-manager.html:351
localStorage.setItem('roboparts_api_key', key);              // ← API Key 明文存 localStorage
```

全仓加密相关代码只出现在 4 个文件，且**全部是支付/积分域**：
- `functions/api/credits/balance.js`（SHA-256 哈希 email）
- `functions/api/payment/notify.js`（支付签名）
- `functions/api/register.js`、`waitlist.js`

**选型方案与 BOM 的存储路径上，没有任何加密。**

**修复方案**
1. 二选一：
   - **方案 A（推荐，成本低）**：修改 README 话术为"传输层 HTTPS + KV 静态加密，BOM 以 API Key 隔离"，**删除"端到端加密"表述**
   - **方案 B（成本高）**：真做 E2EE——客户端 `crypto.subtle` 加密后上传，服务端只存密文。但这与"服务端要做 BOM 校验"冲突，需要架构权衡
2. 强烈建议选 A：**在一个把诚实当卖点的项目里，"说了没做"比"没做"贵得多**
3. 前端 API Key 明文存 localStorage 应改为 `sessionStorage` 或加短期过期

---

### G-09 · 11 个页面从首页不可达（含 3 个功能页）

**现象**

全站 41 个根页面，首页链出 28 个，**11 个不可达**：

```
api-pricing.html      assembly.html        bom-import.html
compatibility-viz.html credits-history.html geo-dashboard.html
order.html            promo-poster.html    promotion.html
reference-builds.html  supplier-admin.html
```

其中 `assembly.html`（装配）、`compatibility-viz.html`（兼容可视化）、`reference-builds.html`（参考构型）是**核心功能页**，用户从首页走不到。

（注：较昨日报告的 20 个已收敛至 11 个，说明有修复在推进。）

**另发现 1 条真实死链**：

```
funnel.html  →  analytics.html   （analytics.html 不存在）
```

**修复方案**
1. 首页补链：优先 `assembly` / `compatibility-viz` / `reference-builds`
2. `funnel.html` 的 `analytics.html` 链接改为指向已有页面，或创建该页
3. **新增闸门 G-T5**：全站 HTML 的站内 `href`（排除模板字符串 `${}`）必须指向存在的文件；违者判红
4. **新增闸门 G-T6**：根页面集合中，除白名单（`404`/`order`/`supplier-admin` 等后台页）外，必须可从首页 BFS 到达

---

## 4. 🟡 中等缺口（5 项）

### G-10 · 硬编码数字漂移（3 处）

| 位置 | 硬编码值 | 实际值 | 漂移 |
|---|---|---|---|
| `functions/api/compatibility.js:165,174` | "未在 **868** 个实体中匹配到" | 868（当前对，但会随数据变） | ⚠️ 静态写死 |
| `functions/api/search.js:19,141` | "本库 **99** 条标记 quarantine" | **113** | ❌ 差 14 |
| `functions/mcp.js:922` | "**86** 条 AI 模型" | **81**（software） | ❌ 差 5 |

**这三处都在注释/提示语里，不进闸门**——所以数字变了没人知道。

**修复**：改为运行时从 `entities.json` 读取；新增闸门 G-T7——扫描 `functions/` 注释中的"N 条/个实体"硬编码，与真相源比对。

---

### G-11 · 国际化：40/41 页面无 `hreflang`

项目定位明确写"国际化锚点：ISO 9409-1 + ISO 22166-1"，但：

| 项 | 实测 |
|---|---|
| `<html lang>` 分布 | `zh-CN` 39 / `en` 1 / **缺失 1**（`order.html`） |
| 含 `hreflang` 的页面 | **1 / 41** |
| 英文版页面 | 1（`mcp-guide.html`） |

**即：40 个页面没有 hreflang 声明，也没有英文对应版本。**

对"国际化定位"而言，搜索引擎无法识别语言版本关系，英文用户只能看到中文页。

**修复**
1. `order.html` 补 `lang` 属性
2. 至少为**入口页**补 `hreflang="zh-CN"` / `x-default`
3. 英文版优先级：README 已有完整英文段落，建议先出 `index` / `compatibility-viewer` / `api-pricing` 三页英文版

---

### G-12 · 7 个结构性空品类

| 品类 | 条目数 |
|---|---|
| integrated_joints | 1 |
| connectors / cables / power / pcb | 各 2 |
| structural | 3 |
| controllers | 4 |

**这些品类"建了但没填"**。对用户而言，点进一个只有 2 条数据的品类，体验低于"没有这个品类"。

而且 `connectors`（2 条）尤其尴尬——连接器是线缆/信号轴判定的关键，却几乎是空的。

**修复**
1. 要么**补齐**（connectors/cables/power 优先，它们是电气轴判定的输入，见 G-02）
2. 要么**对外隐藏**空品类（<5 条不进导航），并在 docs 里记录"该品类待建设"
3. 建议选 1：`connectors` 与 `cables` 直接支撑电气轴，是补数据 ROI 最高的方向之一

---

### G-13 · 协议实时性能基准覆盖仅 57.8%

README §2 Core Goal 3 承诺"EtherCAT/CANopen/ROS2/MQTT 协议栈对比、**实时性能基准**、跨协议桥接"。

实测：64 条 `protocols` 实体中，含延迟/抖动/带宽类字段的只有 **37 条（57.8%）**，27 条无性能数据。

**修复**：为 27 条补 `latency` / `jitter` / `bandwidth` 结构化字段（带出处），或明确标注"该协议暂无基准数据"。

---

### G-14 · 空品类与可判定性的结构性错配

（与 G-06/G-12 相关，单列以便追踪）

`mechanical_interface` 的 `n_a`（不适用）有 368 条，其中 `software`(81) / `specification`(101) / `market_intelligence`(17) / `organization`(10) 共 209 条本就不该有机械接口——这部分 `n_a` 是**正确的**。

但 `component`(659) 里有 159 条标 `n_a`，**实物零件标"不适用机械接口"需要解释**。建议逐条复核，把"真的不适用"（如线缆）与"其实是没采集"区分开。

---

## 5. 🔵 轻微缺口（2 项）

### G-15 · 11 页无 `meta description`

```
api-pricing / bom-checker / bom-import / compatibility-viz /
designer / funnel / order / oss / ...（共 11）
```

### G-16 · 32 页无 `og:title`

社交分享卡片缺少 Open Graph 标题，分享到微信/Twitter 时无摘要。

**修复**：批量补 `meta description` + `og:title`（可脚本化，1 小时内可完成）。

---

## 6. 补缺清单（按 ROI 排序）

### 第一梯队：本周必做（4 项）

| # | 缺口 | 动作 | 预期效果 |
|---|---|---|---|
| 1 | **G-01** | `govern_source_tier.py` 加搜索引擎黑名单 + 重算 239 条 + 新增闸门 G-T1 | Tier A 从 472 → ~233，**A 级语义 100% 真实** |
| 2 | **G-03** | 统一测试文件命名 + 加"零测试即失败"守卫 | `npm test` 从 0 个 → 真实执行 |
| 3 | **G-09** | 首页补 3 个功能页链接 + 修 `funnel→analytics` 死链 | 核心功能可达 |
| 4 | **G-07** | 301 条 `last_verified` 补入库日期 + 新增棘轮闸门 G-T4 | 消除 README 违约 |

### 第二梯队：两周（4 项）

| # | 缺口 | 动作 |
|---|---|---|
| 5 | G-04 | 删除 20 条 `LLM-*` 占位；17 条 `ACTUATOR-*`/`PROTOCOL-*` 补源或隔离 |
| 6 | G-05 | 16 组重复实体裁决 + 新增唯一性闸门 G-T3 |
| 7 | G-10 | 3 处硬编码改为运行时读取 + 闸门 G-T7 |
| 8 | G-08 | README 删除"端到端加密"表述，改为准确描述；API Key 改 sessionStorage |

### 第三梯队：一个月（4 项）

| # | 缺口 | 动作 |
|---|---|---|
| 9 | G-06 | 对外双口径播报 + 定向补 `actuators` 机械声明 |
| 10 | G-11 | 补 `lang` + 关键页 `hreflang` + 3 页英文版 |
| 11 | G-12 | `connectors`/`cables`/`power` 补齐（支撑电气轴） |
| 12 | G-13 | 27 条协议补性能基准字段 |

### 第四梯队：体验打磨（2 项）

| # | 缺口 | 动作 |
|---|---|---|
| 13 | G-15/G-16 | 批量补 meta description + og:title |
| 14 | G-14 | 复核 159 条 component 的 `n_a` 标注 |

---

## 7. 建议新增的 7 道闸门（防复发）

本次 16 项缺口中，**11 项落在闸门盲区**。建议新增：

| 闸门 ID | 管什么 | 防哪个缺口 |
|---|---|---|
| **G-T1** | Tier A 的 URL 不得命中搜索/聚合站黑名单 | G-01 |
| **G-T2** | 实体名不得等于品类名归一化形式 | G-04 |
| **G-T3** | `name_en` + `manufacturer` 复合唯一性 | G-05 |
| **G-T4** | `last_verified` 覆盖率棘轮（只增不减） | G-07 |
| **G-T5** | 站内 `href` 必须指向存在的文件 | G-09 |
| **G-T6** | 根页面 BFS 可达性（白名单外） | G-09 |
| **G-T7** | `functions/` 注释中的实体数硬编码 vs 真相源 | G-10 |

**设计原则**：这 7 道闸门的共同点是——**它们管的都是"语义正确性"，而不是"数字对齐"**。现有 64 道闸门绝大多数在管后者（数字是否一致、schema 是否合法、产物是否新鲜），而本次查出的漏几乎全在前者。

> **一句话总结这个模式**：项目已经能把"数字算对"这件事管得很好，但还没开始管"证据是不是真的"。

---

## 8. 诚实边界（本报告自身的局限）

1. **G-01 的 239 条未经 HTTP 回探验证**——本地环境对 `google.com` 的代理返回 502，无法实测链接可达性。判定依据是 **URL 形态**（`google.com/search?q=`），而非实测。**形态已足以证明它不是数据手册**，但若需逐条确认"该型号是否另有真实出处"，需联网复验。

2. **G-06 的 6.6% 是本项目自定义口径**（`standard` + `flange` 同时非空）。它与 README 的 16.2%（81/500，含 `partial`）**分母与口径都不同**，不构成"README 造假"的结论，只构成"口径未统一、易被误读"的结论。

3. **G-04 的 37 条占位 ID 是基于命名模式推断**（字母数字严格交替）。`ACT-1x-neo-actuator` 这类语义化 ID 不在其中。可能存在未被该模式捕获的其他占位条目。

4. **G-05 的重复判定基于 `name` / `name_en` 归一化字符串相等**。不同厂商的同名型号（如两家都叫 "A301"）可能被误判；已列出的 16 组经人工抽查，均为真重复。

5. **G-08 的"无端到端加密"结论基于静态扫描**（grep `encrypt` / `crypto` 关键词 + 读存储路径）。未做运行时抓包验证。

6. **G-03 的 `npm test` 结论经实测运行确认**（输出 `tests 0 / pass 0`），但 `test:integration` 分支因本地无 pytest 未能完整验证，其"静默降级"问题是代码级推断。

---

## 附录 A：本次扫描的取证入口

```bash
# 数据层
python -c "import json;d=json.load(open('api/entities.json',encoding='utf-8'));..."

# 溯源定级逻辑
sed -n '123,165p' scripts/govern_source_tier.py      # _is_deep / derive_tier

# 闸门清单
python scripts/ci_gate.py --list                      # 64 道

# 测试体系
npm run test:unit                                     # 实测输出 tests 0

# 页面可达性
python -c "...BFS from index.html..."                 # 11 页不可达

# 判定产出
python -c "import json;d=json.load(open('api/compose_semantics.json'));print(d['aggregates']['overall_counts'])"
```

## 附录 B：与历史报告的关系

| 报告 | 焦点 | 本次的增量 |
|---|---|---|
| 板块评估报告（10-13） | 9 大板块成熟度分档 | — |
| 远景提升方案（10-15） | L1–L5 五个跃迁 | — |
| 地基审计报告（10-16） | 六层地基体检 | 本次发现其 §F5 的 61 条无 source 已收敛至 47 条且全隔离 ✅ |
| **本报告（10-17）** | **只找漏** | **新增：Tier A 污染 / 占位实体 / 重复实体 / npm test 空转 / 明文存储** |

---

*本报告所有数字均由脚本现算，未手工填写。修复后请重跑 `python scripts/ci_gate.py` 与 `npm test` 验证。*
