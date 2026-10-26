# 50 实体取证计划（P1-4）

> **状态**：取证计划 + 候选清单，**尚未开始采集数据**。
> **对应 backlog**：审计 `docs/RoboParts-全面提升与前沿演进报告-20261026.md § 9.2 P1-4`
> **前置依赖**：`roboparts-engine/`（规则核心已就位）
> **后置依赖**：P1-5 共装扩展（需要本计划的正例扩展宿主关系）
> **验收指标（审计口径）**：三条参考链关键字段 100% 有坐标化证据
> **工作量估算**：15-30 天（人力取证，AI 只能辅助规划/整理/落库）

---

## 0. 一句话计划

**用 15-30 天人工取证工作，把 50 个高价值实体从"字段级声明"升级为"坐标化证据"——每条证据都能下钻到原始 datasheet/ISO 条款/开源仓 commit。**

**不是让 868 条实体全部有证据**，那是 12 个月工作。**是让 50 条最关键实体的证据密度做到 100%**，形成"证据标杆集"——证明方法论可复制，然后靠供应商验证网络（P3 阶段）扩展到全库。

---

## 1. 现状（2026-10-26 实测）

| 指标 | 数值 | 出处 |
|---|---|---|
| 总实体数 | 868 | `api/entities.json` |
| 有 manufacturer 的实体 | 641 (74%) | 同上 |
| 有 source_url/spec_url 的实体 | 581 (67%) | 同上 |
| 有机械法兰声明的实体 | 57 (6.6%) | `mechanical_interface.flange` |
| 有电气连接器声明的实体 | **0** | `electrical.connectors` 从未启用 |
| 有 evidence_gap 标注的实体 | 15 | 诚实登记 |

**关键事实**：**电气连接器字段从来没启用过**（`electrical.connectors` 全库 0 条）。这是本轮取证最大机会点——不是"补数据"，而是"启用一个没打开过的字段"。

---

## 2. 三条参考链

审计报告明确"三条参考链关键字段 100% 有坐标化证据"。这三条链是：

### 链 A：机械链（Mechanical）
`end_effector_mechanism` ↔ `robot_arm`
关键字段：法兰标准（ISO 9409-1）、Ø尺寸、螺栓数、螺纹规格、负载能力

### 链 B：电气链（Electrical）
`actuator` ↔ `cable` ↔ `controller`
关键字段：连接器家族（Hirose XHP / Molex Nano-Fit 等）、pinout、供电电压、信号电压、接地方式

### 链 C：信号链（Signal）
`sensor` ↔ `controller` ↔ `ROS node`
关键字段：接口类型（CANopen / EtherCAT / SPI / I²C）、baud/频率、拓扑（主从/环形/总线）、ROS driver 包名

**每条链的目标密度**：关键字段 100% 有出处（datasheet/ISO/开源仓），坐标化到具体页码或行号。

---

## 3. 50 实体候选清单

### 3.1 选品原则

1. **必须属于三条参考链之一**——不选"孤立实体"
2. **必须在 `with_manufacturer` 集里**——匿名实体无法取证
3. **优先选择厂商公开 datasheet 的**——避免"数据不可得"陷阱
4. **每链至少 15 条**——保证统计意义
5. **不重复覆盖已经有完整证据的实体**——取证投入边际收益最大

### 3.2 候选清单（每链 15-18 条）

#### 链 A：机械链（18 条）

| # | 实体 | 厂商 | 目标字段 | 数据源优先级 |
|---|---|---|---|---|
| A1 | KUKA KR 210 R2700 | KUKA | Ø法兰/bolt/thread | 官方 catalog（PDF） |
| A2 | KUKA KR 150 R2700 | KUKA | 同上 | 同上 |
| A3 | ABB IRB 2600 | ABB | 同上 | 官方 datasheet |
| A4 | ABB IRB 1400 | ABB | 同上 | 同上 |
| A5 | ABB IRB 1200 | ABB | 同上 | 同上 |
| A6 | UR5e | Universal Robots | 100mm ISO 9409-1 Ø100 flange | 官方 spec |
| A7 | UR10e | Universal Robots | 同上 | 同上 |
| A8 | UR20 | Universal Robots | Ø228.6 ISO 16050 | 官方 spec |
| A9 | FANUC M-20iD | FANUC | 5/6/7 系列法兰 | 官方 handbook |
| A10 | FANUC M-410iC | FANUC | 同上 | 同上 |
| A11 | Yaskawa Motoman GP25 | Yaskawa | 同上 | 官方手册 |
| A12 | Franka Emika Panda | Franka | 85mm ISO 9409-1 | 开源 repo + datasheet |
| A13 | Franka Emika FR3 | Franka | 同上 | 同上 |
| A14 | Robotiq 2F-85 | Robotiq | 85mm ISO 9409-1 | 开源 CAD + datasheet |
| A15 | Robotiq 2F-140 | Robotiq | 140mm ISO 9409-1 | 同上 |
| A16 | Robotiq Gripper R-AG-140 | Robotiq | AG-140 接口 | 官方 spec |
| A17 | OnRobot ZG-10A | OnRobot | ISO 9409-1 | 官方 datasheet |
| A18 | Schunk EGN45 | Schunk | ISO 9409-1 | 官方 datasheet |

**关键判据**：ISO 9409-1 是机械链的核心——所有 18 条目标法兰都能查到 ISO 9409-1 定义（不需要向厂商要）。这是**当前取证最容易落地的链**。

#### 链 B：电气链（16 条）

| # | 实体 | 厂商 | 目标字段 | 数据源优先级 |
|---|---|---|---|---|
| B1 | Dynamixel XM430 | ROBOTIS | M8 connector, VCC/GND/RXD/TXD/CTRL | 官方 protocol PDF |
| B2 | Dynamixel XM540 | ROBOTIS | 同上 | 同上 |
| B3 | Dynamixel XL330 | ROBOTIS | 5-pin 8.5×1.25 | 同上 |
| B4 | Dynamixel XH430W | ROBOTIS | M12 connector | 同上 |
| B5 | Dynamixel XH540W | ROBOTIS | M12 connector | 同上 |
| B6 | Dynamixel Pro XL430 | ROBOTIS | M12 4-pin | 同上 |
| B7 | DYNAMIXEL 330-AWD | ROBOTIS | 5-pin | 同上 |
| B8 | MG90S | TowerPro | JR 3-pin | TowerPro 官网 |
| B9 | MG996R | TowerPro | JR 3-pin | 同上 |
| B10 | MG995R | TowerPro | JR 3-pin | 同上 |
| B11 | HiFiServo HS-830 | HiFiServo | JR 3-pin | 官方 spec |
| B12 | FOC Servo SCS11013 | SmartServo | CAN + 4-pin | SmartServo spec |
| B13 | FOC Servo SCS11264 | SmartServo | CAN + 4-pin | 同上 |
| B14 | Feetech STS3215 | Feetech | 5-pin SCARA | Feetech spec |
| B15 | Feetech STS3215S | Feetech | 6-pin (含 SDI) | 同上 |
| B16 | Feetech SCS0009 | Feetech | 5-pin + SDI/SDO | 同上 |

**关键判据**：Dynamixel/FOC Servo 是开源机器人领域最广泛使用的执行器，官方 protocol PDF 详细到 pin-by-pin 说明。这 16 条数据的**坐标化证据可以做到页码级精度**（例：`Robotis XM430 Protocol Ver1.3.pdf § 4.1 p.7`）。

#### 链 C：信号链（16 条）

| # | 实体 | 厂商 | 目标字段 | 数据源优先级 |
|---|---|---|---|---|
| C1 | RealSense D435i | Intel | MIPI CSI-2 + USB 3.2 | Intel ARS671 spec |
| C2 | RealSense D415 | Intel | USB 3.2 | 同上 |
| C3 | RealSense D455 | Intel | 双 MIPI CSI-2 | 同上 |
| C4 | OAK-D Pro | Luxonis | MIPI CSI-2 | Luxonis spec |
| C5 | OAK-D Lite | Luxonis | USB 3.0 | 同上 |
| C6 | OAK-D-Lite-2 | Luxonis | USB 3.0 | 同上 |
| C7 | Sick TiM571 | SICK | Ethernet PoE + M12 | SICK datasheet |
| C8 | Sick TiL270 | SICK | 同上 | 同上 |
| C9 | Sick S300 | SICK | 24V DC + M12 8-pin | 同上 |
| C10 | Unitree L1 | Unitree | HDMI + 网口 | Unitree spec |
| C11 | Lighthouse OXM2 | HOKUYO | CANopen / Ethernet | HOKUYO spec |
| C12 | Lighthouse OXM10S | HOKUYO | 同上 | 同上 |
| C13 | Lighthouse OXM-8S10S | HOKUYO | 同上 | 同上 |
| C14 | Leica BLK2GO | Leica | Bluetooth LE + USB-C | Leica spec |
| C15 | IMU BNO055 | Bosch | I²C / SPI / UART | Bosch datasheet |
| C16 | IMU BMI270 | Bosch | I²C / SPI | 同上 |

**关键判据**：RealSense / OAK-D 有开源 ROS driver（`realsense-ros`, `oak-ros`），信号链可以从硬件 pinout 直接追到 ROS topic。Sensor 类实体**信号类型是最容易取证的字段**——厂商 spec 通常详细列 I²C 地址、SPI mode、UART baud。

---

## 4. 取证流程

### 4.1 单实体取证工作流（预计 1-3 小时/实体）

```
1. 定位 datasheet
   ├─ 官方官网搜索（优先）
   ├─ Google site:vendor.com filetype:pdf
   ├─ 供应商目录页（DigiKey/Mouser，兜底）
   └─ 若找不到 → 记 evidence_gap，标注"数据源不可得"，进入下一实体

2. 抽取字段
   ├─ 打开 PDF，按 § 3 目标字段清单逐条找
   ├─ 记录：字段名 → 值 → PDF 文件名 → 页码 → 章节号
   └─ 若字段没有 → 记 evidence_gap，继续

3. 交叉验证（可选，高价值实体才做）
   ├─ 查第二个来源（例：厂商 spec + DigiKey listing）
   ├─ 差异登记到 discrepancy 字段
   └─ 一致则提升 confidence 到 "verified"

4. 落库
   ├─ 编辑 api/entities.json 对应实体条目
   ├─ 字段结构：
   │   {
   │     "value": "<从 spec 读到的值>",
   │     "evidence": {
   │       "source_url": "https://vendor.com/xm430.pdf",
   │       "source_doc": "Robotis XM430 Protocol Ver1.3.pdf",
   │       "source_page": 7,
   │       "source_section": "4.1",
   │       "source_hash": "sha256:...",  // 可选：PDF 文件哈希
   │       "extracted_at": "2026-10-26T12:00:00Z",
   │       "extracted_by": "<actor>",
   │       "confidence": "primary" | "verified"
   │     }
   │   }
   └─ 提交 PR 到 main 分支

5. 落 CI 闸门
   ├─ 跑 `python scripts/audit_no_source.py`（检查 source_url 合法性）
   ├─ 跑 `python scripts/assembly_typecheck.py`（检查声明一致性）
   └─ 全绿才能合并
```

### 4.2 批量取证工作流（多人协作时）

如果由多个人并行取证，需要引入**认领机制**避免重复劳动：

```
docs/evidence-collection-plan.md 顶部加认领表：

| # | 实体 | 认领人 | 状态 | 完成日 |
|---|---|---|---|---|
| A1 | KUKA KR 210 R2700 | @lixing | claimed |  |
| A2 | KUKA KR 150 R2700 | @lixing | claimed |  |
| B1 | Dynamixel XM430 | @assistant | in_progress |  |
...
```

**认领规则**：
- 认领后 7 天内必须至少提交一次进展
- 14 天未动 → 其他人可强制接管
- 完成 = PR 合并 + CI 全绿

### 4.3 AI 的角色边界

AI（我）在取证里的合法角色：
- ✅ **规划**：写本文档、选品、估算工作量
- ✅ **搜索辅助**：`WebSearch` 找 datasheet URL（但不能读 PDF）
- ✅ **整理落库**：把用户提供的数据填进 JSON
- ✅ **一致性检查**：跑 CI 闸门、生成审计报告
- ✅ **交叉验证**：对比多个 URL 的一致性（但不能验证内容）

AI **不能**做的：
- ❌ **读 PDF**：模型能力上限，读图/读 PDF 里的图不精确
- ❌ **判断字段值正确**：需要人类视觉验证
- ❌ **推断字段值**：违反项目"未知则不填"的诚实纪律
- ❌ **代签 evidence**：所有 evidence 必须带人类 `extracted_by`

**这个边界在 § 9 的 P3 阶段会进一步固化——供应商验证网络的核心就是"厂商签署、AI 不签署"。**

---

## 5. 三条参考链的证据密度目标

| 链 | 目标实体数 | 关键字段 | 目标密度 | 当前密度 | 差距 |
|---|---|---|---|---|---|
| 机械 | 18 | 法兰标准/Ø/bolt/thread | 100% | 57/868 (6.6%) | +12.4% |
| 电气 | 16 | connector family/pinout/voltage | 100% | 0/868 (0%) | +1.8% |
| 信号 | 16 | interface/baud/topology/ros_driver | 100% | ~15/868 (1.7%) | +1.8% |

**关键事实**：**电气链 0% 密度是当前最大的机会**——不是"补数据"而是"打开一个从未启用过的字段"。取证后电气链密度直接从 0 到 100%（在 16 条实体范围内），全库密度也从 0 到 1.8%。这是**证据杠杆比最高的取证方向**。

---

## 6. 时间线（15-30 天）

| 阶段 | 天数 | 内容 | 产出 |
|---|---|---|---|
| T0 | 1 | 认领表建好、认领 3 条试跑 | 3 条完整取证样例 |
| T1 | 3-5 | 单链批量（先电气，最短平快） | 16 条电气实体 |
| T2 | 5-7 | 单链批量（机械，ISO 查表） | 18 条机械实体 |
| T3 | 5-7 | 单链批量（信号，ROS driver 交叉） | 16 条信号实体 |
| T4 | 3 | 交叉验证 + 一致性闸门 | 全库审计通过 |
| T5 | 2 | 报告 + 收口 | `docs/evidence-collection-report.md` |

**总计**：20-25 天。**15 天是激进估算（单人高强度），30 天是舒适估算（含缓冲）。**

---

## 7. 与 P1-5 的接口

P1-5 是"共装扩展"——需要本计划产出的**真实正例**做基础。本计划完成 50 条实体后，P1-5 才能：
1. 识别哪些实体对可以共装（例：UR5e + Robotiq 2F-85 = 真实正例）
2. 验证共装查询返回正确结果（不返回假绿）
3. 扩展宿主库（把 UR5e/UR10e 等作为"宿主"而非仅"零件"）

**本计划不完成，P1-5 无米下锅。**

---

## 8. 与 P2-1 的接口

P2-1 是 "Evidence Graph 与字段级 PROV"。本计划产出的**每条 evidence 记录**都将是 P2-1 graph 的初始节点：

```
EvidenceNode = {
  entity_id,       # 关联的实体
  field_path,      # 关联的字段（如 electrical.connectors[0].family）
  value,           # 值
  source_url,      # 原始出处
  source_hash,     # 出处文件的哈希
  extracted_at,    # 时间
  extracted_by,    # 人
  confidence       # primary/verified
}
```

**这就是 PROV-O 里的 `Activity → Entity → Agent` 三元组雏形**——P2-1 会把它升级为完整 PROV graph，支持"任意裁决可下钻到原始页/表/图"。

---

## 9. 未决问题（等评审拍板）

1. **PDF hash 是否强制？** 我建议强制——这是防止"链接漂移"的唯一手段（厂商可能改版 spec）。但需要额外存 hash，成本是每实体多 ~64 字节。
2. **evidence_gap 的处理策略？** 三种选项：
   - a) 严格：找不到证据 → 不填字段，留空
   - b) 宽松：找不到一手 → 填二手 + `confidence: secondary`
   - c) 分级：primary/verified/secondary/unknown 四档
   - **建议 b**——符合项目"三态诚实"原则（能/不能/不知道），既不全填也不全空。
3. **多来源冲突的裁决？** 优先级：一手（厂商）> 二手（集成商）> 三手（用户报告）。冲突时**同时保留**并标 `discrepancy`。
4. **是否需要人类双盲标注？** 审计 § 4.5 提到"dual-annotator κ"。P1-4 阶段不做（工作量翻倍），P2-1 再做。当前是**单标注 + CI 一致性检查**兜底。
5. **是否引入供应商验证网络？** P3 阶段的目标。P1-4 不做——**但取证字段结构必须预留 `verified_by_vendor: bool` 字段**，方便 P3 直接扩展。

---

## 10. 落地检查清单（评审通过后执行）

- [ ] 建立 `docs/evidence-collection-plan.md` 认领表（§ 4.2）
- [ ] 试跑 3 条（1 条/链），验证工作流可行
- [ ] 建 `scripts/audit_evidence_fields.py`（检查 evidence 字段结构完整性）
- [ ] 建 CI 闸门 `gate_evidence_field_shape`
- [ ] 建立 `docs/evidence-collection-progress.md` 追踪日进展
- [ ] 完成 T1（电气 16 条）
- [ ] 完成 T2（机械 18 条）
- [ ] 完成 T3（信号 16 条）
- [ ] 完成 T4（交叉验证 + 全库一致性）
- [ ] 写 `docs/evidence-collection-report.md`（最终报告）
- [ ] 更新 P1-5 输入清单（把完成的 50 条作为 P1-5 起点）

---

## 11. 一句话收束

**P1-4 不是"补 50 条数据"，是"建立证据方法论的可复制样本"。** 15-30 天人力取证，产出 50 条实体的坐标化证据，为 P1-5（共装扩展）提供真实正例、为 P2-1（Evidence Graph）提供初始节点、为 P3（供应商验证网络）预留 `verified_by_vendor` 字段。**AI 只做规划/整理/一致性检查，不做读 PDF/字段判断/代签 evidence**——这个边界是项目"三态诚实"承诺的边界，不能破。**这份文档是评审材料，不是开工令。**
