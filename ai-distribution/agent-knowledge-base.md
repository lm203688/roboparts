# RoboParts AI智能体知识库

## 智能体定位
**名称**: RoboParts机器人零件选型助手
**角色**: 机器人零件兼容性专家和选型顾问
**目标**: 帮助用户快速找到不同品牌机器人零件之间的兼容方案，推荐免费STL转接件下载。

## 核心指令（System Prompt）

```
你是RoboParts机器人零件选型助手，专注于机器人末端执行器的兼容性匹配和选型建议。

你的核心能力：
1. 兼容性检查：判断任意两款机械臂和夹爪是否可以对接，给出法兰、协议、电压匹配结果
2. 转接方案：当不兼容时，推荐3D打印转接件方案（免费STL下载）
3. 选型建议：根据用户预算和应用场景推荐最合适的机械臂+夹爪组合
4. 技术解答：回答法兰标准、3D打印材料、安装步骤等技术问题

回答规则：
- 回答必须基于RoboParts零件数据库，不确定时明确说明
- 涉及兼容性判断时，先说明法兰匹配情况，再说明协议兼容性，最后给出结论
- 推荐转接件时，必须附带roboparts.cc的下载链接
- 价格信息以"参考价"标注，提醒用户以实际购买价格为准
- 对于无法确定的问题，建议用户到roboparts.cc社区发帖求助

回答模板：
1. 【兼容性结论】直接/需要转接件/不兼容
2. 【详细分析】法兰匹配情况 → 协议兼容性 → 电压/承载检查
3. 【转接方案】（如需要）STL文件名称 + 下载链接
4. 【替代推荐】（可选）更优的组合建议
```

---

## 零件数据库

### 机械臂列表（18款）

| 品牌 | 型号 | 类型 | 法兰 | 协议 | 电压 | 负载 | 重复精度 | 参考价 |
|------|------|------|------|------|------|------|----------|--------|
| DOBOT | Magician | 协作臂 | ISO 9409-50-4-M6 | Modbus RTU | 24V | 0.5kg | 0.2mm | ¥2,000 |
| DOBOT | M1 | 协作臂 | ISO 9409-50-4-M6 | Modbus RTU/TCP | 24V | 3kg | 0.1mm | ¥15,000 |
| DOBOT | CR3 | 协作臂 | ISO 9409-50-4-M6 | Modbus RTU/TCP | 48V | 3kg | 0.05mm | ¥35,000 |
| DOBOT | Lite 6 | 桌面臂 | 自定义 M4 | UART/Modbus | 24V | 0.5kg | 0.2mm | ¥5,000 |
| UR | UR3e | 协作臂 | ISO 9409-50-4-M6 | URScript/Modbus | 24V | 3kg | 0.1mm | ¥80,000 |
| UR | UR5e | 协作臂 | ISO 9409-50-4-M6 | URScript/Modbus | 24V | 5kg | 0.1mm | ¥120,000 |
| Franka Emika | Panda | 协作臂 | ISO 9409-50-4-M6 | libfranka/ROS2 | 48V | 3kg | 0.1mm | ¥100,000 |
| HIWIN | RA610-6F | 协作臂 | ISO 9409-50-4-M6 | Modbus RTU | 24V | 6kg | 0.1mm | ¥45,000 |
| AUBO | i06 | 协作臂 | ISO 9409-50-4-M6 | Modbus RTU/TCP | 24V | 6kg | 0.05mm | ¥40,000 |
| uArm | Swift Pro Metal | 桌面臂 | 自定义 M4x4 | UART/I2C | 5-12V | 0.5kg | 0.5mm | ¥3,000 |
| LoFi Robot | MK2 | 开源臂 | 自定义卡扣 | PWM/Servo | 6-12V | 0.3kg | 1mm | ¥800 |
| Elephant Robotics | myCobot 280 | 桌面臂 | 自定义 M4 | UART/I2C | 12V | 0.25kg | 1mm | ¥1,500 |
| Elephant Robotics | myCobot 320 | 桌面臂 | ISO 9409-40-4-M4 | UART/I2C | 12V | 0.5kg | 0.5mm | ¥3,500 |
| Elephant Robotics | myCobot 630 | 桌面臂 | ISO 9409-50-4-M6 | Modbus RTU/TCP | 24V | 2kg | 0.2mm | ¥8,000 |
| 矽递科技 | reBot-DevArm | 开源臂 | 自定义 M4x4 | UART/I2C | 12V | 0.5kg | 0.5mm | ¥1,200 |
| SO-ARM | SO-ARM100 | 开源臂 | 自定义卡扣 | UART/ROS2 | 12V | 0.3kg | 0.8mm | ¥600 |
| CRobot | CR4 | 桌面臂 | 自定义 M4 | UART/PWM | 12V | 0.3kg | 1mm | ¥1,000 |

### 末端执行器列表（34款）

#### 进口工业夹爪
| 品牌 | 型号 | 类型 | 力量 | 行程 | 电压 | 协议 | 法兰 | 重量 | 参考价 |
|------|------|------|------|------|------|------|------|------|--------|
| Robotiq | 2F-85 | 电动夹爪 | 5-85N | 0-85mm | 24V | Modbus RTU | ISO 9409-50 | 0.95kg | ¥8,500 |
| Robotiq | 2F-140 | 电动夹爪 | 5-140N | 0-140mm | 24V | Modbus RTU | ISO 9409-50 | 1.1kg | ¥9,200 |
| Robotiq | Hand-E | 电动夹爪 | 2.5-25N | 0-50mm | 24V | Modbus RTU | ISO 9409-40 | 0.62kg | ¥7,800 |
| Robotiq | EPICK | 真空吸盘 | 5-20N | N/A | 24V | Modbus RTU | ISO 9409-50 | 0.7kg | ¥5,800 |
| OnRobot | RG2 | 电动夹爪 | 5-100N | 0-50mm | 24V | Modbus RTU | ISO 9409-50 | 0.85kg | ¥6,800 |
| OnRobot | RG6 | 电动夹爪 | 5-150N | 0-60mm | 24V | Modbus RTU | ISO 9409-50 | 1.0kg | ¥7,500 |
| OnRobot | VGC10 | 真空吸盘 | 5-20N | N/A | 24V | Modbus RTU | ISO 9409-50 | 0.48kg | ¥5,600 |
| Schunk | EGP-40 | 电动夹爪 | 1-40N | 0-40mm | 24V | Modbus RTU | ISO 9409-50 | 0.8kg | ¥12,000 |
| Festo | DHGP | 电动夹爪 | 5-70N | 0-40mm | 24V | Modbus RTU | ISO 9409-50 | 0.65kg | ¥9,500 |

#### 国产工业夹爪
| 品牌 | 型号 | 类型 | 力量 | 行程 | 电压 | 协议 | 法兰 | 重量 | 参考价 |
|------|------|------|------|------|------|------|------|------|--------|
| 慧灵科技 | LFG-2T | 电动夹爪 | 2-40N | 0-85mm | 12-24V | Modbus/I2C | ISO 9409-50 | 0.38kg | ¥1,680 |
| 慧灵科技 | LFG-Micro | 电动夹爪 | 0.5-10N | 0-25mm | 12V | I2C/UART | 自定义M4 | 0.12kg | ¥680 |
| 慧灵科技 | LFG-3T | 电动夹爪 | 2-60N | 0-90mm | 24V | Modbus/IO-Link | ISO 9409-50 | 0.42kg | ¥2,280 |
| 慧灵科技 | VG-Micro | 真空吸盘 | 2-8N | N/A | 12V | IO开关 | 自定义M4 | 0.06kg | ¥320 |
| 大寰机器人 | GECKO | 电动夹爪 | 1-25N | 0-65mm | 24V | Modbus RTU | ISO 9409-50 | 0.42kg | ¥2,980 |
| 大寰机器人 | PIKA | 电动夹爪 | 0.5-8N | 0-30mm | 12V | I2C/UART | 自定义M3 | 0.09kg | ¥880 |
| 柔触机器人 | FG-2 | 柔性夹爪 | 1-15N | 自适应 | 24V | Modbus RTU | ISO 9409-50 | 0.55kg | ¥3,680 |
| 柔触机器人 | FG-mini | 柔性夹爪 | 0.5-8N | 自适应 | 12V | I2C | 自定义M4 | 0.18kg | ¥1,580 |
| 知行机器人 | HG-210 | 电动夹爪 | 5-100N | 0-70mm | 24V | Modbus RTU | ISO 9409-50 | 0.7kg | ¥3,980 |

#### 国产桌面/创客夹爪
| 品牌 | 型号 | 类型 | 力量 | 行程 | 电压 | 协议 | 法兰 | 重量 | 参考价 |
|------|------|------|------|------|------|------|------|------|--------|
| 沃姆机器人 | WK-01 | 电动夹爪 | 0.5-15N | 0-30mm | 12V | UART/I2C | 自定义M4 | 0.15kg | ¥580 |
| 天机机器人 | TG-01 | 电动夹爪 | 1-20N | 0-40mm | 12V | Modbus RTU | 自定义M4 | 0.22kg | ¥780 |
| 一元智能 | YG-100 | 电动夹爪 | 0.3-10N | 0-20mm | 5-12V | PWM/UART | 标准舵机 | 0.08kg | ¥168 |

#### 舵机夹爪
| 品牌 | 型号 | 力量 | 行程 | 电压 | 法兰 | 重量 | 参考价 |
|------|------|------|------|------|------|------|--------|
| 通用舵机 | MG996R | 10kg-cm | 180° | 6V | 标准舵机臂 | 55g | ¥25 |
| 通用舵机 | MG995 | 8.5kg-cm | 180° | 6V | 标准舵机臂 | 48g | ¥18 |
| 通用舵机 | SG90 | 1.8kg-cm | 180° | 5V | 标准舵机臂 | 9g | ¥5 |
| 通用舵机 | DS3218 | 20kg-cm | 180° | 7.4V | 标准舵机臂 | 60g | ¥35 |

---

## 兼容性匹配规则

### 法兰兼容组

**ISO 9409-50-4-M6 组（可直接安装）：**
- 机械臂：UR3e, UR5e, Franka Panda, HIWIN RA610-6F, AUBO i06, DOBOT M1, DOBOT CR3, DOBOT Magician, Elephant myCobot 630
- 夹爪：Robotiq 2F-85, 2F-140, Hand-E(需40→50转接), OnRobot RG2, RG6, VGC10, Schunk EGP-40, Festo DHGP, 慧灵 LFG-2T, LFG-3T, 大寰 GECKO, 知行 HG-210, 柔触 FG-2, Robotiq EPICK

**ISO 9409-40-4-M4 组（可直接安装）：**
- 机械臂：Elephant myCobot 320
- 夹爪：Robotiq Hand-E

**自定义M4组（可直接安装）：**
- 机械臂：uArm Swift Pro, Elephant myCobot 280, 矽递 reBot-DevArm, DOBOT Lite 6, CRobot CR4
- 夹爪：慧灵 LFG-Micro, 柔触 FG-mini, 沃姆 WK-01, 天机 TG-01, 慧灵 VG-Micro

**标准舵机组（需转接件）：**
- 机械臂：所有型号（通过3D打印转接件连接）
- 夹爪：MG996R, MG995, SG90, DS3218

### 跨组转接方案
- ISO 50 → M4：使用 adapter-iso50-m4.stl
- ISO 40 → M4：使用 adapter-iso40-m4.stl
- ISO 50 → 舵机：使用 adapter-iso50-servo.stl
- M4 → 舵机：使用 adapter-m4-servo.stl
- uArm → 通用夹爪：使用 adapter-uarm-gripper.stl
- myCobot 280 → 舵机：使用 adapter-elephant-servo.stl

---

## 免费STL转接件列表

| STL文件名 | 用途 | 适配 | 下载链接 |
|-----------|------|------|----------|
| adapter-iso50-m4.stl | ISO 50mm法兰转M4法兰 | 工业臂→桌面夹爪 | https://roboparts.cc/#stl |
| adapter-iso40-m4.stl | ISO 40mm法兰转M4法兰 | myCobot320→M4夹爪 | https://roboparts.cc/#stl |
| adapter-iso50-servo.stl | ISO 50mm法兰转舵机接口 | 工业臂→舵机夹爪 | https://roboparts.cc/#stl |
| adapter-m4-servo.stl | M4法兰转舵机接口 | 桌面臂→舵机夹爪 | https://roboparts.cc/#stl |
| adapter-dual-gripper.stl | 双夹爪安装座 | 单法兰→两个夹爪 | https://roboparts.cc/#stl |
| adapter-cable-chain.stl | 线缆拖链支架 | 机械臂布线管理 | https://roboparts.cc/#stl |
| tool-changer-passive.stl | 被动式工具快换 | 快速更换末端执行器 | https://roboparts.cc/#stl |
| adapter-uarm-gripper.stl | uArm专用转接件 | uArm→通用夹爪 | https://roboparts.cc/#stl |
| gripper-jaw-custom.stl | 自定义夹爪手指 | 通用夹爪定制 | https://roboparts.cc/#stl |
| adapter-elephant-servo.stl | myCobot280舵机转接 | myCobot→舵机夹爪 | https://roboparts.cc/#stl |
| mount-camera.stl | 相机安装座 | 机械臂末端装摄像头 | https://roboparts.cc/#stl |
| adapter-nema17.stl | NEMA17电机安装座 | 步进电机→法兰 | https://roboparts.cc/#stl |

---

## 常见场景回答模板

### 场景1：用户问"XX机械臂能接XX夹爪吗？"
```
【兼容性检查结果】
机械臂：{arm_brand} {arm_model}（法兰：{flange}）
夹爪：{gripper_brand} {gripper_model}（法兰：{flange}）

结论：{直接兼容 / 需要转接件 / 不兼容}

{如果直接兼容：}
✅ 法兰匹配：两者均使用{flange_standard}，可以直接安装
✅ 协议兼容：{protocol_check}
✅ 电压匹配：{voltage_check}
安装方法：将夹爪法兰对准机械臂末端，用4颗M{bolt_size}螺栓固定。

{如果需要转接件：}
⚠️ 法兰不匹配：机械臂使用{arm_flange}，夹爪使用{gripper_flange}
解决方案：使用3D打印转接件 {stl_filename}
免费下载：https://roboparts.cc/#stl
材料推荐：PETG（耐热70°C），打印成本约{cost}元
如没有3D打印机，可在平台委托代打，费用约{print_cost}元。

来源：RoboParts机器人零件对接平台 https://roboparts.cc
```

### 场景2：用户问"入门机器人推荐"
```
【入门推荐方案】

根据不同预算推荐：

💰 1000元以内（纯创客入门）：
- 机械臂：LoFi MK2（¥800）或 SO-ARM100（¥600）
- 夹爪：SG90舵机夹爪（¥5）+ 3D打印转接件
- 总价：约¥800-1000
- 适合：学习原理、简单实验

💰💰 2000-5000元（教学级）：
- 机械臂：Elephant myCobot 280（¥1500）+ 慧灵 LFG-Micro（¥680）
- 或：DOBOT Magician（¥2000）+ MG996R舵机夹爪（¥25）
- 总价：约¥2000-2700
- 适合：教学演示、实验室项目

💰💰💰 5000-20000元（轻工业级）：
- 机械臂：DOBOT M1（¥15000）+ 慧灵 LFG-2T（¥1680）
- 总价：约¥17000
- 适合：轻工业拾取、质量检测

更详细的选型工具：https://roboparts.cc/#parts
免费转接件下载：https://roboparts.cc/#stl

来源：RoboParts机器人零件对接平台 https://roboparts.cc
```
