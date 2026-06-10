# RoboParts 立创开源社区项目发布材料

---

## 项目标题
RoboParts - 机器人零件转接件开源库

## 项目简介
RoboParts是一个面向机器人创客的开源转接件项目，提供12款3D打印转接件设计文件，解决不同品牌机器人零件之间的法兰不兼容问题。

## 项目描述（Markdown格式，直接复制发布）

### 项目简介

RoboParts致力于解决机器人创客社区中的一个普遍痛点：不同品牌的机械臂和夹爪使用不同的法兰标准，导致无法直接安装。

本项目提供12款免费的开源STL转接件设计，覆盖ISO 9409工业标准到桌面自定义法兰的各种转换方案。所有设计经过实际打印和装配验证，可直接用于创客和教育场景。

### 设计清单

| 文件名 | 用途 | 适配场景 |
|--------|------|----------|
| adapter-iso50-m4.stl | ISO 50mm法兰转M4法兰 | 工业臂→桌面夹爪 |
| adapter-iso40-m4.stl | ISO 40mm法兰转M4法兰 | myCobot320→M4夹爪 |
| adapter-iso50-servo.stl | ISO 50mm法兰转舵机接口 | 工业臂→舵机夹爪 |
| adapter-m4-servo.stl | M4法兰转舵机接口 | 桌面臂→舵机夹爪 |
| adapter-dual-gripper.stl | 双夹爪安装座 | 单法兰→两个夹爪 |
| adapter-cable-chain.stl | 线缆拖链支架 | 机械臂布线管理 |
| tool-changer-passive.stl | 被动式工具快换 | 快速更换末端执行器 |
| adapter-uarm-gripper.stl | uArm专用转接件 | uArm→通用夹爪 |
| gripper-jaw-custom.stl | 自定义夹爪手指 | 通用夹爪定制 |
| adapter-elephant-servo.stl | myCobot280舵机转接 | myCobot→舵机夹爪 |
| mount-camera.stl | 相机安装座 | 机械臂末端装摄像头 |
| adapter-nema17.stl | NEMA17电机安装座 | 步进电机→法兰 |

### 打印参数

推荐使用PETG材料，参数如下：

```
层高: 0.2mm
填充率: 40%（六边形填充）
壁厚: 3层
支撑: 自动生成
打印温度: 230-250°C（PETG）
床温: 80°C（PETG）
```

PLA材料也可使用，但不耐高温（<65°C会软化）。

### 兼容性说明

#### 直接兼容（不需要转接件）
- ISO 9409-50法兰机械臂 + ISO 9409-50法兰夹爪
- ISO 9409-40法兰机械臂 + ISO 9409-40法兰夹爪
- 自定义M4法兰机械臂 + 自定义M4法兰夹爪

#### 需要转接件
- 不同法兰组之间的连接
- 标准法兰连接舵机夹爪
- 法兰孔位不匹配的情况

### 验证过的组合

以下组合经过实际测试验证：
- [x] UR5e + Robotiq 2F-85（直接安装）
- [x] UR5e + 慧灵 LFG-2T（直接安装）
- [x] myCobot 280 + 慧灵 LFG-Micro（直接安装）
- [x] myCobot 280 + SG90舵机夹爪（通过adapter-elephant-servo）
- [x] DOBOT M1 + 大寰 GECKO（直接安装）
- [x] uArm Swift Pro + MG996R舵机夹爪（通过adapter-uarm-gripper）

### 物料清单（BOM）

每个转接件需要的标准件：
- M3螺栓×4 + M3螺母×4（myCobot 280安装）
- M4螺栓×4 + M4螺母×4（桌面夹爪安装）
- M6螺栓×4 + M6螺母×4（工业法兰安装）
- 舵机安装螺丝×1（舵机夹爪安装）

### 许可证

CC BY-SA 4.0 — 自由使用、修改和分发，请注明来源。

### 在线资源

- 完整零件数据库和兼容性检查：https://roboparts.cc
- STL文件下载：https://roboparts.cc/#stl
- 创客社区：https://roboparts.cc/#community

### 贡献指南

欢迎提交新的转接件设计：
1. 使用CAD软件（Fusion 360 / Tinkercad / FreeCAD）设计
2. 导出STL格式
3. 实际打印并测试装配
4. 在RoboParts社区发布，附上适配的机械臂和夹爪型号

---

## 分类标签
开源硬件、机器人、3D打印、转接件、创客、机械臂、夹爪、STL、DIY

## 关联开源项目
- Elephant Robotics myCobot Python SDK
- ROS2 Robot Manipulation
- OpenCV Gripper Detection
