#!/usr/bin/env python3
"""
Cloudflare Pages Direct Upload - bypasses wrangler
Uses Cloudflare API directly with the provided token
"""
import json, os, sys, subprocess, hashlib, mimetypes
from datetime import datetime
import urllib.request, urllib.error

# Load token from .env.local
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
CLOUDFLARE_API_TOKEN = ""
CLOUDFLARE_ACCOUNT_ID = ""

if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("CLOUDFLARE_API_TOKEN="):
                CLOUDFLARE_API_TOKEN = line.split("=", 1)[1]
            elif line.startswith("CLOUDFLARE_ACCOUNT_ID="):
                CLOUDFLARE_ACCOUNT_ID = line.split("=", 1)[1]

# Also check environment variables (override .env.local)
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", CLOUDFLARE_API_TOKEN)
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", CLOUDFLARE_ACCOUNT_ID)

PROJECT = "robotparts"
DEPLOY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".deploy-staging")


def api_call(method, path, data=None, headers=None):
    """Make Cloudflare API call"""
    url = "https://api.cloudflare.com/client/v4" + path
    hdrs = {
        "Authorization": "Bearer " + CLOUDFLARE_API_TOKEN,
        "Content-Type": "application/json",
    }
    if headers:
        hdrs.update(headers)

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def upload_file(project_id, file_path, relative_path):
    """Upload a single file to Cloudflare Pages"""
    url = "https://api.cloudflare.com/client/v4/accounts/{}/pages/projects/{}/upload".format(
        CLOUDFLARE_ACCOUNT_ID, project_name
    )

    # Read file
    with open(file_path, "rb") as f:
        file_data = f.read()

    # Get MIME type
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    # Create multipart form data
    boundary = "----WebKitFormBoundary" + hashlib.md5(str(datetime.now()).encode()).hexdigest()[:16]
    body = b""
    body += ("--" + boundary + "\r\n").encode()
    body += ('Content-Disposition: form-data; name="file"; filename="{}"\r\n'.format(relative_path)).encode()
    body += ("Content-Type: " + mime_type + "\r\n\r\n").encode()
    body += file_data
    body += ("\r\n--" + boundary + "--\r\n").encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + CLOUDFLARE_API_TOKEN,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def main():
    print("[DEPLOY] Cloudflare Pages Direct Upload")
    print("[DEPLOY] Token: {}...".format(CLOUDFLARE_API_TOKEN[:20]))
    print("[DEPLOY] Account: {}".format(CLOUDFLARE_ACCOUNT_ID))

    if not CLOUDFLARE_API_TOKEN:
        print("[ERROR] No CLOUDFLARE_API_TOKEN found")
        return 1

    if not CLOUDFLARE_ACCOUNT_ID:
        print("[ERROR] No CLOUDFLARE_ACCOUNT_ID found")
        return 1

    # Get project info
    print("\n[1/4] Getting project info...")
    result = api_call("GET", "/accounts/{}/pages/projects/{}".format(CLOUDFLARE_ACCOUNT_ID, PROJECT))
    if not result.get("success"):
        print("[ERROR] Failed to get project:", result.get("errors"))
        return 1
    print("[OK] Project found: {}".format(PROJECT))

    # Create deployment
    print("\n[2/4] Creating deployment...")
    result = api_call(
        "POST",
        "/accounts/{}/pages/projects/{}/deployments".format(CLOUDFLARE_ACCOUNT_ID, PROJECT),
        {"branch": "main"}
    )
    if not result.get("success"):
        print("[ERROR] Failed to create deployment:", result.get("errors"))
        return 1

    deployment = result["result"]
    deployment_id = deployment["id"]
    print("[OK] Deployment created: {}".format(deployment_id))

    # Upload files
    print("\n[3/4] Uploading files...")
    if not os.path.exists(DEPLOY_DIR):
        print("[ERROR] Deploy directory not found:", DEPLOY_DIR)
        return 1

    uploaded = 0
    for root, dirs, files in os.walk(DEPLOY_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, DEPLOY_DIR).replace("\\", "/")

            result = upload_file(deployment_id, file_path, relative_path)
            if result.get("success"):
                uploaded += 1
                if uploaded % 10 == 0:
                    print("  Uploaded {} files...".format(uploaded))
            else:
                print("  [WARN] Failed to upload:", relative_path)

    print("[OK] Uploaded {} files".format(uploaded))

    # Complete deployment
    print("\n[4/4] Completing deployment...")
    result = api_call(
        "POST",
        "/accounts/{}/pages/projects/{}/deployments/{}/complete".format(
            CLOUDFLARE_ACCOUNT_ID, PROJECT, deployment_id
        )
    )
    if result.get("success"):
        print("[OK] Deployment complete!")
        print("[URL] https://roboparts.cc")
        return 0
    else:
        print("[WARN] Completion response:", result)
        return 0


if __name__ == "__main__":
    sys.exit(main())
