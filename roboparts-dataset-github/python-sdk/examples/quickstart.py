"""RoboParts Python SDK 快速入门示例。

本示例演示 SDK 的完整工作流程:

    1. 注册新用户（如果无 API Key）
    2. 查询积分余额
    3. 搜索执行器
    4. 获取传感器列表
    5. 获取芯片详情
    6. 导出 BOM（CSV 和 JSON 格式）
    7. 查看技术情报分析

运行方式::

    # 方式一：设置环境变量后运行
    export ROBOPARTS_API_KEY="gtk_your_key"
    python examples/quickstart.py

    # 方式二：无 API Key 运行（自动注册新用户）
    python examples/quickstart.py

    # 方式三：直接在代码中传入 API Key
    # 修改下方 API_KEY 变量
"""

import os
import sys

# 将上级目录加入 sys.path，以便直接运行此脚本时能导入 roboparts 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from roboparts import (
    RoboPartsClient,
    RoboPartsError,
    AuthenticationError,
    InsufficientCreditsError,
    BOMItem,
)


# ─────────────────────────────────────────────────────────────────
# 配置：在此填入你的 API Key，或留空自动注册
# ─────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ROBOPARTS_API_KEY", "")
BASE_URL = "https://roboparts.cc"
REGISTER_EMAIL = "sdk-demo@example.com"  # 注册时使用的邮箱


def section(title: str):
    """打印分隔标题。"""
    print("\n" + "=" * 64)
    print(f"  {title}")
    print("=" * 64)


def step1_register(client: RoboPartsClient) -> str:
    """步骤 1：注册新用户（如果无 API Key）。"""
    section("步骤 1: 注册新用户")
    if API_KEY:
        print(f"已提供 API Key: {API_KEY[:12]}...，跳过注册。")
        return API_KEY

    print(f"未检测到 API Key，正在注册新用户（邮箱: {REGISTER_EMAIL}）...")
    try:
        result = client.register(REGISTER_EMAIL)
        api_key = result.get("api_key", "")
        credits = result.get("credits", 0)
        plan = result.get("plan", "free")
        print(f"注册成功!")
        print(f"  API Key : {api_key}")
        print(f"  套餐    : {plan}")
        print(f"  积分    : {credits}")
        print(f"  限流    : {result.get('rate_limit', 'N/A')}")
        print(f"\n请妥善保存 API Key，后续使用它访问付费端点。")
        return api_key
    except RoboPartsError as e:
        print(f"注册失败: {e}")
        print("将使用匿名模式访问免费端点。")
        return ""


def step2_check_balance(client: RoboPartsClient):
    """步骤 2：查询积分余额。"""
    section("步骤 2: 查询积分余额")
    if not client.api_key:
        print("无 API Key，跳过积分查询。")
        return

    try:
        balance = client.get_balance()
        print(f"  邮箱    : {balance.get('email', 'N/A')}")
        print(f"  套餐    : {balance.get('plan', 'N/A')}")
        print(f"  剩余积分: {balance.get('credits', 0)}")
        print(f"  API 调用: {balance.get('api_calls', 0)} 次")
    except AuthenticationError as e:
        print(f"认证失败: {e}")
    except RoboPartsError as e:
        print(f"查询失败: {e}")


def step3_search_actuators(client: RoboPartsClient):
    """步骤 3：搜索执行器。"""
    section("步骤 3: 搜索执行器")

    # 获取执行器列表
    try:
        actuators = client.get_actuators(limit=5)
        print(f"获取到 {len(actuators)} 个执行器（限 5 个）:\n")
        for a in actuators:
            name = a.get("name", "N/A")
            mfr = a.get("manufacturer", "N/A")
            torque = a.get("torque", "N/A")
            protocol = a.get("protocol", "N/A")
            ros = "是" if a.get("ros_support") else "否"
            print(f"  [{a.get('id', '?')}] {name}")
            print(f"      品牌: {mfr} | 扭矩: {torque} | 协议: {protocol} | ROS: {ros}")
    except RoboPartsError as e:
        print(f"获取执行器失败: {e}")
        return

    # 使用 search 方法进行关键词搜索
    print(f"\n--- 搜索关键词 'DYNAMIXEL' ---")
    try:
        results = client.search(keyword="DYNAMIXEL", category="actuators", limit=5)
        print(f"找到 {len(results)} 个匹配结果:")
        for r in results:
            print(f"  [{r.get('id')}] {r.get('name')} - {r.get('manufacturer')}")
    except RoboPartsError as e:
        print(f"搜索失败: {e}")


def step4_get_sensors(client: RoboPartsClient):
    """步骤 4：获取传感器列表。"""
    section("步骤 4: 获取传感器列表")
    try:
        sensors = client.get_sensors(limit=5)
        print(f"获取到 {len(sensors)} 个传感器（限 5 个）:\n")
        for s in sensors:
            name = s.get("name", "N/A")
            stype = s.get("type", "N/A")
            srange = s.get("range", "N/A")
            print(f"  [{s.get('id', '?')}] {name}")
            print(f"      类型: {stype} | 量程: {srange}")
    except RoboPartsError as e:
        print(f"获取传感器失败: {e}")


def step5_get_chip_detail(client: RoboPartsClient):
    """步骤 5：获取芯片详情。"""
    section("步骤 5: 获取芯片详情")
    try:
        chips = client.get_chips(limit=3)
        if not chips:
            print("未获取到芯片数据。")
            return

        print(f"获取到 {len(chips)} 个芯片（限 3 个）:\n")
        for c in chips:
            print(f"  [{c.get('id')}] {c.get('name')}")
            print(f"      品牌: {c.get('manufacturer')} | CPU: {c.get('cpu', 'N/A')}")
            print(f"      GPU: {c.get('gpu', 'N/A')} | AI: {c.get('ai_perf', 'N/A')}")
            print(f"      TDP: {c.get('tdp', 'N/A')} | ROS: {'是' if c.get('ros_support') else '否'}")
            print()

        # 获取单个芯片详情
        target_id = chips[0].get("id")
        print(f"--- 获取单个芯片详情 (ID: {target_id}) ---")
        detail = client.get_component(target_id, "chips")
        if detail:
            print(f"  名称: {detail.get('name')}")
            print(f"  接口: {', '.join(detail.get('interfaces', []))}")
            print(f"  应用: {', '.join(detail.get('applications', []))}")
        else:
            print(f"  未找到 ID 为 {target_id} 的芯片。")
    except RoboPartsError as e:
        print(f"获取芯片失败: {e}")


def step6_export_bom(client: RoboPartsClient):
    """步骤 6：导出 BOM（CSV 和 JSON 格式）。"""
    section("步骤 6: 导出 BOM 物料清单")

    if not client.api_key:
        print("无 API Key，BOM 导出需要 API Key，跳过此步骤。")
        print("（BOM 导出消耗 1 积分，注册即可获得 100 免费积分）")
        return

    # 构建 BOM 条目（混合使用 BOMItem 对象和字典）
    bom_items = [
        BOMItem(
            id="ACT-001",
            name="DYNAMIXEL XM540-W270-T",
            category="actuators",
            manufacturer="ROBOTIS",
            specs="9.2Nm @ 12V, TTL/RS485",
            price=450.0,
            quantity=6,
            supplier="ROBOTIS 官方",
        ),
        BOMItem(
            id="SENS-004",
            name="IMU (Inertial Measurement Unit)",
            category="sensors",
            manufacturer="Bosch",
            specs="±2g to ±200g; ±125°/s to ±4000°/s",
            price=120.0,
            quantity=1,
        ),
        {
            "id": "CHIP-001",
            "name": "NVIDIA Jetson Orin NX",
            "category": "chips",
            "manufacturer": "NVIDIA",
            "specs": "8-core ARM, 1024-core Ampere, 70 TOPS",
            "price": 3500.0,
            "quantity": 1,
            "supplier": "NVIDIA 官方",
        },
    ]

    project_name = "人形机器人v1-SDK演示"

    # 导出 JSON 格式
    print("--- 导出 JSON 格式 BOM ---")
    try:
        result = client.export_bom(
            project_name=project_name,
            items=bom_items,
            format="json",
            include_suppliers=True,
        )
        print(f"  项目名称  : {result.project_name}")
        print(f"  条目总数  : {result.total_items}")
        print(f"  总成本    : ¥{result.total_cost:.2f}")
        print(f"  导出时间  : {result.created_at}")
        if result.credits_remaining is not None:
            print(f"  剩余积分  : {result.credits_remaining}")
        print(f"\n  条目明细:")
        for item in result.items:
            print(f"    {item['index']}. {item['name']} x{item['quantity']}"
                  f" = ¥{item['subtotal']:.2f} ({item.get('print_advice', '')})")
    except InsufficientCreditsError as e:
        print(f"  积分不足: {e} (剩余 {e.credits_remaining}, 需要 {e.credits_needed})")
    except RoboPartsError as e:
        print(f"  JSON 导出失败: {e}")

    # 导出 CSV 格式
    print(f"\n--- 导出 CSV 格式 BOM ---")
    try:
        csv_content = client.export_bom(
            project_name=project_name,
            items=bom_items,
            format="csv",
            include_suppliers=True,
        )
        # 显示 CSV 前 15 行
        lines = csv_content.split("\n")
        print(f"  CSV 共 {len(lines)} 行，前 15 行预览:")
        for line in lines[:15]:
            print(f"  | {line}")

        # 保存到文件
        output_path = "roboparts_bom_demo.csv"
        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)
        print(f"\n  CSV 已保存到: {output_path}")
    except InsufficientCreditsError as e:
        print(f"  积分不足: {e}")
    except RoboPartsError as e:
        print(f"  CSV 导出失败: {e}")


def step7_intelligence(client: RoboPartsClient):
    """步骤 7：查看技术情报分析。"""
    section("步骤 7: 技术成熟度与市场动量分析")
    try:
        intel = client.get_intelligence()

        # 元信息
        meta = intel.get("meta", {})
        print(f"  生成时间  : {meta.get('generated_at', 'N/A')}")
        print(f"  实体总数  : {meta.get('total_entities', 'N/A')}")
        print(f"  数据版本  : v{meta.get('version', 'N/A')}")

        # 各品类统计
        categories = intel.get("categories", {})
        print(f"\n  各品类技术成熟度 (TRL) 与动量 (Momentum):")
        print(f"  {'品类':<16} {'数量':>6} {'平均TRL':>8} {'动量':>6} {'阶段':<12} {'主信号':>6}")
        print(f"  {'-' * 60}")
        for cat, stats in categories.items():
            count = stats.get("count", 0)
            trl = stats.get("avg_trl", 0)
            mom = stats.get("avg_momentum", 0)
            label = stats.get("trl_label", "N/A")
            signal = stats.get("dominant_signal", "?")
            print(f"  {cat:<16} {count:>6} {trl:>8.1f} {mom:>6} {label:<12} {signal:>6}")

        # Top signals（高动量实体）
        top_signals = intel.get("top_signals", [])
        if top_signals:
            print(f"\n  高动量实体 Top 5:")
            for i, sig in enumerate(top_signals[:5], 1):
                name = sig.get("name", "N/A")
                cat = sig.get("category", "N/A")
                mom = sig.get("momentum", 0)
                trl = sig.get("trl", 0)
                print(f"    {i}. {name} [{cat}] - 动量: {mom}, TRL: {trl}")

        # 趋势预测
        predictions = intel.get("predictions", {})
        if predictions:
            print(f"\n  趋势预测:")
            for key, value in list(predictions.items())[:5]:
                if isinstance(value, dict):
                    desc = value.get("description", value.get("summary", str(value)))
                else:
                    desc = str(value)
                print(f"    - {key}: {desc[:80]}")

    except RoboPartsError as e:
        print(f"获取情报分析失败: {e}")


def main():
    """运行所有示例步骤。"""
    print("=" * 64)
    print("  RoboParts Python SDK 快速入门")
    print(f"  Base URL: {BASE_URL}")
    print(f"  API Key : {API_KEY[:12] + '...' if API_KEY else '无（将自动注册）'}")
    print("=" * 64)

    # 初始化客户端
    client = RoboPartsClient(api_key=API_KEY or None, base_url=BASE_URL)
    print(f"\n客户端: {client}")

    # 步骤 1：注册
    api_key = step1_register(client)
    if api_key and not API_KEY:
        # 注册成功后，用新 Key 重新初始化客户端
        client = RoboPartsClient(api_key=api_key, base_url=BASE_URL)
        print(f"\n已使用新 API Key 重新初始化客户端: {client}")

    # 步骤 2：查询积分
    step2_check_balance(client)

    # 步骤 3：搜索执行器
    step3_search_actuators(client)

    # 步骤 4：获取传感器
    step4_get_sensors(client)

    # 步骤 5：获取芯片详情
    step5_get_chip_detail(client)

    # 步骤 6：导出 BOM
    step6_export_bom(client)

    # 步骤 7：技术情报分析
    step7_intelligence(client)

    # 完成
    section("全部示例完成")
    print("  如需了解更多，请参阅 README.md 或访问 https://roboparts.cc")
    print("=" * 64)


if __name__ == "__main__":
    main()
