# 全面体检报告（2026-10-04）

> **性质**：这是体检，**不是进度汇报**。目的是找出「以为自己解决了、其实没解决」的地方。
> 全部数字现算自 `api/*.json`，复现命令附在每节末尾。
> **纪律**：本报告只登记实测结果，不给未经验证的乐观判断留位置。

---

## 0. 一句话结论

> **工程与研究层已经很扎实，但存在一个此前完全没被发现的结构性问题：
> 3 天的研究产出对 MCP 工件面零可见性（0/5）——
> AI agent 实际调用的 `check_compatibility` 走的是另一套引擎、另一种维度。**
>
> 本轮已修复（0/5 → 5/5，桥接 4 个工具上线），并加了闸门防止复发。
> **除此之外，剩下的问题按 ROI 排序是：商业验证 > 机械轴证据深度 > 信号轴结构。**

---

## 1. 体检范围与口径

| 维度 | 量了什么 | 现算结果 |
|---|---|---|
| 工程 | CI 闸门 / 产物一致性 / 部署 | **72 项全绿** |
| 研究 | 三轴裁决 / 取证判据 / 归因诊断 | 4 个判据层 + 3 条定理 |
| **产品** | **研究资产对用户/agent 的可达性** | **0/5（本轮发现并修复）** |
| 商业 | 传播 / 调用 / 转化 | 0 star / 29 调用 / **0 注册** |
| 生态 | 分发 / 论文 / 目标客户 | 4 家分发绿 · 论文就绪未投 · Feather 未接触 |

---

## 2. ★ 本轮最重要的发现：两套引擎、两种维度、断层

### 2.1 事实

本项目同时存在**两套兼容性裁决引擎**，此前无人把它们放在一起看：

| | 产品面（agent 实际调用） | 研究层（近 3 天产出） |
|---|---|---|
| 引擎 | `functions/_lib/compat_engine.js` | `scripts/compose_engine.py` |
| 维度 | protocol / electrical / mechanical / **software** | mechanical / electrical / **signal** |
| 数据源 | `api/entities.json` 的**声明字段** | `api/morphology_graph.json` 端口 + **297 条类型级裁决** |
| 入口 | `/api/compatibility`、MCP `check_compatibility` | `api/compose_semantics.json`（**此前零工具引用**） |

**维度交集只有 `electrical` + `mechanical`。**
产品层独有 `protocol`/`software`，研究层独有 `signal`。
**两套维度不互为子集** —— 这意味着它们不是「同一套判据的两个实现」，
而是**两套不同的维度体系**，不能靠"取并集"合并。

### 2.2 为什么这是本项目最大的结构性问题

体检前 5 个研究层产物在 `functions/` 下**引用数全部为 0**：

```
compose_semantics.json    → 0    cohort_feasibility.json  → 0
compose_frontier.json     → 0    evidence_valuation.json  → 0
electrical_evidence.json  → 0
```

后果不是 bug（两套都能跑、都不报错、68 项闸门此前也全绿），
而是：**研究者以为结论被用上了，agent 实际拿的是另一套口径的答案。**

这类故障的性质决定它**无法被任何算术守卫抓到**——它不是数字错了，
是资产没接线。只能靠显式扫引用。

### 2.3 一个更刺眼的事实：研究层数据覆盖**远高于**产品层

| 层 | 覆盖 |
|---|---|
| 产品层字段（`protocol` / `interface` / `voltage` / `ros_support`） | **4.3% – 5.7%**（42/865、37/865、42/865、49/865）|
| 研究层 signal 有效端口 | **393 / 654 = 60.1%** |
| 研究层 mechanical 有效端口 | 81 / 654 = 12.4% |
| 研究层 electrical 有效端口 | 13 / 654 = **2.0%** |

即：**产品层靠 4-6% 的字段覆盖在对外回答兼容性，
研究层靠类型级裁决在做更细的判定，但没人看得到后者。**

### 2.3b 顺带量出的另一个事实：机械轴的 unknown 主要是「专有接口」

126 组 mechanical unknown 类型对的构成（现算）：

| 组合 | 组数 |
|---|---|
| proprietary × registered_standard | 63 |
| proprietary × proprietary | 28 |
| registered_standard × unparseable_bare | 9 |
| registered_standard × unknown | 9 |
| proprietary × unparseable_bare | 7 |
| proprietary × unknown | 7 |
| 其余 3 组 | 3 |
| **含 proprietary 合计** | **105 / 126 = 83.3%** |

**判读**：机械轴不可判定的**主要原因是厂商只声明"我们有自研接口"却不给几何**
（这正是 §7 里"机械声明率低不是真问题"的另一面）。
补几何取证能解锁这 105 组——但**它们的 MDV 尚未计算**，
按本项目自己的纪律（不补"贡献为 0"的数据），**必须先算 MDV 再决定是否取证**。

### 2.4 本轮修复（已落地）

新增 **4 个桥接 MCP 工具**（11 → **15 个工具**），只透传研究层现算结论、
不重新裁决、不做跨层合并（避免造出第三套口径）：

| 工具 | 承载 | 何时用 |
|---|---|---|
| `explain_compose_frontier` | 三轴裁决 + composed=0 归因 | "为什么 type_error""composed 是 0" |
| `explain_evidence_cohort` | 最小可行同质集 | "取证从哪开始""K=2 什么意思" |
| `explain_evidence_mdv` | 零贡献轴证明 | "补哪个轴最划算" |
| `explain_connector_types` | 连接器三元组判据 | "同为 M8 为什么不兼容" |

每个返回值都带 `caliber` 字段，明示**不可与 `check_compatibility` 的四维混用**。

**结果：0/5 → 5/5 可达**，已线上验证四个工具全部可被 agent 调用。
**新增 `gate_reachability_gap` 闸门**：一旦可达性归零即判红。

复现：`python scripts/build_reachability_gap.py` · `python scripts/verify_reachability_gap.py`

---

## 3. 工程面：健康，但有一个待记账的债

| 项 | 状态 |
|---|---|
| CI 闸门 | **72 项全绿**（本轮 +4：可达性及配套）|
| 实体 schema / rp_id 唯一性 | ✅ 已修（11 组跨厂商撞号归零）|
| 部署 | ✅ 线上验证通过，20 页 + 4 接口数字与真相源一致 |
| 产物漂移 | 每次跑闸门会产生 ~40 个时间戳漂移文件 |

**待记账的债**：`composable` 字段语义过宽。
654 个"可组合"节点里有 **204 个（31.2%）** 端口全为 `not_declared`
（`MECH:not_declared` 50 + `ELEC:not_declared` 164），
但因为 `composable = bool(ports)` 而 ports 含 not_declared，它们被算作"可组合"。
**它们在 cohort / frontier 分析里混进了分母。**

这不是 bug（口径已在 `non_composable_reason` 里说明），但**它让"可组合节点 654"
这个数字对外有误导性**。修法有两种（改口径 or 改字段名），属产品决策，本轮不动。

---

## 4. 研究面：四条判据 + 三条定理，都可复现

| 层 | 产物 | 核心结论 |
|---|---|---|
| MDV | `evidence_valuation.json` | mechanical/signal 零贡献率 **100%**（严格证明）|
| MVC | `cohort_feasibility.json` | K=1 不可能、**K=2 即可**；同质可行对 46,092 对 / 627 节点 |
| 共装前沿 | `compose_frontier.json` | `composed=0` 是**关系类型错配**（L1 28,310 → L2 63 → L3 0）|
| 电气取证 | `electrical_evidence.json` | 9 器件 / 11 连接器 / 3 组冲突；`(family,pins,pinout)` 三元组判据 |

**三条定理**（均可复现，见 `docs/HEALTHCHECK_20261004.md` 与既有决策记录）：
- **T1** 三轴 AND 收敛下界：某轴密度 < 1/N 时全局可判定数 → 0
- **T2** 单声明零收益定理：单条声明的边际可判定收益恒为 0
- **T3** 共装错配：EOAT 器件按设计不互插（**强假说，13/13 样本**）

**诚实的弱点**：T3 目前是**强假说而非定理**（样本 13 对判出，全 incompatible，
但只覆盖 16 个 L2 节点中的 9 个）。升级条件已写进产物。

---

## 5. ★ 商业面：这是最大的短板，且不是技术问题

| 指标 | 值 | 判读 |
|---|---|---|
| GitHub stars / forks | **0 / 0** | 从未进入任何传播渠道 |
| API 调用 → 注册 | 29 → **0** | 有调用无转化 |
| MCP 分发 | Registry / Smithery / LobeHub / Glama **4/4 绿** | 渠道做完了 |
| MCP 工具数 | 11 → **15** | 本轮增加 4 个研究层入口 |
| 论文 | Mechatronics 投稿版就绪 | **未投**（差 2 个字段）|

**判断**：技术侧从"能跑"到"有可发表的定理"只用了 3 天，
而商业侧从 0 到现在仍是 0。**这是资源配置失衡，不是能力问题。**

**具体表现**：分发明明全绿（4 家平台），工具从 11 增到 15（更全了），
但注册仍是 0。这说明**分发渠道不是瓶颈**（已被 29 次调用 0 注册证过），
瓶颈是"有人为什么需要这个"这个问题没被回答。

---

## 6. 生态面：目标客户明确，但零接触

- **目标客户：Feather Robotics**（$29,990 轮式双臂人形，23 DOF，
  Python+ROS2 Open SDK，无公开 repo）。他们卖 body+SDK，
  我们卖 **body 之间怎么接**。
- **生态接入点：AgenticROS**（RealSense 赞助）——
  `npx agenticros skills install lm203688/roboparts` 一次接入 4 客户端。
  **但本轮发现：15 个工具里有 4 个是研究层入口，
  AgenticROS 的接入文档是否需要同步说明它们，已超出体检范围，属运营动作。**
- **哲学背书**：Isaac ROS 5.0 的 `rosidl::buffer` 是供应商中立的内存传输接口
  ⇒ RoboParts = 零件兼容性层的 `rosidl::buffer`。已上 hero 区。

---

## 7. 硬骨头重排（按 ROI）

| 优先级 | 硬骨头 | 判据 | 状态 |
|---|---|---|---|
| **P0** | **论文投出** | 稿子就绪，差 2 字段 | **用户手动**，学术背书是当前最高 ROI 渠道 |
| **P0** | **商业验证** | 29 调用 0 注册 | **必须换问法**，见 §8 |
| P1 | 电气取证补齐 | 共装假说 13/13 → 需 16/16 才成定理 | 9/16 器件已取，可续 |
| P1 | 机械轴证据深度 | 126 组 mechanical unknown 类型对，**105 组含 proprietary** | 未量化价值 |
| P2 | 信号轴结构 | schema 只能表达 1:1 离散映射（MUSE 试写证伪） | 属 D5 多年期，**本轮明确不做** |
| P2 | `composable` 口径 | 204/654 节点端口全 not_declared 却算"可组合" | 属产品决策 |

**已明确不做**（与既有决策记录一致）：
造脑/连接组仿真 · MUSE 数据接入 · 扩展 signal schema 加 channel 层 ·
继续加分发平台（已证不是瓶颈）· 机械声明率 5.69%→30%（严格证明贡献为 0）

---

## 8. 本轮给出的三条决策建议（不含推荐，需你拍板）

### 建议 1：商业问题必须换问法

现状是"我们有什么"（865 实体 / 15 工具 / 4 平台），
而用户的问题是"**我这台机器人能不能同时装夹爪 A 和传感器 B**"。

后者正是 `compose_frontier` 诊断出的、模型答不了的那个问题
（EOAT 器件的关系是**共装**而非点对点直连）。

**若把 `explain_compose_frontier` 的 L2 层做成一个用户可查的
「能不能共装」查询，产品的价值主张会从"零件库"变成"集成决策器"。**
这比继续加实体数的边际价值高得多——但它需要你先回答：
**接单要按"兼容性查询"收费，还是按"集成方案"收费？** 二者的产品形态完全不同。

### 建议 2：两套引擎的处置（`api/reachability_gap.json` 的 `decision_options`）

| 方案 | 成本 | 收益 | 风险 |
|---|---|---|---|
| OPT-1 产品面换真相源 | 高 | 单一真相源 | protocol/software 是已宣传能力，移除影响既有用户 |
| OPT-2 研究层降级为离线分析 | 低 | 诚实、零回归 | 研究价值主张被削弱 |
| **OPT-3 桥接层** | **中** | **研究层可见，零回归** | 两套口径同时可见，**agent 可能困惑** |

**本轮实施了 OPT-3**（保守、可逆、不动既有判定口径）。
工具描述里已写明口径隔离，但**两套口径同时对 agent 可见确实有混淆风险**——
建议观察一段时间的 `mcp:tool:explain_*` 调用量再决定是否收敛到 OPT-1。

### 建议 3：把体检做成常规动作

本轮建的 `gate_reachability_gap` 只能守"研究资产是否可见"。
**体检的价值在于发现没人主动看的地方**，
建议每月跑一次「有没有新产物没被任何工具/页面引用」——
这个检查现在只覆盖 `functions/`，**尚未覆盖
`llms.txt` / `skills/README.md` / `agent-discovery.json` / 分发包**。

---

## 9. 复现命令

```bash
# 体检核心：研究层↔产品面可达性
python scripts/build_reachability_gap.py
# → 可达 5/5，维度交集 [electrical, mechanical]，
#   产品层独有 [protocol, software] / 研究层独有 [signal]

python scripts/verify_reachability_gap.py    # 正样本 + 反向对照 + 6 变异

# 全闸门 72 项
python scripts/ci_gate.py

# 线上验证桥接工具可被 agent 调用
curl -s -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  https://roboparts.cc/mcp | python -c "import sys,json;print(len(json.load(sys.stdin)['result']['tools']),'个工具')"
```

**纪律提醒**：本报告所有数字**禁止手改**。改数据源串一律改生成器。
