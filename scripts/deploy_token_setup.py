#!/usr/bin/env python3
"""
Deploy Token Setup - automate Cloudflare Wrangler authentication
Instead of manual OAuth, use API token directly via environment variable
Target: eliminate manual OAuth dependency for deployment
"""
import os, sys, subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRANGLER_TOML = os.path.join(ROOT, "wrangler.toml")
ENV_LOCAL = os.path.join(ROOT, ".env.local")


def check_existing_auth():
    """Check if wrangler already has valid auth"""
    try:
        result = subprocess.run(
            ["npx", "wrangler", "whoami"],
            capture_output=True, text=True, timeout=30, cwd=ROOT
        )
        if result.returncode == 0 and "email" in result.stdout.lower():
            return True, result.stdout.strip()
    except Exception:
        pass
    return False, ""


def setup_api_token():
    """Set up Cloudflare API token via environment variable"""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        token = os.environ.get("CF_API_TOKEN", "")

    if token:
        os.environ["CLOUDFLARE_API_TOKEN"] = token
        print(f"  [SETUP] CLOUDFLARE_API_TOKEN set from environment")
        return True

    if os.path.exists(ENV_LOCAL):
        with open(ENV_LOCAL, "r", encoding="utf-8") as f:
            for line in f:
                if "CLOUDFLARE_API_TOKEN" in line or "CF_API_TOKEN" in line:
                    key, _, val = line.strip().partition("=")
                    if val:
                        os.environ[key.strip()] = val.strip()
                        print(f"  [SETUP] {key.strip()} loaded from .env.local")
                        return True

    return False


def test_deployment():
    """Test if deployment works with current auth"""
    try:
        result = subprocess.run(
            ["npx", "wrangler", "pages", "project", "list"],
            capture_output=True, text=True, timeout=30, cwd=ROOT
        )
        if result.returncode == 0:
            return True, "Auth works"
        return False, result.stderr[:200]
    except Exception as e:
        return False, str(e)[:200]


def main():
    print(f"[DEPLOY-TOKEN] {datetime.now().isoformat()}")

    has_auth, auth_info = check_existing_auth()
    if has_auth:
        print(f"  [OK] Wrangler already authenticated: {auth_info[:80]}")
        return 0

    print("  [INFO] No active Wrangler auth, trying API token...")
    if setup_api_token():
        ok, msg = test_deployment()
        if ok:
            print(f"  [OK] API token works: {msg}")
            return 0
        print(f"  [WARN] Token set but test failed: {msg}")

    print("  [ESCALATE] No valid auth available. Need one of:")
    print("    1. Set CLOUDFLARE_API_TOKEN environment variable")
    print("    2. Run 'npx wrangler login' manually once")
    print("    3. Add CF_API_TOKEN to .env.local")
    return 1


if __name__ == "__main__":
    sys.exit(main())
