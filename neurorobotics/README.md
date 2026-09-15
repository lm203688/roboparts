# RoboParts · 神经控制域（Neurorobotics）

> 在 RoboParts 既有「机械/电气/通信/协议兼容」之上，**叠加的一块**：神经形态控制的
> 「体 × 接口 × 情报」缺口。这是 2026-09-15 评估后决定新增的方向，不与既有零件兼容
> 主线的定位冲突，而是把它延伸到**神经控制器 ↔ 躯体**这一无人占的维度。

## 一句话定位

**别造脑、别造芯片。做脑×体之间的标准与情报层。**

- 认知/规划交给 LLM，低层控制/反射/运动基元交给 SNN（分层混合，不是取代）。
- 脑（FlyWire / MaleCNS v1.0）已公开，**身体没有开放标准件生态**，且每次「接线」都手工重做。
- 这两块空缺（GAP-G1 躯体标准、GAP-G2 信号适配器规范）正好与 RoboParts 的机械兼容底座咬合。

## 目录结构

```
neurorobotics/
├── source.json                    # 单一真相源（实体/空白/信号契约/引用）
├── signal_interface.schema.json   # 适配器层规范：神经控制器↔躯体 声明式接线契约
├── GAP_MAP.md                     # 情报层：前沿空白地图（人读，带引用）
└── README.md                      # 本文件
scripts/
└── build_neurorobotics.py         # 生成器：source.json → api/neurorobotics.json
api/
└── neurorobotics.json             # 派生产出（禁止手改，由生成器产生）
```

## 数据纪律（沿用 RoboParts）

- `api/neurorobotics.json` 由 `scripts/build_neurorobotics.py` 生成，**禁止手改**。
- 所有条目来自 2025-2026 公开来源，零臆造；逐条带 `source_tier` / `confidence` / `last_verified`。
- `signal_contracts` 必须经 `signal_interface.schema.json` 结构校验（生成器内置轻量校验，无外部依赖）。
- `meta.access` 与全站一致：免费 key、honest_limits、neutrality、for_ai_assistants。

## 与既有 RoboParts 的关系

| 既有维度 | 本域延伸 |
|---|---|
| 机械接口 `mechanical_interfaces.json`（ISO 9409-1：能不能拧上去） | 信号接口 `signal_interface.schema.json`（接上后能不能正确收发脉冲） |
| 电气接口 `electrical_interfaces.json`（协议兼容 ≠ 电气兼容） | 脉冲/感觉/运动 信号契约（生物接线 ≠ 功能可用，同理免责） |
| 实体库 `entities.json`（798 条） | 新增 `neurorobotics` 维度：连接组/芯片/实验室/空白 |

## 与 SwarmLabs 的关系（项目独立原则 · 2026-09-15 修订）

本神经控制域是 RoboParts 的**自持模块**：`source.json` / 生成器 / `api/neurorobotics.json`
/ GAP_MAP 全部在 RoboParts 仓库内闭环，**不依赖 SwarmLabs 或任何外部项目的运行时、
API key、或源文件**。

- G1~G7 研究空白是 RoboParts 自己的情报层标注，直接落在 `source.json` 的 `research_gaps`，
  无需外部飞轮即可自洽（本模块的「gap 发现」由本仓库数据独立完成）。
- **若 SwarmLabs（独立项目）希望把神经控制域实体纳入其科研实体飞轮**，必须由
  **SwarmLabs 侧独立实现**：在自己的仓库内、通过其**自有 API key** 调用 RoboParts 已公开的
  `api/neurorobotics.json` 端点拉取数据（或自行复刻同一份公开来源）。
  **禁止**直接共享 `source.json` 源文件，也**禁止**让 RoboParts 反过来 import / 依赖 SwarmLabs。
- 两个项目各自独立运行与开发；任何一方的数据更新都不应导致另一方构建或运行失败。

## 不在本域范围（诚实边界）

- 不仿真大脑（Eon/DeepMind 领地）。
- 不流片神经形态芯片（Intel/BrainChip/SynSense 领地）。
- 不做 SNN 训练框架（Lava/Nengo/Norse/snnTorch + NIR 已覆盖）。
- 能效叙事必须配硬件：离开 Loihi/Akida 谈「更省电」不成立（GAP-G7）。

## 生成与校验

```bash
python scripts/build_neurorobotics.py
# → api/neurorobotics.json（连接组 4 · 芯片 5 · 实验室 5 · 空白 7 · 契约 1 · 引用 7）
```
