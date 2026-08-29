#!/usr/bin/env python3
"""
DNS Auto-Configurator - manage Cloudflare DNS via API
Replace manual DNS changes with programmatic control
Target: auto-configure www CNAME, verify domain, fix soft-404
"""
import os, sys, json, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_cf_credentials():
    """Get Cloudflare API token and zone ID"""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "") or os.environ.get("CF_API_TOKEN", "")
    zone_id = os.environ.get("CLOUDFLARE_ZONE_ID", "")

    if not token and os.path.exists(os.path.join(ROOT, ".env.local")):
        with open(os.path.join(ROOT, ".env.local"), "r", encoding="utf-8") as f:
            for line in f:
                if "CLOUDFLARE_API_TOKEN" in line:
                    _, _, val = line.strip().partition("=")
                    if val:
                        token = val.strip()

    return token, zone_id


def cf_api(method, path, token, body=None):
    """Make a Cloudflare API call"""
    url = f"https://api.cloudflare.com/client/v4{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def check_dns_records(token, zone_id):
    """Check current DNS records for roboparts.cc"""
    if not token or not zone_id:
        return None

    result = cf_api("GET", f"/zones/{zone_id}/dns_records?name=roboparts.cc&type=CNAME", token)
    if result.get("success"):
        return result.get("result", [])
    return None


def main():
    print(f"[DNS-CONFIG] {datetime.now().isoformat()}")

    token, zone_id = get_cf_credentials()

    if not token:
        print("  [SKIP] CLOUDFLARE_API_TOKEN not set, cannot manage DNS")
        print("  To enable: set CLOUDFLARE_API_TOKEN in .env.local or environment")
        return 0

    if not zone_id:
        print("  [SKIP] CLOUDFLARE_ZONE_ID not set, cannot manage DNS")
        print("  To enable: set CLOUDFLARE_ZONE_ID in .env.local or environment")
        return 0

    print("  [CHECK] Current DNS records...")
    records = check_dns_records(token, zone_id)
    if records is None:
        print("  [WARN] Cannot read DNS records")
        return 1

    print(f"  Found {len(records)} CNAME records for roboparts.cc")
    for r in records:
        print(f"    {r.get('name')} -> {r.get('content')} (proxied: {r.get('proxied')})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
