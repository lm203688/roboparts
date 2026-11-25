# RoboParts：长尾经济启发 → 三项查询缺口评估与收口路线

- 日期：2026-11-24
- 触发：用户提出「机器人存量越大，支撑系统长尾越长」的产业观察，问对 roboparts 项目的启发与提升路径
- 性质：**查缺评估报告**（非执行），已读取引擎源码核实接口，不含虚构结论
- 结论先行：三项缺口中，**第 1 项（互换等价类）可由现有 pair_verdict 直接推导，不需要新数据、不需要新引擎维度**；第 2 项（维修依赖图）需要新增关系类型；第 3 项（现场维修场景本体）是数据缺口而非代码缺口。

---

## 0. 已核实的引擎接口（本次实际读取，非推断）

读取范围：`scripts/compose_core.py`（599 行，纯函数内核）、`scripts/compose_engine.py`（111 行，IO 层）、`api/morphology_graph.json`（`type_compat` 段）。

| 接口 | 位置 | 语义 |
|---|---|---|
| `CompatIndex.__init__(type_compat)` | `compose_core.py:130` | 双向索引，后写覆盖前写（有意，便于注入变异体自证） |
| `CompatIndex.pair_verdict(ta, tb)` | `compose_core.py:147` | 返回 `(pair_verdict, entry\|None)`；`ta==tb` 未显式登记 ⇒ `identity`（公理 R1） |
| `pair_verdict` 值域 | `type_compat` 实测 | `identity` / `adapter_required` / `unknown` / `incompatible` 四态 |
| `type_compat` 条目字段 | `morphology_graph.json:39302` | `a`, `b`, `verdict`, `reason`, `blocking_dims` |
| `compose(a, b, graph)` | `compose_core.py:256` | 三轴（mechanical / electrical / signal）聚合；fail-closed |
| `eval_all_pairs(graph, examples_per_class)` | `compose_core.py:311` | 确定性全对评测，只回聚合不回逐对 |
| R5 优先级 | `compose_core.py:293` | 任一轴 incompatible ⇒ `type_error`；否则任一轴 unknown ⇒ `unknown`；否则 `composed` |

关键判断：**现有 `type_compat` 是一个「二元兼容性关系」（identity / adapter_required / unknown / incompatible），不是等价关系。** 这正是要补的地方——互换等价类在数学上不是二元关系的直接产物，但**可由二元关系的行为签名推导**（见 §2）。

---

## 1. 三项缺口总览

```
缺口①  互换等价类查询     → 可推导（本次已确认可行）   → Phase 0，新增查询层
缺口②  维修依赖图         → 需新增关系类型             → Phase 1，改数据模型
缺口③  现场维修场景本体   → 数据缺口，不是代码缺口     → Phase 2，数据征集
```

---

## 2. 缺口①互换等价类：确认可由 pair_verdict 推导（本次核心结论）

### 2.1 问题定义

「互换性」不是 A 与 C 之间的一条二元边，而是**语境化**的：零件 C 能否在原来装 A 的位置上直接替换。形式化为：A 与 C 在关于端口 B 的语境下可互换，当且仅当它们对 B 的裁决一致。推广到全语境：

> **t1 ~ t2 当且仅当 对全部语境 x，`pair_verdict(t1, x) == pair_verdict(t2, x)`**

这就是**行为等价（observational equivalence）**，签名定义为：

```
sig_ax(t) = { x : pair_verdict_ax(t, x)  for x in T_ax }   # T_ax = 该轴的全部类型标号
类(t)     = { u in T_ax : sig_ax(u) == sig_ax(t) }
```

### 2.2 为什么这条路径成立（而非需要新数据）

1. **只需现有数据**：签名只调 `CompatIndex.pair_verdict`，该函数已含公理 R1（自配对）与规则 R2（双向查表），不需要新增 `type_compat` 条目。
2. **三轴必须分开建**：机械互换性、电气互换性、信号互换性是**三套独立等价类系统**——同一标号的法兰与连接器即使"都没连什么"也不应合并。因此必须按轴隔离签名空间。
3. **单调性继承**：追加证据只会让签名更细（更多 x 被区分），**永远只会拆分类、不会合并类**。这与已证明的 Theorem 1（Evidence Monotonicity，`compose_core.py:511`）同构——等价类划分对证据集是单调精化的。这是一个值得写进论文的形式性质。

### 2.3 必须诚实标注的三个边界

| # | 边界 | 说明 |
|---|---|---|
| **B1** | **孤立类型陷阱** | 任何没有任何连接的类型，其签名全为 `unknown`，会被误合并成一个大类。**守卫**：仅合并「至少存在一条非-unknown 边」的类型；或限制签名空间为「与该类型共享至少一个共同语境」的类型子集。不加守卫则等价类直接失真。 |
| **B2** | **观测等价 ≠ 物理互换** | 推导结果是「在当前证据下观察到的等价」，是**真互换性的上界**。它可能把两个物理上不同但现有证据无法区分的类型误合并。对外必须标注为 **candidate 级**（候选互换），不能标注为**认证互换**。这与 `Internal Consistency`（原称 Soundness，`compose_core.py:486`）的诚实标注是同一逻辑：不宣称证明物理可行。 |
| **B3** | **专有接口不可判定** | 对 `PROPRIETARY:*` 类型，`pair_verdict` 恒为 `unknown`（Theorem 3，`compose_core.py:562`）。这类类型**永远无法**通过补证据进入任何互换类——这是本质不可判定，不是「还差一条数据」。必须在查询结果里显式标注。 |

### 2.4 落地成本

- 新增一个**查询层**（建议 `scripts/interchangeability.py`），产出 `api/interchangeability_classes.json`。
- **不改 `compose_core.py`**：不引入新引擎维度，不动 R0–R5 规则表，不动三定理。这是最重要的约束——等价类是**派生视图**，不是新证据。
- 规模：类型标号数量远小于 35 万零件对，签名计算是 O(|T|²) 且确定性、无随机，可直接进 CI。

---

## 3. 缺口②维修依赖图：需要新增关系类型

### 3.1 现状

`morphology_graph.json` 目前表达「零件间能否装配」（type_compat）。但维修长尾需要的是**替换关系**：

- `replaced_by`（A 型停产，用 B 型替代）
- `interchangeable_with`（A、B 双向可换）
- `supersedes`（新版本取代旧版本，带修订号）
- `compatible_substitute`（降规替代，带损耗标注）

### 3.2 为什么不塞进 type_compat

`type_compat` 的裁决是**对称装配语义**，而 `supersedes` 是**有向时间语义**（V2 取代 V1，但 V1 不能取代 V2）。混入会让规则表 R0–R5 污染。

**结论：新增独立关系数组** `repair_edges`，带 `relation` 枚举字段，与 `type_compat` 平级但语义正交。引擎不消费它（保持三定理纯净），只由查询层与前端消费。

---

## 4. 缺口③现场维修场景本体：数据缺口

长尾的「极度分散、高度本地化、依赖现场判断」三个特征，对应需要采集的字段：

| 长尾特征 | 需要的本体字段 | 当前状态 |
|---|---|---|
| 维修 | 故障模式 → 拆卸步骤 → 工具清单 | 无 |
| 校准 | 标定周期、标定规程、公差带 | 无 |
| 零部件更换 | 备件关键度分级 | 无 |
| 保险/认证二手 | 使用历史、服役里程 | 无 |
| 责任法律 | 缺陷归属链、召回记录 | 无 |

**这是数据缺口，不是代码缺口**——不能靠加代码解决，只能靠数据征集与合作方。诚实标注：这三类需求 RoboParts 现阶段**没有一手数据**，任何"我们已经覆盖"的说法都是假的。

---

## 5. 提升路线（按投入产出比排序）

### Phase 0（1–3 天，零新数据，可立即做）

1. 新增 `scripts/interchangeability.py`，产出 `api/interchangeability_classes.json`
2. 三轴隔离 + 孤立类型守卫（B1）+ 专有接口标注（B3）
3. 产物对外标注 **candidate 级**（B2）
4. **门禁**：新增性质测试——等价类划分对 `type_compat` 追加条目必须单调精化（注入变异体验证，与 Theorem 1 同测法）

### Phase 1（1–2 周，改数据模型）

5. `repair_edges` 关系数组 + `relation` 枚举
6. 修复链查询：`replaced_by` 传递闭包，产出可维修性报告

### Phase 2（数据征集，周期长）

7. 现场维修场景本体字段征集，优先「备件关键度分级」——它是唯一能立刻提升搜索排序的字段

---

## 6. 对用户产业观察的回应

「机器人存量越大，支撑系统长尾越长」——**这个观察对 RoboParts 是资产而非负债**，理由：

- 长尾的分散性 = 需要**本地化裁决数据**的地方多 = `type_compat` 的 `blocking_dims` 字段（已知存在）正是为此设计的载体
- 长尾的持续需求 = 等价类查询的**真实消费场景**：二手市场、备件替代、保险定损全部要问「能换什么」
- 但必须诚实：**等价类只回答了「结构上能不能换」，没回答「现场换不换得了」**（工具、工时、资质）。后者是缺口③，现阶段无法用代码补。

---

## 7. 诚实边界（全文适用）

- 本报告**未运行任何引擎**，仅读取源码与图文件核实接口；`pair_verdict` 可推导等价类是**接口级推断**，Phase 0 实施时需用实际 `morphology_graph.json` 验证签名分布。
- 第 2.3 节 B2 是硬约束：不得把 candidate 级互换宣称成认证互换。
- 缺口③的三类数据 RoboParts **当前不存在**，不做假设性覆盖。