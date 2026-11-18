# MotionDecode 数据集 · RoboParts 资产登记（2026-11-18）

> 登记人：RoboParts lead · 依据：Chief《MotionDecode-赋能档案-2026-11-18.md》（1.swarmlabs/intel/datasets/）——Chief 已于 11-18 完成全部实测并**最终绑定 WorldModel**。
> 本登记是 RoboParts 侧的**资产可用性记录**，不搬数据、不改代码、不提交。

## 一、数据概况

- 全名：ChingMu 1000-Hour Embodied Motion Dataset（CMRobot/MotionDecode，青瞳视觉）
- 仓库总量 78.89 GB；`samples/` 15,527 条剪辑 ≈ 24 GB（平均 1.67 MB/条，Chief 实测修正）；其余为 arrow/bin/h5/7z 等格式（554 条扩展名通配）
- 内容：**全部已 retarget 到 Unitree_G1**，每条 CSV 35 列 = root_pos(x/y/z) + root_rot(四元数) + 29 个 `dof_*_joint(rad)`，即 **G1 的关节级驱动轨迹（ground truth）**
- 类目：22 个一级类 / 110 个二级类，含 Action_Sequences(77)、Daily_Life(54)、Special_Occupation(49)、Emotional(48) 等

## 二、许可红线（非商业）

- LICENSE.md：允许 **academic research / personal study / non-commercial prototyping**；未经书面许可禁止商用分发、转售、作为竞品数据集托管；须署名、不得误述来源。
- → RoboParts 作为**开源项目**使用需注意：用户核心目标含 3D 打印商业化（平台下单→打印寄送→组装），若未来将 G1 动作资产打包进 RoboParts 公开资产/数据端点，可能触及"作为竞品托管/商用分发"红线——**使用前须经 Chief/用户确认许可边界**。

## 三、RoboParts 侧对接状态

- **当前无接入点**：`kinematics/source.json` 仅 2 条链（KC-OMY-ARM、KC-ODM-BIPED），均 `topology_only`（缺 joint_order/axis/link_mm/limits）；**无 G1 构型链**；README 无"动作资产"消费层。
- **价值定位**：次选（Chief 赋能档案 §六）。G1 动作库可接"机器人生态的动作资产层"，但需先补 G1 构型链 + 关节限位元数据（当前 `link_mm` 声明率 5.75%、机械声明率 16.2% 缺口大）。
- **归属**：首选/已绑定 **WorldModel**（22 类带真值标签的 G1 关节轨迹 = 世界模型缺的 oracle 验证材料）。RoboParts 不重复消费。

## 四、对接动作（本次）

1. 登记本资产为 RoboParts 可用外部数据（含许可红线、次选关系）。
2. 明确：**不搬数据到 robopart、不建消费管线**——避免偏离主线（组合校验）且撞非商业红线。
3. 触发条件（未来可用）：当 RoboParts 补入 G1 构型链 + 关节限位元数据、且 Chief/用户确认许可边界后，可将本数据接入"动作资产层"验证。

---
## 五、用户拍板确认（2026-11-18 16:05）

- 用户对"拍板的都同意"——确认本资产登记 + 许可红线成立。
- **接入纪律**：未来若将 G1 动作资产接入 RoboParts 公开端点，必须先确认非商业许可边界（academic/research/prototyping），且不得打包转售/作为竞品托管；接入条件 = 补入 G1 构型链 + 关节限位元数据 + 许可边界二次确认。
- 本次不搬数据、不建消费管线、不提交数据文件本体。

---
*登记完成。只读评估，未改代码、未提交；数据仍在 1.swarmlabs/intel/datasets/MotionDecode 原处。*
