# RoboParts Dataset — 仿生机器人零部件结构化数据集

[![RoboParts](https://img.shields.io/badge/RoboParts-仿生机器人生态平台-06b6d4)](https://roboparts.cc)
[![Entities](https://img.shields.io/badge/Entities-798-10b981)](./data/)
[![License](https://img.shields.io/badge/License-CC--BY--4.0-blue)](./LICENSE)
[![ModelScope](https://img.shields.io/badge/ModelScope-数据集-ff6a00)](https://www.modelscope.cn/datasets/lm203688/roboparts-data)
[![PyPI](https://img.shields.io/badge/PyPI-roboparts-3775a9)](https://pypi.org/project/roboparts/)

> 覆盖 **20 大品类**（执行器、芯片、传感器、通信协议、机器人AI模型、数据采集设备、接口、大模型、平台、夹爪 / 末端执行器、柔性执行器、仿生机构、减速器、控制器、结构件、连接器、线缆、电源、电路板、一体化关节）的结构化零部件数据集，
> 专为具身智能 / 仿生机器人研发设计，可被 AI Agent 直接检索与引用。
> 当前 **798 条实体**。

<!-- 本文件由 scripts/sync_dataset_dist.py 从 api/entities.json 生成，所有数字现算。
     请勿手工编辑数字：手改会被 regression / CI 的分发漂移闸门判红。 -->

## 30 秒接入（无需注册表单 / 无需信用卡 / 无需审批）

**直接读数据（不需要任何 key）**
```bash
curl https://roboparts.cc/api/entities.json             # 798 条实体全量
curl https://roboparts.cc/api/parameter_semantics.json  # 参数口径规范
```

**需要调用兼容性校验时，一行拿 key**
```bash
curl -X POST https://roboparts.cc/api/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com"}'
# 即时返回 api_key + 100 次免费额度（30 次/小时），邮箱仅存 SHA-256 摘要
```

```bash
curl -X POST https://roboparts.cc/api/validate \
  -H "Authorization: Bearer gtk_你的key" \
  -H "Content-Type: application/json" \
  -d '{"components":["ACT-001","SEN-001"]}'
```

**给 AI Agent 的说明**：机读接入描述见 [`agent-discovery.json`](https://roboparts.cc/agent-discovery.json) 与 [`llms.txt`](https://roboparts.cc/llms.txt)，可直接解析后代用户执行。

## 我们不隐瞒的四件事

在你决定是否使用这份数据前，这些事实值得先知道（数字均由生成器现算，不是宣传口径）：

1. **798 条实体中，参数口径达到"可跨厂商直接比较"的是 0 条。** 行业普遍不声明测试条件——扭矩不给温升与持续时间、背隙不给加载条件。我们把这个缺陷公开登记（含我方自身数据的同类问题），而不是用漂亮数字掩盖。判据见 [参数口径规范](https://roboparts.cc/robot-joint-parameter-spec)。
2. **机械互换维度（"能不能拧上去"）声明率仅 1.67%。** 适用分母 418 条（总数 798 减去 380 条本身无机械接口的实体）中，仅 2 条完整声明 + 5 条部分声明；其余 411 条如实标注 `not_declared`，我们不做猜测填充。
3. **溯源分布是公开的**：A 402 条（50.4%） · B 246 条（30.8%） · C 150 条（18.8%）。Tier C 为无溯源历史导入，`confidence` 上限 0.30。有原始链接（`source_url`）的实体 511 条（64.0%）——**意味着约 36.0% 的实体目前无法一键回溯到原始文档**。
4. **兼容性结论是基于已声明数据的线索，不是认证，不替代样机实测。**

**为什么这仍然值得用**：RoboParts 不生产、不销售、不代理任何零部件。关节厂商自建的选型器无法回避一个结构性问题——选型结果天然偏向自家可造方案。中立是我们唯一无法被复制的东西，而中立的代价就是必须连自己的短板一起公开。

## 数据概览（798 实体 · 20 品类 · 2026-09-04 更新）

| 品类 | 数量 | 高频字段（现算） |
|---|---|---|
| 执行器 (Actuators) | 220 | 类型、厂商、应用 |
| 芯片 (Chips) | 108 | 类型、厂商、应用、接口、形态、CPU |
| 传感器 (Sensors) | 95 | 类型、标准合规、厂商、量程 |
| 通信协议 (Protocols) | 64 | 类型、标准、速度、延迟、确定性、拓扑 |
| 机器人AI模型 (Robot AI Models) | 46 | 类型、参数量、厂商、开发方、机器人集成、应用 |
| 数据采集设备 (Data Acquisition) | 46 | 类型、厂商、接口、应用、数据模态、开源 |
| 接口 (Interfaces) | 44 | 类型、速度、功率、连接器、应用、优点 |
| 大模型 (LLMs) | 42 | 参数量、厂商、类型、输入、输出、机器人用途 |
| 平台 (Platforms) | 41 | 厂商、类型、价格区间、年份、应用 |
| 夹爪 / 末端执行器 (Grippers) | 23 | 厂商、类型、应用、规格 |
| 柔性执行器 (Flexible Actuators) | 22 | 类型、厂商、应用、开源项目 |
| 仿生机构 (Bionic Mechanisms) | 17 | 厂商、类型、biomimetic_target、应用、兼容性、自由度 |
| 减速器 (Reducers) | 14 | 厂商、类型、应用、减速比、输出扭矩、背隙 |
| 控制器 (Controllers) | 4 | 厂商、类型、应用、规格 |
| 结构件 (Structural) | 3 | 厂商、类型、应用、规格 |
| 连接器 (Connectors) | 2 | 厂商、开源项目、类型、形态、应用、current |
| 线缆 (Cables) | 2 | 厂商、类型、应用、规格 |
| 电源 (Power) | 2 | 厂商、类型、应用、规格 |
| 电路板 (PCB) | 2 | 厂商、类型、应用、规格 |
| 一体化关节 (Integrated Joints) | 1 | 厂商、类型、composition、composition_note、应用、价格区间 |

**总计：798 个实体，覆盖 20 大品类**

> 「高频字段」= 该品类中填充率 ≥ 40% 的业务字段，由生成器统计得出。
> 长尾品类（数量个位数）字段稀疏属实，未做填充美化。

## 数据质量（覆盖率现算，非宣传值）

| 字段 | 覆盖 | 覆盖率 | 说明 |
|---|---|---|---|
| 名称 | 798/798 | 100.0% | 官方型号或通用名称 |
| 厂商 | 571/798 | 71.6% | 采集自官网 / 目录 |
| 原始链接 | 511/798 | 64.0% | 可一键回溯到来源文档 |
| 价格区间 | 209/798 | 26.2% | 参考公开报价 |
| 标准符合性已评估 | 88/798 | 11.0% | ISO / GB / IEC / ROS2 维度 |

溯源分级（Provenance Tier）：

- `A` 一手可复核（官方规格书 / 标准文本 / 带链接厂商文档）—— 建议默认采信
- `B` 弱归因（厂商目录声明值）—— 可参考，需二次核验
- `C` 无溯源（历史导入待补）—— `confidence` 上限 0.30，带 `needs_provenance: true`

## 为什么是 RoboParts（不只是另一个选型器）

- 🔗 **跨品牌兼容性矩阵**：电气 / 机械 / 协议 / 软件四维兼容检测——选完型，来 RoboParts 验证「它能不能拼在一起」。
- 🤖 **AI 可检索（GEO 友好）**：`llms.txt` + `robots.txt` 显式欢迎 GPTBot / ClaudeBot / PerplexityBot 等抓取，数据可被大模型与 Agent 直接引用（CC-BY 4.0，注明出处即可）。
- 📦 **开源可下载**：数据集已发布至 [ModelScope（公开）](https://www.modelscope.cn/datasets/lm203688/roboparts-data)。
- 🧬 **仿生品类**：SEA 串联弹性驱动器、柔性驱动器、仿生脊柱、灵巧手、人工肌肉。
- ✅ **溯源透明**：每条实体标注 `source_tier`（A/B/C）+ `confidence`，公开 Tier C 与隔离数据的存在，可核验性优先于数量宣称。

## Topics

`robotics` `robot-parts` `humanoid-robot` `embodied-ai` `actuator` `sensor` `ros2` `bionic` `dataset` `open-data` `flexible-actuator` `robot-ai` `vla` `compatibility`

## 快速开始

### 方式一：Python SDK

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

访问 [roboparts.cc](https://roboparts.cc) 使用可视化选型 + 兼容性校验。

## 数据结构

分发文件 [`data/roboparts_full.json`](./data/roboparts_full.json) 的实体对象与官网
`/api/entities.json` **完全一致**（不裁剪字段），顶层结构：

```json
{
  "meta": {
    "total_entities": 798,
    "category_count": 20,
    "category_counts": { "...": 0 },
    "mechanical_interface_declared_rate_pct": 1.67,
    "truth_source": "api/entities.json",
    "generated_by": "scripts/sync_dataset_dist.py"
  },
  "entities": [ /* 798 条 */ ]
}
```

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

数据缺口是公开的（尤其机械接口声明率 1.67%），欢迎补数据：

1. **补机械接口声明**（最缺、门槛最低）——
   用 [机械接口声明 Issue 模板](https://github.com/lm203688/roboparts/issues/new?template=mechanical-interface.yml)
   贴出处链接即可，**不必会写 JSON**，我们代录
2. **报数据错误** ——
   用 [数据纠错 Issue 模板](https://github.com/lm203688/roboparts/issues/new?template=data-correction.yml)
3. **提 PR 直接改** `api/entities.json`，本地跑 `python scripts/ci_gate.py` 自检后提交

贡献要求与最小可核验格式详见主仓
[`CONTRIBUTING.md`](https://github.com/lm203688/roboparts/blob/main/CONTRIBUTING.md)。
无出处的数据一律不收 —— 我们宁愿留着 `not_declared`，也不猜。

## 许可

[CC BY 4.0](./LICENSE) — 自由使用，需注明出处。

## 相关链接

- 官网 / 选型引擎：[https://roboparts.cc](https://roboparts.cc)
- 数据集（ModelScope，公开）：[https://www.modelscope.cn/datasets/lm203688/roboparts-data](https://www.modelscope.cn/datasets/lm203688/roboparts-data)
- Python SDK：[`python-sdk/`](./python-sdk)
- API 文档：[https://roboparts.cc/api-pricing](https://roboparts.cc/api-pricing)
- 数据主权中心：[https://roboparts.cc/data-hub](https://roboparts.cc/data-hub)
