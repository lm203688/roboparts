---
title: "为你的开源人形机器人选膝关节执行器：扭矩、惯量比与协议匹配"
description: "从天工 TienKung、Unitree G1 到 LeRobot-Humanoid，开源人形项目最容易踩坑的就是膝关节执行器。本文基于 RoboParts 收录的 {{RP:CAT:actuators}} 款执行器实测参数，给出可直接套用的选型与兼容性校验方法。"
keywords: ["开源人形机器人", "膝关节执行器", "执行器选型", "惯量比", "谐波减速器", "SEA", "CAN FD", "天工机器人", "Unitree G1", "LeRobot"]
tags: ["open-source-robotics", "humanoid", "sourcing", "actuators", "bom"]
slug: "open-source-humanoid-knee-actuator-selection"
author: "RoboParts Research"
canonical: "https://roboparts.cc/content/article-01-knee-actuator-selection.md"
---

# 为你的开源人形机器人选膝关节执行器：扭矩、惯量比与协议匹配

> 本文首发于 [RoboParts 开源机器人兼容性平台](https://roboparts.cc)，数据集与在线选型工具均已开源。

如果你正在复刻 **天工 TienKung**、基于 **Unitree G1** 做二次开发，或者从零搭一台 **LeRobot-Humanoid**，膝关节几乎一定是你第一个卡住的地方。

原因很简单：膝关节是全身负载最高的关节之一。一个 70kg 级人形机器人在下蹲或上楼梯时，膝关节瞬时峰值扭矩可达 **100-150Nm**。选错执行器，轻则控制带宽不足导致抖动，重则减速器过载报废——而开源项目的 BOM 往往只给了一个型号名，没有告诉你换成手边能买到的替代品之后，扭矩、惯量比、协议还对不对得上。

本文基于 RoboParts 数据集收录的 **{{RP:CAT:actuators}} 款执行器**实测参数，给出膝关节选型的系统化方法论。如果你只想快速验证手上这份 BOM 能不能装，可以直接用免费的 [BOM 兼容性检查](https://roboparts.cc/bom-checker.html)。

---

## 一、膝关节的核心技术指标

### 1.1 扭矩需求计算

膝关节的峰值扭矩由两部分组成：

- **重力矩**：$\tau_g = m \cdot g \cdot l_{com} \cdot \sin(\theta)$
- **惯性矩**：$\tau_i = I \cdot \alpha$

对于 70kg 级人形机器人（大腿+小腿质量约 12kg，质心距膝关节约 0.3m）：

| 动作 | 膝关节角度 | 估算峰值扭矩 |
|---|---|---|
| 站立支撑 | 5° | 40-50 Nm |
| 深蹲 | 90° | 100-120 Nm |
| 上楼梯（单腿支撑） | 45° | 120-150 Nm |
| 落地缓冲 | 30° | 150-200 Nm |

**结论**：膝关节执行器的 **持续扭矩应 ≥ 60Nm，峰值扭矩应 ≥ 150Nm**，并保留 1.5-2 倍安全余量。

> **对开源项目的提醒**：天工 TienKung 这类全尺寸开源人形整机质量偏大，膝关节余量要按上限取；而 LeRobot-Humanoid、roboto_origin 这类桌面/半尺寸平台整机质量常在 20kg 以内，按 70kg 级参数选型会严重过配，白白增加成本和转动惯量。先确认你的整机质量段，再套下面的公式。

### 1.2 转速与带宽

人形机器人行走步频约 1-2Hz，膝关节角速度峰值约 **150-200°/s**（2.6-3.5 rad/s）。

执行器输出转速需满足：
$$\omega_{motor} \cdot N_{gear} \geq 200°/s$$

其中 $N_{gear}$ 为减速比。谐波减速典型减速比 50:1-160:1，对应电机转速需达到 10,000-32,000 rpm。这基本排除了普通直流无刷电机，**必须选用高转速无框力矩电机或专用关节模组**。

### 1.3 惯量比

惯量比（Load Inertia Ratio）是膝关节选型的隐形杀手：

$$J_{ratio} = \frac{J_{load}}{J_{motor} \cdot N_{gear}^2}$$

- **$J_{ratio} < 3$**：优秀，伺服响应快
- **$J_{ratio} = 3-10$**：可接受，需调 PID
- **$J_{ratio} > 10$**：控制困难，易振荡

膝关节负载惯量主要来自小腿和足部，约 **0.05-0.1 kg·m²**。若选用减速比 100:1、电机转子惯量 $10^{-5}$ kg·m² 的执行器：

$$J_{ratio} = \frac{0.08}{10^{-5} \cdot 100^2} = 0.8$$

非常优秀。但若减速比仅 30:1：

$$J_{ratio} = \frac{0.08}{10^{-5} \cdot 30^2} = 8.9$$

已接近临界值。

> **这是开源复刻最常见的翻车点**：社区里大量"平替方案"只对齐了峰值扭矩，却把减速比从 100:1 换成了 36:1 或 30:1。扭矩数字看着达标，惯量比却翻了 10 倍，结果就是上电后膝关节抖到无法站立。**换型号时，扭矩和减速比必须同时校验。**

---

## 二、执行器类型对比

膝关节可选的执行器类型主要有三种：

| 类型 | 代表产品 | 峰值扭矩 | 重量 | 优势 | 劣势 |
|---|---|---|---|---|---|
| 谐波+力矩电机 | Harmonic Drive FHA | 150-300Nm | 1.5-2.5kg | 零背隙、高精度 | 柔轮疲劳寿命有限 |
| 行星+无刷电机 | Maxon EPOS | 80-150Nm | 1.0-1.8kg | 成本低、耐用 | 背隙 3-5arcmin |
| SEA 串联弹性 | ANYbotics | 100-200Nm | 1.2-2.0kg | 力控优秀、缓冲好 | 结构复杂、带宽受限 |

### 2.1 谐波减速方案

适合追求精度和紧凑性的场景。以 RoboParts 数据集中 Harmonic Drive FHA-32C 为例：

- 额定扭矩：109 Nm
- 峰值扭矩：310 Nm
- 减速比：100:1
- 重量：2.1 kg
- 背隙：≤ 1 arcmin

**适用**：高精度双足行走、舞蹈动作。天工 TienKung 一类强调全尺寸稳定行走的开源整机，下肢多走这条路线。

### 2.2 SEA 方案

串联弹性执行器（Series Elastic Actuator）在膝关节有独特优势：

- **力控带宽**：弹性体将力测量转化为位移测量，分辨率提升 10 倍
- **能量存储**：落地时弹性体储能，蹬地时释放，能效提升 15-30%
- **抗冲击**：弹性体吸收冲击，保护减速器

RoboParts 数据集中收录的 SEA 产品包括 ANYbotics ANYdrive、MIT Cheetah 同款执行器，以及 OpenTorque 等社区开源 SEA 设计——后者对预算有限的开源构建者尤其友好。

### 2.3 从已有开源平台"借"选型

如果你不想从零推导，最快的路径是参照成熟开源平台的关节配置再做等效替换：

| 参考平台 | 类型 | 下肢/关节方案特征 | 适合谁 |
|---|---|---|---|
| 天工 TienKung | 全尺寸开源人形 | 高扭矩谐波+力矩电机，EtherCAT 为主 | 做全尺寸双足行走 |
| Unitree G1 / Go2 | 商用平台、API 开放 | 高集成关节模组，CAN 总线 | 二次开发、快速验证 |
| LeRobot-Humanoid | 社区开源人形 | 低成本模组，CAN/串口 | 教学、算法研究 |
| Trossen OpenArm | 开源机械臂 | 中小扭矩模组，模块化 | 上肢/操作任务 |
| roboto_origin | 开源整机 | 轻量化关节，成本优先 | 入门构建 |

**注意**：直接照抄型号往往买不到或超预算，真正需要做的是"等效替换"——保证扭矩、减速比、法兰接口、通信协议四项同时对齐。RoboParts 的[开源组件兼容性数据层](https://roboparts.cc/oss.html)就是为这件事建的：按开源项目查它的组件清单，再查每个组件的可替代型号。

---

## 三、通信协议选择

膝关节执行器的通信协议直接影响控制延迟和系统复杂度：

| 协议 | 带宽 | 延迟 | 拓扑 | 适用场景 |
|---|---|---|---|---|
| CAN FD | 2-8 Mbps | 0.1-1ms | 总线 | 中小规模，成本敏感 |
| EtherCAT | 100 Mbps | 50-100μs | 菊花链 | 高精度，大规模 |
| RS-485 | 1-10 Mbps | 1-5ms | 总线 | 低速关节，legacy 系统 |

**建议**：

- 若全身 ≤ 20 个自由度，CAN FD 足够，线缆简洁
- 若追求 1kHz 以上控制频率或 > 30DoF，选 EtherCAT
- 混合方案：上半身 CAN FD，下半身 EtherCAT（膝关节需要高带宽）

**开源构建者的额外约束**：你选的执行器必须有可用的 ROS2 驱动或开放的 SDK，否则再好的硬件参数也用不上。Unitree Go2/G1 的优势之一就是 SDK 成熟；而一些工业模组虽然参数漂亮，社区驱动却是空白。选型时把"是否有开源驱动"当成硬指标。

---

## 四、在线选型实操

以上参数对比如果手动查手册，至少需要 **2-3 天**。我们把这些数据结构化后，做成了在线选型引擎：

访问 [选型引擎](https://roboparts.cc/selection.html)，输入：

1. 关节位置：膝关节
2. 扭矩要求：120Nm
3. 预算范围：$500-2000
4. 协议偏好：CAN FD
5. 勾选：仿生优先、国标合规

系统会在 **{{RP:CAT:actuators}} 款执行器**中自动筛选，并按多因子评分排序：

- 扭矩/价格比（30%）
- 轻量化（20%）
- 协议匹配（25%）
- 仿生特性（15%）
- 标准合规（10%）

**推荐工作流（针对开源项目）**：

1. 用 [BOM 兼容性检查](https://roboparts.cc/bom-checker.html) 把现有 BOM 跑一遍，先找出机械/电气/协议不匹配项
2. 对报错的执行器，用[选型引擎](https://roboparts.cc/selection.html)找等效替代
3. 通过[供应商寻源](https://roboparts.cc/suppliers.html)确认替代型号的可购性与交期
4. 需要把兼容性校验接进 CI 或自研工具链，用[兼容性数据 API](https://roboparts.cc/data-hub.html)

---

## 五、数据集开源

本文引用的全部参数来自 **RoboParts 结构化数据集**，已开源：

- GitHub：https://github.com/roboparts/roboparts-dataset
- HuggingFace：https://huggingface.co/datasets/roboparts/roboparts-dataset
- API（实时更新）：https://roboparts.cc/api/data.json

数据集覆盖 {{RP:TOTAL}} 个实体、{{RP:CATEGORIES}} 大品类，CC BY 4.0 许可，欢迎引用。

---

## 引用

```bibtex
@dataset{roboparts2026,
  title={RoboParts: A Structured Dataset for Bionic Robot Components},
  author={RoboParts Team},
  year={2026},
  url={https://roboparts.cc}
}
```

---

**RoboParts · 开源机器人构建者资源**

- 🔧 免费 BOM 兼容性检查：https://roboparts.cc/bom-checker.html
- 📦 开源组件兼容性数据层：https://roboparts.cc/oss.html
- 🔌 兼容性数据 API（Pro）：https://roboparts.cc/data-hub.html
- 🛒 供应商寻源：https://roboparts.cc/suppliers.html

正在构建或维修开源机器人？用 RoboParts 把零件兼容性一次性查清。

---
