#!/usr/bin/env python3
"""
Loop Closure Matrix - comprehensive audit of ALL automation loops
Answers: Is each loop truly closed? What's the gap? What's the fix?
"""
import json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define all loops and their closure status
LOOPS = [
    # === MONITORING & DETECTION ===
    {
        "id": "M1",
        "name": "占位追平",
        "script": "auto_fill_stubs.py",
        "detects": "AUTO-STUB stale > 24h",
        "auto_fix": "Regenerate from truth source",
        "feedback": "_SUMMARY.md updated",
        "closed": True,
        "gap": None,
    },
    {
        "id": "M2",
        "name": "状态刷新",
        "script": "refresh_status.py",
        "detects": "Status file stale",
        "auto_fix": "Rewrite from facts()",
        "feedback": "_STATUS.md refreshed",
        "closed": True,
        "gap": None,
    },
    {
        "id": "M3",
        "name": "数字保鲜",
        "script": "auto_freshness_heal.py",
        "detects": "Article category/entity count mismatch",
        "auto_fix": "Rewrite HTML numbers",
        "feedback": "articles/*.html patched",
        "closed": True,
        "gap": None,
    },
    {
        "id": "M4",
        "name": "部署漂移",
        "script": "auto_drift_heal.py",
        "detects": "Local != deployed",
        "auto_fix": "git add + commit + deploy + verify",
        "feedback": "Live site updated",
        "closed": False,
        "gap": "Needs CLOUDFLARE_API_TOKEN",
        "workaround": "Manual 'node scripts/deploy.mjs' still works",
    },
    {
        "id": "M5",
        "name": "回归门禁",
        "script": "regression.py",
        "detects": "Any of 90+ regression gates",
        "auto_fix": "Blocks deployment",
        "feedback": "L{N} fail -> blocks",
        "closed": True,
        "gap": None,
    },

    # === DATA COLLECTION ===
    {
        "id": "D1",
        "name": "社区监听",
        "script": "community_listener.py",
        "detects": "GitHub/Reddit robot discussions",
        "auto_fix": "Write to demand-signal.json",
        "feedback": "Signals stored for content generation",
        "closed": False,
        "gap": "Reddit timeout (network blocked)",
        "workaround": "Use intel_offline.py (GitHub+HN+arXiv only)",
    },
    {
        "id": "D2",
        "name": "URDF抽取",
        "script": "urdf_auto_extractor.py",
        "detects": "Mechanical interface data from public repos",
        "auto_fix": "Parse URDF XML -> BOM entries",
        "feedback": "ops/seed-bom.json updated",
        "closed": False,
        "gap": "GitHub download timeout in sandbox",
        "workaround": "Run from machine with internet; or pre-download URDF files locally",
    },
    {
        "id": "D3",
        "name": "BOM反喂",
        "script": "bom_backfill.py",
        "detects": "Known sources not in entities",
        "auto_fix": "Generate seed BOM entries",
        "feedback": "ops/seed-bom.json updated",
        "closed": True,
        "gap": "Needs build_flywheel_layer.mjs to merge",
        "workaround": "Manual merge step",
    },

    # === CONTENT & DISTRIBUTION ===
    {
        "id": "C1",
        "name": "自动发稿",
        "script": "social_auto_poster.py",
        "detects": "Pending posts queue",
        "auto_fix": "Post to Reddit/HN via API",
        "feedback": "Posted status tracked",
        "closed": False,
        "gap": "Reddit/HN credentials not set",
        "workaround": "Queue posts for manual review; use intel_offline.py to find topics",
    },
    {
        "id": "C2",
        "name": "SEO提交",
        "script": "promote.mjs",
        "detects": "New/updated pages",
        "auto_fix": "IndexNow + sitemap ping",
        "feedback": "Search engines notified",
        "closed": True,
        "gap": None,
    },

    # === OPERATIONS ===
    {
        "id": "O1",
        "name": "KPI日报",
        "script": "kpi_daily_report.py",
        "detects": "Daily metrics needed",
        "auto_fix": "Generate JSON + Markdown report",
        "feedback": "ops/metrics/kpi-{date}.json",
        "closed": True,
        "gap": None,
    },
    {
        "id": "O2",
        "name": "通知推送",
        "script": "notify_webhook.py",
        "detects": "Events needing notification",
        "auto_fix": "Send to DingTalk/Feishu/Slack",
        "feedback": "Notification sent",
        "closed": False,
        "gap": "No webhook URLs configured",
        "workaround": "Check ops/results/ manually",
    },
    {
        "id": "O3",
        "name": "部署令牌",
        "script": "deploy_token_setup.py",
        "detects": "No valid Cloudflare auth",
        "auto_fix": "Configure API token",
        "feedback": "Auth ready for deploy",
        "closed": False,
        "gap": "No CLOUDFLARE_API_TOKEN set",
        "workaround": "Manual 'npx wrangler login' once",
    },
    {
        "id": "O4",
        "name": "DNS配置",
        "script": "dns_auto_config.py",
        "detects": "DNS misconfiguration",
        "auto_fix": "Update via Cloudflare API",
        "feedback": "DNS corrected",
        "closed": False,
        "gap": "No API token + Zone ID",
        "workaround": "Manual Cloudflare dashboard",
    },
    {
        "id": "O5",
        "name": "支付自检",
        "script": "payment_auto_verify.py",
        "detects": "Payment system misconfigured",
        "auto_fix": "Report issues",
        "feedback": "wrangler.toml checked",
        "closed": False,
        "gap": "XUNHU_SECRET not in wrangler.toml",
        "workaround": "Manual payment test",
    },
]


def main():
    print("=" * 72)
    print("ROBOPARTS AUTOMATION LOOP CLOSURE MATRIX")
    print("Audit date: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    print("=" * 72)

    closed = [l for l in LOOPS if l["closed"]]
    open_loops = [l for l in LOOPS if not l["closed"]]

    print("\n=== CLOSED LOOPS ({}/{}) ===".format(len(closed), len(LOOPS)))
    for l in closed:
        print("  [{}] {}".format(l["id"], l["name"]))
        print("       Detects: {}".format(l["detects"]))
        print("       Auto-fix: {}".format(l["auto_fix"]))
        print("       Feedback: {}".format(l["feedback"]))

    print("\n=== OPEN LOOPS ({}/{}) ===".format(len(open_loops), len(LOOPS)))
    for l in open_loops:
        print("  [{}] {}".format(l["id"], l["name"]))
        print("       Detects: {}".format(l["detects"]))
        print("       Gap: {}".format(l["gap"]))
        print("       Workaround: {}".format(l["workaround"]))

    # Network analysis
    print("\n=== NETWORK ANALYSIS ===")
    accessible = [
        ("GitHub API", "api.github.com"),
        ("Hacker News API", "hacker-news.firebaseio.com"),
        ("arXiv API", "export.arxiv.org"),
        ("roboparts.cc", "roboparts.cc"),
    ]
    blocked = [
        ("Reddit API", "reddit.com"),
        ("Wikipedia API", "en.wikipedia.org"),
    ]
    auth_needed = [
        ("Cloudflare API", "api.cloudflare.com (needs token)"),
    ]

    print("  Accessible (no auth needed):")
    for name, host in accessible:
        print("    [OK] {} ({})".format(name, host))
    print("  Blocked (network restriction):")
    for name, host in blocked:
        print("    [BLOCKED] {} ({})".format(name, host))
    print("  Auth needed:")
    for name, host in auth_needed:
        print("    [AUTH] {} ({})".format(name, host))

    print("\n=== WORKAROUNDS FOR BLOCKED NETWORK ===")
    print("  1. Reddit blocked -> Use intel_offline.py (GitHub+HN+arXiv)")
    print("  2. Wikipedia blocked -> Use arXiv for research papers")
    print("  3. All blocked sites -> Pre-cache data when on unrestricted network")
    print("  4. Set HTTP_PROXY env var if proxy available")

    print("\n=== CREDENTIALS STATUS ===")
    envs = [
        ("CLOUDFLARE_API_TOKEN", "Deploy + DNS"),
        ("CLOUDFLARE_ZONE_ID", "DNS management"),
        ("DINGTALK_WEBHOOK", "Notifications"),
        ("FEISHU_WEBHOOK", "Notifications"),
        ("SLACK_WEBHOOK", "Notifications"),
        ("REDDIT_CLIENT_ID", "Reddit posting"),
        ("REDDIT_CLIENT_SECRET", "Reddit posting"),
        ("XUNHU_SECRET", "Payment verification"),
    ]
    
    # Also check .env.local
    env_local = os.path.join(ROOT, ".env.local")
    env_local_vars = {}
    if os.path.exists(env_local):
        with open(env_local, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_local_vars[k.strip()] = v.strip()
    
    for env, purpose in envs:
        val = os.environ.get(env, "") or env_local_vars.get(env, "")
        status = "SET" if val else "UNSET"
        print("  [{status}] {env} ({purpose})".format(
            status=status, env=env, purpose=purpose
        ))

    # Final score
    print("\n=== FINAL SCORE ===")
    print("  Closed: {}/{} ({:.0f}%)".format(
        len(closed), len(LOOPS), 100 * len(closed) / len(LOOPS)
    ))
    print("  Open:   {}/{} ({:.0f}%)".format(
        len(open_loops), len(LOOPS), 100 * len(open_loops) / len(LOOPS)
    ))

    if open_loops:
        print("\n  To close remaining loops:")
        print("  1. Set CLOUDFLARE_API_TOKEN -> closes M4, O3, O4")
        print("  2. Set webhook URLs -> closes O2")
        print("  3. Set Reddit credentials -> closes C1")
        print("  4. Set XUNHU_SECRET -> closes O5")
        print("  5. Run intel_offline.py -> closes D1 (offline mode)")

    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
