# 应有特征推导层（Predicted-Feature Index）

**产物**：`api/derived_features.json`（schema `derived_features/v1`）
**生成器**：`scripts/build_derived_features.py`（唯一真相源，挂部署链 0b6）
**实测日期**：2026-09-16

---

## 1. 它在解决什么问题

本站此前的机械数据只有一路来源：**厂商声明**。这带来两个硬伤：

1. **声明率就是判定天花板。** 厂商不写，平台就无从判断。`api/standard-audit.json` 实测只有 29 条机械声明，覆盖 16 个实体，占全站 798 个实体的 2%。
2. **声明层自身无法自我校验。** 登记表里手写的 `is_canonical_iso` 布尔值和 `note` 里的"偏离 ISO 标准梯级为 N×Mk"都是人写的断言，没有任何机制能发现它们写错。

推导层的思路：**不采集数据，只推导**。给一个 ISO 9409-1 标号，按标准梯级算出它「应当」有什么孔数、什么螺纹、什么外径，然后把声明值拿来比。

## 2. 方法学出处：与 MS2KOSMOS 同构

Cornell 的 **MS2KOSMOS**（bioRxiv 2026.08）在质谱鉴定上做的事与本层同构：

| | MS2KOSMOS | 本层 |
|---|---|---|
| 观测对象 | 质谱峰 | 法兰几何 |
| 朴素做法 | 拿观测谱图去检索已知谱图库 | 拿厂商声明去查登记表 |
| 天花板 | 谱图库里没测过的分子判不了 | 厂商没声明的参数判不了 |
| 突破点 | **预先对已知小分子结构计算出应有的观测谱图**（8 亿+ 预测谱）再入库 | **预先从标准梯级算出应有几何**再入库 |
| 效果 | 未测过的观测也能被比对 | 未声明/无规范行的标号也能被判定 |

关键洞察一致：**把"期望值"当成可索引的资产**，而不是等观测自己长出来。

## 3. 推导规则

以 `d1_mm`（PCD）为键查 `canonical_ladder_iso_9409_1`，得应有 `(holes, thread, iso_outer_diameter)`：

| 分类 | 判据 | 本轮实测 |
|---|---|---|
| `matches_canonical` | 实测孔数与螺纹同时等于梯级期望 | 4 |
| `deviates_thread_only` | 孔数相同，仅螺纹不同 | 1（A31.5-4-M5） |
| `deviates_holes_and_thread` | 孔数不同（螺纹可能同时不同） | 2（A100-4-M8、A160-4-M12） |
| `no_standard_rung` | 该 PCD 不在标准梯级上，给出最近 2 档 | 2（A20-4-M3、A250-4-M16） |

`no_standard_rung` 不是判错——KUKA KR1000 TITAN 实测确实是 PCD250 4×M16，只是该尺寸不在 ISO 9409-1 标准梯级里。推导层给出最近档（PCD200 8×M20、PCD160 8×M16）供转接与选型参考，不臆造"应当是什么"。

## 4. 交叉验证结果（本轮实测）

### 4.1 独立复现 `is_canonical_iso`

推导层不读 `is_canonical_iso` 字段，而是从几何独立算出结论，再与手写字段比对：

**9/9 一致，0 分歧。**

这是**内部一致性**校验：两个独立写法对同一事实下结论，不一致即登记数据有错。本轮没有发现错，但这个闸门是新的——此前手写字段无人看管。

### 4.2 机械复算手写 `note`

`note` 里的"偏离 ISO 标准梯级为 N×Mk""最近为 PCDx"这类断言，以前只能相信人写的话。现在可机械复算：

**5 条含断言的 note，5 条可机械解析，5 条与推导一致，0 条不可解析。**

例如 `A31.5-4-M5` 的 note 同时写了实测值（4×M5）与标准值（4×M6），推导独立算出期望为 4×M6 → 一致。

不可解析的断言计为 `unparseable` 而非通过——宁可留白，不制造假绿。

### 4.3 实体侧标号判定

| 标号 | 实体数 | 裁决 |
|---|---|---|
| `ISO 9409-1-50-4-M6` | 15 | `registered_and_canonical` |
| `ISO 9409-1-31.5-4-M5` | 7 | `registered_documented_deviation`（ISO 期望 4×M6，实测 4×M5） |
| `ISO 9409-1-40-4-M6` | 6 | `registered_and_canonical` |
| `ISO 9409-1` | 1 | `unparseable_bare_standard`（BIONIC-HAND-002，只给标准号没给几何） |

4 个在用标号中 3 个可由推导层判定，覆盖 28 个实体（去重）。第 4 个不是数据缺口可补，是厂商未声明到可判定粒度——本层如实标记，不硬判。

## 5. 同轮发现的两个冻结快照（已修）

推导层上线的同时暴露了两处**对外假陈述**，均为同一族病：派生物一旦对外，就必须和真相源同一时刻更新。

### 5.1 `designations_in_use` 区块

`api/mechanical_interfaces.json` 里的该区块原由 `scripts/curate_flange_registry_20260811.py` 一次性写死，此后未重算：

| | 存盘快照 | 实际现算 |
|---|---|---|
| `total_tokens_in_use` | 3 | 4 |
| `unregistered_count` | **2** | **0** |
| `used_by_entity_ids` | `[ACT-028, SENS-31]` | 16 个实体 |

`unregistered_count=2` 是**对外假陈述**：`31.5-4-M5` 与 `40-4-M6` 两行自 commit `11af550` 起就已登记，且二者的 `aliases` 精确含实体侧写法。成因是 `075e96b` 那次提交同时新增 aliases 与本区块——当时两行还不存在，判 unregistered 无误；两行后来补上，区块没跟上。

修复：`scripts/refresh_designations_in_use.py`（部署链 0b5），并保留原 `unregistered_policy` 原文（那是 L1.77 纪律声明，不是派生数据）。

### 5.2 `api/standard-audit.json`

该文件 2026-08-17 生成后从未重建，且**不在部署链里**，靠人记得手工跑。后果：对外报 4 条 `unverified_mechanical_claim`，声称 `31.5-4-M5` / `40-4-M6`「不在已知指定集中」——实为已登记，纯属过期快照的连带假报。而 `/standard-audit` 页面与 MCP 工具 `get_standard_audit` 都在读它。

顺带修了脚本自身的**死角检测**：原写法遍历区块顶层键找 `registry_row=null`，而真正带 `registry_row` 的 `entries` 是一个**列表**，永远读不到 → `registry_gaps` 恒为 `[]`，缺口检测从未生效过。

另修一处**过度计数**：裸标号 `ISO 9409-1` 因出现在 `designations_in_use` 里会命中 known 集，被算成"已核实"，但它没有可核实内容。新增 `unresolvable_granularity` 桶区分。

修复后：机械声明 29 条（核实 28 / 未核实 0 / 粒度不足 1），冲突 0（原 4 条假报），登记表缺口 0。

`generated_at` 语义同步改为**锚定源内容内时间戳字段的最大值**（非脚本运行时刻、非文件 mtime），配 `source_digest` 做字节级精确锚定——避免挂进部署链后每次部署都产生纯时间戳 diff。

## 6. 必须诚实的边界

### 6.1 推导层不是独立外部权威

`canonical_ladder_iso_9409_1` 在登记表里是**裸数组，无 `source` 字段、无 `source_tier`**。本层的全部期望值都压在这个未引用基准上，因此：

- **能做的事**：内部一致性闸门（9/9 通过即无矛盾）、声明缺失时的判定补位、手写 note 的机械复算。
- **不能做的事**：它不构成独立外部权威。期望值与 `is_canonical_iso` 标签最终都压在同一个未引用基准上——所以"9/9 一致"证明的是内部自洽，不是"符合 ISO 原文"。

因此 `derivation_confidence_cap = B`，继承登记表 tier，绝不因"是算出来的"而自封 A。

### 6.2 不发明标准行

本层只查表与比对，**绝不向 `flange_designations` 新增条目**（L1.77：未读到 ISO 9409-1:2004 原文即不替标准发明条目）。

### 6.3 查表与裁决分离

`normalize()` 把带 A 与不带 A 两种写法映射到同一规范行，仅用于**查表**。本层不裁决"两种书写形式所指的法兰可否互装"——那是 `grammar.designation_forms.join_scope` 明确划出的另一件事。

### 6.4 幂等与新鲜度锚定

`freshness` 记录两个源文件的 sha256 前 16 位。内容不变则输出字节不变（已实测连跑两次哈希一致）；内容一变则摘要必变。

**注意构建顺序**：`refresh_designations_in_use.py` 会改写 `mechanical_interfaces.json`，故 `build_derived_features.py` 必须在其之后运行。顺序反了会记下刷新前的源摘要——这正是本轮踩到的坑，已由回归 L1.95 的现算对账锁住。

## 7. 三条硬约束

### 7.1 Shannon 方法学只借原则，不抄代码

本层的"只报告可复现结论"原则借鉴 **KeygraphHQ/shannon**（AGPL-3.0）。AGPL 具网络传染性，因此：**仅借鉴原则，未复制任何代码**。判定依据是否来自推导、是否可机械复现，由本仓库自己的实现承担。

### 7.2 项目独立

本层只消费本仓库内的 `api/mechanical_interfaces.json` 与 `api/entities.json`。**不引入任何外部项目依赖**，不接其他项目的 API key 或数据通道。若其他项目需要本层数据，应各自实现，不共享运行时。

### 7.3 第三方规格表是不可信输入

抓取第三方厂商规格表属**不可信输入**，进入 agent 上下文存在提示注入风险。本层不直连任何外部页面，只消费仓库内已核验落地的 JSON；外部来源的核验责任在上游采集环节。

---

## 8. 复现

```bash
python scripts/refresh_designations_in_use.py    # 必须先跑（改写机械接口登记表）
python scripts/build_derived_features.py         # 生成 api/derived_features.json
python scripts/build_standard_audit.py           # 重建 api/standard-audit.json
```

三者均幂等；内容不变时不写盘。已挂 `scripts/deploy.mjs` 的 0b5 / 0b6 / 0b7，部署时无需人工干预。
