"""RoboParts SDK 客户端核心模块。

提供 :class:`RoboPartsClient` 类，封装了 RoboParts 平台所有 API 端点，
包括认证注册、积分查询、零部件数据查询、BOM 导出和支付订单创建。

基础用法::

    from roboparts import RoboPartsClient

    client = RoboPartsClient()                  # 匿名访问免费数据
    client = RoboPartsClient(api_key="gtk_xxx")  # 带密钥访问付费数据

    actuators = client.get_actuators(limit=10)
    balance = client.get_balance()
"""

import json as _json
import os
from typing import Any, Dict, List, Optional, Union

import requests

from .exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    NotFoundError,
    RateLimitError,
    RoboPartsError,
)
from .models import BOMItem, BOMResult

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30

# User-Agent 标识，便于服务端统计 SDK 调用
_USER_AGENT = "roboparts-python-sdk/1.0.0"


class RoboPartsClient:
    """RoboParts API 客户端。

    Args:
        api_key: API Key（``gtk_`` 前缀）。如果为 ``None``，则尝试从环境变量
            ``ROBOPARTS_API_KEY`` 读取。匿名访问仅能使用免费数据端点。
        base_url: API 基础地址，默认为 ``https://roboparts.cc``。
        timeout: 请求超时时间（秒），默认 30 秒。

    Attributes:
        api_key: 当前使用的 API Key。
        base_url: API 基础地址（末尾不含斜杠）。
        session: 复用的 :class:`requests.Session` 实例。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://roboparts.cc",
        timeout: int = DEFAULT_TIMEOUT,
    ):
        # 优先使用显式传入的 api_key，其次读取环境变量
        if api_key is None:
            api_key = os.environ.get("ROBOPARTS_API_KEY")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        })
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    # ──────────────────────────────────────────────────────────────
    # 认证
    # ──────────────────────────────────────────────────────────────

    def register(self, email: Optional[str] = None) -> Dict[str, Any]:
        """注册新用户，获取 API Key 和 100 免费积分。

        对应端点: ``POST /api/register``

        Args:
            email: 注册邮箱（需包含 ``@``）。匿名注册时可不传，但服务端
                可能拒绝，建议始终提供有效邮箱。

        Returns:
            包含 ``api_key``、``credits``、``plan`` 等字段的字典。
            注册成功后，返回的 ``api_key`` 不会自动设置到当前客户端，
            需要调用方自行保存并用于后续请求。

        Raises:
            RoboPartsError: 注册失败（如邮箱格式无效）。

        Example::

            result = client.register("user@example.com")
            print(result["api_key"])   # gtk_xxxxxxxx
            print(result["credits"])   # 100
        """
        payload: Dict[str, Any] = {}
        if email:
            payload["email"] = email
        return self._request("POST", "/api/register", json=payload)

    def get_balance(self) -> Dict[str, Any]:
        """查询当前 API Key 的积分余额和套餐信息。

        对应端点: ``POST /api/credits/balance``

        Returns:
            包含 ``credits``、``plan``、``api_calls``、``email`` 等字段的字典。

        Raises:
            AuthenticationError: 未提供 API Key。
            NotFoundError: API Key 未在系统中注册。

        Example::

            balance = client.get_balance()
            print(f"剩余积分: {balance['credits']}")
        """
        if not self.api_key:
            raise AuthenticationError(
                "查询积分余额需要 API Key，请在初始化客户端时传入 api_key 参数。"
            )
        payload = {"api_key": self.api_key}
        return self._request("POST", "/api/credits/balance", json=payload)

    # ──────────────────────────────────────────────────────────────
    # 数据查询
    # ──────────────────────────────────────────────────────────────

    def get_actuators(self, limit: Optional[int] = None) -> List[dict]:
        """获取执行器列表（147 个实体，免费）。

        对应端点: ``GET /api/actuators.json``

        数据涵盖舵机、直驱电机、SEA 仿生关节等，包含扭矩、转速、重量、
        电压、协议、接口、ROS 支持等字段。

        Args:
            limit: 限制返回条目数量。``None`` 表示返回全部。

        Returns:
            执行器字典列表。

        Example::

            actuators = client.get_actuators(limit=5)
            for a in actuators:
                print(a["name"], a["torque"])
        """
        return self._get_data("/api/actuators.json", limit=limit)

    def get_sensors(self, limit: Optional[int] = None) -> List[dict]:
        """获取传感器列表（42 个实体，免费）。

        对应端点: ``GET /api/sensors.json``

        数据涵盖 LiDAR、IMU、触觉传感器、事件相机、力矩传感器等。

        Args:
            limit: 限制返回条目数量。

        Returns:
            传感器字典列表。
        """
        return self._get_data("/api/sensors.json", limit=limit)

    def get_chips(self, limit: Optional[int] = None) -> List[dict]:
        """获取芯片列表（95 个实体，免费）。

        对应端点: ``GET /api/chips.json``

        数据涵盖 NVIDIA Jetson、Qualcomm RB、地平线征程等 AI 推理芯片，
        包含 CPU、GPU、内存、TDP、AI 算力、接口等字段。

        Args:
            limit: 限制返回条目数量。

        Returns:
            芯片字典列表。
        """
        return self._get_data("/api/chips.json", limit=limit)

    def get_protocols(self, limit: Optional[int] = None) -> List[dict]:
        """获取通信协议列表（64 个实体，免费）。

        对应端点: ``GET /api/protocols.json``

        数据涵盖 EtherCAT、CANopen、ROS2 DDS 等，包含速率、延迟、
        确定性、拓扑、最大节点数等字段。

        Args:
            limit: 限制返回条目数量。

        Returns:
            协议字典列表。
        """
        return self._get_data("/api/protocols.json", limit=limit)

    def get_intelligence(self) -> Dict[str, Any]:
        """获取技术成熟度与市场动量分析报告。

        对应端点: ``GET /api/intelligence.json``

        基于真实数据计算的 TRL（技术成熟度 1-9）和 momentum（动量 0-100）
        分析，包含 7 个品类统计、top_signals（高动量实体）、
        maturity_distribution（成熟度分布）、cross_domain_insights
        （跨品类洞察）、predictions（趋势预测）。

        Returns:
            完整的情报分析字典。
        """
        return self._request("GET", "/api/intelligence.json")

    def get_entities(self) -> Dict[str, Any]:
        """获取全量实体数据（消耗 50 积分）。

        对应端点: ``GET /api/entities.json``

        返回所有品类的完整实体数据。免费用户（无 API Key）仅返回摘要字段
        （id/name/category/focus），持有有效 API Key 且积分充足时返回
        完整数据并扣除 50 积分。

        Returns:
            全量实体字典。付费用户返回 ``{"count", "updated", "data": [...]}``；
            免费用户返回 ``{"meta": {...}, "entities": [...]}``（字段受限）。

        Raises:
            InsufficientCreditsError: 积分不足（需要 50 积分）。
            AuthenticationError: API Key 无效或未注册。

        Note:
            此端点会消耗积分，请谨慎调用。返回结果中的 ``_credits_remaining``
            属性（通过 :attr:`last_credits_remaining` 获取）可查看剩余积分。
        """
        result = self._request("GET", "/api/entities.json")
        return result

    def search(
        self,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """客户端侧搜索过滤。

        从多个数据端点拉取数据后在本地进行关键词和类别过滤。该操作不消耗积分，
        适合快速查找特定零部件。

        Args:
            keyword: 搜索关键词，匹配 name、manufacturer、protocol 等文本字段
                （不区分大小写）。``None`` 表示不限关键词。
            category: 类别过滤，可选值: ``actuators``、``sensors``、``chips``、
                ``protocols``。``None`` 表示搜索所有类别。
            limit: 每个类别的最大返回条目数，默认 10。

        Returns:
            匹配的实体字典列表，每项额外添加 ``_source`` 字段标识来源类别。
        """
        # 类别到数据获取方法的映射
        category_map = {
            "actuators": self.get_actuators,
            "sensors": self.get_sensors,
            "chips": self.get_chips,
            "protocols": self.get_protocols,
        }

        # 确定要搜索的类别
        if category:
            category = category.lower()
            if category not in category_map:
                raise ValueError(
                    f"无效的类别 '{category}'，可选值: "
                    f"{', '.join(category_map.keys())}"
                )
            categories_to_search = {category: category_map[category]}
        else:
            categories_to_search = category_map

        results: List[dict] = []
        kw_lower = keyword.lower() if keyword else None

        for cat_name, fetcher in categories_to_search.items():
            try:
                items = fetcher()
            except RoboPartsError:
                # 单个类别查询失败不影响其他类别
                continue

            for item in items:
                if kw_lower:
                    # 在多个文本字段中搜索关键词
                    searchable = " ".join(
                        str(item.get(field, ""))
                        for field in (
                            "name", "manufacturer", "protocol", "type",
                            "description", "category", "cpu", "gpu",
                            "interface", "standard",
                        )
                    ).lower()
                    if kw_lower not in searchable:
                        continue
                # 标记来源类别
                item_copy = dict(item)
                item_copy["_source"] = cat_name
                results.append(item_copy)
                if len([r for r in results if r["_source"] == cat_name]) >= limit:
                    break

        return results

    def get_component(self, component_id: str, category: str) -> Optional[dict]:
        """获取单个零部件详情。

        根据 ID 和类别从对应数据端点拉取列表，然后在本地查找匹配项。

        Args:
            component_id: 零部件 ID，如 ``ACT-001``、``SENS-004``、``CHIP-002``。
            category: 类别，可选值: ``actuators``、``sensors``、``chips``、
                ``protocols``。

        Returns:
            匹配的零部件字典；未找到时返回 ``None``。

        Raises:
            ValueError: 类别无效。
            RoboPartsError: 数据获取失败。
        """
        category_map = {
            "actuators": self.get_actuators,
            "sensors": self.get_sensors,
            "chips": self.get_chips,
            "protocols": self.get_protocols,
        }
        category = category.lower()
        if category not in category_map:
            raise ValueError(
                f"无效的类别 '{category}'，可选值: {', '.join(category_map.keys())}"
            )

        items = category_map[category]()
        for item in items:
            if item.get("id") == component_id:
                return item
        return None

    # ──────────────────────────────────────────────────────────────
    # BOM 物料清单
    # ──────────────────────────────────────────────────────────────

    def export_bom(
        self,
        project_name: str,
        items: List[Union[BOMItem, dict]],
        format: str = "csv",
        include_suppliers: bool = True,
    ) -> Union[BOMResult, str]:
        """导出 BOM 物料清单（消耗 1 积分）。

        对应端点: ``POST /api/bom/export``

        支持导出 CSV 和 JSON 两种格式，自动计算总成本，可选择附带供应商建议
        和 3D 打印建议。每次导出消耗 1 积分。

        Args:
            project_name: 项目名称，如 ``"人形机器人v1"``。
            items: BOM 条目列表，每项可以是 :class:`BOMItem` 实例或字典
                （含 id/name/category/manufacturer/specs/price/quantity/supplier）。
            format: 导出格式，``"csv"`` 或 ``"json"``，默认 ``"csv"``。
            include_suppliers: 是否附带供应商建议，默认 ``True``。

        Returns:
            ``format="json"`` 时返回 :class:`BOMResult` 实例；
            ``format="csv"`` 时返回 CSV 字符串。

        Raises:
            AuthenticationError: 未提供 API Key 或 API Key 未注册。
            InsufficientCreditsError: 积分不足（需要 1 积分）。
            ValueError: items 为空或 format 无效。

        Example::

            items = [
                BOMItem(id="ACT-001", name="DYNAMIXEL XM540", category="actuators",
                        manufacturer="ROBOTIS", price=450, quantity=2),
            ]
            result = client.export_bom("人形机器人v1", items, format="json")
            print(f"总成本: ¥{result.total_cost}")
        """
        if not self.api_key:
            raise AuthenticationError(
                "BOM 导出需要 API Key，请在初始化客户端时传入 api_key 参数。"
            )
        if not items:
            raise ValueError("items 不能为空，请提供至少一个 BOM 条目。")

        fmt = format.lower()
        if fmt not in ("csv", "json"):
            raise ValueError(f"format 必须为 'csv' 或 'json'，收到 '{format}'。")

        # 统一将 items 转换为字典列表
        serialized_items = []
        for item in items:
            if isinstance(item, BOMItem):
                serialized_items.append(item.to_dict())
            elif isinstance(item, dict):
                serialized_items.append(item)
            else:
                raise TypeError(
                    f"items 中的元素必须是 BOMItem 或 dict，收到 {type(item).__name__}。"
                )

        payload = {
            "api_key": self.api_key,
            "project_name": project_name,
            "format": fmt,
            "items": serialized_items,
            "include_suppliers": include_suppliers,
        }

        # BOM 导出端点根据格式返回不同 Content-Type，需要特殊处理
        response = self._request_raw("POST", "/api/bom/export", json=payload)

        if fmt == "json":
            data = response.json()
            return BOMResult.from_api(data)
        else:
            # CSV 格式返回纯文本
            return response.text

    # ──────────────────────────────────────────────────────────────
    # 支付
    # ──────────────────────────────────────────────────────────────

    def create_payment_order(
        self,
        plan: str,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建积分充值订单。

        对应端点: ``POST /api/payment/create``

        通过支付网关创建积分充值订单，返回支付链接和二维码。

        Args:
            plan: 套餐名称，可选值:
                - ``"starter"``: ¥9 / 500 积分
                - ``"pro"``: ¥29 / 2000 积分
                - ``"lifetime"``: ¥199 / 9999 积分
            email: 联系邮箱（可选）。

        Returns:
            包含 ``order_id``、``payment_url``、``qrcode_url``、``price``、
            ``credits`` 等字段的字典。

        Raises:
            ValueError: plan 无效。
            RoboPartsError: 订单创建失败。

        Example::

            order = client.create_payment_order("pro", email="user@example.com")
            print(f"请访问支付: {order['payment_url']}")
        """
        valid_plans = ("starter", "pro", "lifetime")
        if plan not in valid_plans:
            raise ValueError(
                f"无效的套餐 '{plan}'，可选值: {', '.join(valid_plans)}"
            )

        payload: Dict[str, Any] = {"plan": plan}
        if self.api_key:
            payload["api_key"] = self.api_key
        if email:
            payload["email"] = email

        return self._request("POST", "/api/payment/create", json=payload)

    # ──────────────────────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Any:
        """统一请求方法，自动处理错误和 JSON 解析。

        Args:
            method: HTTP 方法（GET/POST 等）。
            path: API 路径（以 ``/`` 开头）。
            **kwargs: 传递给 :meth:`requests.Session.request` 的额外参数。

        Returns:
            解析后的 JSON 响应（字典或列表）。

        Raises:
            AuthenticationError: HTTP 401/403。
            InsufficientCreditsError: HTTP 402。
            NotFoundError: HTTP 404。
            RateLimitError: HTTP 429。
            RoboPartsError: 其他 HTTP 错误或网络错误。
        """
        response = self._request_raw(method, path, **kwargs)
        # 尝试解析 JSON，失败则返回原始文本
        try:
            return response.json()
        except ValueError:
            return response.text

    def _request_raw(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response:
        """发送原始 HTTP 请求并处理错误状态码。

        与 :meth:`_request` 不同，此方法返回原始 Response 对象，不自动解析 JSON。
        供需要区分 Content-Type 的方法（如 BOM 导出）使用。
        """
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)
        except requests.ConnectionError as e:
            raise RoboPartsError(f"网络连接失败: {e}") from e
        except requests.Timeout as e:
            raise RoboPartsError(f"请求超时（{self.timeout}s）: {e}") from e
        except requests.RequestException as e:
            raise RoboPartsError(f"请求异常: {e}") from e

        # 错误状态码处理
        if response.status_code >= 400:
            self._handle_error_response(response)

        return response

    def _handle_error_response(self, response: requests.Response) -> None:
        """根据 HTTP 状态码抛出对应的异常。"""
        status_code = response.status_code

        # 尝试解析错误响应体
        try:
            error_data = response.json()
        except ValueError:
            error_data = {"error": response.text or "Unknown error"}

        message = (
            error_data.get("message")
            or error_data.get("error")
            or f"HTTP {status_code}"
        )

        if status_code in (401, 403):
            raise AuthenticationError(message, status_code=status_code, response=error_data)
        elif status_code == 402:
            raise InsufficientCreditsError(
                message,
                status_code=status_code,
                response=error_data,
                credits_remaining=error_data.get("credits_remaining"),
                credits_needed=error_data.get("credits_needed"),
            )
        elif status_code == 404:
            raise NotFoundError(message, status_code=status_code, response=error_data)
        elif status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                message,
                status_code=status_code,
                response=error_data,
                retry_after=int(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        else:
            raise RoboPartsError(message, status_code=status_code, response=error_data)

    def _get_data(self, endpoint: str, limit: Optional[int] = None) -> List[dict]:
        """获取数据端点并返回 data 数组。

        数据端点（actuators/sensors/chips/protocols）返回格式为::

            {"count": N, "updated": "...", "data": [...]}

        此方法提取 ``data`` 数组并根据 ``limit`` 截断。

        Args:
            endpoint: 数据端点路径（如 ``/api/actuators.json``）。
            limit: 限制返回条目数量。

        Returns:
            数据数组。
        """
        result = self._request("GET", endpoint)

        # 兼容两种返回格式：直接数组 或 {data: [...]}
        if isinstance(result, list):
            data = result
        elif isinstance(result, dict):
            data = result.get("data", [])
            # 如果 data 为空但 entities 存在（免费 entities 端点）
            if not data and "entities" in result:
                data = result.get("entities", [])
        else:
            data = []

        if limit is not None and limit > 0:
            data = data[:limit]

        return data

    def __repr__(self) -> str:
        masked_key = f"{self.api_key[:8]}..." if self.api_key else "None"
        return f"RoboPartsClient(base_url='{self.base_url}', api_key='{masked_key}')"
