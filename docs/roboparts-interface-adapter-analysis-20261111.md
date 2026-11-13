# RoboParts 生态接口适配分析 · FlyBrain / 世界模型

> **文档性质**：接口契约映射分析（How/接口定义），非技术路线图。基于既有阶段目标（`docs/roboparts-核心目标-20261106.md` 阶段二）与已有方向锚点（`docs/direction-evolution-roadmap-20260923.md` 脑×体×智组合）。
> **生成时间**：2026-11-11
> **文档状态**：DRAFT · 待 Chief 审阅
> **来源锚点**：`docs/direction-change-feasibility-20260923.md`（FlyBrain 对接点）、`docs/technical-decisions-20261014.md` TDD-2026-01（世界模型排除）、`neurorobotics/signal_interface.schema.json`（信号契约）、`api/mechanical_interfaces.json`（机械接口登记）、`adapters/gen_adapter.py`（转接件生成器）

---

## 0. 任务范围与诚实边界

| 维度 | 本分析覆盖 | 本分析不覆盖 |
|---|---|---|
| **FlyBrain** | BCI 解码层 × RoboParts adapter 层的契约映射（神经信号维度 → 零件几何维度） | FlyBrain 内部神经拓扑生成算法；神经仿真引擎（Nengo/NEURON）集成 |
| **世界模型** | 动态策略输出 × RoboParts 静态校验层的契约映射（动作空间 → 装配约束） | 世界模型训练/推理管线；视觉生成模型集成 |
| **实时性** | 契约定义 + 校验（静态层） | 实时数据交换（RT 控制回路） |

**核心诚实边界**：
1. RoboParts 已实现"静态组合校验"（零件能不能装），未实现"动态仿真"（策略能不能跑）。
2. 与 FlyBrain/世界模型接口属于"**契约定义 + 校验**"层面，非实时数据交换。
3. `signal_interface.schema.json` 已知表达力边界：只能表达**离散的、1:1 的**「控制器群体→躯体执行器」映射，不能表达**连续多通道生理信号**（详见 §1.4）。

---

## 1. FlyBrain BCI 解码层 × RoboParts adapter 层契约映射

### 1.1 双方资产定位（事实核对）

| 维度 | FlyBrain 侧 | RoboParts 侧 | 咬合点 |
|---|---|---|---|
| 神经拓扑 | 22 蓝图 / 5 stacks / 40 motifs；`ModuleFactory` 含 `motor` 模块 | 无（不生成神经拓扑） | flybrain motor 输出 ↔ RoboParts 执行器 |
| 躯体标准件 | 拓扑需真实机械接口规格 | 222 actuators + 23 grippers；ISO 9409-1 法兰登记 | RoboParts 提供 flange registry |
| 信号契约 | 果蝇→Doom 手工接线的替代方案 | `signal_interface.schema.json`（GAP-G2） | schema 直接作为 bridge |
| 溯源合规 | W3C PROV-JSON（70/70 通过） | `schemas/embodiment_provenance.schema.json` | 可拼端到端溯源链 |

来源：`docs/direction-change-feasibility-20260923.md` §1.2/§方向二；`docs/roboparts-核心目标-20261106.md` 阶段二呼应。

### 1.2 契约映射：神经信号维度 → 零件几何维度

**核心命题**：flybrain 的 `motor` 模块输出（神经脉冲信号）需要一个物理躯体去驱动；RoboParts 恰好提供这个躯体（执行器 + 信号契约）。映射本质 = **信号类型检查 + 机械接口类型检查**的双层契约。

#### 层 1：信号维度（`signal_interface.schema.json`）

```
controller.output_populations[]  →  body.actuators[]
     │                                   │
     ├─ encoding: rate/temporal/event/membrane-potential
     │                                   ├─ type: discrete/continuous/pwm/spike-train
     │                                   ├─ range: [min, max]
     │                                   └─ unit: e.g. "N·m" / "rad/s"
     │
     └─ mappings.output[]: { controller_population, body_actuator, rule, scale }
```

- **类型检查规则**：`encoding` 与 `body.actuators[].type` 必须可互转。如 `rate` → `continuous`（频率编码到连续力矩）；`event` → `discrete`（事件触发到开关量）；`spike-train` → `pwm`（脉冲序列到占空比）。
- **scale 字段**：解码比例，如"群体放电率 10Hz → 关节力矩 1 N·m"。
- **rule 字段**：映射规则的可读描述（如"线性映射""阈值触发"），供人工复核与 CI 校验。

#### 层 2：机械维度（`api/mechanical_interfaces.json` flange_designations）

```
RoboParts 执行器法兰  ←→  ISO 9409-1 标准法兰
     │                          │
     ├─ d1_mm (螺栓节圆直径)     ├─ interchange_rule: d1/n/thread 三者全等 → 可互换（必要条件）
     ├─ bolt_count              ├─ 仍需校验：螺纹旋入深度 / 法兰总厚 / 中心通孔直径
     └─ thread                  └─ 三者任一不符 → 不可直接互换（需转接件）
```

- **转接件规则**：两侧法兰不匹配时，`adapters/gen_adapter.py` 生成可 3D 打印转接板（PCD/孔数/螺纹不一致 → 自动生成）。
- **装配红线**：ISO 9409-1 法兰规范——螺栓不得过长（顶破油封）、强度等级按原厂、定位销 g6 过渡配合、产物为几何建议不构成认证。

#### 层 3：组合校验（compose 语义）

`scripts/compose_core.py` 的 `compose(a, b, graph)` 返回 `overall ∈ {composed, type_error, unknown}`：
- `composed`：信号 + 机械接口全部匹配 → 可装配。
- `type_error`：任一维度（信号/机械/电气/软件）不匹配 → 不可装配，附 `verdict_reason`。
- `unknown`：数据不足（无法判定）→ fail-closed，不臆断。

### 1.3 数据接口定义（JSON Schema 层级）

| 契约层 | Schema | 作用域 | 校验入口 |
|---|---|---|---|
| 信号契约 | `neurorobotics/signal_interface.schema.json` | 神经控制器 ↔ 躯体（执行器/传感器） | `gate_cross_engine_consistency`（重放测试） |
| 机械接口 | `api/mechanical_interfaces.json` flange_designations | 执行器法兰 ↔ 标准法兰 | `gate_adapter_five_source`（5 源几何门） |
| 生态接入 | 阶段二定义（数据模式 + 版本协商 + 校验入口） | 外部生态声明接入 | 待实现（阶段二验收项） |
| 溯源 | `schemas/embodiment_provenance.schema.json` | 神经元 → 拓扑 → 躯体 → 策略 → 行为 | PROV-O 对齐 |

### 1.4 已知表达力边界（诚实标注）

`signal_interface.schema.json` `$comment`（2026-10-04 实测登记）：
- **只能表达**：离散的、1:1 的「控制器群体→躯体执行器」映射。
- **不能表达**：连续多通道生理信号。实测依据：MUSE 2016 EEG 头环（4 干电极 TP9/AF7/AF8/TP10 + FPz 参考，256 Hz 12-bit，BLE 4.0）逐字段核对 controller 段，`channels[]` / `reference` / `sampling_hz` / `transport` / `unit` 五字段全部被 `additionalProperties: false` 拒绝。
- **后果**：信号轴目前只能靠品类级推断（Tier B）赋值，无法由设备级声明升级。
- **结论**：要支持真实信号源（如 BCI 多通道）需扩展 schema（新增 channel 层 + populations 数组），属 D5 范畴论路线范畴，本轮明确不做。

---

## 2. 世界模型仿真层 × RoboParts 静态校验层契约映射

### 2.1 核心命题与 TDD-2026-01 定位

**核心命题**：世界模型（动态策略输出）与 RoboParts 静态校验层（装配约束）的映射本质 = **"生成式预测"与"规则确定性判定"的互补关系**——世界模型可以生成环境和交互候选，但视觉连贯不等于尺寸、力学、电气和制造约束正确。

**关键决策锚点**：`docs/technical-decisions-20261014.md` TDD-2026-01 已**明确排除** H-JEPA / Odyssey-3 / Cosmos 3 引入 RoboParts 核心链路，四条硬指标全部冲突：

| # | 判据 | 世界模型要求 | RoboParts 现状 | 冲突 |
|---|---|---|---|---|
| 1 | 范式 | 生成式 / 预测式（预测下一帧、动作流） | 规则确定性（符号/规则组合校验） | ✅ |
| 2 | 输入 | 视觉观测序列 + 动作序列 | 结构化 attributes（868 entities × 20 categories） | ✅ |
| 3 | 可追溯 | 黑盒推理输出 | ISO 22166-1 / GB/T 20255807-T-604 要求每条判定可回溯到证据来源 | ✅ |
| 4 | 部署 | VRAM 数十 GB | Cloudflare Pages 静态部署 + 20s/30% 冷启动指标 | ✅ |

### 2.2 契约映射：动态策略输出 → 静态装配约束

**核心命题**：世界模型输出（动作空间/轨迹）必须映射到 RoboParts 的**静态装配约束**（关节极限/接口类型/组合合法性），否则策略可能生成"看起来合理但装不上/跑不动"的动作。

```
世界模型（动态层）                    RoboParts 静态校验层
    │                                      │
    ├─ action space: 关节角度/力矩/末端位姿   ├─ 装配约束：法兰类型匹配（PCD/孔数/螺纹）
    ├─ observation: 视觉/本体感知             ├─ 电气约束：电压/协议类型
    ├─ predicted trajectory                 ├─ 信号约束：脉冲/感觉/运动契约
    └─ episode reward                       └─ 组合合法性：compose(a,b,graph) 三态判定
```

**映射规则**：
1. **动作空间 → 关节极限**：世界模型输出的动作范围必须落在 RoboParts 执行器的 `range` / `unit` 内（如关节扭矩 ≤ 执行器额定值）。
2. **轨迹 → 组合合法性**：世界模型生成的装配方案必须通过 `compose()` 校验（`composed` 才可执行）。
3. **预测 → 证据**：世界模型预测结果不直接进入 RoboParts 判定证据（黑盒不可追溯，违反 TDD-2026-01 判据 3）。

### 2.3 替代路径（诚实标注）

世界模型的间接价值 = **更好的训练数据**，不是视频预测。对 RoboParts：
- **B 阶段（推荐）**：VLM 证据抽取。用多模态 LLM 从厂商 PDF/手册页抽取结构化属性，扩充 868 entities。
  - 输出走现有 4 维 schema
  - 抽取结果必须过 `gate_cross_dimensional_signals`（跨维信号一致性）
  - confidence < 0.7 的条目进 pending，不进主库
- **C 阶段（可选）**：规则合成测试对。基于 MDV 排序合成更多组合测试对，比例 ≤ 20%（避免污染 fitness 计算）。

**为什么不直接生成新 entities**：违反 `docs/verification-antipatterns-2026-2026.md` 里的 AP-05（不可追溯的合成数据）。

### 2.4 可推翻条件（TDD-2026-01 已登记）

若未来出现同时满足以下三条的世界模型，可重新评估：
1. **确定性推理**：同一 inputs 输出完全一致（不是 best-of-N 采样语义）。
2. **可解释机制**：能给出"为什么判定为不兼容"的因果链（对齐 ISO 22166-1 证据回溯要求）。
3. **静态部署兼容**：无 GPU / VRAM 数十 MB 级 / 冷启动 < 5s 部署形态。

截至 2026-10-14，公开信息无任何世界模型同时满足。**本分析维持该结论，不推翻。**

---

## 3. 契约映射总览（一图看懂）

| 生态 | 接口方向 | 映射维度 | 契约载体 | 状态 |
|---|---|---|---|---|
| **FlyBrain** | 神经信号 → 机械接口 | ① 信号类型检查（encoding ↔ actuator.type）② 机械类型检查（ISO 9409-1 法兰） | `signal_interface.schema.json` + `mechanical_interfaces.json` | ✅ 契约已定义；演示待实现 |
| **世界模型** | 动态策略 → 静态约束 | ① 动作空间 → 关节极限 ② 轨迹 → 组合合法性 | TDD-2026-01 排除核心链路；B 阶段 VLM 证据抽取 | ✅ 决策已留痕；不引入 |
| **生态接入** | 外部生态声明接入 | 数据模式 + 版本协商 + 校验入口 | 阶段二契约（待实现） | ⏳ 待定义演示 |
| **溯源** | 神经元 → 行为 | PROV-O 五层链 | `embodiment_provenance.schema.json` | ✅ schema 已定义 |

---

## 4. 结论

1. **FlyBrain 契约映射可落地**：`signal_interface.schema.json`（信号层）+ `mechanical_interfaces.json`（机械层）+ `compose()`（组合层）三层契约已就位，只需实现演示（阶段二验收项：至少 1 个外部生态完成接入契约演示）。
2. **世界模型不引入核心链路**：TDD-2026-01 四条硬指标全部冲突，决策已留痕并挂 CI 闸门（`gate_world_model_exclusion`）。世界模型的间接价值通过 B 阶段 VLM 证据抽取实现。
3. **诚实边界**：本分析为"契约定义 + 校验"层面，非实时数据交换；`signal_interface.schema.json` 已知表达力边界（不能表达连续多通道生理信号）；世界模型预测结果不直接进入判定证据。

---

*本文基于 2026-11-11 项目内资产核实撰写，所有外部事实均可溯源。*
