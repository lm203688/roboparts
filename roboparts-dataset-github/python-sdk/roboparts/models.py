"""RoboParts SDK 数据模型。

使用 ``dataclasses`` 定义与 API 返回字段对应的数据模型，提供类型安全
的数据访问方式。每个模型类都包含一个 ``from_api`` 类方法，用于从 API
返回的原始字典构建实例，兼容字段缺失或额外字段的情况。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Actuator:
    """执行器模型（对应 /api/actuators.json 中的单项）。

    覆盖舵机、直驱电机、SEA 仿生关节等 147 个执行器实体。
    """

    id: str
    name: str
    category: str
    manufacturer: str
    torque: Optional[str] = None
    speed: Optional[str] = None
    weight: Optional[str] = None
    voltage: Optional[str] = None
    protocol: Optional[str] = None
    interface: Optional[str] = None
    ros_support: Optional[bool] = None
    applications: List[str] = field(default_factory=list)
    price_range: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "Actuator":
        """从 API 返回的字典构建 Actuator 实例，忽略未知字段。"""
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)


@dataclass
class Sensor:
    """传感器模型（对应 /api/sensors.json 中的单项）。

    覆盖 LiDAR、IMU、触觉传感器、事件相机等 42 个传感器实体。
    """

    id: str
    name: str
    type: str
    range: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None

    @classmethod
    def from_api(cls, data: dict) -> "Sensor":
        """从 API 返回的字典构建 Sensor 实例，忽略未知字段。"""
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in data.items() if k in known}
        # type 字段在 API 中可能不存在，确保有默认值
        kwargs.setdefault("type", data.get("type", "unknown"))
        return cls(**kwargs)


@dataclass
class Chip:
    """芯片模型（对应 /api/chips.json 中的单项）。

    覆盖 NVIDIA Jetson、Qualcomm RB、地平线征程等 95 个 AI 推理芯片。
    """

    id: str
    name: str
    category: str
    manufacturer: str
    cpu: Optional[str] = None
    gpu: Optional[str] = None
    memory: Optional[str] = None
    tdp: Optional[str] = None
    ai_perf: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)
    ros_support: Optional[bool] = None

    @classmethod
    def from_api(cls, data: dict) -> "Chip":
        """从 API 返回的字典构建 Chip 实例，忽略未知字段。"""
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)


@dataclass
class Protocol:
    """通信协议模型（对应 /api/protocols.json 中的单项）。

    覆盖 EtherCAT、CANopen、ROS2 DDS 等 64 个通信协议。
    """

    id: str
    name: str
    category: Optional[str] = None
    type: Optional[str] = None
    speed: Optional[str] = None
    latency: Optional[str] = None
    determinism: Optional[str] = None
    topology: Optional[str] = None
    max_nodes: Optional[str] = None
    standard: Optional[str] = None
    applications: List[str] = field(default_factory=list)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    compatibility: List[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> "Protocol":
        """从 API 返回的字典构建 Protocol 实例，忽略未知字段。"""
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs.setdefault("name", data.get("name", "unknown"))
        return cls(**kwargs)


@dataclass
class BOMItem:
    """BOM 物料清单条目，作为 :meth:`RoboPartsClient.export_bom` 的输入。"""

    id: str
    name: str
    category: str
    manufacturer: Optional[str] = None
    specs: Optional[str] = None
    price: float = 0.0
    quantity: int = 1
    supplier: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为 API 请求所需的字典格式。"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "manufacturer": self.manufacturer or "",
            "specs": self.specs or "",
            "price": self.price,
            "quantity": self.quantity,
            "supplier": self.supplier or "",
        }


@dataclass
class BOMResult:
    """BOM 导出结果（JSON 格式返回时解析为此模型）。

    Attributes:
        project_name: 项目名称。
        total_cost: 总成本（CNY）。
        total_items: 条目总数。
        items: 完整的 BOM 条目列表（含小计、供应商建议等）。
        created_at: 导出时间（ISO 8601）。
        credits_remaining: 导出后剩余积分。
    """

    project_name: str
    total_cost: float
    total_items: int
    items: List[dict]
    created_at: str
    credits_remaining: Optional[int] = None

    @classmethod
    def from_api(cls, data: dict) -> "BOMResult":
        """从 /api/bom/export 的 JSON 响应构建 BOMResult 实例。

        API 返回结构为::

            {
              "metadata": {"project_name", "total_cost", "total_modules",
                           "item_count", "created_at", "credits_remaining"},
              "items": [...]
            }
        """
        meta = data.get("metadata", {})
        items = data.get("items", [])
        return cls(
            project_name=meta.get("project_name", "未命名项目"),
            total_cost=float(meta.get("total_cost", 0)),
            total_items=int(meta.get("item_count", len(items))),
            items=items,
            created_at=meta.get("created_at", ""),
            credits_remaining=meta.get("credits_remaining"),
        )
