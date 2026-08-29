# RoboParts — 仿生机器人零部件结构化数据集

> 中立、开源、可机器读取的仿生/人形机器人零部件数据库。覆盖执行器、传感器、芯片、接口、协议、机器人 AI 模型、数据采集、LLM、平台、柔性执行器、连接器共 **708** 个实体、**11** 个类别。

## 一句话定位
RoboParts 把分散在各厂商目录里的机器人硬件参数，归一化成可横向比较、可核验来源、且**诚实标注缺失**的结构化数据集，供选型、兼容性判定、世界模型/URDF 生成与标准符合性自查使用。

## 数据规模
| 指标 | 数值 |
|---|---|
| 实体总数 | 708 |
| 类别数 | 11 |
| 清洁集（去重可信） | 607 |
| 隔离集（quarantine，不进默认选型） | 101（14.27%）|
| 已核验（verified=true） | 352 |
| 最后更新 | 2026-08-12T12:22:31.965602Z |

### 类别分布
| 类别 | 数量 |
|---|---|
| actuators | 217 |
| sensors | 90 |
| chips | 108 |
| interfaces | 37 |
| protocols | 64 |
| llms | 42 |
| platforms | 40 |
| flexible_actuators | 21 |
| robot_ai_models | 44 |
| data_acquisition | 43 |
| connectors | 2 |


## 字段说明（entities.csv）
`id, name, name_en, category, manufacturer, type, torque, speed, weight, voltage, protocol, interface, position_resolution, applications, price_range, compatibility, ros_support, domestic_rate, import_dependency, verified, quarantine, data_quality, source, source_tier, confidence, mech_status, mech_mount_type, mech_standard, std_assessed, std_ros2, entity_kind`

- `applications` / `compatibility` 为 `; ` 分隔的多值字段。
- `ros_support`：`true` / `false` / 空（**空=厂商从未声明，不等于不兼容**）。
- `mech_status`：`declared` / `not_declared` / 空（空=该类别不适用机械接口）。
- `source_tier`：A=可点开复核的一手来源；B=弱归因（厂商目录声明值，无原始链接）；C=无溯源。

## 数据诚实性（本项目核心差异点）
很多零部件数据库会把"不知道"悄悄写成"没有"。RoboParts 刻意把缺失当作**第三态**显式保留，绝不把"未声明"折叠成"不兼容"。

### 1. 来源分级与可溯源率
| 来源分级 | 数量 |
|---|---|
| Tier A（可点开复核的一手来源） | 91 |
| Tier B（弱归因，如厂商目录声明值） | 210 |
| Tier C（无溯源，confidence 上限 0.30） | 407 |

- 有来源字段占比 `source_pct = 79.24%`（含 Tier B 弱归因，仅作过程指标）
- **可点开复核占比 `traceable_pct = 12.85%`**（主指标，曾虚报已更正）
- 置信度已标注占比 `confidence_pct = 100.0%`
- 最近核验占比 `last_verified_pct = 69.21%`

### 2. 机械接口维度（三态）
| 状态 | 数量 |
|---|---|
| 适用实体 | 358 |
| 已声明（declared） | 2 |
| 未声明（not_declared，显式缺口） | 352 |

机械接口已获厂商声明的比例仅 **1.68%**——这是一个真实的、被显式记录的缺口，不是字段缺失。

### 3. ROS 支持维度（三态）
| 状态 | 数量 |
|---|---|
| 声明支持 ROS | 47 |
| 声明不支持 ROS | 27 |
| 从未声明（不推断为不兼容） | 634 |

### 4. 隔离与去重策略
- `quarantine=true` 的 101 条不删除，前端默认不进选型结果，仅在"显示未核验数据"时展示。
- 同名同厂商重复登记只保留一条规范条目，其余隔离，清洁集内不再有同物异 ID。

## 许可证
[Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)

## 获取与实时访问
数据集会随站点持续更新；如需实时数据请用开放 API（免费 key，无需信用卡）：
```bash
curl -X POST https://roboparts.cc/api/register -H "Content-Type: application/json" -d '{"email":"you@example.com"}'
curl -H "X-API-Key: YOUR_KEY" https://roboparts.cc/api/data.json
```
- 在线平台：https://roboparts.cc
- 数据集仓库：https://github.com/lm203688/roboparts
- MCP Server：`roboparts-mcp-server`（npm）

## 中立性声明
本平台不生产、不代理任何零部件，与所收录厂商无销售利益关系。本库参数为厂商公开声明值，未经我方实测复现；跨厂商可直接横向比较的 A 级条目为 0 条，机械接口有线索的占 1.68%。请据此判断可信度，不要把声明值当实测值使用。

## 使用方式
```python
import pandas as pd
df = pd.read_csv('entities.csv')
# 查看已声明 ROS 支持的实体
df[df['ros_support'] == True]
# 查看机械接口已声明的实体
df[df['mech_status'] == 'declared']
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
