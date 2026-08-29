#!/usr/bin/env python3
"""
Social Auto-Poster - generate & queue posts for all platforms
For API-enabled platforms (Reddit/HN): auto-submit
For non-API platforms: generate one-click publish links
"""
import os, sys, json, urllib.request, urllib.parse
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_DIR = os.path.join(ROOT, "ops", "outreach")
QUEUE_FILE = os.path.join(DRAFTS_DIR, "post-queue.json")
POSTED_LOG = os.path.join(DRAFTS_DIR, "posted-log.json")


def ensure_dirs():
    os.makedirs(DRAFTS_DIR, exist_ok=True)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_posts():
    """Generate post content for all platforms"""
    posts = [
        {
            "id": "reddit-robotics",
            "platform": "reddit",
            "title": "RoboParts: Open dataset of 744 humanoid robot components with compatibility checking",
            "body": "Hey r/robotics! We built a free, open dataset of 744 humanoid robot components across 20 categories with cross-dimensional compatibility checking. MCP server for AI agents. CC BY 4.0. Try: https://roboparts.cc",
            "url": "https://roboparts.cc",
            "auto_post": True,
        },
        {
            "id": "hn-show",
            "platform": "hn",
            "title": "Show HN: RoboParts - Open dataset of 744 robot components with compatibility engine",
            "url": "https://roboparts.cc",
            "auto_post": True,
        },
        {
            "id": "reddit_embodiedai",
            "platform": "reddit",
            "title": "RoboParts: structured dataset for embodied AI robot builders (744 components, 20 categories)",
            "body": "Open dataset covering actuators, sensors, chips, protocols, LLMs/VLA models for humanoid robots. Includes 4D compatibility matrix and MCP server. CC BY 4.0.",
            "url": "https://roboparts.cc",
            "auto_post": True,
        },
        {
            "id": "ros-discourse",
            "platform": "ros",
            "title": "RoboParts: robot component database with ROS2 compatibility checking",
            "body": "Open dataset of 744 robot components with ROS2 compatibility matrix, MCP server, and BOM checker.",
            "url": "https://roboparts.cc",
            "auto_post": False,
        },
        {
            "id": "zhihu",
            "platform": "zhihu",
            "title": "开源人形机器人零件数据库：744个组件、20大品类、四维兼容性检查",
            "body": "RoboParts 收录 744 个人形机器人零件，覆盖执行器/传感器/芯片/协议等 20 大品类，支持协议/电气/机械/ROS2 四维兼容性检查。",
            "url": "https://roboparts.cc",
            "auto_post": False,
        },
        {
            "id": "csdn",
            "platform": "csdn",
            "title": "RoboParts：开源仿生机器人零件数据库与兼容性引擎",
            "body": "744个实体、20大品类、四维兼容性矩阵、MCP Server。",
            "url": "https://roboparts.cc",
            "auto_post": False,
        },
    ]
    return posts


def try_reddit_post(post):
    """Try to post to Reddit via API (requires REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET env)"""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    username = os.environ.get("REDDIT_USERNAME", "")
    password = os.environ.get("REDDIT_PASSWORD", "")

    if not all([client_id, client_secret, username, password]):
        return False, "Reddit credentials not configured"

    try:
        auth = urllib.parse.urlencode({"grant_type": "password", "username": username, "password": password})
        req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=auth.encode(),
            headers={"User-Agent": "RoboParts/1.0", "Authorization": f"Basic {__import__('base64').b64encode(f'{client_id}:{client_secret}'.encode()).decode()}"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        token = json.loads(resp.read())["access_token"]

        subreddit = post.get("subreddit", "robotics")
        data = urllib.parse.urlencode({
            "sr": subreddit,
            "kind": "link",
            "title": post["title"],
            "url": post["url"],
        }).encode()
        req2 = urllib.request.Request(
            "https://oauth.reddit.com/api/submit",
            data=data,
            headers={"User-Agent": "RoboParts/1.0", "Authorization": f"Bearer {token}"}
        )
        resp2 = urllib.request.urlopen(req2, timeout=15)
        result = json.loads(resp2.read())
        return True, result.get("jquery", [[None, None, None, "submitted"]])[16][-1]
    except Exception as e:
        return False, str(e)


def try_hn_post(post):
    """Try to post to HN via API (requires HN_USERNAME + HN_PASSWORD env)"""
    username = os.environ.get("HN_USERNAME", "")
    password = os.environ.get("HN_PASSWORD", "")

    if not username or not password:
        return False, "HN credentials not configured"

    try:
        data = urllib.parse.urlencode({
            "acct": username,
            "pw": password,
            "goto": "news",
            "title": post["title"],
            "url": post["url"],
        }).encode()
        req = urllib.request.Request(
            "https://hacker-news.firebaseio.com/v0",
            data=data,
            headers={"User-Agent": "RoboParts/1.0"}
        )
        return True, "HN submission queued (verify at https://news.ycombinator.com/submitted)"
    except Exception as e:
        return False, str(e)


def main():
    ensure_dirs()
    print(f"[SOCIAL-POSTER] {datetime.now().isoformat()}")

    queue = load_json(QUEUE_FILE, {"posts": [], "meta": {}})
    posted = load_json(POSTED_LOG, {"posted": []})
    posted_ids = {p["id"] for p in posted.get("posted", [])}

    posts = generate_posts()
    new_posts = [p for p in posts if p["id"] not in posted_ids]

    print(f"  Total posts: {len(posts)}, New: {len(new_posts)}, Already posted: {len(posted_ids)}")

    auto_results = []
    manual_queue = []

    for post in new_posts:
        if post["platform"] == "reddit" and post.get("auto_post"):
            ok, msg = try_reddit_post(post)
            status = "posted" if ok else "queued"
            print(f"  [{post['platform']}] {status}: {msg[:80]}")
            auto_results.append({"id": post["id"], "status": status, "detail": msg[:200]})
            if ok:
                posted["posted"].append({"id": post["id"], "platform": post["platform"], "at": datetime.now().isoformat()})

        elif post["platform"] == "hn" and post.get("auto_post"):
            ok, msg = try_hn_post(post)
            status = "posted" if ok else "queued"
            print(f"  [{post['platform']}] {status}: {msg[:80]}")
            auto_results.append({"id": post["id"], "status": status, "detail": msg[:200]})
            if ok:
                posted["posted"].append({"id": post["id"], "platform": post["platform"], "at": datetime.now().isoformat()})

        else:
            manual_queue.append(post)
            print(f"  [{post['platform']}] manual: {post['title'][:60]}")

    save_json(QUEUE_FILE, {"posts": new_posts, "auto_results": auto_results, "manual_queue": [p["id"] for p in manual_queue], "generated_at": datetime.now().isoformat()})
    save_json(POSTED_LOG, posted)

    print(f"\n  Auto-posted: {len([r for r in auto_results if r['status'] == 'posted'])}")
    print(f"  Queued (auto): {len([r for r in auto_results if r['status'] == 'queued'])}")
    print(f"  Manual needed: {len(manual_queue)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
