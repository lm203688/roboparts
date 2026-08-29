# 触觉 / 力觉原始数据采集路线

> 配套：`api/training_dataset.json`（v2）+ `docs/modality-extension-blueprint.md`
> 现状快照：2026-08-12，实体 708 / 组件 509

---

## 0. 先说清楚：现在有什么、没有什么

本平台当前是**结构化兼容性真值层**，不是传感数据库。多模态 v2 扩展里的 `force`/`tactile` 模态**只承载声明级/类别级参数**，原始传感时序为零。

### 已有的真实信号（可直接用，已进数据集）
| 来源 | 覆盖 | 含义 |
|---|---|---|
| `torque` 字段 | 63 个实体声明，27 个可解析为 Nm | 舵机/驱动器额定扭矩 |
| `weight` 字段 | 35 声明，23 可解析 | 负载/自重 |
| `bionic_features` | 33 个（软体/类肌肉） | "力控精度±0.5Nm""类肌肉柔顺性"等描述 |
| `data_modalities` | 42 个实体自带 | 含 `tactile`×8、`force_torque`×1、`haptic_feedback`×2、`grasp_force`×1、`touch`×1 |
| `material_note` | 2 个 | 表面材质（触觉相关） |
| `category=flexible_actuators` | 21 个 | 软体/触觉相关类别 |

### 缺失的原始传感（必须采集，不能编）
- ❌ 六维 F-T 传感器**原始时序日志**（装配/插拔过程中的 wrench 曲线）
- ❌ GelSight / 视触觉阵列的**原始触觉图像/压力分布**
- ❌ 抓取力闭环的**力-位同步轨迹**
- ❌ 原始 RGB(-D) 观测流（RoboParts 不提供，归训练平台）

---

## 1. 缺口根因（诚实）

`interaction_type` 分布实测：flange_mount 仅 **1** 条、connector_insert **435**、bus_coupling **6734**。
原因：机械身份键（`mechanical_interface.standard/flange`）**声明率仅 ~0.57%**，绝大多数实体的几何/力接口未公开。即——

> 力觉/触觉扩展的**第一瓶颈不是算法，是机械接口数据没采上来**。

补机械接口 → geometric/force 覆盖上去 → 力觉策略才有"装在哪、受多大力"的真值锚点。

---

## 2. 真实可落地的采集路线

### A. 厂商贡献原始标定（最直接）
- 针对 `sensors` 类 90 个实体（含力/力矩传感器，如宇立 C025XX/C075XX 六维力传感器）：
  邀请厂商上传**出厂标定原始日志**（Fx/Fy/Fz/Mx/My/Mz 采样序列）+ 典型装配/抓取 demo 的 wrench 曲线。
- 针对 `flexible_actuators` 21 个 + `bionic_features` 33 个：征集软体抓握的**接触力-形变**样本。
- 入库形式：保留为独立 `api/tactile_force_samples.json`（与结构化数据集分离，避免污染兼容性真值），v3 再关联 `component.id`。

### B. 公开/学术抓取库对接（参考，不内嵌）
RoboParts 做"零件级先验 + 兼容性真值"，原始抓取轨迹应从专业库取，本平台只**索引+标注接口约束**：
- 在 `compatibility_edges` 上挂 `recommended_datasets` 指针（如某 flange_mount 边推荐某 ISO 9409-1 装配抓取集），不搬运数据。
- 诚实标注：这些外部集的力觉标签质量需消费方自审，本平台不背书。

### C. 飞轮自动补机械接口（性价比最高）
- 飞轮每轮对 `mechanical_interface.status=not_declared` 的实体，按厂商手册抽取 `standard`/`flange`（ISO 9409-1 编码）。
- 每补一条身份键 → geometric 覆盖 +1、潜在 flange_mount 边 +N。这是当前覆盖翻倍的最短路径。
- 纪律：抽取须带 `source_url` 证据，无原始链接不写（沿用 L1 证据纪律）。

### D. 触觉/力觉合成仅作占位（明确边界）
- 不生成"假触觉"。若需冷启动，可用物理仿真（Isaac/MoziSim）按 `modality_details.force.torque_nm` 生成**接触力曲线**，但须打 `synthetic:true` 标签，与真实标定分开，且不得进 `evidence` 真值层。

---

## 3. 里程碑（建议，非强制）

| 阶段 | 动作 | 预期覆盖变化 |
|---|---|---|
| 短期（1–2 轮飞轮） | C：补机械身份键 + 提升 geometric | geometric 36 → 100+，flange_mount 边 1 → 数十 |
| 中期 | A：接入 3–5 家力/力矩传感器厂商原始标定 | 新增 `tactile_force_samples.json`，force 从声明级→传感级 |
| 长期 | B：外部抓取库索引 + 仿真合成（synthetic 标签） | tactile 从类别级→观测级 |

---

## 4. 验收口径（防假绿）

- `force`/`tactile` 模态一旦标 `declared:true`，必须能回溯 `basis`（torque/weight/bionic_features/data_modalities/material_note/category）之一；无 basis 不得标。
- 原始传感样本入库须带 `source_url` 或厂商授权凭证，否则进 `quarantine`。
- `meta.totals.modality_coverage` 每次导出如实刷新，覆盖率下降视为回归（数据被改坏），飞轮报警。
