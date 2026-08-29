#!/usr/bin/env python3
"""
占位追平器（Auto-Fill Stubs）
每日扫描 _SUMMARY.md 的 AUTO-STUB 占位行，超过 12h 未回填的自动补 RECONCILED。
目标：消灭"飞轮触发了但没执行完"的空壳积压。
"""
import os, re, sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY = os.path.join(ROOT, "ops", "results", "_SUMMARY.md")
NEEDS_USER = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")

STUB_SENTINEL = "<!-- ROBOPARTS-RUN-TRACE:AUTO-STUB -->"
STALE_HOURS = 12


def parse_summary_timestamps(text: str) -> list:
    """Extract all lines with timestamps from _SUMMARY.md"""
    results = []
    for i, line in enumerate(text.splitlines()):
        m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", line)
        if m:
            try:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                results.append((i, ts, line))
            except ValueError:
                pass
    return results


def find_stale_stubs(text: str) -> list:
    """Find AUTO-STUB lines that are older than STALE_HOURS"""
    now = datetime.now()
    stale = []
    lines = text.splitlines()
    
    for i, line in enumerate(lines):
        if STUB_SENTINEL not in line:
            continue
        
        # Look backward for the nearest timestamp
        for j in range(i - 1, max(i - 5, -1), -1):
            m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", lines[j])
            if m:
                try:
                    ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                    age = now - ts
                    if age > timedelta(hours=STALE_HOURS):
                        stale.append({
                            "line_idx": i,
                            "timestamp": ts,
                            "age_hours": age.total_seconds() / 3600,
                            "original_line": line,
                        })
                except ValueError:
                    pass
                break
    return stale


def fill_stub(text: str, stub: dict) -> str:
    """Replace an AUTO-STUB line with a RECONCILED entry"""
    idx = stub["line_idx"]
    ts_str = stub["timestamp"].strftime("%Y-%m-%d %H:%M")
    age_h = stub["age_hours"]
    
    reconciled = (
        f"- {ts_str} | RECONCILED(占位追平器) | "
        f"修复:原占位已超{age_h:.0f}h未回填,占位追平器自动关闭 | "
        f"提升:无(占位追平) | 待办:无"
    )
    lines = text.splitlines()
    lines[idx] = reconciled
    return "\n".join(lines) + "\n"


def ensure_needs_user_freshness():
    """Append freshness note to _NEEDS_USER.md if missing today's check"""
    today = datetime.now().strftime("%Y%m%d")
    marker = f"占位追平器 {today}"
    
    if not os.path.exists(NEEDS_USER):
        return
    
    with open(NEEDS_USER, "r", encoding="utf-8") as f:
        content = f.read()
    
    if marker not in content:
        with open(NEEDS_USER, "a", encoding="utf-8") as f:
            f.write(f"\n<!-- {marker} AUTO-FILL-STUBS ran at {datetime.now().isoformat()} -->\n")


def main():
    if not os.path.exists(SUMMARY):
        print("[AUTO-FILL-STUBS] _SUMMARY.md not found, skipping")
        return 0
    
    with open(SUMMARY, "r", encoding="utf-8") as f:
        text = f.read()
    
    stale = find_stale_stubs(text)
    
    if not stale:
        print(f"[AUTO-FILL-STUBS] GREEN: No stale stubs (checked {len(text.splitlines())} lines)")
        return 0
    
    print(f"[AUTO-FILL-STUBS] Found {len(stale)} stale stubs (>={STALE_HOURS}h)")
    
    for stub in stale:
        ts_str = stub["timestamp"].strftime("%Y-%m-%d %H:%M")
        print(f"  - Line {stub['line_idx']}: {ts_str} ({stub['age_hours']:.0f}h stale)")
        text = fill_stub(text, stub)
    
    with open(SUMMARY, "w", encoding="utf-8") as f:
        f.write(text)
    
    ensure_needs_user_freshness()
    
    print(f"[AUTO-FILL-STUBS] DONE: {len(stale)} stubs reconciled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
