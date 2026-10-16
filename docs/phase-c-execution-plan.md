# Phase C 执行计划 — L5 标准位（6-12 个月）

> **性质**：Phase C 的详细执行计划，按优先级排序，区分 AI 可自主完成 vs 需用户配合。
> 
> **入口画像**（2026-10-16）：
> - composed=0（三轴 AND 收敛为 0 对）
> - 电气轴可判定对 8 对（瓶颈轴）
> - 370 个节点缺 ['mechanical', 'electrical'] 双轴
> - fitness 排序：电气取证同质集 #1（net_gain=1.46）

---

## 优先级排序

| # | 动作 | 类型 | 依赖 | 预期收益 |
|---|---|---|---|---|
| C1 | 电气取证同质集（16 节点） | AI 框架已建，需用户填数据 | 厂商 datasheet / ISO 查表 | 解锁 15 对，net_gain=1.46 |
| C2 | ISO 22166 标准共建准备 | 需外部配合 | ISO 委员会联系 | 标准位卡位 |
| C3 | 论文 Mechatronics 跟进 | 需用户配合 | 补邮箱+单位 | 学术影响力 |
| C4 | 生态扩展（AgenticROS / Feather） | 需用户配合 | 外部联系 | 生态位 |
| C5 | 电气类型系统扩容（H2） | AI 可自主 | C1 前置 | 类型系统完整度 |
| C6 | 三层契约级联（H4） | AI 可自主 | C1 数据 | 完整链数 0→N |

---

## C1: 电气取证同质集（16 节点）

### 目标节点（已建骨架）
- Actuators: ACT-004~ACT-011（8 个）
- Sensors: SEN-001~SEN-004（4 个）
- Grippers: GRP-001~GRP-004（4 个）

### 取证字段（9 个）
1. `connector_family`（必填）：M8, M12, JST-XH
2. `connector_pins`（必填）：3, 4, 5, 8
3. `pinout`（可选）：["VCC", "GND", "SIG+"]
4. `voltage_range`（必填）：12V DC, 24V DC
5. `current_max`（可选）：5.0
6. `interface_protocol`（必填）：CANopen, Modbus, RS485
7. `source_url`（必填）：https://...
8. `source_tier`（必填）：A, B, C
9. `source_date`（必填）：2026-10-16

### 执行步骤
1. ✅ 框架已建：`scripts/electrical_cohort.py`
2. ✅ 骨架已生成：`evidence/electrical_cohort/electrical_cohort.json`
3. ⏳ 用户填入 16 节点电气参数（需厂商 datasheet / ISO 查表）
4. ⏳ 运行 `python scripts/electrical_cohort.py --validate` 校验
5. ⏳ 批量推送到 entities.json（不零散补数）

### 设计纪律
- **批量推进**：16 节点一起提交，不零散补数（T2 定理：单声明零收益）
- **溯源必填**：每条证据必须带 source_url + source_tier + source_date
- **不读图**：模型不能读图，用户贴图须声明无法读

---

## C2: ISO 22166 标准共建准备

### 当前状态
- ✅ ISO 22166-201/-202 条款级映射表已建（20 条，10/20 PASS）
- ⏳ 10 条 FAIL 是因为 10 个 ISO 字段确实未建（Phase B 取证路径）

### 下一步
1. 补 10 个 ISO 字段（与 C1 电气取证同步推进）
2. 准备 ISO 标准共建提案（需用户联系 ISO 委员会）
3. 映射层：RoboParts schema ↔ ISO 22166 条款

### 纪律
- 无原文 ⇒ 只做方向性映射，显式声明不构成符合性
- ISO 映射必须分 Phase 推进，Phase A 只建骨架，Phase B 补字段

---

## C3: 论文 Mechatronics 跟进

### 当前状态
- ✅ 已提交 Mechatronics（2026-10-15 21:05）
- Manuscript ID: `b3827f4c-4443-4dff-ba5f-65741ac70a78`
- 标题: Three-State Honesty in Robotic Hardware Compatibility: A Vendor-Neutral Determination Layer

### 下一步
1. ⏳ 补邮箱 + 单位（用户配合）
2. ⏳ 等待回执（通常 2-4 周）
3. ⏳ 根据审稿意见修改

### 纪律
- 数字现算 / 不夸大（composed=0 是诚实画像）
- 可用 contribution：T1（AND 收敛下界）+ T2（单声明零收益定理）+ MVC 判据

---

## C4: 生态扩展

### 目标客户
- Feather Robotics（feather.dev，$29,990 轮式双臂人形，Python+ROS2 Open SDK）
- AgenticROS（agenticros.com，RealSense 赞助）

### 下一步
1. ⏳ 联系 Feather Robotics（用户配合）
2. ⏳ 安装 AgenticROS skill：`npx agenticros skills install lm203688/roboparts`
3. ⏳ 生态接入点验证

### 纪律
- 分发≠增长（29 调用 0 注册⇒别再加平台）
- 哲学背书 Isaac ROS 5.0 rosidl::buffer ⇒ RoboParts=零件兼容性层的 rosidl::buffer

---

## C5: 电气类型系统扩容（H2）

### 当前状态
- 连接器类型键=(family,pins,pinout) 三元组
- family 不可省（M8 是家族非类型；同针数针序可因螺纹不同不可插）

### 下一步
1. ✅ C1 前置（电气取证同质集）
2. ⏳ 扩容类型系统（更多 family/pins/pinout 组合）
3. ⏳ 类型兼容矩阵（哪些组合可插）

### 纪律
- 取证链路缺一步白干：补证据须登记 type_compat
- 形态图须读它；接线键用 rp_id 非本地 id
- rp_id 须唯一（schema_contract 唯一性校验防撞号污染）

---

## C6: 三层契约级联（H4）

### 当前状态
- 完整链数=0
- 需要三层契约级联（接口契约 → 装配契约 → 系统契约）

### 下一步
1. ⏳ C1 数据（电气取证）
2. ⏳ 三层契约级联设计
3. ⏳ 完整链数 0→N

### 纪律
- 完整链数=0 是诚实画像，不是 bug
- 契约级联需要真实的装配案例验证

---

## 统计

| 指标 | 值 |
|---|---|
| 总动作 | 6 |
| AI 可自主 | 2（C5, C6） |
| 需用户配合 | 4（C1, C2, C3, C4） |
| 框架已建 | 1（C1） |
| 待填数据 | 16 节点电气参数 |

---

_生成时间：2026-10-16 · 关联：RoboParts-下一阶段全面提升方案-20261011.md §7_
