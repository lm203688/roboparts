# RoboParts Dataset — 仿生机器人零部件结构化数据集

[![RoboParts](https://img.shields.io/badge/RoboParts-仿生机器人生态平台-06b6d4)](https://roboparts.cc)
[![Entities](https://img.shields.io/badge/Entities-688-10b981)](./data/)
[![License](https://img.shields.io/badge/License-CC--BY--4.0-blue)](./LICENSE)
[![ModelScope](https://img.shields.io/badge/ModelScope-数据集-ff6a00)](https://www.modelscope.cn/datasets/lm203688/roboparts-data)
[![HuggingFace](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-尚未同步-lightgrey)](https://www.modelscope.cn/datasets/lm203688/roboparts-data)
[![PyPI](https://img.shields.io/badge/PyPI-roboparts-3775a9)](https://pypi.org/project/roboparts/)

> 机器人行业首个覆盖**执行器、柔性执行器、传感器、芯片、通信协议、大模型、机器人AI模型、接口、平台、数据采集设备**十大品类的结构化数据集，专为具身智能 / 仿身机器人研发设计。可被 AI Agent 直接检索与引用。

## 30 秒接入（无需注册表单 / 无需信用卡 / 无需审批）

**直接读数据（不需要任何 key）**
```bash
curl https://roboparts.cc/api/entities.json          # 688 条实体全量
curl https://roboparts.cc/api/parameter_semantics.json  # 参数口径规范
```

**需要调用兼容性校验时，一行拿 key**
```bash
curl -X POST https://roboparts.cc/api/register   -H "Content-Type: application/json"   -d '{"email":"you@example.com"}'
# 即时返回 api_key + 100 次免费额度（30 次/小时），邮箱仅存 SHA-256 摘要
```

```bash
curl -X POST https://roboparts.cc/api/validate   -H "Authorization: Bearer gtk_你的key"   -H "Content-Type: application/json"   -d '{"components":["ACT-001","SEN-001"]}'
```

**给 AI Agent 的说明**：机读接入描述见 [`agent-discovery.json`](https://roboparts.cc/agent-discovery.json) 与 [`llms.txt`](https://roboparts.cc/llms.txt)，可直接解析后代用户执行。

## 我们不隐瞒的三件事

在你决定是否使用这份数据前，这些事实值得先知道：

1. **688 条实体中，参数口径达到"可跨厂商直接比较"的是 0 条。** 行业普遍不声明测试条件——扭矩不给温升与持续时间、背隙不给加载条件。我们把这个缺陷公开登记（含我方自身数据的同类问题），而不是用漂亮数字掩盖。判据见 [参数口径规范](https://roboparts.cc/robot-joint-parameter-spec)。
2. **机械互换维度（"能不能拧上去"）声明率仅 0.57%。** 其余 685 条如实标注 `not_declared`，我们不做猜测填充。
3. **兼容性结论是基于已声明数据的线索，不是认证，不替代样机实测。**

**为什么这仍然值得用**：RoboParts 不生产、不销售、不代理任何零部件。关节厂商自建的选型器无法回避一个结构性问题——选型结果天然偏向自家可造方案。中立是我们唯一无法被复制的东西，而中立的代价就是必须连自己的短板一起公开。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=lm203688/roboparts&type=Date)](https://star-history.com/#lm203688/roboparts&Date)

## 数据概览（688 实体 · 2026-08-05 更新）

| 品类 | 数量 | 核心字段 |
|---|---|---|
| 执行器 (Actuators) | 199 | 扭矩、速度、电压、协议、重量、价格 |
| 传感器 (Sensors) | 90 | 量程、精度、类型、厂商 |
| 芯片 (Chips) | 108 | CPU、AI性能、功耗、价格区间、VLA支持 |
| 协议 (Protocols) | 64 | 速度、延迟、最大节点、标准 |
| 接口 (Interfaces) | 37 | 速度、供电、连接器类型 |
| 大模型 (LLMs) | 42 | 参数量、开源、具身智能支持 |
| 平台 (Platforms) | 40 | 类型、开源、仿真支持 |
| 柔性执行器 (Flexible Actuators) | 21 | 柔性、变形、驱动方式、材料 |
| 机器人AI模型 (Robot AI Models) | 44 | 模型类型、参数量、任务、开源 |
| 数据采集设备 (Data Acquisition) | 43 | 遥操作、动作捕捉、触觉传感器 |

**总计：688 个实体，覆盖 10 大品类**

## 为什么是 RoboParts（不只是另一个选型器）

市面上的选型工具多为「黑箱算法 + 自有封闭库」。RoboParts 的差异化定位是 **开放的、可被引用的兼容性数据底座**：

- 🔗 **跨品牌兼容性矩阵**：电气 / 机械 / 协议 / 软件四维兼容检测——选完型，来 RoboParts 验证「它能不能拼在一起」。
- 🤖 **AI 可检索（GEO 友好）**：`llms.txt` + `robots.txt` 显式欢迎 GPTBot / ClaudeBot / PerplexityBot 等抓取，数据可被大模型与 Agent 直接引用（CC-BY 4.0，注明出处即可）。
- 📦 **开源可下载**：数据集已发布至 [ModelScope（公开）](https://www.modelscope.cn/datasets/lm203688/roboparts-data)，HuggingFace 同步中。
- 🧬 **仿生品类**：SEA 串联弹性驱动器、柔性驱动器、仿生脊柱、灵巧手、人工肌肉。
- ✅ **溯源透明**：每条实体标注 `source_tier`（A/B/C）+ `confidence`，公开 Tier C 与隔离数据的存在，可核验性优先于数量宣称。

## Topics

`robotics` `robot-parts` `humanoid-robot` `embodied-ai` `actuator` `sensor` `ros2` `bionic` `dataset` `open-data` `flexible-actuator` `robot-ai` `vla` `compatibility`

## 快速开始

### 方式一：Python SDK（推荐）

```bash
pip install roboparts
```

```python
from roboparts import RoboPartsClient

client = RoboPartsClient()
data = client.get_all()

# 查找所有仿生执行器
bionic = client.filter(category="actuators", bionic=True)
print(f"找到 {len(bionic)} 个仿生执行器")

# 膝关节推荐（额定扭矩 > 80 Nm）
knee = client.filter(category="actuators", min_torque=80)
```

### 方式二：直接下载 JSON

```bash
curl -o roboparts-data.json https://roboparts.cc/api/data.json
```

### 方式三：在线选型引擎

访问 [roboparts.cc](https://roboparts.cc) 使用可视化选型 + 兼容性校验：
- 输入关节位置、扭矩要求、预算 → 自动匹配兼容执行器
- 多因子评分（扭矩/价格比 30%、轻量化 20%、协议匹配 25%、仿生特性 15%、标准合规 10%）
- 四维兼容矩阵校验「选出来的零件能不能拼在一起」

## 数据质量

| 字段 | 覆盖率 | 说明 |
|---|---|---|
| 名称 | 100% | 官方型号或通用名称 |
| 厂商 | 95% | 采集自官网 |
| 规格参数 | 85% | 来自数据手册 |
| 价格区间 | 70% | 参考公开报价 |
| 标准合规 | 60% | 持续验证中（GB 模块化人形机器人通用技术要求 / ISO 8373 / IEC 61508 / ROS2）|

溯源分级（Provenance Tier）：
- `A` 一手可复核（官方规格书 / 标准文本 / 带链接厂商文档）—— 建议默认采信
- `B` 弱归因（厂商目录声明值）—— 可参考，需二次核验
- `C` 无溯源（历史导入待补）—— `confidence` 上限 0.30，带 `needs_provenance: true`

## 应用场景

- **机器人研发**：快速查找执行器、传感器参数
- **具身智能研究**：获取 VLA 模型（GR00T N1.7、SmolVLA、π0.5、τ(0)-VLA、InternVLA-A1.5、Hy-Embodied VLA-0.5）和机器人平台数据
- **供应链分析**：比价、交期、认证信息
- **教育 / 论文**：引用结构化数据作为实验基础

## 引用

```bibtex
@dataset{roboparts2026,
  title={RoboParts: A Structured Dataset for Bionic Robot Components},
  author={RoboParts Team},
  year={2026},
  url={https://roboparts.cc}
}
```

## 贡献

欢迎通过以下方式贡献：
1. 提交 Issue 报告数据错误
2. 提交 PR 补充新实体
3. 在 [roboparts.cc](https://roboparts.cc) 使用在线纠错功能

## 许可

[CC BY 4.0](./LICENSE) — 自由使用，需注明出处。

## 相关链接

- 官网 / 选型引擎：[https://roboparts.cc](https://roboparts.cc)
- 数据集（ModelScope，公开）：[https://www.modelscope.cn/datasets/lm203688/roboparts-data](https://www.modelscope.cn/datasets/lm203688/roboparts-data)
- 数据集（HuggingFace）：**尚未同步**（HF_TOKEN 未配置，同步流程未跑通）。请使用上方 ModelScope 镜像，内容与本仓库一致。
- Python SDK：[`python-sdk/`](./python-sdk)
- API 文档：[https://roboparts.cc/api-pricing](https://roboparts.cc/api-pricing)
- 设计画布：[https://roboparts.cc/designer](https://roboparts.cc/designer)
- 数据主权中心：[https://roboparts.cc/data-hub](https://roboparts.cc/data-hub)
