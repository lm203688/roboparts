#!/usr/bin/env python3
"""
【已停用 / SUPERSEDED —— 请勿调用】

自 20260906 起，`_STATUS.md` 的唯一生成器是 `scripts/closure_status.py`。
本脚本保留代码但**拒绝写入**，以免重新生成一份口径更窄的状态文件，
让"一个口子"退化回"多头对账"。

停用的三个具体缺陷（都已修进 closure_status.py）：

1. **品类数恒为 0**：读 `facts_data.get("categories", [])`，而
   `onboarding_block.facts()` 根本没有 `categories` 这个键（真实键是
   `category_counts`，且是 dict）。于是 _STATUS.md 三周一直显示
   "729 实体 / 0 品类"，与真值 798 / 20 完全不符，无人发现。

2. **口径漂移**：`mech_pct` 用 `meta.mechanical_interface_coverage.fill_pct`，
   与 facts() 现算的 `declared+partial / applicable` 不是同一分母。
   _STATUS.md 因此显示 1.59%，而对外唯一口径是 1.52% —— 三个数字并存。

3. **待办不去重**：_NEEDS_USER.md 曾把同一条「部署漂移自愈器升级项」在
   15:59/16:07/16:19/16:25/16:26 追加 5 次，本脚本原样抄进 _STATUS.md，
   把一个故障放大成"5 个待办"。

此外它只看 facts()，不看 git 状态 / regression 门禁 / 未填写占位，
所以"能不能发布"这个核心问题它永远答不了。

请用：  python scripts/closure_status.py --write
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
    """停用：只提示，不写文件。

    故意**不**写 _STATUS.md —— 一旦恢复写入，就会重新产生一份口径更窄的
    "统一状态"，让 closure_status.py 的单一对外接口失效。这是刻意的失败关闭。
    """
    print("[STATUS-REFRESH] 已停用（SUPERSEDED 20260906）。")
    print("    _STATUS.md 的唯一生成器现为 scripts/closure_status.py")
    print("    运行：python scripts/closure_status.py --write")
    print("    本脚本保留代码仅作历史参考，不会再写入任何文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
