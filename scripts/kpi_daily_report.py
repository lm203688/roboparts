#!/usr/bin/env python3
"""
埋点 KPI 日报生成器（KPI Daily Report）
消费本地统计数据（entities、API hits、MCP calls），
产出 PV/UV/注册/转化/API 调用 KPI 到 ops/metrics/。
目标：让"推广效果"第一次可以被证伪。
"""
import os, sys, json, glob
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_DIR = os.path.join(ROOT, "ops", "metrics")


def ensure_dir():
    os.makedirs(METRICS_DIR, exist_ok=True)


def load_usage_stats():
    """Load api/usage.json for API call stats"""
    usage_path = os.path.join(ROOT, "api", "usage.json")
    if not os.path.exists(usage_path):
        return {}
    
    with open(usage_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_demand_signals():
    """Load api/demand-signal.json for community signal count"""
    path = os.path.join(ROOT, "api", "demand-signal.json")
    if not os.path.exists(path):
        return {"signals": []}
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_entities_count():
    """Load entity count from entities.json"""
    path = os.path.join(ROOT, "api", "entities.json")
    if not os.path.exists(path):
        return 0
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("meta", {}).get("total_entities", 0)


def load_oss_count():
    """Load OSS component count"""
    path = os.path.join(ROOT, "api", "oss_components.json")
    if not os.path.exists(path):
        return 0
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("meta", {}).get("total", 0)


def count_hourly_results():
    """Count hourly run results from ops/results/"""
    results_dir = os.path.join(ROOT, "ops", "results")
    today = datetime.now().strftime("%Y%m%d")
    
    count = 0
    for f in glob.glob(os.path.join(results_dir, f"roboparts-{today}-*.md")):
        count += 1
    return count


def count_pending_user_items():
    """Count open items in _NEEDS_USER.md"""
    path = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")
    if not os.path.exists(path):
        return 0
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return sum(1 for line in content.splitlines() if line.strip().startswith("- [ ]"))


def generate_report():
    """Generate the daily KPI report"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    
    entities = load_entities_count()
    oss = load_oss_count()
    usage = load_usage_stats()
    signals = load_demand_signals()
    hourly_runs = count_hourly_results()
    pending = count_pending_user_items()
    
    # Count signals by source
    signal_sources = {}
    for sig in signals.get("signals", []):
        src = sig.get("source", "unknown")
        signal_sources[src] = signal_sources.get(src, 0) + 1
    
    report = {
        "date": today,
        "generated_at": now.isoformat(),
        "data": {
            "total_entities": entities,
            "oss_components": oss,
            "api_calls": usage.get("total_calls", 0),
            "mcp_calls": usage.get("mcp_calls", 0),
            "community_signals": len(signals.get("signals", [])),
            "signal_sources": signal_sources,
        },
        "operations": {
            "hourly_runs_today": hourly_runs,
            "pending_user_items": pending,
        },
        "health": {
            "entities_stable": entities > 700,
            "pending_acceptable": pending <= 3,
            "runs_active": hourly_runs > 0,
        },
    }
    
    return report


def save_report(report):
    """Save report to ops/metrics/"""
    today = report["date"].replace("-", "")
    path = os.path.join(METRICS_DIR, f"kpi-{today}.json")
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return path


def generate_markdown_summary(report):
    """Generate a human-readable markdown summary"""
    d = report["data"]
    o = report["operations"]
    h = report["health"]
    
    status_emoji = lambda ok: "✅" if ok else "⚠️"
    
    return f"""# RoboParts KPI 日报 - {report['date']}

## 数据资产
- 实体总数：{d['total_entities']} {status_emoji(h['entities_stable'])}
- OSS 组件：{d['oss_components']}
- API 调用：{d['api_calls']}
- MCP 调用：{d['mcp_calls']}

## 运营
- 今日飞轮运行：{o['hourly_runs_today']} 次 {status_emoji(h['runs_active'])}
- 待用户操作：{o['pending_user_items']} 项 {status_emoji(h['pending_acceptable'])}

## 社区信号
- 累计信号：{d['community_signals']}
- 来源分布：{json.dumps(d['signal_sources'], ensure_ascii=False)}

## 健康度
- 数据稳定：{status_emoji(h['entities_stable'])}
- 待办可控：{status_emoji(h['pending_acceptable'])}
- 飞轮活跃：{status_emoji(h['runs_active'])}

---
*自动生成于 {report['generated_at']}*
"""


def main():
    ensure_dir()
    
    print(f"[KPI-REPORT] Generating for {datetime.now().strftime('%Y-%m-%d')}")
    
    report = generate_report()
    
    # Save JSON
    json_path = save_report(report)
    print(f"[KPI-REPORT] JSON saved: {json_path}")
    
    # Save markdown
    md_path = os.path.join(METRICS_DIR, f"kpi-{report['date'].replace('-', '')}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(generate_markdown_summary(report))
    print(f"[KPI-REPORT] Markdown saved: {md_path}")
    
    # Print summary
    d = report["data"]
    print(f"\n[KPI-REPORT] SUMMARY:")
    print(f"  Entities: {d['total_entities']}")
    print(f"  OSS: {d['oss_components']}")
    print(f"  API calls: {d['api_calls']}")
    print(f"  MCP calls: {d['mcp_calls']}")
    print(f"  Community signals: {d['community_signals']}")
    print(f"  Pending items: {report['operations']['pending_user_items']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
