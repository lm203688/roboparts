"""RoboParts Python SDK

仿生机器人零部件结构化数据 API 客户端，覆盖执行器(147)、传感器(42)、
芯片(95)、协议(64) 共 412 个实体。支持零部件搜索、BOM 导出、积分充值。

快速开始::

    from roboparts import RoboPartsClient

    # 匿名访问免费数据
    client = RoboPartsClient()
    actuators = client.get_actuators(limit=10)

    # 注册获取 API Key 和 100 免费积分
    result = client.register("user@example.com")
    client = RoboPartsClient(api_key=result["api_key"])
    print(client.get_balance())

文档: https://roboparts.cc
"""

from .client import RoboPartsClient
from .exceptions import (
    RoboPartsError,
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    NotFoundError,
)
from .models import Actuator, Sensor, Chip, Protocol, BOMItem, BOMResult

__version__ = "1.0.0"

__all__ = [
    "RoboPartsClient",
    "RoboPartsError",
    "AuthenticationError",
    "InsufficientCreditsError",
    "RateLimitError",
    "NotFoundError",
    "Actuator",
    "Sensor",
    "Chip",
    "Protocol",
    "BOMItem",
    "BOMResult",
]
