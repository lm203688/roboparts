# RoboParts 多模态训练数据集 · 模态扩展蓝图（v2）

> 参考对象：TurboVLA（华中科技大学 + 华为，arXiv:2607.27205，GitHub Apache-2.0）
> 配套数据集：`api/training_dataset.json`（schema_version 2.0）
> 采集路线：`docs/tactile-force-collection-roadmap.md`

---

## 1. 为什么参考 TurboVLA

TurboVLA 的关键不是"又一个大模型"，而是一次**架构判断**：

- 传统 VLA 走 `V → L → A`（视觉先过 LLM，再解码动作），延迟高（π0.5 在 RTX 4090 上 93.6ms）、显存大（12.8GB）。
- TurboVLA 改成 `V + L → A`：**DINOv3 视觉编码器 + BERT 语言编码器独立编码，经 6 层双向交叉注意力融合，再进轻量动作块解码器**。
  - 0.2B 参数、31.2ms、0.9GB、RTX 4090 上 **32Hz**；LIBERO 97.7%、RoboTwin 2.0 60.2%、真机 4 任务 80–92.5%。
- **核心可扩展点**：融合模块本身就是"多模态流的双向交叉注意力"。加触觉/力觉编码器流是天然扩展，不需改骨架。

TurboVLA 已接受的模态：多相机 RGB、**语言指令**、**机器人本体感觉（关节角/夹爪，独立 MLP 直送解码器）**。它没有触觉/力觉流——这正是 RoboParts 能补的位。

---

## 2. RoboParts 在多模态训练里的定位（诚实）

RoboParts **不提供原始传感流**。它提供的是**零件级物理先验真值层**：

| 模态 | RoboParts 是否提供原始流 | 提供什么 |
|---|---|---|
| vision | ❌ 不提供 | 仅当零件本身是视觉/位姿系统（`data_modalities` 含视觉类）时标记 `exposed` |
| geometric | ✅ 提供 | 机械接口几何 + 孔位级互换真值（ISO 9409-1 等），`components[].modality_details.geometric` |
| electrical | ✅ 提供 | 电压区间 + 通信协议互通判定，`modality_details.electrical` |
| force | ⚠️ 仅声明级 | `torque`/`weight`/`bionic_features` 解析出的力/负载参数，`modality_details.force`（原始六维 F-T 时序为零） |
| tactile | ⚠️ 仅声明级 | 软体柔顺性/表面材质/抓握力等类别级描述，`modality_details.tactile`（原始触觉传感为零） |

**价值主张**：把 RoboParts 的 `force`/`tactile` 作为"零件级物理先验 token"，在双向融合里与视觉特征交互，让力觉策略在装配/插拔任务里**提前知道该关注哪个受力维度**——而不是从零学。

---

## 3. 如何把 force / tactile 接入双向跨注意力

以 TurboVLA 的 `V+L→A` 为骨架，扩展为 `V + L + F + T → A`（F=force，T=tactile）：

```
相机 RGB ──┐
           ├─[双向交叉注意力 ×N]──┐
语言 BERT ─┤                      ├─[动作块解码器(ACT风格)]──> 连续动作
本体感觉  ─┤                      │
force先验 ─┘   (RoboParts modality_details.force)   │
tactile先验─┐ (RoboParts modality_details.tactile)  │
            └───────────────────────────────────────┘
```

### 输入流定义（训练平台侧）
- **vision stream**：自备 RGB(-D) 相机（`RoboParts 不提供`，消费方负责）。
- **language stream**：BERT 编码任务指令（同 TurboVLA）。
- **proprioception stream**：关节角/夹爪（同 TurboVLA，独立 MLP 直送解码器）。
- **force stream**：从 `components[].modality_details.force` 投影——
  - `torque_nm`、`weight_kg` 作为连续标量；`force_control_precision_nm`（如有）作为力控精度先验。
  - 若该零件无声明，force token = 学习到的"未知"嵌入（**不许填 0 假装无重力**，否则误导策略）。
- **tactile stream**：从 `modality_details.tactile.basis` 投影——
  - 类别级 one-hot（flexible_actuators / bionic / material_note / data_modalities:tactile）。
  - 原始触觉传感缺失时，tactile token 标记为"无观测"，由视觉+力觉补偿（诚实降级）。

### force_profile 驱动力觉策略的受力维度
`compatibility_edges[].force_profile.force_senses` 直接告诉策略该边对应什么力学约束：
- `flange_mount` → `['axial_load','bolt_torque']`（螺栓法兰，关注轴向载荷与拧紧扭矩）
- `connector_insert` → `['insertion_force','electrical_contact']`（接插件，关注插拔力与接触力）
- `rigid_join` → 两者并集
- `bus_coupling` → 空（信号级，无显著力学约束）

训练时可用 `force_profile.guidance` 作为**课程/正则信号**：例如 flange_mount 任务在 loss 里加轴向力权重，让策略一开始就学"拧螺丝要控扭矩"。

---

## 4. 字段契约（RoboParts → 训练平台）

| 训练平台需要 | 来自 | 字段路径 |
|---|---|---|
| 零件暴露哪些模态 | `components[].modalities` | `['geometric','electrical','force','tactile','vision']` |
| 力参数（真实） | `components[].modality_details.force` | `{torque_nm, weight_kg, force_control_precision_nm, basis}` |
| 触觉描述（类别级） | `components[].modality_details.tactile` | `{declared, basis, note}` |
| 几何身份 | `modality_details.geometric.identity` | `[ISO 9409-1-50-4-M6, ...]` |
| 边物理交互类型 | `compatibility_edges[].interaction_type` | `flange_mount / connector_insert / rigid_join / bus_coupling` |
| 边力觉剖面 | `compatibility_edges[].force_profile` | `{force_senses, guidance}` |
| 兼容性真值 | `compatibility_edges[].overall_compatible` | `true/false/null` |

---

## 5. 诚实边界（务必遵守）

1. **原始触觉/力觉传感时序本平台为零**。force/tactile 流进的是"声明级/类别级"先验，不是传感器样本。模型若当原始传感用会过拟合到厂商文案。
2. **未声明即"未知嵌入"，不填 0**。把"厂商没给扭矩"填成 torque_nm=0，等于骗策略"这个零件没有重力"，是假绿。
3. 兼容性 `overall_compatible=null` 表示"无法判定"，不是"不兼容"。训练时按无标签处理，不要当负样本。
4. 覆盖率见 `meta.totals.modality_coverage`：当前 geometric=36、electrical=37、force=77、tactile=46、vision=37（共 509 零件）。**几何/力覆盖偏低是真实数据缺口**，补法见采集路线文档。

---

## 6. 下一步

- 训练平台侧：实现 §3 的 `V+L+F+T→A` 投影脚本（可直接消费本 JSON）。
- 数据侧：按 `docs/tactile-force-collection-roadmap.md` 补齐原始 F/T 时序与触觉样本，把 force/tactile 从"声明级"升级为"传感级"。
- 几何侧：飞轮补 `mechanical_interface.standard/flange` 身份键，提升 geometric 覆盖（当前仅 36，瓶颈在机械接口未公开）。
