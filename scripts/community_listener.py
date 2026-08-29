#!/usr/bin/env python3
"""
社区需求监听器（Community Listener）
扫描 HN/Reddit/知乎/ROS Discourse 的"兼容性/互换/选型"提问，
写入 demand-signal.json，生成补录建议。
目标：复活 N08/L2 职能，建立"用户反馈→数据补录"闭环。
"""
import os, sys, json, re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMAND_SIGNAL = os.path.join(ROOT, "api", "demand-signal.json")
NEEDS_USER = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")

KEYWORDS = [
    "bionic robot", "humanoid robot", "robot joint", "actuator selection",
    "CANopen", "EtherCAT", "robot compatibility", "modular robot",
    "ISO 9409", "robot gripper", "robot sensor", "harmonic reducer",
    "仿生机器人", "人形机器人", "关节选型", "执行器", "兼容性",
    "减速器", "力矩传感器", "谐波减速器", "机器人芯片",
]

SOURCES = {
    "github_issues": "https://api.github.com/search/issues?q=robot+compatibility+language:markdown&sort=updated&per_page=5",
    "ros_discourse": "https://discourse.ros.org/latest.json",
    "reddit_robots": "https://www.reddit.com/r/robotics/hot.json?limit=10",
    "reddit_embodied": "https://www.reddit.com/r/EmbodiedAI/hot.json?limit=10",
}


def load_existing_signals():
    """Load existing demand signals"""
    if not os.path.exists(DEMAND_SIGNAL):
        return {"meta": {"total": 0, "sources": []}, "signals": []}
    
    with open(DEMAND_SIGNAL, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Normalize: ensure 'signals' key exists
    if "signals" not in data:
        data["signals"] = []
    if "meta" not in data:
        data["meta"] = {"total": 0, "sources": []}
    
    return data


def scan_github_issues():
    """Scan GitHub issues for robot compatibility questions"""
    import urllib.request
    
    signals = []
    try:
        url = SOURCES["github_issues"]
        req = urllib.request.Request(url, headers={"User-Agent": "RoboParts-Listener/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        
        for item in data.get("items", [])[:5]:
            title = item.get("title", "")
            body = (item.get("body", "") or "")[:500]
            text = f"{title} {body}".lower()
            
            matched_kw = [kw for kw in KEYWORDS if kw.lower() in text]
            if matched_kw:
                signals.append({
                    "source": "github_issues",
                    "title": title[:100],
                    "url": item.get("html_url", ""),
                    "matched_keywords": matched_kw[:3],
                    "timestamp": datetime.now().isoformat(),
                    "status": "new",
                })
    except Exception as e:
        print(f"  [LISTENER] GitHub scan error: {e}")
    
    return signals


def scan_reddit(subreddit):
    """Scan a subreddit for relevant posts"""
    import urllib.request
    
    signals = []
    try:
        url = SOURCES.get(f"reddit_{subreddit}", "")
        if not url:
            return signals
        
        req = urllib.request.Request(url, headers={
            "User-Agent": "RoboParts-Listener/1.0 (educational research)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        
        for child in data.get("data", {}).get("children", [])[:5]:
            post = child.get("data", {})
            title = post.get("title", "")
            selftext = post.get("selftext", "")[:500]
            text = f"{title} {selftext}".lower()
            
            matched_kw = [kw for kw in KEYWORDS if kw.lower() in text]
            if matched_kw:
                signals.append({
                    "source": f"reddit_{subreddit}",
                    "title": title[:100],
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "matched_keywords": matched_kw[:3],
                    "timestamp": datetime.now().isoformat(),
                    "status": "new",
                })
    except Exception as e:
        print(f"  [LISTENER] Reddit r/{subreddit} scan error: {e}")
    
    return signals


def generate_suggestions(signals):
    """Generate data entry suggestions from signals"""
    suggestions = []
    
    for sig in signals:
        kws = sig.get("matched_keywords", [])
        if any(kw in ["actuator selection", "关节选型", "执行器"] for kw in kws):
            suggestions.append({
                "type": "data_entry",
                "from": sig["title"][:60],
                "action": "补录机械接口声明（ISO 9409-1 法兰）",
                "priority": "P2",
            })
        if any(kw in ["CANopen", "EtherCAT", "robot compatibility", "兼容性"] for kw in kws):
            suggestions.append({
                "type": "data_entry",
                "from": sig["title"][:60],
                "action": "补录协议兼容性声明",
                "priority": "P2",
            })
        if any(kw in ["harmonic reducer", "谐波减速器", "减速器"] for kw in kws):
            suggestions.append({
                "type": "data_entry",
                "from": sig["title"][:60],
                "action": "补录减速器品类数据",
                "priority": "P2",
            })
    
    return suggestions


def main():
    print(f"[COMMUNITY-LISTENER] Starting at {datetime.now().isoformat()}")
    
    existing = load_existing_signals()
    existing_urls = {s.get("url") for s in existing.get("signals", [])}
    
    all_signals = []
    
    # Scan GitHub
    print("[COMMUNITY-LISTENER] Scanning GitHub issues...")
    all_signals.extend(scan_github_issues())
    
    # Scan Reddit
    for sub in ["robots", "embodied"]:
        print(f"[COMMUNITY-LISTENER] Scanning Reddit r/{sub}...")
        all_signals.extend(scan_reddit(sub))
    
    # Deduplicate
    new_signals = [s for s in all_signals if s["url"] not in existing_urls]
    
    print(f"[COMMUNITY-LISTENER] Found {len(all_signals)} total, {len(new_signals)} new")
    
    # Generate suggestions
    suggestions = generate_suggestions(new_signals)
    if suggestions:
        print(f"[COMMUNITY-LISTENER] Generated {len(suggestions)} data entry suggestions")
    
    # Update demand-signal.json
    existing["signals"].extend(new_signals)
    existing["meta"]["total"] = len(existing["signals"])
    existing["meta"]["last_scan"] = datetime.now().isoformat()
    existing["meta"]["sources"] = list(set(s.get("source") for s in existing["signals"]))
    existing["meta"]["suggestions"] = suggestions
    
    with open(DEMAND_SIGNAL, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    # Log to _NEEDS_USER if significant
    if len(new_signals) >= 3:
        now = datetime.now().strftime("%Y%m%d-%H%M")
        with open(NEEDS_USER, "r", encoding="utf-8") as f:
            content = f.read()
        
        marker = f"COMMUNITY-LISTENER-{now}"
        if marker not in content:
            entry = (
                f"\n- [ ] **社区需求监听器发现 {len(new_signals)} 条新信号（{now}）**：\n"
                f"  来源：{', '.join(set(s['source'] for s in new_signals))}\n"
                f"  建议：{len(suggestions)} 条数据补录建议已写入 demand-signal.json\n"
            )
            lines = content.splitlines()
            insert_idx = 3
            for i, line in enumerate(lines):
                if line.strip() == "---":
                    insert_idx = i + 1
                    break
            lines.insert(insert_idx, entry)
            with open(NEEDS_USER, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
    
    print(f"[COMMUNITY-LISTENER] DONE: {len(existing['signals'])} total signals in demand-signal.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
