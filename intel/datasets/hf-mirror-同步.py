#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 hf-mirror 同步 HuggingFace 数据集仓库到本地（断点续传、逐文件校验）

用法:
  python hf-mirror-同步.py <repo_id> <目标目录> [--threads 8]
示例:
  python hf-mirror-同步.py lvhaidong/LAFAN1_Retargeting_Dataset "C:\\...\\intel\\datasets\\LAFAN1_Retargeting"
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://hf-mirror.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TOKEN = os.environ.get("HF_TOKEN")


def api_tree(repo):
    url = "%s/api/datasets/%s/tree/main?recursive=true" % (BASE, repo)
    req = urllib.request.Request(url, headers=UA)
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return [(d["path"], d.get("size") or 0) for d in data if d.get("type") != "directory"]


def download(repo, dest, path, size):
    target = os.path.join(dest, path.replace("/", os.sep))
    if os.path.exists(target) and os.path.getsize(target) == size:
        return "skip", path
    os.makedirs(os.path.dirname(target), exist_ok=True)
    # 同一文件加锁：以 .part 存在与否判断是否被其他线程占用（单线程逐文件，无需锁）
    url = "%s/datasets/%s/resolve/main/%s" % (BASE, repo, urllib.parse.quote(path))
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, headers=UA)
            if TOKEN:
                req.add_header("Authorization", "Bearer " + TOKEN)
            tmp = target + ".part"
            with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(tmp) != size:
                raise IOError("size mismatch %d != %d" % (os.path.getsize(tmp), size))
            os.replace(tmp, target)
            return "ok", path
        except Exception as e:
            if attempt == 7:
                return "fail:%s" % e, path
            time.sleep(min(2 ** attempt, 60))
    return "fail", path


def main():
    repo, dest = sys.argv[1], sys.argv[2]
    threads = 8
    if "--threads" in sys.argv:
        threads = int(sys.argv[sys.argv.index("--threads") + 1])
    files = api_tree(repo)
    total = sum(s for _, s in files)
    print("repo=%s  files=%d  total=%.2f GB -> %s" % (repo, len(files), total / 1e9, dest))
    os.makedirs(dest, exist_ok=True)
    done = fail = skipped = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futures = [ex.submit(download, repo, dest, p, s) for p, s in files]
        for i, f in enumerate(futures, 1):
            status, path = f.result()
            if status == "ok":
                done += 1
            elif status == "skip":
                skipped += 1
            else:
                fail += 1
                print("FAIL %s %s" % (path, status))
            if i % 20 == 0 or i == len(files):
                print("[%d/%d] new=%d skip=%d fail=%d %.1fs" % (i, len(files), done, skipped, fail, time.time() - t0))
    # 校验
    bad = []
    for p, s in files:
        t = os.path.join(dest, p.replace("/", os.sep))
        if (not os.path.exists(t)) or os.path.getsize(t) != s:
            bad.append(p)
    print("DONE new=%d skip=%d fail=%d missing_or_bad=%d" % (done, skipped, fail, len(bad)))
    for b in bad[:10]:
        print("  BAD", b)


if __name__ == "__main__":
    main()
