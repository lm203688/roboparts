#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloudflare Pages Direct Upload（manifest 版，适配 2024+ API）。

流程：
  1. 准备 .deploy-staging：从项目根复制（排除 .git/.workbuddy/ops/node_modules 等）
  2. 计算每文件 sha256，构造 manifest
  3. POST /deployments with manifest → 拿 upload_url + deployment_id
  4. PUT 每文件到 upload_url/{path}
  5. POST /deployments/{id}/complete

用法：python scripts/_deploy_cf_pages.py
"""
from __future__ import annotations
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / ".deploy-staging"
PROJECT = "robotparts"
EXCLUDE_DIRS = {".git", ".workbuddy", "ops", "node_modules", ".deploy-staging", "ops"}

def load_env() -> tuple[str, str]:
    env_file = ROOT / ".env.local"
    tok = ""
    acct = ""
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("CLOUDFLARE_API_TOKEN="):
                tok = line.split("=", 1)[1].strip()
            elif line.startswith("CLOUDFLARE_ACCOUNT_ID="):
                acct = line.split("=", 1)[1].strip()
    tok = os.environ.get("CLOUDFLARE_API_TOKEN", tok)
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", acct)
    return tok, acct

TOKEN, ACCOUNT = load_env()
if not TOKEN or not ACCOUNT:
    raise SystemExit("!! missing CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID")

BASE = "https://api.cloudflare.com/client/v4"

def cf(method: str, path: str, data=None, headers=None):
    url = f"{BASE}{path}"
    hdrs = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
    }
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        if isinstance(data, bytes):
            body = data
        else:
            hdrs["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        r = urllib.request.urlopen(req, timeout=180)
        return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"!! CF {method} {path} → {e.code}: {err[:400]}")

# ---------- 1. 准备 staging ----------
print("[1/4] 准备 .deploy-staging ...")
if STAGING.exists():
    shutil.rmtree(STAGING)
STAGING.mkdir()

copied = 0
for item in ROOT.iterdir():
    name = item.name
    if name in EXCLUDE_DIRS or name.startswith(".deploy-"):
        continue
    dst = STAGING / name
    if item.is_dir():
        shutil.copytree(item, dst, ignore=shutil.ignore_patterns(
            ".git", ".workbuddy", "node_modules", "__pycache__", "*.pyc",
            "ops", ".deploy-staging",
        ))
        copied += 1
    elif item.is_file():
        shutil.copy2(item, dst)
        copied += 1

print(f"  复制了 {copied} 项到 staging")

# ---------- 2. 构造 manifest ----------
print("[2/4] 构造 manifest ...")
manifest = []
for root, dirs, files in os.walk(STAGING):
    for fname in files:
        full = Path(root) / fname
        rel = full.relative_to(STAGING).as_posix()
        h = hashlib.sha256(full.read_bytes()).hexdigest()
        manifest.append({"path": rel, "hash": h})

print(f"  manifest 条目 {len(manifest)}")

# ---------- 3. 创建 deployment ----------
print("[3/4] 创建 deployment ...")
r = cf("POST", f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}/deployments",
       {"branch": "main", "manifest": manifest})
if not r.get("success"):
    raise SystemExit(f"!! create deployment failed: {r}")
dep = r["result"]
dep_id = dep["id"]
upload_url = dep["upload_url"]
print(f"  deployment_id: {dep_id[:12]}")
print(f"  upload_url: {upload_url[:80]}...")

# ---------- 4. 上传文件 ----------
print(f"[4/4] 上传 {len(manifest)} 个文件 ...")
uploaded = 0
failed = 0
t0 = time.time()
for entry in manifest:
    rel = entry["path"]
    full = STAGING / rel
    if not full.exists():
        print(f"  [MISS] {rel}")
        failed += 1
        continue
    data = full.read_bytes()
    mime = mimetypes.guess_type(rel)[0] or "application/octet-stream"
    url = f"{upload_url}/{rel.lstrip('/')}"
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": mime,
    })
    try:
        urllib.request.urlopen(req, timeout=120).read()
        uploaded += 1
        if uploaded % 30 == 0:
            dt = time.time() - t0
            print(f"  uploaded {uploaded}/{len(manifest)} ({dt:.1f}s)")
    except urllib.error.HTTPError as e:
        print(f"  [FAIL] {rel}: {e.code}")
        failed += 1

print(f"  上传完成：{uploaded}/{len(manifest)} 成功，{failed} 失败")

# ---------- 5. Complete ----------
print("[5/5] Complete deployment ...")
r = cf("POST", f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}/deployments/{dep_id}/complete")
if r.get("success"):
    print(f"[OK] Deployment complete!")
    print(f"[URL] https://roboparts.cc")
else:
    print(f"[WARN] Complete response: {r}")
    sys.exit(1)
