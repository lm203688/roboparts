---
title: "为你的开源人形机器人选总线：CAN FD 与 EtherCAT 的实战选型博弈"
description: "30+ 自由度的开源人形机器人，总线选错会直接卡死控制频率和 BOM 成本。本文对比 CAN FD 与 EtherCAT 的实测周期、同步精度、布线与成本，并结合天工 TienKung、Unitree G1、LeRobot-Humanoid 给出可落地的决策树。"
keywords: ["CAN FD", "EtherCAT", "开源人形机器人", "机器人通信协议", "总线选型", "分布式时钟", "ROS2", "天工机器人", "Unitree G1"]
tags: ["open-source-robotics", "humanoid", "sourcing", "protocols", "bom"]
slug: "open-source-humanoid-canfd-vs-ethercat"
author: "RoboParts Research"
canonical: "https://roboparts.cc/content/article-05-canfd-vs-ethercat.md"
---

# 为你的开源人形机器人选总线：CAN FD 与 EtherCAT 的实战选型博弈

> 本文首发于 [RoboParts 开源机器人兼容性平台](https://roboparts.cc)。

当你设计一台 30+ 自由度的开源人形机器人——不管是复刻天工 TienKung，还是在 LeRobot-Humanoid 基础上加自由度——通信协议的选择会直接影响：

- 控制频率能否达到 1kHz
- 全身协调的同步精度
- 线束重量和布线复杂度
- 单台 BOM 成本（差异可达 $500-2000）

更麻烦的是：**总线是最难中途改的一层**。执行器选错还能换一个，总线选错意味着所有关节驱动板、线束、主控全部返工。

本文基于实际项目经验，对比 CAN FD 和 EtherCAT 在开源机器人场景中的真实表现。

---

## 一、协议核心参数

| 参数 | CAN FD | EtherCAT |
|---|---|---|
| 物理层 | 双绞线（差分） | 以太网（100BASE-TX） |
| 最大速率 | 8 Mbps（数据段） | 100 Mbps |
| 最小周期 | 250μs-1ms | 50-100μs |
| 拓扑 | 总线 | 菊花链 |
| 节点数 | 128 | 65535 |
| 电缆成本 | 低（$0.5/m） | 中（$1-2/m） |
| 节点成本 | 低（$5-15） | 高（$30-80） |
| 主站复杂度 | 低 | 高 |
| 热插拔 | 不支持 | 支持 |

---

## 二、控制周期实测

### 场景：30DoF 人形机器人，1kHz 控制频率

**CAN FD 方案**：
- 每帧 8-64 字节数据
- 30 个关节 × 2 方向（指令+反馈）= 60 帧
- 仲裁时间 + 传输时间 ≈ 800μs
- **结论：勉强达到 1kHz，余量极小**

**EtherCAT 方案**：
- 过程数据对象（PDO）集中传输
- 30 个关节数据打包为 1 个 EtherCAT 帧
- 传输时间 ≈ 50-80μs
- **结论：轻松 2-5kHz，大量余量**

### 同步精度

人形机器人双足行走要求左右腿严格同步：

- **CAN FD**：软件同步，抖动 ±100-500μs
- **EtherCAT**：分布式时钟（DC），抖动 < 1μs

对于 1kHz 控制，500μs 抖动意味着 **50% 的周期偏差**，可能导致左右腿相位不一致。

> **开源项目的现实约束**：EtherCAT 主站要跑实时性，Linux 侧通常需要 PREEMPT_RT 补丁内核 + SOEM/IgH 主站栈。这在 Jetson 上并非开箱即用——很多开源人形团队最后选 CAN FD，不是因为性能够用，而是因为把 RT 内核和 EtherCAT 主站在 Jetson 上跑稳的成本太高。**决策时把这部分工程量算进去。**

---

## 三、布线复杂度

### CAN FD 总线拓扑

```
主控 → 关节1 → 关节2 → ... → 关节30 → 终端电阻
         ↓      ↓            ↓
       支线   支线          支线
```

- 优点：布线简单，一根干线贯穿全身
- 缺点：支线长度受限（< 0.3m），故障排查困难

### EtherCAT 菊花链

```
主控 → 关节1 → 关节2 → ... → 关节30
```

- 优点：每个节点自动转发，物理层简单
- 缺点：断链即全身瘫痪，需冗余设计

**实际建议**：
- 下半身（12-16DoF）用 EtherCAT：高负载、高同步要求
- 上半身（12-16DoF）用 CAN FD：轻负载、成本敏感
- 头/手（6-10DoF）用 RS-485 或 CAN：低速、简单

---

## 四、成本对比（30DoF 人形）

| 项目 | CAN FD | EtherCAT | 混合方案 |
|---|---|---|---|
| 主站控制器 | $50（STM32+TCAN） | $200（x86+EtherCAT主站） | $150 |
| 从站节点（×30） | $300（$10×30） | $1500（$50×30） | $900 |
| 线缆 | $50 | $100 | $80 |
| 开发时间 | 2周 | 6周 | 4周 |
| **总计** | **$400** | **$1800** | **$1130** |

**混合方案**（下半身 EtherCAT + 上半身 CAN FD）在性能和成本间取得平衡，是多数团队的选择。

---

## 五、主流开源平台走的是哪条路

在自己拍板之前，先看看你要参考或对接的平台用的是什么：

| 平台 | 总线方案 | 对你的影响 |
|---|---|---|
| 天工 TienKung | 下肢以 EtherCAT 为主，追求高频同步 | 复刻需准备 RT 内核 + 主站栈 |
| Unitree Go2 / G1 | 私有 CAN 协议，SDK 封装 | 二次开发省事，但混入第三方模组需协议转换 |
| Trossen OpenArm | 串行总线 / CAN，模块化 | 上肢够用，不必上 EtherCAT |
| LeRobot-Humanoid | 低成本 CAN / 串口 | 优先保证 ROS2 驱动可用性 |
| roboto_origin | CAN 为主，成本优先 | 入门友好，扩展自由度时注意带宽上限 |

**最容易踩的坑是"混用"**：把 Unitree 的关节模组和标准 CANopen 驱动器挂在同一条总线上，帧 ID 分配和对象字典都对不上，必须写转换层。想避免这种情况，先在[开源组件兼容性数据层](https://roboparts.cc/oss.html)确认目标项目的协议栈，再决定要不要引入异构模组。

---

## 六、协议兼容性数据

RoboParts 数据集收录了 **{{RP:CAT:protocols}} 款通信协议**和 **{{RP:CAT:chips}} 款芯片**的兼容性矩阵：

```python
# 查找支持 EtherCAT 的电机驱动芯片
ethercat_chips = [
    c for c in db["chips"]
    if "EtherCAT" in str(c.get("specs", {}).get("接口", ""))
]

# 查找支持 CAN FD 的执行器
canfd_actuators = [
    a for a in db["actuators"]
    if "CAN FD" in str(a.get("specs", {}).get("通信协议", ""))
]
```

在线交叉引用：用 [BOM 兼容性检查](https://roboparts.cc/bom-checker.html) 把你的执行器清单 + 主控型号一起提交，可以直接查出"某几个关节模组不支持你选的总线"这类冲突；需要在自研工具或 CI 里做同样校验，走[兼容性数据 API](https://roboparts.cc/data-hub.html)。

---

## 七、选型决策树

```
全身 DoF < 12？
  └─ 是 → CAN FD 足够
  └─ 否 → 控制频率 > 500Hz？
           ├─ 是 → 能否投入 RT 内核 + EtherCAT 主站工程量？
           │        ├─ 能 → EtherCAT
           │        └─ 不能 → 混合方案（下肢 EtherCAT 模组 + 上肢 CAN FD）
           └─ 否 → 预算 < $1000？
                    ├─ 是 → CAN FD
                    └─ 否 → 混合方案
```

---

## 八、数据集

完整协议参数、芯片兼容性、线缆规格已结构化收录：

- 协议库：{{RP:CAT:protocols}} 个条目，含速率、延迟、拓扑、标准
- 芯片库：{{RP:CAT:chips}} 个条目，按接口类型分类
- 兼容性矩阵：电气/机械/协议/软件 4 维度

定好协议后，用[选型引擎](https://roboparts.cc/selection.html)筛符合该总线的执行器与驱动芯片，再用[供应商寻源](https://roboparts.cc/suppliers.html)确认交期——EtherCAT 从站芯片近年交期波动较大，早确认早安心。

GitHub：https://github.com/roboparts/roboparts-dataset
API：https://roboparts.cc/api/data.json

---

**RoboParts · 开源机器人构建者资源**

- 🔧 免费 BOM 兼容性检查：https://roboparts.cc/bom-checker.html
- 📦 开源组件兼容性数据层：https://roboparts.cc/oss.html
- 🔌 兼容性数据 API（Pro）：https://roboparts.cc/data-hub.html
- 🛒 供应商寻源：https://roboparts.cc/suppliers.html

正在构建或维修开源机器人？用 RoboParts 把零件兼容性一次性查清。

---
