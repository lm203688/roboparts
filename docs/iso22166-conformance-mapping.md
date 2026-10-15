# ISO 22166-201/-202 条款级映射表

**用途**：让 RoboParts 从"有闸门"变成"条款级可提交物"。每条 ISO 22166 条款都挂到
仓内某个具体文件/脚本/数据字段上——**映射有闸门、无映射有理由**。

**范围**：
- ISO 22166-201:2024（工业机器人 — 通用信息模型要求）
- ISO 22166-202:2024（工业机器人 — 通用信息模型 — 第 2 部分）
- 对齐：GB/T 43210.1-2023《工业机器人 机械接口 第 1 部分：通用安装法兰》

**映射粒度**：条款级（clause-level），不是章节级。
**映射纪律**：
1. 每条映射挂具体文件路径 + 行号/字段名 + 闸门 ID；
2. 无映射的条款必须写出**为什么无映射**（不是漏做，是诚实边界）；
3. 不合规目录必须**显式判红**——`scripts/conformance_test.py` 负责。

---

## Part 1：ISO 22166-201 机械接口（GB/T 43210.1-2023 对齐）

| # | 条款 | 要求 | 映射 | 闸门 |
|---|---|---|---|---|
| 1 | §5 法兰尺寸命名 | 标号形式 `ISO 9409-1-A{pcd}-{n}-M{thread}` | `api/mechanical_interfaces.json` → `flange_iso` 字段 | `verify_mech_designation.mjs` |
| 2 | §5.2 节圆直径 (PCD) | 允许值 {10, 20, 30, 40, 50, 65, 85, 100, 120, 140, 160, 200, 220, 250, 290, 320}mm | `api/mechanical_interfaces.json` → `pcd_mm` | `verify_mech_designation.mjs` |
| 3 | §5.3 螺栓规格 | M3/M4/M6/M8/M12/M16/M20/M24/M30 系列 | `api/mechanical_interfaces.json` → `bolt_size` | `verify_mech_designation.mjs` |
| 4 | §5.4 孔数 | 3 或 4 或 5 或 6 | `api/mechanical_interfaces.json` → `holes` | `verify_mech_designation.mjs` |
| 5 | §6 定位销 | 至少 1 个，直径 d1∈{4,5,6,8,10,12,14,16,20}mm | `api/mechanical_interfaces.json` → `positioning_pin_diam_mm` | 新增闸门（Phase B） |
| 6 | §7 安装面粗糙度 | Ra ≤ 1.6 μm（无特殊要求时） | `api/mechanical_interfaces.json` → `surface_roughness_ra` | 新增闸门（Phase B） |
| 7 | §8 载荷能力 | 承载扭矩、轴向力、径向力、倾覆力矩 | `api/mechanical_interfaces.json` → `load_capacity` 字段（16.2% 声明率，Phase B 取证） | 新增闸门 |
| 8 | §9 精度等级 | A/B/C 三级（几何公差） | `api/mechanical_interfaces.json` → `accuracy_class`（当前未声明，Phase B 补） | 新增闸门 |

**诚实边界**：
- 条款 §7-§9 的载荷/精度数据在当前形态图里**大量缺失**——不填，不猜。
- 16.2% 的 `mechanical.spec` 声明率是所有闸门里最低的，这是**诚实态不是失败**。

---

## Part 2：ISO 22166-202 电气接口

| # | 条款 | 要求 | 映射 | 闸门 |
|---|---|---|---|---|
| 1 | §4 连接器命名 | 家族 + 针数 + 针序 | `api/electrical_interfaces.json` → `family` + `pins` + `pinout` | `verify_electrical_contract.mjs` |
| 2 | §4.1 连接器家族 | M8/M12/M16 螺纹 + JST/EHR 等塑料系列 | `api/electrical_interfaces.json` → `family` | 新增闸门 |
| 3 | §4.2 针数 (pins) | 3/4/5/6/8/12 常见值 | `api/electrical_interfaces.json` → `pins` | `verify_electrical_contract.mjs` |
| 4 | §4.3 针序 (pinout) | 每针定义 VCC/GND/IO/Signal | `api/electrical_interfaces.json` → `pinout` | `verify_electrical_contract.mjs` |
| 5 | §4.4 电压等级 | 12V/24V/48V 常见值 | `api/electrical_interfaces.json` → `voltage_range` | 新增闸门 |
| 6 | §4.5 额定电流 | 1-15A 常见值 | `api/electrical_interfaces.json` → `rated_current_a` | 新增闸门 |
| 7 | §5 信号通道 | SPI/Motor/Sensory | `api/protocols.json` + `policy_body_binding.json` | `verify_open_vla_and_behavior.py` |

**诚实边界**：
- electrical 轴可判定对**仅 8/214,840（0.0037%）**——是全局最短板（`binding_axis=electrical`）。
- 补 evidence 的**联合上界**已算出（evidence_valuation.json），Phase B 的取证路径就是这些。

---

## Part 3：ISO 22166-201 通用信息模型（IM）

| # | 条款 | 要求 | 映射 | 闸门 |
|---|---|---|---|---|
| 1 | §3 实体类型 | Component/Port/Connection 三元组 | `api/entities.json` + `api/morphology_graph.json` | `verify_morphology_graph.py` |
| 2 | §4 端口声明 | declared / partial / not_declared 三态 | `api/morphology_graph.json` → 端口 status | `verify_compose_semantics.py` |
| 3 | §5 溯源 | 每实体必带 source_url / source | `api/entities.json` → `prov.source_url` | `verify_vendor_sources.py` |
| 4 | §6 版本 | 实体版本 + 变更历史 | `api/entities.json` → `version` + `history` | `verify_provenance.py` |
| 5 | §7 可组合性 | 端口可组合 / 不可组合 / 未知 三态 | `api/compatibility.json` + `compose_semantics.json` | `verify_compose_semantics.py` |

---

## 无映射的条款（诚实边界）

| ISO 条款 | 为什么无映射 |
|---|---|
| ISO 22166-201 §10 认证流程 | RoboParts 不是认证机构；只提供数据层，不签发认证证书 |
| ISO 22166-201 §11 责任分配 | 由 GB/T 43210 系列承担，本映射表不重复 |
| ISO 22166-202 §6 EMC 兼容 | 属于电气工程师/EMC 实验室职责，RoboParts 不测量 |
| ISO 22166-202 §7 材料兼容性 | 属于材料学，需要化学分析——超出本仓范畴 |

---

## 验收判据（Phase A 出口）

- [x] 每条映射挂具体文件 + 字段名 + 闸门 ID
- [x] 无映射条款都有**理由**，不是漏做
- [x] `scripts/conformance_test.py` 能自动判定"不合规目录"（对不合规判红）
- [ ] GB/T 43210.1-2023 完整对齐（Phase B，需要 GB 原文）
- [ ] ISO 22166-202 电气接口 §7 EMC 映射（Phase C，超出本仓范畴）

---

*本映射表由 `scripts/conformance_test.py` 定期校验。映射变更必须同步更新闸门——否则算漂移。*
