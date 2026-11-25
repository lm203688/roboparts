#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ModelScope 数据集同步（单流多文件并发 + 前缀过滤 + 断点续传 + 字节校验）

用法: python modelscope-同步.py <owner/name> <目标目录> [--include data/,annotation/] [--threads 8]
"""
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
LOCK = threading.Lock()
GOT = {"n": 0}
T0 = time.time()


def api(repo, root="", page=1):
    url = ("https://modelscope.cn/api/v1/datasets/%s/repo/tree"
           "?Revision=master&Root=%s&Recursive=true&PageSize=1000&PageNumber=%d"
           % (repo, urllib.parse.quote(root), page))
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        d = json.load(r)["Data"]
    return d


def listing(repo):
    out, page = [], 1
    while True:
        d = api(repo, "", page)
        files = d.get("Files") or []
        out += [(f["Path"], f.get("Size") or 0) for f in files if f.get("Type") != "tree"]
        total = d.get("TotalCount") or 0
        if len(out) >= total or not files or page > 60:
            break
        page += 1
    return out, total


def grab(url, target, size):
    tmp = target + ".part"
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    for attempt in range(8):
        try:
            headers = dict(UA)
            if have:
                headers["Range"] = "bytes=%d-" % have
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180) as r, open(tmp, "ab") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b); have += len(b)
                    with LOCK:
                        GOT["n"] += len(b)
            if os.path.getsize(tmp) == size:
                os.replace(tmp, target)
                return True
        except Exception:
            have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            time.sleep(min(2 ** attempt, 30))
    return False


def main():
    repo, dest = sys.argv[1], sys.argv[2]
    inc = []
    thr = 8
    if "--include" in sys.argv:
        inc = [s for s in sys.argv[sys.argv.index("--include") + 1].split(",") if s]
    if "--threads" in sys.argv:
        thr = int(sys.argv[sys.argv.index("--threads") + 1])

    files, total_cnt = listing(repo)
    if inc:
        files = [f for f in files if any(f[0].startswith(p) for p in inc)]
    total = sum(s for _, s in files)
    print("repo=%s  total_entries=%d  selected=%d  %.2f GB  threads=%d" % (repo, total_cnt, len(files), total / 1e9, thr), flush=True)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({p: s for p, s in files}, f, ensure_ascii=False, indent=1)

    stop = threading.Event()

    def rep():
        last = 0
        while not stop.is_set():
            time.sleep(15)
            with LOCK:
                cur = GOT["n"]
            print("  %.2f/%.2f GB  %.2f MB/s  %.0f min" % (cur / 1e9, total / 1e9, (cur - last) / 15 / 1048576, (time.time() - T0) / 60), flush=True)
            last = cur

    threading.Thread(target=rep, daemon=True).start()

    tasks = []
    for p, s in files:
        t = os.path.join(dest, p.replace("/", os.sep))
        os.makedirs(os.path.dirname(t) or dest, exist_ok=True)
        if os.path.exists(t) and os.path.getsize(t) == s:
            with LOCK:
                GOT["n"] += s
            continue
        if s == 0:
            open(t, "wb").close()
            continue
        tasks.append((p, s, t))

    ok = [0]

    def run(t):
        p, s, target = t
        url = "https://modelscope.cn/api/v1/datasets/%s/repo?Revision=master&FilePath=%s" % (repo, urllib.parse.quote(p))
        good = grab(url, target, s)
        if good:
            with LOCK:
                ok[0] += 1
        else:
            print("FAIL %s" % p, flush=True)
        return good

    with ThreadPoolExecutor(max_workers=thr) as ex:
        res = list(ex.map(run, tasks))
    stop.set()
    bad = [p for p, s in files if not os.path.exists(os.path.join(dest, p.replace("/", os.sep)))
           or os.path.getsize(os.path.join(dest, p.replace("/", os.sep))) != s]
    print("DONE ok=%d fail=%d bad=%d  %.2f GB  %.1f min" % (ok[0], res.count(False), len(bad), total / 1e9, (time.time() - T0) / 60), flush=True)


if __name__ == "__main__":
    main()
