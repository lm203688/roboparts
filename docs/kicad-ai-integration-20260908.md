# GPT-6 × KiCad 与机器人电路板：对 RoboParts 的参考价值与融入方案

> 检索与核实日期：2026-09-08。所有外部事实均附一手来源，未核实项显式标注 `未核实`，**不臆造**。
> 结论先行：**机制真实，但"代替电路设计"是夸大；我们不应自己做 PCB 设计，而应抢"机电接口规格上游"这个位置。**

---

## 1. 事实核查：这个说法到底真不真？

| 说法 | 判定 | 依据 |
|---|---|---|
| OpenAI 官宣 GPT-6 Astra 在 KiCad 里设计电路板 | ✅ **为真** | GPT-6 Astra 发布（2026-09-07）官方演示：AI 打开 KiCad 做器件布局与走线，官方定义为"可制造的电路板" |
| "直接联动"（官方集成/MCP 插件） | ⚠️ **措辞不准** | 演示走的是 **computer-use（屏幕操作 GUI）**，不是 KiCad 官方插件或 API 集成 |
| "代替电路设计 PCB 和原理图" | ❌ **夸大** | 见下 §2 |

### 2. 一手实测：能力边界在哪

**实测 A（社区最大规模复现，开源可查）** —— 开发者 `jlcjak` 用单条 prompt 让 Astra 生成**六层 CM5 双 NVMe 载板**并全板布线（`astra_piNas`，GitHub 开源）：

- 原理图阶段明显优于前代，但**布局仍不如人工/专用工具**
- 布线**大量依赖开源自动布线器 Freerouting**：自己手画约一半，其余外包
- 高度依赖迭代：整板布完 → 记笔记 → 从零重来
- **2 小时 20 分钟、"fast" 模式、消耗 15% 周额度后第 5 版仍未完成**
- 作者结论原文倾向：对复杂 PCB 布线，**Astra 并不好用**

**实测 B（行业基准 EEBench，atopile 团队出品，2026-09-01 榜）** —— 13 项电路设计任务、SPICE 物理仿真、真实器件 + 最恶劣容差角压测：

| 模型 | 得分 |
|---|---|
| Claude Opus 5 | **61.6%** |
| Grok 4.6 | 57.1% |
| Claude Fable 5.1 | 56.4% |
| GPT-5.5 | 42.3% |
| GPT-5.6 Sol | 39.4% |
| GPT-6 Astra | **尚无成绩** |

61.6% 直译：若把 AI 设计直接送厂贴片，**近四成产品无法正常工作**。
注意：**GPT-6 Astra 自己还没跑过 EEBench** —— 官宣演示 ≠ 通过工程基准。

### 3. 更重要的判断：GUI 路线是弯路

EEBench 团队与多家评测给出了同一个关键观察，这直接决定我们的技术选型：

> 模型读过的电子学知识远多于它在 GUI 工具里能表现出的。**让 agent 操作图形 CAD，大量上下文被坐标、菜单、应用状态吃掉**，剩下的才是电路本身。

因此真正可复现、可工程化的路线是 **hardware-as-code（声明式硬件代码）**：

| 路线 | 代表 | 许可证 | 状态 |
|---|---|---|---|
| 声明式硬件语言 | **atopile**（`.ato` → 编译为 KiCad 工程；YC W24，团队来自 Tesla/DJI/Lilium） | MIT | 活跃，自带 **MCP server** + CLI + Python API |
| 声明式硬件语言 | tscircuit（TypeScript / React 风格组件） | MIT | 活跃 |
| 物理驱动布线 | Quilter（$40M 融资，Oct 2025 Series B） | 商业 | 843 元件 8 层 i.MX8M 板：38.5h vs 人工 428h（约 11×） |
| 强化学习布线 | DeepPCB（InstaDeep） | 免费起步 | 自评 97.3% 完成率（厂商自评，需谨慎） |
| 文件级 MCP | kicad-copilot（biosshot） | — | 直接读写 `.kicad_sch`/`.kicad_pcb`，**无需装 KiCad 即可读**，本地 WASM 布线 |
| 文件级 MCP | KiCad MCP Server（tylerwagler） | — | 75 工具，会话事务模型（先预览后提交，可回滚） |

**atopile 的编译器已经在做的事**：类型系统建模电压/电流/容差/总线拓扑 —— 电压电流跨网络兼容性检查、**I²C/SPI/CAN 总线地址与冲突检查**、上下拉强度与上升时间计算、SPICE 断言（如 `assert ripple < 30mV`）。

> ⚠️ 这一段是整个评估里最重要的：atopile 做的是**电气兼容性判定**，而 RoboParts 做的是**机械兼容性判定**。这是同一个问题的两半，目前**没有任何一方把两半连起来**。

---

## 4. 对我们项目的判断（含与直觉相反的部分）

### 4.1 「是不是可以直接设计机器人的电路板？」—— 我的答案：**不该自己做**

用户直觉可能是"既然 AI 能画板子，我们也做一个"。我认为这是**错误方向**，理由三条：

1. **能力栈完全不同**：PCB 工程的深水区是 SI/PI、电源完整性、EMC、热、DFM、安规 —— 不是"把线连起来"。EEBench 61.6% 的失败全部发生在这些深水区。我们团队（现状）没有这块积累。
2. **打不过，也不必打**：atopile（MIT）+ KiCad MCP 生态 + Quilter 已经把这条路铺完，且**免费/开源**。我们一个月做出来的东西不可能超过它们，还会背上"设计出的板子炸了谁负责"的责任链。
3. **会稀释定位**：RoboParts 的护城河是「零件级兼容判定」，PCB 设计是一个全新的、不相关的产品。同时做两个 = 两个都做不透。

### 4.2 但这里确实有一个**真实且无人占**的机会窗口

AI 画板子的**真正瓶颈不是"画"，是"选对件并确定它们能连"**。EEBench 明确显示失败集中在：

- 真实器件的**容差角**（标称值能过、到货的器件过不了）
- **器件选型 + 供货 + 成本**的三角博弈

这正是 RoboParts 的位置：我们有 **798 实体 / 768 真实厂商件**，是"真实器件"这一层的数据源。

**而更关键的缺口是：机器人 BOM 的兼容性判定目前只有"机械"一个轴。**

举个本轮一手核实出来的、我们**现在完全没判**的真实例子：

| 问题 | 现状 | 后果 |
|---|---|---|
| Dynamixel `XM430-W350-T`（TTL 3pin，10–14.8V）与 `PH54-200-S500-R`（RS-485 4pin，24–48V）能串在同一条链上吗？ | RoboParts 显示两者都是 "DYNAMIXEL Protocol 2.0"，**判定为兼容** | ❌ 连接器针数不同（3 vs 4）、供电轨不同（12V vs 24–48V）——**实际会烧** |
| Feetech `STS3215`（5264-3P）与 Dynamixel X（JST EHR-03）都是 3pin，能互插吗？ | 无任何判定 | ❌ 都是 3pin 但连接器型号/间距不同（2.54mm 杜邦系 vs 2.5mm JST EH 系），**插不上但看起来一样** |
| Raspberry Pi Zero 2W（GPIO 3.3V）直接驱动 Dynamixel？ | 无任何判定 | ❌ 官方推荐电路为 **5V 或 5V-tolerant MCU** 设计，3.3V GPIO **需 level shifter** |

**这三条每一条都是"按我们现在的判定去装机就会烧板子"。** 这不是理论缺口，是实打实的责任缺口。

### 4.3 结论：定位应为「AI-PCB 流水线的机电接口规格上游」

不做 Gerber，做**规格**。

```
RoboParts（机电双轴判定 + 真实器件数据）
        │  输出：接口规格 + 已判定 BOM（JSON / .ato 草案）
        ▼
atopile / kicad-copilot / Quilter（生成 + 布线 + 仿真）
        ▼
     Gerber → 制板
```

这个位置的好处：**不背上"板子炸了"的责任**（我们不生成电路），却卡住了整条流水线的入口（**选什么件、能不能连**由我们判）。与 Tnkr 那条的结论同构——**成为生态一环，而不是自己单开一条产品线**。

---

## 5. 融入方案（三层，按 ROI 排序）

### L0 — 参考构型补「电气轴」（本轮已落地 ✅）

给 `api/reference_builds.json` 的 RB-OMY / RB-ODM 增加 `electrical_interface` 段：供电轨 / 总线 / 连接器 / 电平 / 跨轨判定。
**意义**：让"参考构型"的结论从「机械能装」升级为「机械能装 **且** 电气能通」，并跑通这套字段设计，作为全库铺开的样板。

### L1 — 建立「电气接口轴」正式数据层（建议，待授权）

新增 `api/electrical_interfaces.json`，机械 `negative_compat` 的**电气孪生**：

- `power_domain`：电压域（如 12V / 24–48V / 7.4V / 5V / 3.3V）—— 跨域 = `separate_rail_required`
- `bus`：协议与物理层（DYNAMIXEL Protocol 2.0 / TTL 半双工 / RS-485 / CAN / I²C / PWM）
- `connector`：型号 + 针数 + 引脚定义（JST EHR-03 / EHR-04 / 5264-3P …）
- 判定输出：`identity` / `direct` / `adapter_required`（转接线/转接板）/ `level_shift_required` / `incompatible`

### L2 — 输出 AI-PCB 可读的接口规格（远期）

把 L1 的判定结果导出为 atopile `.ato` 草案 / kicad-copilot 可读的 BOM+net-intent JSON，使 AI 拿到的是**已被判定过的确定规格**，而不是让它自己猜件。

### 明确不做

- ❌ 自研 PCB 生成/布线
- ❌ 宣称 "RoboParts 能设计电路板"
- ❌ 用 GPT-6 Astra 式 GUI 自动化（EEBench 已证明这条路上下文效率低）

---

## 6. 当前数据缺口（诚实版）

本轮查库实测（`api/entities.json`，798 条）：

| 字段 | 覆盖 | 说明 |
|---|---|---|
| `voltage` | 40 (5.0%) | 集中在 actuators（35） |
| `protocol` | 40 (5.0%) | 集中在 actuators（34） |
| `power` | 29 (3.6%) | — |
| `connector` | 28 (3.5%) | **actuators 上为 0** |
| `current` | 1 (0.1%) | 基本等于没有 |

⇒ **电气轴目前是碎片，不能对外宣称"我们有电气兼容判定"。** `connector` 在 actuators 上为 0 尤其致命——连接器正是线束/载板设计的关键，且它是**低成本可补**的（Dynamixel X / Feetech 的连接器型号均为公开规格）。

---

## 7. 一手核实事实清单（本轮）

**Dynamixel（ROBOTIS e-Manual + robotis.us 官方技术提示）**

- TTL 版：Housing **JST EHR-03** / PCB Header **JST B3B-EH-A** / Crimp **JST SEH-001T-P0.6** / 21 AWG；Pin1 GND、Pin2 VDD、Pin3 DATA
- RS-485 版：Housing **JST EHR-04** / Header **B4B-EH-A** / 21 AWG；Pin1 GND、Pin2 VDD、Pin3 DATA+、Pin4 DATA-
- 官方规则：型号**以 T 结尾 = TTL 3-pin**；**以 R 结尾 + P 系列 = RS-485 4-pin**
- AX/MX 老系列用 Molex 连接器，与新款 JST 不同，混用需转接线
- 官方推荐电路 NOTE：**为 5V 或 5V-tolerant MCU 设计，否则需 Level Shifter**
- 供电经 Pin1(−)/Pin2(+) 供给

**Feetech STS3215（官方规格书）**

- 接口：**5264-3P**；Pin1 GND、Pin2 VCC、Pin3 Signal/TTL
- 半双工异步串行，波特率 38400bps ~ 1 Mbps
- 电压：**型号依赖** —— 7.4V 标称版规格书列 6V 行数据；C044 标 5–8.4V，C047 标 4–14V
- Stall 电流 2A / Rated 500mA / Idle 6mA

**未核实（不写入任何对外结论）**

- Open Duck Mini 所用 STS3215 的具体 C 编号与电池/BMS/UBEC 型号
- OpenManipulator-Y 具体电源规格（本轮未检索）

---

## 8. 优先级建议

| 优先级 | 事项 | 理由 |
|---|---|---|
| **P0** | 全库补 `connector`（尤其 actuators） | 当前 0 覆盖，且是载板/线束设计的硬输入；Dynamixel/Feetech 型号公开可采 |
| **P1** | L1 电气接口轴（`electrical_interfaces.json`） | 与机械轴同构，是我们唯一能占的位；先做 Dynamixel/Feetech/CAN/I²C 四族 |
| **P1** | 修正现有判定责任缺口 | 上述三条"现在会判错"的案例须尽快出判定，否则对外口径有风险 |
| **P2** | L2 atopile / kicad-copilot 导出 | 等 L1 数据成型后再接，避免空管道 |
| **不做** | 自研 PCB 生成 | 见 §4.1 |

---

## 9. 与其他开源目标的协同

- **Tnkr**：其项目包四层（hardware/software/data/models）里 `hardware` 目前只有机械 BOM —— 电气接口规格可作为第五层补入，强化"参考构型即接入内容"。
- **Open Duck Mini**：本轮已补电气段，是 L1 最好的样板（连接器/电平/跨轨三个坑全占）。
- **CLAP**：仍为正交（策略/感知基础模型），不受本轮影响。
