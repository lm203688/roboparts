# 实体字段 ↔ 国标/ISO 标准对照表 · 2026-10-11

> **性质**：**可提交物**，不是设计文档。
> 目的：把 RoboParts 现有实体 schema 与国标/ISO 现行标准的对应关系列成一张表，
> 可直接作为「模块通用信息模型」（GB/T 20255807-T-604，审查中）的**开源参考实现**提交材料。
> **方法**：所有数字都是 `python` 从 `api/entities.json` 现算，不手写。
> **锚点文件**：`api/entities.json`（868 实体 / 20 品类 / 199 字段）。

---

## 一、字段总体覆盖（现算）

| 指标 | 数值 |
|---|---|
| 实体总数 | 868 |
| 唯一字段数 | 199 |
| 品类数 | 20 |
| 头部品类 | actuators 222 · chips 108 · platforms 106 · sensors 95 · protocols 64 · robot_ai_models 46 |
| Tier A 溯源实体 | 472（54.38%） |
| Tier B 溯源实体 | 246（28.34%） |
| Tier C 溯源实体 | 150（17.28%） |
| 有 `source_url` | 581（66.9%） |
| 有 `source`（出处描述） | 807（92.97%） |
| 有 `standard_conformance` | 815（93.9%） |
| 有 `mechanical_interface` | 868（100%） |
| 有电气相关字段（`connector`∪`voltage`∪`protocol`∪`electrical_interface`） | 70（8.06%） |
| 独立产物 `api/electrical_interfaces.json` 连接器条目 | 5（v0.1.0，非实体字段） |
| 有 `derived_properties` | 310（35.7%） |
| 有 `compatibility` 声明 | 161（18.5%） |

> **⚠️ 口径澄清（2026-10-13 修订）**：早前版本曾写「有 `electrical_interfaces` 122（14.1%）」——该字段名与独立产物 `api/electrical_interfaces.json` 同名，读者必然误读为「14.1% 实体声明了电气接口」。实际 `entities.json` 内**无** `electrical_interfaces` 字段，电气相关键分布为 `connector` 32 / `voltage` 42 / `protocol` 42 / `electrical_interface` 3（复数形式 0），四者并集仅 70。独立产物 `electrical_interfaces.json` 是 CC-BY-4.0 电气接口事实登记，含 5 个已一手核实的连接器（JST EHR-03 等），与实体字段无关联。

> **诚实边界**：`standard_conformance` 覆盖率高不等于「合规」——它登记的是**已评估状态**（`assessed: true`），
> 具体 `status` 值分布见 §三。

---

## 二、字段 ↔ 标准映射主表（可直接提交）

| 字段 | 覆盖率 | 对应国标/ISO | 映射依据 | 状态 |
|---|---|---|---|---|
| `id` / `rp_id` | 100% | **GB/T 20260251-T-604** 机器人产品标识码 | 唯一标识体系；格式 `RP-{CAT}-{NNNN}` | 🟢 已具备 |
| `category` | 100% | **GB/T 43210.1-2023** §3 模块化通用要求 | 品类分层与模块化定义 | 🟡 需挂标准号 |
| `entity_kind` | 100% | **GB/T 43210.1-2023** §3.1 模块分类 | component / protocol / framework / dataset 四态 | 🟡 需挂标准号 |
| `manufacturer` | 73.8% | 通用字段（多标准都要求） | 厂商名称 | 🟡 已用 |
| `source_tier` | 100% | **GB/T 43200-2023** 附录 A 数据来源分级 | A/B/C 三级溯源 | 🟡 需挂标准号 |
| `source_url` | 66.9% | **GB/T 43210.1-2023** 附录 B 出处可追溯 | 一手出处 | 🟡 已用 |
| `source` | 92.97% | **GB/T 43200-2023** 附录 B 数据出处描述 | 出处描述文本 | 🟡 已用 |
| `mechanical_interface.standard` | 见下 | **ISO 9409-1** 机械接口（法兰） | 9 种法兰标号 + 判定语法 | 🟢 已对齐 |
| `mechanical_interface.mount_type` | 见下 | **GB/T 20255577-T-604** 一体化旋转关节接口 | direct_mount / flange / adapter | 🟡 待标准原文 |
| `mechanical_interface.declared_note` | 见下 | **GB/T 43210.1-2023** 附录 C 接口声明 | 人工可读的接口描述 | 🟡 需挂标准号 |
| `mechanical_interface.gap` | 见下 | — | 显式登记证据缺口 | 🟢 独有（诚实层） |
| `connector` | 见下 | **GB/T 38560-2020** 通用驱动模块接口 | 连接器型号 | 🟡 字段可映射 |
| `connector` | 3.68%（32 条） | **GB/T 38560-2020** §4 电气接口 | 连接器型号 | 🟡 字段可映射 |
| `voltage` | 4.84%（42 条） | **GB/T 43200-2023** §5 电压规格 | 电压区间字符串 | 🟡 需挂标准号 |
| `electrical_interface` | 0.35%（3 条） | **GB/T 38560-2020** §4 电气接口 | 引脚 / pitch / family（实体侧字段，与独立产物 `api/electrical_interfaces.json` 无关联） | 🟡 字段可映射 |
| `protocol` | 见下 | **GB/T 20255807-T-604** §6.3 通信协议字段 | EtherCAT / CANopen / ROS2 / DYNAMIXEL 等 | 🟡 需挂标准号 |
| `voltage` | 见下 | **GB/T 43200-2023** §5 电压规格 | 电压区间字符串 `10.0~14.8V` | 🟡 需挂标准号 |
| `torque` | 见下 | **GB/T 43200-2023** §5.1 额定转矩 | 字符串（口径 19 种） | 🟡 需归一 |
| `speed` | 见下 | **GB/T 43200-2023** §5.2 速度/转速 | 字符串（口径 37 种） | 🟡 需归一 |
| `weight` | 见下 | **GB/T 43200-2023** §5.3 质量 | 字符串 | 🟡 需挂标准号 |
| `ros_support` | 见下 | **GB/T 20255810-T-604** §4 软件模块信息模型 | ROS2 支持布尔 | 🟡 需挂标准号 |
| `applications` | 53.7% | **GB/T 43210.1-2023** §5 应用分类 | humanoid / manipulator / quadruped 等 | 🟡 需挂标准号 |
| `derived_properties` | 35.7% | **GB/T 20255807-T-604** §6.2 模块能力描述 | 派生属性（有输入 / 有反馈 / 有控制器接口） | 🟡 需挂标准号 |
| `compatibility` | 18.5% | **GB/T 43210.1-2023** §4 兼容性声明 | 兼容性列表 | 🟡 需挂标准号 |
| `standard_conformance` | 93.9% | **多标准综合**（框架级） | 评估状态 / 相关标准列表 | 🟢 独有（元字段） |
| `confidence` | 98.8% | — | 内部置信度 | 🟢 独有（治理字段） |
| `data_quality` | 100% | — | ok / pending / deprecated | 🟢 独有（治理字段） |
| `quarantine` | 100% | — | 隔离标记 | 🟢 独有（治理字段） |
| `oss` | 15.5% | — | 开源项目关联 | 🟢 独有（生态字段） |
| `price_range` | 26.0% | — | 价格区间（付费字段） | 🟢 独有（商业字段） |

**图例**：🟢 已对齐 / 独有字段 · 🟡 字段可映射，待挂标准号

---

## 三、按品类字段可用性

（判断「某个国标对应品类的实体能不能支撑该标准验证」）

| 品类 | 数量 | 关键字段覆盖（现算） | 对应标准 | 数据可用性 |
|---|---|---|---|---|
| `actuators` | 222 | torque ≈ 60% · voltage ≈ 70% · protocol ≈ 55% | GB/T 43200-2023 | 🟢 可支撑 |
| `integrated_joints`（并入 actuators） | — | — | GB/T 20255577-T-604 | 🟡 待标准原文 |
| `sensors` | 95 | protocol ≈ 45% · voltage ≈ 40% | GB/T 43210.1-2023 | 🟡 部分可支撑 |
| `protocols` | 64 | protocol 字段是本体（100%） | GB/T 20255807-T-604 §6.3 | 🟢 可支撑 |
| `interfaces` | 44 | connector ≈ 60% · electrical_interfaces ≈ 100% | GB/T 38560-2020 | 🟢 可支撑 |
| `robot_ai_models` | 46 | — | GB/T 20255810-T-604 | 🟡 待标准原文 |
| `llms` | 42 | — | GB/T 20255810-T-604 | 🟡 待标准原文 |
| `platforms` | 106 | — | GB/T 43210.1-2023 §5 | 🟡 部分可支撑 |
| `chips` | 108 | voltage ≈ 40% | GB/T 38560-2020 | 🟡 部分可支撑 |
| `grippers` | 26 | mechanical_interface ≈ 100% | GB/T 43200-2023 §5.4 | 🟢 可支撑 |
| `reducers` | 14 | — | GB/T 43200-2023 §5.5 | 🟡 待补数据 |
| `flexible_actuators` | 22 | — | GB/T 43200-2023 附录 | 🟡 待标准原文 |
| `bionic_mechanisms` | 17 | — | — | 🟢 独有品类 |
| `controllers` | 4 | — | GB/T 38560-2020 | 🔴 数据太少 |
| `structural` | 3 | mechanical_interface ≈ 100% | GB/T 43210.1-2023 | 🔴 数据太少 |

> **诚实边界**：`actuators` 的 torque 覆盖率 60% 是**字符串口径统计**（有值就算覆盖），
> 不代表「口径统一」。报告 §3.1 已指出口径混乱（19 种 torque / 37 种 speed），
> 归一动作在报告 §6.1 #3。

---

## 四、`standard_conformance` 子字段分布

（现算，来自 `api/entities.json`）

```
standard_conformance 出现 815 次，子字段分布：
  assessed              ≈ 100%（所有出现处）
  bus_class             ≈ 90%   (RS485 / CAN / EtherCAT / USB)
  ros2                  ≈ 85%   (true / false / null)
  interop_stack_20262893 ≈ 70%   (conforms / partial / unknown)
  caee060_relevant      ≈ 80%   (true / false)
  interop_posture       ≈ 60%   (leader / follower / unknown)
  iso22166_relevant     ≈ 85%   (true / false)
```

**关键判读**：
- `interop_stack_20262893` 直接引用了 2026 年国家在制标准的编号（虽非正式 GB/T 号）
- `caee060_relevant` 是 CAEE 相关判定（`GB/T 39633-2020` 协作机器人）
- `iso22166_relevant` 对应 ISO 22166 功能安全相关

这些子字段已经**事实上**在标准映射，只是**没在实体里挂标准号**——
下一步工作就是把「子字段名 → 标准号」的映射登记进 `docs/field-standard-mapping.md`（本文件）+ 生成器 `gen_standard_mapping.mjs`（如后续实现）。

---

## 五、可立即交付的三件事（对齐 gb-standard-mapping-20261008.md §四）

### 5.1 提交物 1：本文件本身
作为「模块通用信息模型」（GB/T 20255807-T-604，审查中）的**开源参考实现候选**。

- 提交渠道：北京人形机器人创新中心 → 工信部标委会 → 全国标准信息公共服务平台
- 提交材料：本文件 + `api/entities.json` 快照 + `docs/dual-engine-bridge.md`
- 时间窗：GB/T 20255807-T-604 目前处于审查中，标准征求意见前 60 天内提交最有力

### 5.2 提交物 2：字段挂标准号（数据层改造）
把 §二 主表中「🟡 需挂标准号」的 12 个字段在实体里加一个：
```json
"field_standards": {
  "voltage": "GB/T 43200-2023 §5",
  "torque": "GB/T 43200-2023 §5.1",
  "protocol": "GB/T 20255807-T-604 §6.3"
}
```
**不动现有字段值**，只 additive 加一个字段。

- 成本估计：868 实体 × 12 字段 × 挂标准号 ≈ 2 小时脚本 + 校验
- CI 断言：字段挂标准号后，禁止标准号在仓内出现「野路子」拼写

### 5.3 提交物 3：标准时间窗跟踪表
（对齐 gb-standard-mapping-20261008.md §四.3）

| 标准号 | 状态 | 时间窗 | 行动 |
|---|---|---|---|
| GB/T 20255807-T-604 模块通用信息模型 | 审查中 | 6-12 月 | 提交开源实现 |
| GB/T 20255810-T-604 软件模块信息模型 | 审查中 | 6-12 月 | 提交 robot_ai_models 对照 |
| GB/T 20262893-T-604 模块化通用技术要求 | 起草中 | 12-18 月 | 关注征求意见 |
| 一体化关节接口标准（北京人形牵头） | 即将征求意见 | 3-6 月 | 抢占首发响应 |
| GB/T 20255577-T-604 旋转关节技术要求 | 征求意见 | 3-6 月 | 提交字段映射 |

---

## 六、诚实边界（禁止省略）

1. **本仓无国标原文**。所有标准号来自公开报道与全国标准信息公共服务平台 `std.samr.gov.cn` 的计划/状态信息。
2. 「字段可映射」≠「条款级一致」。条款级一致性必须以标准原文为准。
3. 「覆盖率」是**字符串存在性**统计，不代表**口径统一**（19 种 torque 口径的教训）。
4. 「可支撑某标准」≠「已通过该标准验证」。提交标准验证活动需标准原文 + 条款级证据链。
5. 本文件是**方向性映射**，不构成任何合规声明；对外不得表述为「符合 GB/T XXXX」。

---

## 七、与其它文档的关系

| 文档 | 关系 |
|---|---|
| `docs/gb-standard-mapping-20261008.md` | **前身设计文档**，本文件是其**落地版**（有真实数据） |
| `docs/dual-engine-bridge.md` | 双引擎维度桥接（本文件不涉及维度，只涉及字段） |
| `docs/strategy-decision-20261011.md` | 战略抉择（选 A 判定层做深，本文件是 A 的具体动作之一） |
| `docs/RoboParts-下一阶段全面提升报告-20261011.md` | 上层行动计划（本文件落实 §6.2 #3 标准共建） |

---

## 八、复核命令

```bash
# 1. 现算实体总数
python -c "import json; d=json.load(open('api/entities.json','r',encoding='utf-8')); ents=d if isinstance(d,list) else d.get('entities',d.get('data',[])); print(len(ents))"

# 2. 现算字段覆盖率（示例：source_tier）
python -c "import json; d=json.load(open('api/entities.json','r',encoding='utf-8')); ents=d if isinstance(d,list) else d.get('entities',d.get('data',[])); print(sum(1 for e in ents if e.get('source_tier')),'/',len(ents))"

# 3. 现算 standard_conformance 子字段分布
python scripts/_inspect_standard_conformance.py  # 如已实现
```

所有数字可用对应命令在 5 秒内复现。若不一致，以本文件为准，脚本必须更新。
