#!/usr/bin/env python3
"""
Webhook Notification System - replaces agent-mail
Sends notifications to DingTalk/Feishu/WeCom/Slack webhooks
Also writes to local notification log for audit trail
"""
import os, sys, json, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTIF_LOG = os.path.join(ROOT, "ops", "results", "_notifications.json")

WEBHOOKS = {
    "dingtalk": os.environ.get("DINGTALK_WEBHOOK", ""),
    "feishu": os.environ.get("FEISHU_WEBHOOK", ""),
    "wecom": os.environ.get("WECOM_WEBHOOK", ""),
    "slack": os.environ.get("SLACK_WEBHOOK", ""),
}


def load_log():
    if os.path.exists(NOTIF_LOG):
        with open(NOTIF_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"notifications": []}


def save_log(log):
    with open(NOTIF_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def send_dingtalk(title, text):
    webhook = WEBHOOKS["dingtalk"]
    if not webhook:
        return False, "DINGTALK_WEBHOOK not set"
    payload = json.dumps({"msgtype": "markdown", "markdown": {"title": title, "text": text}}).encode()
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return True, resp.read().decode()
    except Exception as e:
        return False, str(e)


def send_feishu(title, text):
    webhook = WEBHOOKS["feishu"]
    if not webhook:
        return False, "FEISHU_WEBHOOK not set"
    payload = json.dumps({"msg_type": "interactive", "card": {"header": {"title": {"tag": "plain_text", "content": title}}, "elements": [{"tag": "markdown", "content": text}]}}).encode()
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return True, resp.read().decode()
    except Exception as e:
        return False, str(e)


def send_slack(title, text):
    webhook = WEBHOOKS["slack"]
    if not webhook:
        return False, "SLACK_WEBHOOK not set"
    payload = json.dumps({"text": f"*{title}*\n{text}"}).encode()
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return True, resp.read().decode()
    except Exception as e:
        return False, str(e)


def notify(title, text, level="info"):
    """Send notification to all configured webhooks + log locally"""
    log = load_log()
    results = {}

    senders = {"dingtalk": send_dingtalk, "feishu": send_feishu, "slack": send_slack}
    for name, sender in senders.items():
        if WEBHOOKS.get(name):
            ok, msg = sender(title, text)
            results[name] = {"ok": ok, "msg": msg[:200]}

    entry = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "text": text[:500],
        "level": level,
        "results": results,
    }
    log["notifications"].append(entry)
    if len(log["notifications"]) > 500:
        log["notifications"] = log["notifications"][-500:]
    save_log(log)

    sent = sum(1 for r in results.values() if r.get("ok"))
    print(f"[NOTIFY] {title} -> {sent}/{len(results)} channels sent")
    return sent > 0


def main():
    """Send daily digest notification"""
    from kpi_daily_report import generate_report
    report = generate_report()
    d = report["data"]
    o = report["operations"]

    title = f"RoboParts Daily Digest - {report['date']}"
    text = (
        f"## Data\n"
        f"- Entities: {d['total_entities']}\n"
        f"- OSS: {d['oss_components']}\n"
        f"- API calls: {d['api_calls']}\n\n"
        f"## Operations\n"
        f"- Runs today: {o['hourly_runs_today']}\n"
        f"- Pending items: {o['pending_user_items']}\n"
    )
    notify(title, text, level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
