# 决策记录：MUSE 开源硬件 / muselsl Linux SDK 是否接入 RoboParts

> **结论先行**：
> **SDK 本身对本项目零加持（Q1 直接不通过）；MUSE 作为「数据源」不该接；**
> **但它是一件有价值的「证伪工具」——它实测暴露了本项目信号轴的一个结构上限。**
> 本轮已把该上限登记进 `neurorobotics/signal_interface.schema.json`（`$comment`），
> **不做任何 MUSE 数据接入。**
>
> 决策日期：2026-10-04 · 决策人：项目负责人 · 状态：**已裁决（不做数据接入）**

---

## 0. 事实核实（不靠记忆）

| 项 | 事实 | 出处 |
|---|---|---|
| 开源 SDK | `muselsl`（PyPI 包名），仓库 `rindieeagle/muse-lsl` | GitHub |
| 许可 | **BSD-3-Clause** | 仓库 LICENSE |
| 维护状态 | v2.3.1，最后提交 **2024-06-03** | 仓库 tag/commit |
| 兼容型号 | Muse 2 / Muse S / classic Muse (2016) | 仓库 README |
| Linux 支持 | **官方支持**。默认 `bleak` BLE 后端，**无需 dongle** | README "Research Tool Compatibility: Linux" |
| 依赖 | `pygatt` / `bleak` / `BlueMuse`（Windows GUI）/ `bgapi`（Mac BLED112） | README |
| 数据链路 | BLE → `muselsl` → **LSL 流**（或直接 CSV 录制） | README |
| 设备规格（Muse 2016） | BT 4.0 BTLE · **256 Hz / 12-bit** · 电极 **TP9, AF7, AF8, TP10**（干电极）· 参考 **FPz (CMS/DRL)** · 输入量程 2 mV p-p · 三轴加速度计 52 Hz/16-bit · 60 g | InteraXon 官方规格表 |

**注意**：市场上有多个 `muse-lsl` 仓库（`digital-cinema-arts`、`andrewjaykeller`、
`jnaulty`、`Neural-Dynamics-Lab-VT` 等），均为同一上游的不同 fork。
**只有 `rindieeagle/muse-lsl` 仍在维护且已 `pip install muselsl` 化**——
引用时必须指明这一条，否则会引到 2016 年的死代码。

---

## 1. 逐条过方向闸门（锚点 §2 三问）

| 闸门 | 判定 | 依据 |
|---|---|---|
| **Q1 产出别人做不出的东西？** | ❌ **不通过** | `pip install muselsl` 即可流 EEG。SDK 是**通用能力**，不依赖本项目任何独有资产。装它不会让 RoboParts 多出任何别人做不出的东西。 |
| **Q2 定义了新问题？** | ⚠️ **部分通过** | 「连续多通道生理信号源如何声明式接入躯体」确实是新问题——但**它不是 RoboParts 的新问题**，它是 BCI 社区已有的问题（OpenBCI / BrainFlow / LSL 生态都在做）。我们没有先占。 |
| **Q3 更接近「具身组合演算」？** | ❌ **不通过** | muselsl 是**数据采集工具**，不产生任何组合/裁决/可判定性。它离「让组合变得可校验」很远。 |

**三问两否 ⇒ 按锚点 §2 纪律丢弃。**

补充否证：锚点 §3 负向边界已列「❌ 造脑 / 连接组仿真」——
MUSE 是**读脑**而非造脑，形式上不撞这条线，但它落在「非本域」侧：
本项目的 `neuron` 层被明确定义为**连接组**（connectome，结构化神经元数据，
见 `api/provenance.json#layer_inventory.neuron.count = 5`），
而 MUSE 给的是**头皮电生理时间序列**。把 MUSE 塞进 `neuron` 层是
**语义错配**——与 2026-10-04 发现的共装错配（`co_mount` 那条）**同型**：
关系/类型对不上，硬塞只会制造看起来合规、实则无意义的数据。

---

## 2. 三个「能不能接」的分层回答

用户问「我们项目是否可以来源连接 muse 的开源硬件？」——「连接」有三层含义，
结论**逐层不同**。混着回答会得出错误结论，所以分开答：

### (a) 能不能在 Linux 上跑它的 SDK 流 EEG？ → **能，但不是我们的事**
`pip install muselsl` + BLE 即可。这属于**用户侧/实验侧**的采集工具，
放进 RoboParts 仓库不产生任何方向价值。

### (b) 能不能把 MUSE 当作一个「零件」录入 parts registry？ → **不该**
- MUSE **没有法兰、没有 ISO 9409-1、没有机器人侧电气端口**。
- 录进来后 `mechanical` 轴只能判 `n_a`，`electrical` 轴无端口可判。
- 即 **MDV = 0**：补它对任何配对的判定结果**零贡献**。
  这正是本项目 2026-10-03 建 MDV 层要防的那类「补了也不改变任何判定」的数据。
- 录进来的唯一效果是**虚增实体数**，而实体数是本站的核心对外数字
  （`onboarding_block.facts()`，全站 20 页 + 4 接口的唯一真相源）。
  **为无效数据放大核心指标 = 自我注水**，明确不做。

### (c) 能不能用它闭合一条 provenance 链 / 填满 signal contract？ → **不能，schema 表达力不够**
这是本轮唯一有实质结论的一层。**实测如下**（逐字段核对，非推测）：

以 MUSE 2016 为实例，试写一份 `signal_interface.schema.json` 契约：

```
controller 段：required=['connectome_ref','neuron_model']  additionalProperties=false
  ❌ 试写的 channels[] / device / reference / sampling_hz / transport 五个字段全部越界
  ❌ 且缺必填的 connectome_ref（MUSE 不是连接组）
mappings.output：controller_population 是 string，不是数组
  ❌ 无法表达「4 个 EEG 通道经解码器产生一个控制量」
```

**结论：本 schema 只能表达「离散的、1:1 的」群体→执行器映射，
无法表达「连续多通道生理信号」。**

**这暴露了一个我们此前没有明说的结构上限**：
信号轴目前只能靠**品类级推断**赋值
（`build_morphology_graph.SIG_ROLE_BY_CATEGORY`，Tier B），
**无法由设备级声明升级**——因为根本没有放通道/采样率的地方。

这个上限其实早就写在代码注释里（`SIG_PORT_CAVEAT`：「品类级推断（Tier B），
非厂商 datasheet 实测」），但**从未被量化到「差哪几个字段」**。
MUSE 提供了这个量化：**差 5 个字段 + populations 需要从 string 变 array。**

---

## 3. 本轮实际做了什么（以及为什么只做这么多）

**已做（成本 ~1 小时，全部非破坏性）**：

1. 在 `neurorobotics/signal_interface.schema.json` 加 `$comment`，
   把上述表达力边界**登记为 schema 自身的能力声明**。
   - 用 `$comment`（JSON Schema 2020-12 保留关键字）而非新增 property：
     **不参与校验、不会被 `additionalProperties:false` 拒绝、
     也不会被 `build_morphology_graph` 读成新的语义。**
   - 已复核：`properties` 逐键未变，重建形态图产物完全一致。
   - 这与项目既有纪律一致：**「不知道」必须显式可见**（参照 `evidence_gap` 机制）——
     schema 表达不了什么，也得写出来，否则下一个人会试着硬塞。

2. 写下本决策记录（本文），使这个问题**被裁决过一次**，不必重复讨论。

**明确不做（并给出不做的理由）**：

| 不做 | 理由 |
|---|---|
| ❌ 引入 muselsl 依赖 | Q1/Q3 不通过；它是采集工具，不产生任何可判定性 |
| ❌ 把 MUSE 录进 entities registry | MDV = 0，且会虚增核心对外指标（自我注水） |
| ❌ 扩展 schema 加 channel 层 | 属 D5 范畴论路线（锚点 §6.2 多年期）；且**没有第二个用例**证明这个扩展值得——为一个设备改 schema 属过度设计 |
| ❌ 写 MUSE 集成文档/教程 | 锚点 §2 判据示例：旧问题、无独特贡献、无关方向 |

**唯一值得保留的长期价值**：MUSE 是一个**现成的证伪用例**。
若将来要扩展 schema 支持多通道信号源，MUSE 的规格（4 通道 / 256 Hz /
12-bit / FPz 参考 / BLE 4.0）可以直接当**验收测试的输入向量**，
不必再找一个设备。现已记录在 `$comment` 里。

---

## 4. 与既有发现的连接

本轮这个「schema 表达力上限」与 2026-10-04 的另一个发现**同型**，
值得并列记录：

| 发现 | 症状 | 根因 | 共同教训 |
|---|---|---|---|
| **共装错配**（`api/compose_frontier.json`） | `composed` 恒为 0 | 模型只有 peer-to-peer 一种关系，缺 co-mount | 关系类型比数据量更早成为瓶颈 |
| **信号轴上限**（本记录） | 信号轴只能是 Tier B 品类推断 | schema 只能表达 1:1 离散映射，缺 channel 层 | **声明格式的能力上限，会伪装成「数据不够」** |

**教训**：当某个轴长期停在 Tier B 且怎么补数据都升不上去时，
**先怀疑声明格式的表达力，再怀疑数据量**。
判据：拿一个**真实的该领域设备**去逐字段试写 schema——
**试写失败 ⇒ 是格式问题；试写成功却没数据 ⇒ 才是数据问题。**
MUSE 在这里的作用是「试写失败」的那个设备，这比补 100 条声明更有诊断价值。

---

## 5. 复现命令

```bash
# 决策依据：schema 表达力实测（逐字段核对）
python -c "
import json
d=json.load(open('neurorobotics/signal_interface.schema.json',encoding='utf-8'))
c=d['properties']['controller']
print('required:', c['required'], 'addProps:', c['additionalProperties'])
print('allowed:', sorted(c['properties'].keys()))
m=d['properties']['mappings']['properties']
for k,v in m.items():
    print(k, '->', sorted(v['items']['properties'].keys()))
"
# 现状：controller 只允许 connectome_ref/neuron_model/output_populations/
#       input_populations/reward_populations；mappings.output 的
#       controller_population 是 string（单一个体），无 channel / sampling 概念

# 本仓既有口径（证明信号轴确实是 Tier B 推断）
grep -n "SIG_PORT_CAVEAT" scripts/build_morphology_graph.py
grep -n "SIG_ROLE_BY_CATEGORY" scripts/build_morphology_graph.py
```

---

## 6. 一句话收束

> **muselsl 是通用采集工具，接进来不加持本项目（Q1/Q3 不通过）；
> MUSE 作为数据源不该接（MDV=0 + 会虚增核心指标）；
> MUSE 作为证伪工具很有用——它实测暴露了信号轴的声明格式上限，
> 这个上限已登记进 schema 自身。**
>
> **判据固化**（本记录最可复用的部分）：
> 拿一个真实设备去逐字段试写 schema。
> **试写失败 ⇒ 格式问题，别去补数据；试写成功却没数据 ⇒ 才是数据问题。**
