# RoboParts 切口三步核验报告（v2）

- 核验对象：`C:\Users\xing\Desktop\所有项目\2.robopart`
- 核验日期：2026-11-08
- 版本：v2（在 v1 基础上补入共装层实测、厂商跨越分析、零分类学）
- 数据基准：`api/*.json` 现算，`morphology_graph.json` 生成于 2026-11-07T17:02:38+08:00，`co_mount.json` 为 `co_mount_engine/v1`
- 溯源标签：`[V]` 已复算/已查证；`[O]` 一方称；`[E]` 工程估算

## v1 → v2 的四处更正（先看这里）

1. **v1 说"关系层只有 3 条 `mounts_to` 规则，须先补标注"——这句话错了。** 3 条 `mounts_to` 只存在于遗留的 `compatibility.json`；仓库另有独立的共装层 `co_mount_engine/v1`，已完成 360 对裁决、3 个宿主、16 个器件。我把两个层混为一谈，属实质性误判，在此更正。
2. **判决性实验已经做过，而且结论不是"解锁"。** 共装层实测 `mountable = 0 / 360`，即换关系类型也没有产生任何可安装对。
3. **零的成因发生了迁移，不是消失。** 互插层 99.939% 的零是证据缺口；共装层只有 17.5% 是证据缺口，35% 是宿主资源耗尽、47.5% 是角色不互补。这是新命题的核心。
4. **"可判定对几乎都是同厂商"这句也错了。** 机械轴 2,016 个可判定对里 85.7% 是跨厂商；真正同厂商化的是电气轴（62.5%）。两个轴的对比才是故事。

---

## 0. 判定：条件立项（命题已重设，骨架已定）

| 步骤 | 结论 |
| --- | --- |
| ① 占位核验 | "不完备"这个**发现**已被 Tola 2022 占位；"形式化接口做组合"已被 Siltala / Zheng 占位。未占位的是**测量 + 分解** |
| ② 最近邻差异 | 差异成立，但原创性只能押在测量结果与零分类学上，不能押在任何单个概念上 |
| ③ 量级与预算 | 数量级够（656 节点 / 214,840 对 / 360 对共装），证据深度不够（verified 仅 9%，EOAT 可标注仅 14/121） |

**一句话结论**：这个切口现在有了一根比原方案更硬的骨架——**零是守恒的，变的只是成因**。

---

## 1. 第一步：占位核验

### 1.1 检索日志

| # | 检索式 | 命中 | 判断 |
| --- | --- | --- | --- |
| 1 | constraint-based configuration incomplete knowledge unknown values | Sabin & Freuder 1996；Lallouet & Legtchenko（AI EDAM）；Mailharro；ConfWS 2024 | **已占位**：部分定义约束、配置即复合 CSP |
| 2 | modular robotics interoperability interface standards survey | HRIM（arXiv 1802.01459）；Tola 2022；Tola 2024；Zou 2021 | **已占位**：定性诊断 + 信息模型提案 |
| 3 | interface model based configuration design mechatronic systems | Zheng 等 2019（RCIM） | **已占位**：接口模型 + 二值矩阵 + 消除算法 |
| 4 | resource combinations formally described hardware interfaces | Siltala 等（IPAS 2019） | **已占位**：形式化接口→组合 |
| 5 | knowledge-driven framework synthesizing designs modular components | Chaumet & Rehof 2023 | **已占位**：组合逻辑合成，28 模块件 |
| 6 | three-valued logics imperfect information | Ciucci & Dubois；Kleene | **已占位**：三值语义是成熟工具 |
| 7 | value of information evidence acquisition engineering design | Ming 等 2020；Pandey & Herrmann 2021；SHM 领域多篇 | **部分占位**：VoI 是效用/贝叶斯框架，非组合计数 |
| 8 | combinatorial enumeration pair feasibility evidence sufficiency audit | 无直接命中 | **未见占位**（限本轮检索范围） |

**边界**：仅英文关键词，未接 Scopus / WoS，未做引文网络前向追踪。第 8 条只能判"初判未见"，正式立项前需补数据库检索并留日志。

### 1.2 六类已占位工作

| 类别 | 代表 | 已拿走什么 |
| --- | --- | --- |
| 不完备的定性诊断 | Tola, Madsen, Gomes, Esterle, Schlette, Hansen, Larsen 2022 | 六类集成障碍全清单（缺标准化 / ISO 法兰在 datasheet 缺失 / 误导性兼容声明 / 属性缺失 / 误导性不兼容 / 套件损害复用）+ ASP 默认推理提议 + 三家厂商法兰标注率表 |
| 硬件信息模型 | HRIM（Zamalloa 2018）；Zou 2021 | plug-and-play 硬件信息模型 |
| 接口驱动配置 | Zheng 2019 RCIM | 接口模型、`Cp∈{0,1}`、消除算法、焊接系统案例 |
| 形式化接口→组合 | Siltala 2019 IPAS | 从形式化接口生成资源组合 |
| 形式化合成 | Chaumet & Rehof 2023 | 组合逻辑合成 + Fusion 360 插件 + 28 件案例 |
| 部分约束/三值语义 | Sabin & Freuder；Lallouet；Ciucci & Dubois | "未知"作第三值 |

**判断**：不能以"发现不完备"立论；但 Tola 2022 全文止于定性清单，明言"no mature public robot system configurators exist"，没有密度、没有界、没有规模。**这个口子是真的。**

---

## 2. 第二步：最近邻差异表

| 维度 | Tola 2022 | Zheng 2019 | Siltala 2019 | HRIM 2018 | Chaumet 2023 | 本文 |
| --- | --- | --- | --- | --- | --- | --- |
| 对象 | 集成流程与障碍 | 机电模块接口 | 硬件接口 | 信息模型 | 模块件知识库 | 656 节点×3 轴×2 关系类型 |
| 不完备的地位 | 定性障碍，建议 ASP | 假设接口模型已完整 | 假设已形式化描述 | 规范提案 | 假设知识已编目 | **一等对象**，`not_declared` 参与判定 |
| 语义 | 默认逻辑（提议） | 二值 | 二值 | 本体 | 类型论 | 三值 + 轴合取 + fail-closed |
| 规模 | 3 家厂商标注率 | 1 个焊接系统 | 未报告 | 未报告 | 28 件 | **214,840 对 + 360 对共装全枚举** |
| 结论形式 | 方向建议 | 减少候选 | 组合流程 | 模型规范 | 可合成方案 | **密度 + 最弱轴上界 + 零分类学** |
| 关系类型 | 未区分 | 单一"可连接" | 单一装配 | 未区分 | 单一装配 | **区分互插与共装** |

**差异落点**：前人回答"该怎么建标准/模型/合成"；本文回答"标准还没被采纳时能判定多少、补哪条证据有用、以及那些零到底是不是缺数据"。

**必须承认**：前提 borrowed from Tola 2022；三值 borrowed from Kleene/Ciucci-Dubois；枚举 borrowed 自配置领域兼容矩阵传统。原创性只在测量与分类上。

---

## 3. 第三步：量级与数据预算核验

### 3.1 数字更正

| 指标 | v1/文档口径 | 现算 |
| --- | --- | --- |
| 实体总数 | 868 | **868** `[V]` |
| 入图节点 | — | 659（可组合 656 + 不可组合 3；209 个非物理实体不入图：software 81 / specification 101 / market_intelligence 17 / organization 10） |
| 可组合节点 | 654 | **656** `[V]` |
| 端口 | 1,454 | **1,463** `[V]` |
| 端口类型 | 27 | **41** `[V]`（机械 20 / 电气 18 / 信号 3） |
| 有序对 | 427,716 | **430,336** `[V]` = 656²（427,716 = 654²，直接证明旧 N=654） |
| 无序对 | — | **214,840** `[V]` = C(656,2) |
| 同质可行对 / 节点 | 46,149 / 636 | **46,258 / 622** `[V]` |
| 实体级登记率 | 6.57% | **16.2%** `[V]`（81/500 机械适用；含 partial 95/500） |
| CI 闸门 | 91（README）/ 48（文档） | 脚本内 gate 相关定义 **76 处** `[V]` |

### 3.2 互插层（peer-to-peer）

分母 430,336 有序对：`composed 0` / `type_error 262`（0.061%）/ `unknown 430,074`（99.939%）。
gap_distance：0 步 0、1 步 **61**、2 步 60,705、3 步 369,308。1 步之差的 61 对，瓶颈电气 32、信号 29、机械 **0**。

分母 214,840 无序对的三轴可判定密度：

| 轴 | 可判定对 | 密度 |
| --- | --- | --- |
| 机械 | 2,016 | 0.938% |
| 电气 | **8** | **0.0037%** |
| 信号 | 28,500 | 13.27% |
| 机械∧电气 | 7 | — |
| 机械∧信号 | 63 | — |
| 电气∧信号 | **0** | — |
| 三轴合取 | **0** | **0.0000%** |

### 3.3 厂商跨越：两个轴的对比（v2 新增，核心表）

| 轴 | 可判定对 | 同厂商 | 跨厂商 | 同厂商占比 | 读法 |
| --- | --- | --- | --- | --- | --- |
| 机械（ISO 9409-1 已标准化） | 2,016 | 289 | 1,727 | 14.3% | **标准化轴产生跨厂商可判定性** |
| 电气（无统一工具接口标准） | 8 | 5 | 3 | 62.5% | 未标准化轴几乎只在自己家族内成立 |
| 信号（品类级推断 Tier B） | 28,500 | 954 | 27,546 | 3.3% | 跨厂商率高，但声明来自品类映射，须打折 |

**8 个电气可判定对逐个列名** `[V]`：

| # | 对 | 判据 | 厂商关系 |
| --- | --- | --- | --- |
| 1 | ACT-001 × ACT-002 | 同一 JST EHR-03 | ROBOTIS 内部 |
| 2 | ACT-028 × GRIP-002 | ROBOTIQ-COUPLING-10-SPRING-PIN | Robotiq 内部 |
| 3 | ACT-028 × GRIP-006 | 同上 | Robotiq 内部 |
| 4 | GRIP-002 × GRIP-006 | 同上 | Robotiq 内部 |
| 5 | GRIP-012 × GRIP-014 | UR-TOOL-CONNECTOR-COMPOSITE | **OnRobot × Robotiq（跨厂商）** |
| 6 | SENS-047 × SENS-37 | 12-PIN-ROUND-AMPHENOL | ATI 内部 |
| 7 | SENS-049 × SENS-854 | M8-5-PIN | OnRobot 内部 |
| 8 | SENS-31 × SENS-855 | M12-5-PIN-A-CODED | Robotiq 内部 |

跨厂商的那一对（GRIP-012 × GRIP-014）在数据层判为 `identity`，但 B1 首批核验推翻了它的语义——它们不是"能互插"，而是"都插在同一个宿主端口上"（详见 3.9）。这一条必须先修正，否则第 3 条贡献会被审稿人一击致命。

### 3.4 共装层（co-mount）：判决性实验的既有答案（v2 新增）

`co_mount_engine/v1`，3 个宿主（HUB-030、HUB-031、SUPERDEX-fr3）× 16 个 L2 器件 = **360 对裁决** `[V]`

| 裁决 | 对数 | 占比 | 含义 |
| --- | --- | --- | --- |
| mountable | **0** | 0% | 无一对可同时安装 |
| port_exhausted | **126** | 35% | 宿主工具侧 I/O 位已用完（工程约束） |
| type_error | **171** | 47.5% | 角色不互补（两个输出 / 两个感知） |
| unknown | **63** | 17.5% | 宿主端口数未取证（FR3 刻意留空） |

拆开看：147 个夹爪×传感器对里，98 对是 `port_exhausted`（UR 宿主只有 1 个工具侧 8-pin 位）、49 对 `unknown`（FR3）；63 个夹爪×夹爪对与 63 个传感器×传感器对全部 `type_error`（同为输出或同为感知）。
单件维度：`single_mount` 可装 32、unknown 16 —— **单件装得上，双件同时装装不下**。

**这一层的意义**：它证明"换关系类型"不会解锁组合，只会把零的成因从证据换成硬件资源。这是可写进论文的判决性结果，不是待办事项。

### 3.5 边际可判定收益（MDV，逐节点逐轴枚举）

| 轴 | 缺口节点 | 正收益节点 | 结论 |
| --- | --- | --- | --- |
| 机械 | 575 | **0** | 任何单条声明收益上界 0 |
| 电气 | 637 | **1**（SuperDex Robotiq 2F-85，mdv=7，联合上界） | 唯一可投资目标，单独补仍无效 |
| 信号 | 261 | **0** | 同机械 |

不是抽样估计，是 656×3 个格子的穷举。它把"该补哪条证据"从经验判断变成可计算量。

### 3.6 零的分类学（v2 新增，论文第 3 条贡献）

| 类型 | 判据 | 互插层 | 共装层 | 可修手段 |
| --- | --- | --- | --- | --- |
| Z1 证据缺口 | 任一轴 `unknown` | 430,074（99.939%） | 63（17.5%） | 补声明；但 MDV 显示净收益≈0 |
| Z2 接口不兼容 | 某轴 `incompatible` | 262（0.061%） | — | 换器件或加转接 |
| Z3 角色不互补 | 语义层不同向互补 | — | 171（47.5%） | 换组合，数据不可修 |
| Z4 宿主资源耗尽 | `port_budget = exhausted` | — | 126（35%） | 换硬件/加 I/O 扩展，数据不可修 |
| **Z5 坐标系错位** | 两端声明不在同一"侧"（device/host/cable） | 至少 1 对（GRIP-012×GRIP-014） | — | 补 locus 维度并重判 |

**结论句**：换关系类型后，零的总数不变（两层都是 0 正例），证据型零从 99.9% 降到 17.5%，其余迁移到工程约束。**"补数据"能解释的份额，在两种关系下分别是 99.9% 和 17.5%，但没有一次能换来一个可安装对。**

### 3.7 关系标注的可扩展性（v2 更正）

EOAT（夹爪 26 + 传感器 95 = 121 个）中，同时具备 ISO 法兰声明与电气声明的只有 **14 个** `[V]`；88 个传感器与 16 个夹爪**完全没有法兰声明**；实体字段里没有任何 ISO 9409 的自由文本可回收（全库 0 命中）；法兰字段非空仅 57 个、`standard` 非空 72 个。

**因此"补关系标注"不是建模工作，它被证据工作卡住**：要把共装层从 16 扩到 121，必须先做 107 个 EOAT 的法兰与连接器取证——与 4 周取证是同一件事，不能并行省掉。

### 3.8 B1 首批核验：电气轴的"侧"问题（v2 追补，重要）

已核三个厂商文档，结论是**电气端口声明混用了两种"侧"**：

| 器件 | 声明端口 | 厂商文档原话 | 端口实际所在侧 |
| --- | --- | --- | --- |
| Robotiq EPick（GRIP-014） | `UR-TOOL-CONNECTOR-COMPOSITE` | "Plug the coupling cable into the robot tool connector"（e-Series QSG） | **宿主侧** |
| Robotiq 2F-85（GRIP-002） | `ROBOTIQ-COUPLING-10-SPRING-PIN` | "The gripper interfaces with its coupling via a 10-spring pin connector" | **器件侧**（器件↔耦合件） |
| OnRobot VGC10（GRIP-012） | `UR-TOOL-CONNECTOR-COMPOSITE` | "Use the M8-8pin connector on the Quick Changer"（用户手册） | **宿主侧**（经 Quick Changer 中介） |

**这解释了什么**：GRIP-012 与 GRIP-014 判 `identity`，因为两者都把自己的**宿主接口**写成了电气端口。它们不是可以互相插接的两件器件，而是**抢同一个机器人工具端口的两个竞争者**。真正的器件侧接口一个是 M8-8pin（经 Quick Changer），一个是 10-spring pin（经 Robotiq 耦合件），彼此并不相同。

**由此产生的三条修正**

1. **8 对电气可判定里至少 1 对是"伪互插"**（GRIP-012×GRIP-014），真实语义是宿主端口共用。其余 7 对是否为器件侧仍需逐个核，尤其 ATI 的 12-pin 与 Robotiq FT 300 的 M12 大概率是**线缆/宿主侧**，不是器件间插接。
2. **缺的不是"第四根轴"，是每根轴的"侧"（locus）维度**：device-side / host-side / cable-side 未建模，导致同一根轴上的两个声明可能根本不在同一个连接平面上比较。这是比"关系类型错配"更深一层的建模缺陷，也解释了为什么电气密度只有 0.0037%——分母里大部分对根本没有可比较的同一平面。
3. **这也让共装层的 `port_exhausted` 更可信**：既然 EPick 与 VGC10 都占用同一个工具端口，共装必然耗尽，126 对 `port_exhausted` 不是判据错误，是工程事实。

**取证来源**：Robotiq EPick e-Series QSG（`blog.robotiq.com/.../Quick_start_EPick_eS_EN.pdf`）；Robotiq 2F-85/2F-140 UR 手册（`img1.wsimg.com/.../2F-85_2F-140_UR_PDF_20240402.pdf`）；OnRobot VGC10 用户手册（ManualsLib 2937874）；UR 工具连接器规格页（`universal-robots.com/.../electrical-interfaces-tool-connector/`，8-pin，供电+控制信号）。

**全批结论（19 节点已逐件打完 locus）**：device 4（全为执行器总线）、adapter 3、host 3、cable 7、侧未定 1。**末端工具与传感器没有任何一个真正的 device-side 端口**。据此重判 8 对：器件间真互插只剩 **ACT-001 × ACT-002 一对**（DYNAMIXEL TTL 总线可菊花链），电气密度从 0.0037% 下修为 **0.00047%（1/214,840）**。逐件表见同目录 `B1_电气端口取证表`。
另两条宿主事实已落定：UR30-1300 的工具连接器是 **M8 8-pin female**（与 CB/e-Series 的 8-pin male 不同代不同型），FR3 datasheet 仅称 "hardware prepared for 2x DI & 2x DO"、未见已装工具侧 I/O——若确认，则 co_mount 里 FR3 的 63 对 `unknown` 应从 Z1 改为 Z4，共装层分布变为 **Z3 47.5% / Z4 52.5% / Z1 0%**。
**这一节的地位**：它把论文的第 4 条贡献从"零的分类学"推进到"**零的成因里有一类是坐标系错位**"——不是数据缺、不是关系错、不是资源少，而是两个数字被放在不同的平面上比较。

### 3.9 数据可信度

`confidence_tier`：verified 78（9.0%）/ observed 241 / derived 142 / inferred 294 / unverified 113；`source_tier` A 245 / B 324 / C 299；`verified:true` 字段 354 个（与 tier=verified 的 78 不一致）；无制造商实体 227 个；`data_quality` 中 placeholder_id 51、unverifiable_vendor 30、quarantined_no_source 12。

兼容规则层：586 条规则全标 `compatible`，按 `type` 拆为 `same_lineage` **440（75.1%）**、`same_voltage_domain` 114、`same_mechanical_interface` 7、`mounts_to` 3 等。**四分之三的"兼容"是同产品线推断**，不得当接口证据。

---

## 4. 重设后的切口 v2

### 4.1 标题候选

- **A（推荐）** The Conservation of Zeros: Why More Declarations and New Relation Types Do Not Make Modular Robots Composable
- B Zero Is Not Always Missing Data: A Taxonomy of Composability Failures in Modular Robotic Hardware
- C Measured Decidability: 656 Components, 214,840 Pairs, and the Binding Axis of Modular Robot Composition
- D Wrong Plane: Locus Mismatch in Interface Declarations and the Conservation of Zeros in Modular Robot Composition

### 4.2 四条贡献

1. **可复算的测量方法**：三轴端口 + fail-closed 三值裁决 + 对级全枚举，输出密度而非"是否支持"。
2. **最弱轴结论**：三轴合取可判定性 ≤ 最弱轴密度；本目录最弱轴为电气（8 对 / 0.0037%），故机械与信号轴上 575 / 261 个缺口节点的单条声明边际收益恒为 0。
3. **标准化的可测量效应**：标准化轴（机械）2,016 对可判定且 85.7% 跨厂商；未标准化轴（电气）仅 8 对、62.5% 同厂商。B1 全批核验证实，这 8 对里只有 1 对是器件间真互插，其余 7 对是"同一端口家族/线缆端"被当成互插——电气轴对 EOAT 根本不是器件—器件轴，而是器件—线缆轴。
4. **零的分类学与守恒**：Z1–Z5 五类判据（含 B1 新发现的坐标系错位）+ 两种关系类型下的分布（99.9% → 17.5%），证明换关系类型不解锁、只迁移成因。

### 4.3 图表（数据全现成）

| 编号 | 内容 | 源 |
| --- | --- | --- |
| Fig 1 | 三轴端口与 fail-closed 裁决流程 | `morphology_graph.meta` + `compose_semantics.rule_table` |
| Fig 2 | 三轴密度矩阵（单轴/两轴/三轴） | `evidence_valuation.json` |
| Fig 3 | MDV 地图（575/637/261 缺口按轴） | `evidence_valuation.by_axis` |
| Fig 4 | 互插 vs 共装的零成因堆叠柱（Z1–Z4） | `compose_semantics` + `co_mount.summary` |
| Fig 5 | 可判定对的厂商跨越分布（机械 vs 电气） | 本轮现算 |
| Table 1 | 8 个电气可判定对逐条列名 | 本轮现算 |
| Table 2 | 656 节点分层（类别/厂商/可信度） | `entities.json` |
| Table 3 | 近邻差异表 | 本报告第 2 节 |

### 4.4 必须写清的边界

- 不声称"标准化无效"，只声称"标准化单独不足以产生可判定性，而未标准化轴上补声明收益为零"。
- 不声称"全市场 0%"，只声称"本审计目录三轴联合 0/214,840"。
- 不把 `unknown` 当 `incompatible`。
- 不把 `same_lineage` / `same_voltage_domain` 当接口证据（554/586 属此类）。
- 共装层只覆盖单宿主工具侧，跨本体、转接链、多工具未建模（引擎自述已写明）。
- **电气端口声明未分 device-side / host-side / cable-side**，任何"电气可判定对"在定稿前必须逐对核清所在侧；未核清的只能报为"侧未定"，不得计入密度。
- 信号轴 60.2% 声明为品类级推断（Tier B），其 96.7% 跨厂商率必须打折后再引用。

---

## 5. 四周取证计划

| 批次 | 内容 | 产出 | 验收标准 | 工期 |
| --- | --- | --- | --- | --- |
| **B1 电气轴回溯** | 19 个节点 / 25 个端口逐个回溯 datasheet，并为每个端口打 `locus`（device / host / cable）；5 个宿主工具侧事实（UR30 法兰 A80、FR3 端口数、KUKA/ABB/Fanuc 工具 I/O） | 证据表 + 修订后的电气密度 | 每对可判定都有厂商文档且 locus 已定；未定者不得计入密度 | 1 周（已完成 3/19 节点，发现 Z5） |
| **B2 EOAT 法兰与连接器补采** | 107 个无法兰声明的 EOAT（88 传感器 + 16 夹爪 + 3 其他） | 法兰/连接器取证表，可标注面从 14 扩到 ≥50 | 新增标注必须带 source_url 与 tier；无出处一律留空 | 1 周 |
| **B3 外部目录交叉** | 从 UR+ / ROS-Industrial / HRIM 示例取 50 件做第二目录，独立重算密度 | 复现表 | 电气密度与主目录同量级（±1 个数量级）；跨厂商占比方向一致 | 1 周 |
| **B4 稳健性与定稿准备** | 分层 120 件（A/B/C 各 40）双人编码、κ≥0.75；329 家制造商 1,000 次 bootstrap | 置信区间 + 图表定稿 | 主结论在 bootstrap 下不翻转 | 1 周 |

**不可并行项**：B2 必须先于共装层扩容；B1 必须先于任何"最弱轴"表述定稿。
**B1 进度**：已核 Robotiq EPick、Robotiq 2F-85、OnRobot VGC10 三件（对应 GRIP-014 / GRIP-002 / GRIP-012），并同时取到 UR 工具连接器（8-pin）的官方规格。剩余 16 件按厂商分组：ROBOTIS 3、Robotiq 2、OnRobot 2、ATI 3、Schunk 1、CubeMars 1、其他 4。

---

## 6. 必须修的一致性问题

| # | 位置 | 问题 | 处理 |
| --- | --- | --- | --- |
| 1 | `docs/RESEARCH_BARRIERS_20261003.md` | 654/1,454/27/427,716/46,149 全过期 | 用现算值覆盖并附时间戳 |
| 2 | `compose_lattice_tests.json` | Monotonicity 1958/2000 通过但 `failures=[]` | 补 42 例去向 |
| 3 | `entities.json` | `verified:true` 354 vs `tier=verified` 78 | 定义两个字段；论文只引一个 |
| 4 | 文档/README | CI 闸门 48/91/76 三版 | 冻结到某一 commit |
| 5 | README/文档 | "6.57% 可判定率" | 删除或改写为"实体级登记率 16.2%" |
| 6 | `compatibility.json` | 586 条全标 compatible，440 条实为 same_lineage | 打标分离 |
| 7 | `co_mount.json` | `single_mount` 与 `pair` 两套计数并存 | 论文引用时标明"单件 32 / 双件 0"，不可混算 |

---

## 7. 结论

**能做。骨架已经从"K=2 定理"换成了"零的守恒与迁移"，B1 又把它推进到"零里有坐标系错位"这一层——后者是实测、有分类、有边界。**

- 占位：发现层被占，测量层空着。
- 差异：可辩护，但引言必须把 Tola 2022 摆第一。
- 量级：214,840 对 + 360 对共装，足以支撑密度与分类；不足以支撑"市场级"，须限定为"审计目录"。
- 预算：4 周，B1→B2→B3→B4，其中 B1 与 B2 不可并行。

**下一步动作**：直接进 B1。电气轴只有 8 对可判定却要承载"最弱轴"这条主结论，这 19 个节点的 datasheet 是整篇论文最脆的一环，也是最先该钉死的一环。

---

**【2026-11-09 补记】** 本节四项未决（2FG7 / HEX-E 4-pin / Axia80 双端口 / UR20-UR30 跨代）已全部闭环；七处一致性问题已逐条复核（其中 2 处只报实测、5 处未改数据）。详见 `核验报告_RoboParts_收尾B2B3B4_v3.md`，本报告正文保留原文以备对照。
