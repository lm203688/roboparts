#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HF 镜像站多段并行下载（支持 Range 分段 + 断点续传 + 逐文件字节校验）

用法: python hf-mirror-多段下载.py <repo_id> <目标目录> [--parts 8]
"""
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://hf-mirror.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TOKEN = os.environ.get("HF_TOKEN")
LOCK = threading.Lock()
COUNTER = {"bytes": 0}
T0 = time.time()


def headers():
    h = dict(UA)
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    return h


def tree(repo):
    url = "%s/api/datasets/%s/tree/main?recursive=true" % (BASE, repo)
    req = urllib.request.Request(url, headers=headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return [(d["path"], d.get("size") or 0) for d in data if d.get("type") != "directory"]


def fetch_range(url, start, end, out_path):
    """下载 [start,end] 区间，若 out_path 已有内容则从中断处续传"""
    have = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    if have >= (end - start + 1):
        with LOCK:
            COUNTER["bytes"] += 0
        return
    s = start + have
    req = urllib.request.Request(url, headers=dict(headers(), **{"Range": "bytes=%d-%d" % (s, end)}))
    with urllib.request.urlopen(req, timeout=300) as r, open(out_path, "ab") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            with LOCK:
                COUNTER["bytes"] += len(chunk)


def get_one(url, path, size, parts):
    tmpdir = path + ".parts"
    os.makedirs(tmpdir, exist_ok=True)
    n = max(1, parts)
    seg = (size + n - 1) // n
    jobs = []
    for i in range(n):
        s = i * seg
        e = min(s + seg, size) - 1
        if s > e:
            continue
        jobs.append((i, s, e, os.path.join(tmpdir, "p%03d" % i)))

    def worker(job):
        i, s, e, p = job
        for attempt in range(10):
            try:
                fetch_range(url, s, e, p)
                if os.path.getsize(p) == (e - s + 1):
                    return True
            except Exception as ex:
                if attempt == 9:
                    print("  part %d fail: %s" % (i, ex))
                    return False
                time.sleep(min(2 ** attempt, 60))
        return False

    with ThreadPoolExecutor(max_workers=n) as ex:
        ok = all(ex.map(worker, jobs))
    if not ok:
        return False
    # 合并
    with open(path, "wb") as out:
        for _, _, _, p in jobs:
            with open(p, "rb") as f:
                while True:
                    b = f.read(8 << 20)
                    if not b:
                        break
                    out.write(b)
    for _, _, _, p in jobs:
        os.remove(p)
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass
    return os.path.getsize(path) == size


def main():
    repo, dest = sys.argv[1], sys.argv[2]
    parts = int(sys.argv[sys.argv.index("--parts") + 1]) if "--parts" in sys.argv else 8
    files = tree(repo)
    total = sum(s for _, s in files)
    print("repo=%s files=%d total=%.2f GB parts=%d -> %s" % (repo, len(files), total / 1e9, parts, dest))
    os.makedirs(dest, exist_ok=True)
    manifest = {p: s for p, s in files}
    with open(os.path.join(dest, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    stop = threading.Event()

    def reporter():
        last = 0
        while not stop.is_set():
            time.sleep(10)
            with LOCK:
                cur = COUNTER["bytes"]
            rate = (cur - last) / 10 / 1048576
            last = cur
            done_gb = cur / 1e9
            print("  %.2f/%.2f GB  %.2f MB/s  elapsed %.0f min" % (done_gb, total / 1e9, rate, (time.time() - T0) / 60))

    t = threading.Thread(target=reporter, daemon=True)
    t.start()

    okc = failc = 0
    for p, s in files:
        target = os.path.join(dest, p.replace("/", os.sep))
        if os.path.exists(target) and os.path.getsize(target) == s:
            print("skip %s" % p)
            with LOCK:
                COUNTER["bytes"] += s
            okc += 1
            continue
        os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
        if s == 0:
            open(target, "wb").close()
            okc += 1
            continue
        url = "%s/datasets/%s/resolve/main/%s" % (BASE, repo, urllib.parse.quote(p))
        print("start %s (%.2f GB)" % (p, s / 1e9))
        ok = get_one(url, target, s, parts)
        print("%s %s" % ("ok" if ok else "FAIL", p))
        okc += 1 if ok else 0
        failc += 0 if ok else 1

    stop.set()
    bad = [p for p, s in files if (not os.path.exists(os.path.join(dest, p.replace("/", os.sep))))
           or os.path.getsize(os.path.join(dest, p.replace("/", os.sep))) != s]
    print("DONE ok=%d fail=%d bad=%d total=%.2f GB in %.1f min" % (okc, failc, len(bad), total / 1e9, (time.time() - T0) / 60))


if __name__ == "__main__":
    main()
