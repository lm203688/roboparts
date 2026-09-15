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

## 与 SwarmLabs 飞轮的衔接

SwarmLabs 已有 47.5k 结构化科研实体 + Tech Radar（signal→candidate→promote→effect）。
本域的「研究空白 G1~G7」可直接作为 SwarmLabs 的一个**垂直实体桶**复用同一飞轮：
连接组 / 神经形态芯片 / 神经机器人实验室 / 跨域研究空白，跑一遍 gap 分析即可看见
这片图谱里**具体**哪里是空位。RoboParts 侧产出情报，SwarmLabs 侧跑趋势/空白发现，
两处共用同一份 `source.json` 事实基线（避免双源漂移）。

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
