#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续推剩余的 7 个文件。

针对 IncompleteRead 问题（GitHub API GET 大文件被中断），改用
DELETE + POST 策略：DELETE 会 404 时忽略，POST 总是新增。
这样避免 GET 大文件时的网络中断风险。

用法：python scripts/_push_head_resume.py
"""
from __future__ import annotations
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "lm203688/roboparts"
BRANCH = "main"

# 剩下的 7 个文件
REMAINING = [
    "roboparts-dataset-github/data/roboparts_full.json",
    "roboparts-dataset-github/python-sdk/README.md",
    "roboparts-dataset-github/python-sdk/roboparts/__init__.py",
    "scripts/build_open_vla_binding.py",
    "scripts/build_so_lerobot.py",
    "server.json",
    "smithery.yaml",
]

def get_token() -> str:
    import re
    cred = Path.home() / ".git-credentials"
    if cred.exists():
        for line in cred.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.search(r"https?://[^:]+:([^@]+)@github\.com", line)
            if m:
                return m.group(1)
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    raise SystemExit("!! no token")

TOKEN = get_token()

def api(method: str, path: str, data=None, retries: int = 3):
    url = f"https://api.github.com/repos/{REPO}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, method=method, headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "roboparts-push/1.0",
            })
            r = urllib.request.urlopen(req, timeout=120)
            return json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError, ConnectionError, OSError) as e:
            if isinstance(e, urllib.error.HTTPError):
                err_body = e.read().decode("utf-8", errors="replace")
                if e.code == 404:
                    return {"_404": True}
                raise SystemExit(f"!! API {method} {path} → {e.code}: {err_body[:300]}")
            if attempt < retries - 1:
                print(f"    retry {attempt+1}/{retries} for {path}: {e}")
                time.sleep(2)
                continue
            raise

def push_file(rel: str) -> bool:
    ap = rel.replace(os.sep, "/")
    full = ROOT / rel
    content_b64 = base64.b64encode(full.read_bytes()).decode("ascii")
    # 策略：直接 PUT，如果 409 冲突（sha 不匹配）则先 DELETE 再 POST
    data = {
        "message": f"push HEAD: {ap}",
        "content": content_b64,
        "branch": BRANCH,
    }
    try:
        r = api("PUT", f"/contents/{ap}", data=data)
        print(f"  ✓ upd  {ap}")
        return True
    except SystemExit as e:
        if "422" in str(e) or "409" in str(e):
            # sha 不匹配（首次 PUT 不带 sha 可能失败），尝试用 GET 获取 sha
            try:
                blob = api("GET", f"/contents/{ap}?ref={BRANCH}", retries=3)
                if not blob.get("_404"):
                    data["sha"] = blob["sha"]
                    r = api("PUT", f"/contents/{ap}", data=data)
                    print(f"  ✓ upd  {ap} (with sha)")
                    return True
            except SystemExit as e2:
                print(f"  · GET failed for {ap}, fallback to DELETE+POST: {e2}")
            # 兜底：DELETE 再 POST
            try:
                del_r = api("DELETE", f"/contents/{ap}", data={
                    "message": f"[pre-delete] {ap}",
                    "branch": BRANCH,
                })
                print(f"    deleted {ap}")
            except SystemExit as e3:
                print(f"    delete skipped: {e3}")
            # POST 新增
            new_data = {
                "message": f"add {ap}",
                "content": content_b64,
                "branch": BRANCH,
            }
            r = api("POST", f"/contents/{ap}", data=new_data)
            print(f"  ✓ add  {ap}")
            return True
        raise
    except Exception as e:
        print(f"  ✗ err  {ap}: {e}")
        return False

print(f"续推 {len(REMAINING)} 个文件")
ok = 0
for rel in REMAINING:
    if push_file(rel):
        ok += 1
print(f"\n完成：{ok}/{len(REMAINING)} 成功")
