#!/usr/bin/env python3
"""Quick connectivity & loop audit"""
import json, os, sys, urllib.request, urllib.error, ssl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("ROBOPARTS AUTOMATION LOOP AUDIT")
print("=" * 70)

# 1. Network connectivity
print("\n--- NETWORK CONNECTIVITY ---")
tests = [
    ("GitHub API", "https://api.github.com"),
    ("roboparts.cc", "https://roboparts.cc"),
    ("roboparts entities.json", "https://roboparts.cc/api/entities.json"),
    ("Reddit r/robotics", "https://www.reddit.com/r/robotics.json"),
    ("Cloudflare API", "https://api.cloudflare.com/client/v4/user"),
    ("Hacker News", "https://hacker-news.firebaseio.com/v0/topstories.json"),
    ("Wikipedia API", "https://en.wikipedia.org/api/rest_v1/page/summary/Robot"),
    ("arXiv API", "http://export.arxiv.org/api/query?search_query=cat:cs.RO&max_results=1"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for name, url in tests:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoboParts-Audit/1.0"})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = resp.read(500)
        print(f"  [OK]   {name} -> {resp.status} ({len(data)} bytes)")
    except urllib.error.HTTPError as e:
        print(f"  [WARN] {name} -> HTTP {e.code}")
    except Exception as e:
        print(f"  [FAIL] {name} -> {str(e)[:60]}")

# 2. Check all output files
print("\n--- OUTPUT FILES ---")
output_files = {
    "ops/results/_STATUS.md": "Auto-refreshed status",
    "ops/results/_SUMMARY.md": "Stubs tracking",
    "ops/results/_NEEDS_USER.md": "Pending human items",
    "ops/metrics/kpi-20260820.json": "Today KPI JSON",
    "ops/metrics/kpi-20260820.md": "Today KPI Markdown",
    "ops/seed-bom.json": "Seed BOM data",
    "api/entities.json": "Truth source",
    "api/demand-signal.json": "Community signals",
}

for path, desc in output_files.items():
    full = os.path.join(ROOT, path)
    if os.path.exists(full):
        size = os.path.getsize(full)
        mtime = os.path.getmtime(full)
        import datetime
        dt = datetime.datetime.fromtimestamp(mtime)
        print(f"  [OK]   {desc}: {path} ({size}B, {dt.strftime('%m-%d %H:%M')})")
    else:
        print(f"  [MISS] {desc}: {path}")

# 3. Check scripts
print("\n--- SCRIPTS ---")
scripts = [
    "auto_fill_stubs.py", "refresh_status.py", "auto_freshness_heal.py",
    "auto_drift_heal.py", "community_listener.py", "kpi_daily_report.py",
    "bom_backfill.py", "urdf_auto_extractor.py", "social_auto_poster.py",
    "notify_webhook.py", "deploy_token_setup.py", "dns_auto_config.py",
    "payment_auto_verify.py", "orchestrator.py"
]
for s in scripts:
    p = os.path.join(ROOT, "scripts", s)
    if os.path.exists(p):
        print(f"  [OK]   {s}")
    else:
        print(f"  [MISS] {s}")

# 4. Check env vars
print("\n--- CREDENTIALS / ENV VARS ---")
envs = [
    "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ZONE_ID", "CLOUDFLARE_ACCOUNT_ID",
    "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD",
    "HN_USERNAME", "HN_PASSWORD",
    "DINGTALK_WEBHOOK", "FEISHU_WEBHOOK", "SLACK_WEBHOOK",
    "XUNHU_SECRET",
]
for e in envs:
    v = os.environ.get(e, "")
    if v:
        print(f"  [SET]  {e} = {v[:8]}...")
    else:
        print(f"  [UNSET] {e}")

print("\n" + "=" * 70)
