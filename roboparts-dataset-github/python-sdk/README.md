# RoboParts Python SDK

仿生机器人零部件结构化数据 API 客户端，基于 OpenAPI 2.0 规范开发。

覆盖 **688 个实体**：执行器(199)、传感器(90)、芯片(108)、协议(64)、平台(40)、大模型(42)、接口(37)、柔性执行器(21)、机器人AI模型(44)、数据采集设备(43)。

## 安装

### 从 PyPI 安装（推荐）

```bash
pip install roboparts
```

### 从源码安装

```bash
cd python-sdk
pip install -e .
```

### 依赖

- Python >= 3.8
- requests >= 2.28.0

## 快速开始

```python
from roboparts import RoboPartsClient

# 匿名访问免费数据（无需注册）
client = RoboPartsClient()
actuators = client.get_actuators(limit=10)
print(f"获取到 {len(actuators)} 个执行器")

# 注册获取 API Key 和 100 免费积分
result = client.register("user@example.com")
api_key = result["api_key"]
print(f"你的 API Key: {api_key}")
print(f"免费积分: {result['credits']}")

# 使用 API Key 访问付费端点
client = RoboPartsClient(api_key=api_key)
balance = client.get_balance()
print(f"剩余积分: {balance['credits']}")
```

## 认证

RoboParts API 使用 API Key 认证（`gtk_` 前缀），支持两种传递方式：

| 方式 | 用法 |
|------|------|
| Header | `Authorization: Bearer gtk_xxx` |
| Query | `?key=gtk_xxx` |

SDK 默认使用 Header 方式。也可以通过环境变量 `ROBOPARTS_API_KEY` 设置：

```python
import os
os.environ["ROBOPARTS_API_KEY"] = "gtk_your_key"

from roboparts import RoboPartsClient
client = RoboPartsClient()  # 自动读取环境变量
```

## API 方法

### 认证

#### `register(email=None)`

注册新用户，返回 API Key 和 100 免费积分。

```python
result = client.register("user@example.com")
# result = {"api_key": "gtk_xxx", "credits": 100, "plan": "free", ...}
```

#### `get_balance()`

查询当前 API Key 的积分余额。

```python
balance = client.get_balance()
# balance = {"credits": 100, "plan": "free", "api_calls": 5, "email": "..."}
```

### 数据查询

所有数据查询方法返回字典列表，`limit` 参数可限制返回条数。

| 方法 | 端点 | 数量 | 积分消耗 |
|------|------|------|----------|
| `get_actuators(limit)` | `GET /api/actuators.json` | 199 | 免费 |
| `get_sensors(limit)` | `GET /api/sensors.json` | 90 | 免费 |
| `get_chips(limit)` | `GET /api/chips.json` | 108 | 免费 |
| `get_protocols(limit)` | `GET /api/protocols.json` | 64 | 免费 |
| `get_intelligence()` | `GET /api/intelligence.json` | - | 免费 |
| `get_entities()` | `GET /api/entities.json` | 688 | 50 积分 |

```python
# 获取执行器
actuators = client.get_actuators(limit=5)
for a in actuators:
    print(a["name"], a["torque"], a["protocol"])

# 获取技术情报分析
intel = client.get_intelligence()
for cat, stats in intel["categories"].items():
    print(f"{cat}: TRL={stats['avg_trl']}, 动量={stats['avg_momentum']}")

# 获取全量实体（消耗 50 积分）
entities = client.get_entities()
```

### 搜索

#### `search(keyword=None, category=None, limit=10)`

客户端侧搜索过滤，不消耗积分。支持跨类别搜索。

```python
# 搜索所有类别中包含 "CAN" 的实体
results = client.search(keyword="CAN", limit=5)

# 仅在芯片类别中搜索 "Jetson"
results = client.search(keyword="Jetson", category="chips", limit=10)
for r in results:
    print(f"[{r['_source']}] {r['name']}")
```

#### `get_component(component_id, category)`

按 ID 获取单个零部件详情。

```python
chip = client.get_component("CHIP-001", "chips")
print(chip["name"], chip["ai_perf"])
```

### BOM 物料清单

#### `export_bom(project_name, items, format='csv', include_suppliers=True)`

导出 BOM 清单，消耗 1 积分。支持 CSV 和 JSON 格式。

```python
from roboparts import BOMItem

items = [
    BOMItem(id="ACT-001", name="DYNAMIXEL XM540-W270-T",
            category="actuators", manufacturer="ROBOTIS",
            specs="9.2Nm", price=450, quantity=6),
    BOMItem(id="CHIP-001", name="NVIDIA Jetson Orin NX",
            category="chips", manufacturer="NVIDIA",
            specs="70 TOPS", price=3500, quantity=1),
]

# JSON 格式（返回 BOMResult 对象）
result = client.export_bom("人形机器人v1", items, format="json")
print(f"总成本: ¥{result.total_cost}, 条目: {result.total_items}")

# CSV 格式（返回 CSV 字符串）
csv = client.export_bom("人形机器人v1", items, format="csv")
with open("bom.csv", "w", encoding="utf-8-sig") as f:
    f.write(csv)
```

### 支付

#### `create_payment_order(plan, email=None)`

创建积分充值订单。

| 套餐 | 价格 | 积分 |
|------|------|------|
| `starter` | ¥9 | 500 |
| `pro` | ¥29 | 2000 |
| `lifetime` | ¥199 | 9999 |

```python
order = client.create_payment_order("pro", email="user@example.com")
print(f"支付链接: {order['payment_url']}")
print(f"二维码: {order.get('qrcode_url')}")
```

## 错误处理

SDK 将 HTTP 错误状态码映射为对应的异常类，所有异常继承自 `RoboPartsError`：

| HTTP 状态码 | 异常类 | 说明 |
|-------------|--------|------|
| 401 / 403 | `AuthenticationError` | API Key 无效或未注册 |
| 402 | `InsufficientCreditsError` | 积分不足 |
| 404 | `NotFoundError` | 资源不存在 |
| 429 | `RateLimitError` | 请求频率超限 |
| 其他 | `RoboPartsError` | 其他错误 |

```python
from roboparts import (
    RoboPartsError,
    AuthenticationError,
    InsufficientCreditsError,
)

try:
    result = client.export_bom("项目", items, format="json")
except InsufficientCreditsError as e:
    print(f"积分不足: 剩余 {e.credits_remaining}, 还需 {e.credits_needed}")
    # 引导用户充值
    order = client.create_payment_order("starter")
    print(f"充值链接: {order['payment_url']}")
except AuthenticationError as e:
    print(f"认证失败: {e}")
except RoboPartsError as e:
    print(f"其他错误: {e}")
```

## 数据模型

SDK 提供类型安全的数据模型类，可通过 `from_api()` 方法从 API 响应构建：

```python
from roboparts import Actuator, Sensor, Chip, BOMItem, BOMResult

# 从 API 数据构建模型
raw = client.get_actuators(limit=1)[0]
actuator = Actuator.from_api(raw)
print(actuator.name, actuator.torque, actuator.ros_support)

# BOMItem 用于构建 BOM 导出输入
item = BOMItem(id="ACT-001", name="伺服电机", category="actuators",
               manufacturer="ROBOTIS", price=450, quantity=2)
```

## 运行示例

```bash
# 无 API Key 运行（自动注册新用户）
python examples/quickstart.py

# 使用已有 API Key
export ROBOPARTS_API_KEY="gtk_your_key"
python examples/quickstart.py
```

## 项目结构

```
python-sdk/
├── setup.py                  # 包安装配置
├── README.md                 # 本文档
├── roboparts/                # SDK 主包
│   ├── __init__.py           # 包入口，导出公共 API
│   ├── client.py             # RoboPartsClient 客户端类
│   ├── exceptions.py         # 异常定义
│   └── models.py             # 数据模型（Actuator, Sensor, Chip 等）
└── examples/
    └── quickstart.py         # 完整使用示例
```

## API 参考

- 完整 OpenAPI 规范: https://roboparts.cc/api/openapi.json
- 数据集仓库: https://github.com/lm203688/roboparts
- 积分充值: https://roboparts.cc/credits
- 技术支持: support@roboparts.cc

## License

MIT License
