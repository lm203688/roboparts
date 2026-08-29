#!/usr/bin/env python3
"""
Offline Intelligence Gatherer
Uses only accessible APIs: GitHub, HN, arXiv
Fallback for when Reddit/Wikipedia are blocked
"""
import json, os, sys, urllib.request, urllib.error, ssl, re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNALS_FILE = os.path.join(ROOT, "api", "demand-signal.json")
CACHE_DIR = os.path.join(ROOT, "ops", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
HEADERS = {"User-Agent": "RoboParts-Intel/1.0"}


def load_signals():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"signals": [], "last_updated": None}


def save_signals(data):
    data["last_updated"] = datetime.now().isoformat()
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
    return json.loads(resp.read().decode("utf-8"))


def fetch_xml(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
    return resp.read().decode("utf-8")


# --- GitHub ---
def scan_github():
    print("[GITHUB] Scanning for robot compatibility signals...")
    signals = []
    queries = [
        "humanoid robot actuator",
        "robot joint motor selection",
        "open source robot hardware",
    ]
    for q in queries:
        try:
            url = "https://api.github.com/search/issues?q={}&sort=created&order=desc&per_page=5".format(
                q.replace(" ", "+")
            )
            data = fetch_json(url)
            for item in data.get("items", []):
                repo_url = item.get("repository_url", "")
                repo_parts = repo_url.split("/")[-2:] if repo_url else []
                signals.append({
                    "source": "github",
                    "title": item.get("title", ""),
                    "url": item.get("html_url", ""),
                    "repo": "/".join(repo_parts),
                    "created": item.get("created_at", ""),
                    "query": q,
                })
            print("  [OK] {}: {} results".format(q, len(data.get("items", []))))
        except Exception as e:
            print("  [ERR] {}: {}".format(q, str(e)[:50]))
    return signals


# --- Hacker News ---
def scan_hn():
    print("[HN] Scanning Hacker News for robot signals...")
    signals = []
    try:
        story_ids = fetch_json(
            "https://hacker-news.firebaseio.com/v0/topstories.json"
        )[:30]
        keywords = [
            "robot", "actuator", "motor", "servo", "joint",
            "knee", "humanoid", "bipedal", "manipulator",
        ]
        found = 0
        for sid in story_ids:
            try:
                story = fetch_json(
                    "https://hacker-news.firebaseio.com/v0/item/{}.json".format(sid),
                    timeout=10,
                )
                title = story.get("title", "").lower()
                if any(kw in title for kw in keywords):
                    signals.append({
                        "source": "hn",
                        "title": story.get("title", ""),
                        "url": story.get(
                            "url",
                            "https://news.ycombinator.com/item?id={}".format(sid),
                        ),
                        "score": story.get("score", 0),
                        "created": datetime.fromtimestamp(
                            story.get("time", 0)
                        ).isoformat(),
                    })
                    found += 1
            except Exception:
                continue
        print("  [OK] Scanned {} stories, {} robot-related".format(len(story_ids), found))
    except Exception as e:
        print("  [ERR] HN scan failed: {}".format(str(e)[:60]))
    return signals


# --- arXiv ---
def scan_arxiv():
    print("[ARXIV] Scanning arXiv for robot papers...")
    signals = []
    queries = [
        "cat:cs.RO AND humanoid",
        "cat:cs.RO AND actuator",
        "cat:cs.RO AND joint motor",
    ]
    for q in queries:
        try:
            url = "http://export.arxiv.org/api/query?search_query={}&max_results=3&sortBy=submittedDate&sortOrder=descending".format(
                q.replace(" ", "+")
            )
            xml = fetch_xml(url, timeout=20)
            entries = xml.split("<entry>")[1:]  # skip before first entry
            for entry in entries:
                title_match = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                link_match = re.search(r'<id>(.*?)</id>', entry)
                pub_match = re.search(r"<published>(.*?)</published>", entry)
                if title_match and link_match:
                    signals.append({
                        "source": "arxiv",
                        "title": title_match.group(1).strip().replace("\n", " "),
                        "url": link_match.group(1).strip(),
                        "created": pub_match.group(1).strip() if pub_match else "",
                        "query": q,
                    })
            print("  [OK] {}: {} papers".format(q, len(entries)))
        except Exception as e:
            print("  [ERR] {}: {}".format(q, str(e)[:50]))
    return signals


def main():
    print("[INTEL] Offline Intelligence Gatherer")
    print("[INTEL] Using accessible APIs: GitHub + HN + arXiv\n")

    all_signals = []
    all_signals.extend(scan_github())
    all_signals.extend(scan_hn())
    all_signals.extend(scan_arxiv())

    existing = load_signals()
    existing_urls = {s.get("url") for s in existing.get("signals", [])}
    new_signals = [s for s in all_signals if s["url"] not in existing_urls]

    print("\n[RESULT] {} total, {} new (not duplicate)".format(
        len(all_signals), len(new_signals)
    ))

    if new_signals:
        existing["signals"].extend(new_signals)
        existing["signals"] = existing["signals"][-200:]  # keep last 200
        save_signals(existing)
        print("[SAVED] demand-signal.json updated")

        # Save cache
        cache_file = os.path.join(
            CACHE_DIR, "intel-{}.json".format(datetime.now().strftime("%Y%m%d"))
        )
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(new_signals, f, ensure_ascii=False, indent=2)
        print("[CACHE] {}".format(cache_file))
    else:
        print("[SKIP] No new signals to save")

    return 0


if __name__ == "__main__":
    sys.exit(main())
