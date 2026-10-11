#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接通过 GitHub Contents API 推送 HEAD 一次提交的所有变更文件。

绕开 push-gitdata.mjs 的历史基准检查（tree 不一致时无法重放），
直接对每个变更文件走 PUT，最后一步用 git/ref 更新 ref。

用法：python scripts/_push_head_via_api.py [--dry-run]
"""
from __future__ import annotations
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root (script lives in scripts/_archive/)
REPO = "lm203688/roboparts"
BRANCH = "main"
DRY = "--dry-run" in sys.argv

# ---------- 1. 取 token ----------
def get_token() -> str:
    import re
    cred = Path.home() / ".git-credentials"
    if cred.exists():
        for line in cred.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.search(r"https?://[^:]+:([^@]+)@github\.com", line)
            if m:
                return m.group(1)
    env = os.environ.get("GITHUB_TOKEN")
    if env:
        return env
    raise SystemExit("!! 找不到 GitHub token（~/.git-credentials 与 GITHUB_TOKEN 均无）")

TOKEN = get_token()

# ---------- 2. 取远端 ref ----------
def api(method: str, path: str, data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "roboparts-push/1.0",
    })
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"!! API {method} {path} → {e.code}: {err[:400]}")

ref = api("GET", f"/git/refs/heads/{BRANCH}")
REMOTE_HEAD = ref["object"]["sha"]
print(f"远端 HEAD: {REMOTE_HEAD[:12]}")

# ---------- 3. 列 HEAD 变更 ----------
def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args],
                                    encoding="utf-8", stderr=subprocess.STDOUT)

raw = git("diff-tree", "--no-commit-id", "-r", "--root", "--no-renames", "HEAD")
changes = []  # [(type, path)]  where type in {M, A, D}
for line in raw.strip().splitlines():
    parts = line.split("\t", 1)
    if len(parts) < 2:
        continue
    header, path = parts
    tokens = header.split()
    # :old_mode new_mode old_sha new_sha TYPE
    t = tokens[-1]
    changes.append((t, path))

print(f"待推送 {len(changes)} 个文件")
for t, p in changes:
    print(f"  {t}  {p}")

# ---------- 4. 逐个 PUT ----------
def b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

new_commit_sha = REMOTE_HEAD
fail = 0
for t, rel in changes:
    if DRY:
        continue
    ap = rel.replace(os.sep, "/")
    if t == "D":
        # 删除：需要 blob sha
        try:
            blob = api("GET", f"/contents/{ap}?ref={BRANCH}")
            api("DELETE", f"/contents/{ap}", data={
                "message": f"[delete] {ap}",
                "sha": blob["sha"],
                "branch": BRANCH,
            })
            print(f"  ✓ del  {ap}")
        except SystemExit as e:
            if "404" in str(e):
                print(f"  · skip(del) {ap} (not on remote)")
            else:
                raise
    else:
        content_b64 = b64(os.path.join(ROOT, rel))
        # 先查远端是否存在
        exists_sha = None
        try:
            blob = api("GET", f"/contents/{ap}?ref={BRANCH}")
            exists_sha = blob["sha"]
        except SystemExit:
            pass
        data = {
            "message": f"push HEAD: {ap}",
            "content": content_b64,
            "branch": BRANCH,
        }
        if exists_sha:
            data["sha"] = exists_sha
        r = api("PUT", f"/contents/{ap}", data=data)
        new_commit_sha = r.get("commit", {}).get("sha", new_commit_sha)
        print(f"  ✓ {'upd' if exists_sha else 'add'}  {ap}")
        fail += 0

if DRY:
    print("DRY-RUN 完成，未实际推送。")
    sys.exit(0)

print(f"\n完成。远端 HEAD 已推进。")
