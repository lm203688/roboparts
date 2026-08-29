#!/usr/bin/env python3
"""
_STATUS.md 自动刷新器
从 facts() + _NEEDS_USER + _LATEST 重算统一状态视图，覆写 _STATUS.md。
目标：确保"给人看的统一视图"永远与真相源同步。
"""
import os, sys, json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_PATH = os.path.join(ROOT, "ops", "results", "_STATUS.md")
NEEDS_USER = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")
LATEST = os.path.join(ROOT, "ops", "results", "_LATEST.md")


def load_facts():
    """Load truth snapshot from onboarding_block or entities.json"""
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from onboarding_block import facts
        return facts()
    except Exception:
        pass
    
    # Fallback: read from api/entities.json
    try:
        with open(os.path.join(ROOT, "api", "entities.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("meta", {})
        return {
            "total_entities": meta.get("total_entities", 0),
            "categories": meta.get("categories", []),
            "category_counts": meta.get("category_counts", {}),
            "oss_total": meta.get("oss_total", 0),
            "mech_pct": meta.get("mechanical_interface_coverage", {}).get("fill_pct", 0),
        }
    except Exception:
        return {"total_entities": 0, "categories": [], "oss_total": 0, "mech_pct": 0}


def count_pending_items():
    """Count open items in _NEEDS_USER.md"""
    if not os.path.exists(NEEDS_USER):
        return 0, []
    
    with open(NEEDS_USER, "r", encoding="utf-8") as f:
        content = f.read()
    
    pending = []
    for line in content.splitlines():
        if line.strip().startswith("- [ ]"):
            # Extract first 80 chars as summary
            summary = line.strip()[5:].strip()[:80]
            pending.append(summary)
    
    return len(pending), pending


def get_latest_run_time():
    """Get the timestamp from _LATEST.md"""
    if not os.path.exists(LATEST):
        return "unknown"
    
    with open(LATEST, "r", encoding="utf-8") as f:
        for line in f:
            m = __import__("re").search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", line)
            if m:
                return m.group(1)
    return "unknown"


def generate_status(facts_data, pending_count, pending_items, latest_run):
    """Generate the _STATUS.md content"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cats = ", ".join(facts_data.get("categories", [])[:5]) + "..."
    cat_count = len(facts_data.get("categories", []))
    
    pending_section = ""
    for item in pending_items:
        pending_section += f"- [ ] {item}\n"
    if not pending_section:
        pending_section = "- （无待办）\n"
    
    return f"""# RoboParts 总指挥飞轮 · 统一状态汇总（自动刷新）

> 本文件由 `scripts/refresh_status.py` 自动生成，与真相源同步。
> 最近更新：{now}

---

## ① 系统状态

- **数据量**：{facts_data.get('total_entities', 0)} 实体 / {cat_count} 品类 / {facts_data.get('oss_total', 0)} OSS
- **机械声明率**：{facts_data.get('mech_pct', 0)}%
- **最新运行**：{latest_run}
- **待办数量**：{pending_count} 项

---

## ② 真值快照

| 指标 | 值 |
|---|---|
| 实体 | {facts_data.get('total_entities', 0)} |
| 品类 | {cat_count}（{cats}） |
| OSS | {facts_data.get('oss_total', 0)} |
| 机械声明率 | {facts_data.get('mech_pct', 0)}% |

---

## ③ 待用户操作

{pending_section}
---

*本文件由自动刷新器生成，覆盖人工编辑。如需修改，请编辑脚本逻辑。*
"""


def main():
    print("[STATUS-REFRESH] Loading facts...")
    facts_data = load_facts()
    
    print("[STATUS-REFRESH] Counting pending items...")
    pending_count, pending_items = count_pending_items()
    
    print("[STATUS-REFRESH] Getting latest run time...")
    latest_run = get_latest_run_time()
    
    print(f"[STATUS-REFRESH] Facts: {facts_data.get('total_entities', 0)} entities, "
          f"{len(facts_data.get('categories', []))} cats, "
          f"{pending_count} pending")
    
    status_content = generate_status(facts_data, pending_count, pending_items, latest_run)
    
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        f.write(status_content)
    
    print(f"[STATUS-REFRESH] DONE: _STATUS.md refreshed at {datetime.now().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
