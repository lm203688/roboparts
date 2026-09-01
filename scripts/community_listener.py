#!/usr/bin/env python3
"""
社区需求监听器（Community Listener）
扫描 HN/Reddit/知乎/ROS Discourse 的"兼容性/互换/选型"提问，
写入 demand-signal.json，生成补录建议。
目标：复活 N08/L2 职能，建立"用户反馈→数据补录"闭环。
"""
import os, sys, json, re, hashlib, subprocess, tempfile
from datetime import datetime

MAX_KEEP = 500  # 信号数组上限：超过则保留最新，防无限增长（可恢复性）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMAND_SIGNAL = os.path.join(ROOT, "api", "demand-signal.json")
NEEDS_USER = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")
FLYWHEEL_STATE = os.path.join(ROOT, "scripts", "flywheel_state.py")

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


def _sig_id(sig):
    """稳定信号 ID：source+url 的 sha1 前 16 位。

    用 ID 去重（而非裸 url）可同时覆盖「同 URL 被两个扫描器重复命中」
    的轮内重复，以及「与上轮已存信号重复」的跨轮重复 —— 二者都是幂等必需。
    """
    return hashlib.sha1(
        ("%s|%s" % (sig.get("source", ""), sig.get("url", ""))).encode("utf-8")
    ).hexdigest()[:16]


def ingest_signals(existing_signals, incoming, *, max_keep=MAX_KEEP):
    """纯函数：把本轮扫描到的信号幂等并入已有信号。

    返回 (merged, added, dropped_cap)：
      - merged      ：去重 + 截断后的信号数组（确定性顺序：按 timestamp 倒序，
                       同刻优先保留已有信号，避免新信号抢占导致抖动）
      - added       ：本轮实际新增的信号（供「发现 N 条新信号」播报/建议生成）
      - dropped_cap ：因超过 max_keep 被丢弃的旧信号数

    幂等性：同一 incoming 连续两次调用，第二次 added==0（已存在则不再加）。
    纯函数：不修改 existing_signals / incoming 入参。
    """
    existing_signals = list(existing_signals or [])
    incoming = list(incoming or [])
    existing_ids = {_sig_id(s) for s in existing_signals}
    incoming_ids = set()
    added = []
    by_id = {_sig_id(s): s for s in existing_signals}
    for s in incoming:
        sid = _sig_id(s)
        if sid in existing_ids or sid in incoming_ids:
            incoming_ids.add(sid)            # 轮内重复（同 URL 被多扫描器命中）→ 折叠
            continue
        incoming_ids.add(sid)
        by_id[sid] = s
        added.append(s)

    merged = list(by_id.values())
    dropped_cap = 0
    if max_keep and len(merged) > max_keep:
        def _ts(s):
            try:
                return s.get("timestamp") or ""
            except Exception:
                return ""
        # 倒序=最新在前；同刻 existing(0) 排在 incoming(1) 前 → 优先保留旧有
        merged.sort(key=lambda s: (_ts(s), 0 if s in existing_signals else 1),
                    reverse=True)
        dropped_cap = len(merged) - max_keep
        merged = merged[:max_keep]
    return merged, added, dropped_cap


def save_json_atomic(path, obj):
    """原子写：同目录 temp + os.replace，崩溃不留半截文件（可恢复性）。"""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


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
    all_signals = []
    
    # Scan GitHub
    print("[COMMUNITY-LISTENER] Scanning GitHub issues...")
    all_signals.extend(scan_github_issues())
    
    # Scan Reddit
    for sub in ["robots", "embodied"]:
        print(f"[COMMUNITY-LISTENER] Scanning Reddit r/{sub}...")
        all_signals.extend(scan_reddit(sub))
    
    # 幂等并入（ID 去重 + 上限截断）
    merged, added_signals, dropped_cap = ingest_signals(
        existing.get("signals", []), all_signals, max_keep=MAX_KEEP)
    existing["signals"] = merged

    print(f"[COMMUNITY-LISTENER] Found {len(all_signals)} raw, "
          f"{len(added_signals)} new, {dropped_cap} capped (total {len(merged)})")

    # Generate suggestions
    suggestions = generate_suggestions(added_signals)
    if suggestions:
        print(f"[COMMUNITY-LISTENER] Generated {len(suggestions)} data entry suggestions")

    # Update demand-signal.json（原子写，崩溃可恢复）
    existing["meta"]["total"] = len(merged)
    existing["meta"]["last_scan"] = datetime.now().isoformat()
    existing["meta"]["sources"] = list(set(s.get("source") for s in merged))
    existing["meta"]["suggestions"] = suggestions
    save_json_atomic(DEMAND_SIGNAL, existing)

    # 记录 signal 阶段状态（飞轮幂等/可恢复台账）
    try:
        subprocess.run([sys.executable, FLYWHEEL_STATE, "record", "signal",
                        "--file", DEMAND_SIGNAL, "--ok", "1"],
                       capture_output=True, timeout=30, check=False)
    except Exception:
        pass

    # Log to _NEEDS_USER if significant
    if len(added_signals) >= 3:
        now = datetime.now().strftime("%Y%m%d-%H%M")
        with open(NEEDS_USER, "r", encoding="utf-8") as f:
            content = f.read()
        
        marker = f"COMMUNITY-LISTENER-{now}"
        if marker not in content:
            entry = (
                f"\n- [ ] **社区需求监听器发现 {len(added_signals)} 条新信号（{now}）**：\n"
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


def selftest():
    """纯自测（不触网）：覆盖幂等 / 轮内去重 / 跨轮去重 / 上限 / 原子写 / 纯函数。"""
    ok, bad = 0, []

    def ck(c, m):
        nonlocal ok
        if c:
            ok += 1
            print(f"  ✅ {m}")
        else:
            bad.append(m)
            print(f"  ❌ {m}")

    base = datetime.now().isoformat()
    mk = lambda url, src="github": {"source": src, "url": url,
                                    "timestamp": base, "status": "new"}

    # 1 幂等：同输入连续两次，第二次 added==0
    e1, a1, _ = ingest_signals([], [mk("u1"), mk("u2")])
    e2, a2, _ = ingest_signals(e1, [mk("u1"), mk("u2")])
    ck(len(a1) == 2 and len(a2) == 0, "幂等：同信号二次并入 added==0")

    # 2 轮内重复（同 source+url 被扫描器返回两次）→ 折叠为 1
    _, a3, _ = ingest_signals([], [mk("u1"), mk("u1")])
    ck(len(a3) == 1, "轮内重复（同 source+url）折叠为 1 条")

    # 3 跨轮去重：已存在的不再加，新 url 仍新增
    e3, a4, _ = ingest_signals([mk("u1")], [mk("u1"), mk("u9")])
    ck(len(a4) == 1 and any(s.get("url") == "u9" for s in e3),
       "跨轮去重：已存在 u1 不再加，u9 新增")

    # 4 上限截断
    many_in = [mk("u%d" % i) for i in range(600)]
    em, _, cap = ingest_signals([], many_in, max_keep=500)
    ck(len(em) == 500 and cap == 100, "上限 max_keep=500：截断到 500 且 dropped_cap==100")

    # 5 原子写往返
    import tempfile
    tmpd = tempfile.mkdtemp()
    tmpf = os.path.join(tmpd, "demand-signal.json")
    save_json_atomic(tmpf, {"signals": em, "meta": {"total": len(em)}})
    with open(tmpf, encoding="utf-8") as f:
        back = json.load(f)
    ck(back["meta"]["total"] == 500, "原子写 → 读回一致")

    # 6 不修改入参（纯函数）
    src = [mk("x")]
    before = json.dumps(src)
    ingest_signals(src, [mk("y")])
    ck(json.dumps(src) == before, "ingest_signals 不修改入参（纯函数）")

    print(f"\n结果：{ok} 通过 / {len(bad)} 失败")
    return 1 if bad else 0


if __name__ == "__main__":
    # 与 ci_gate 对齐：调用方统一用 "--self-test"（带连字符）；
    # 同时兼容无连字符 "--selftest"，避免拼写差异导致退回 main() 跑脏数据。
    if "--self-test" in sys.argv or "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
