#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ModelScope 单大文件多段并行下载（Range 分段 + 断点续传 + 合并校验）

用法: python modelscope-分段下载.py <owner/name> <repo内路径> <目标文件> [--parts 8]
"""
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def head_size(url):
    req = urllib.request.Request(url, headers=dict(UA, **{"Range": "bytes=0-0"}))
    with urllib.request.urlopen(req, timeout=60) as r:
        cr = r.headers.get("Content-Range") or ""
        if "/" in cr:
            return int(cr.split("/")[-1])
        return int(r.headers.get("Content-Length"))


def part_worker(url, start, end, path):
    want = end - start + 1
    have = os.path.getsize(path) if os.path.exists(path) else 0
    for attempt in range(12):
        have = os.path.getsize(path) if os.path.exists(path) else 0
        if have >= want:
            return True
        try:
            h = dict(UA, **{"Range": "bytes=%d-%d" % (start + have, end)})
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r, open(path, "ab") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
        except Exception:
            time.sleep(min(2 ** attempt, 30))
    return os.path.getsize(path) >= want if os.path.exists(path) else False


def main():
    repo, inner, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    parts = int(sys.argv[sys.argv.index("--parts") + 1]) if "--parts" in sys.argv else 8
    url = "https://modelscope.cn/api/v1/datasets/%s/repo?Revision=master&FilePath=%s" % (repo, urllib.parse.quote(inner))
    size = head_size(url)
    print("file=%s size=%.2f GB parts=%d -> %s" % (inner, size / 1e9, parts, dest))
    if os.path.exists(dest) and os.path.getsize(dest) == size:
        print("already complete")
        return
    pdir = dest + ".parts"
    os.makedirs(pdir, exist_ok=True)
    seg = (size + parts - 1) // parts
    jobs = []
    for i in range(parts):
        s = i * seg
        e = min(s + seg, size) - 1
        if s <= e:
            jobs.append((s, e, os.path.join(pdir, "p%03d" % i)))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=parts) as ex:
        res = list(ex.map(lambda j: part_worker(url, j[0], j[1], j[2]), jobs))
    done = sum(os.path.getsize(j[2]) for j in jobs if os.path.exists(j[2]))
    print("parts done=%s  %.2f/%.2f GB  %.1f min" % (res.count(True), done / 1e9, size / 1e9, (time.time() - t0) / 60))
    if done != size:
        print("INCOMPLETE, keep parts dir")
        return
    with open(dest, "wb") as out:
        for j in jobs:
            with open(j[2], "rb") as f:
                while True:
                    b = f.read(8 << 20)
                    if not b:
                        break
                    out.write(b)
    if os.path.getsize(dest) != size:
        print("MERGE SIZE MISMATCH")
        return
    for j in jobs:
        os.remove(j[2])
    try:
        os.rmdir(pdir)
    except OSError:
        pass
    print("DONE %s %.2f GB in %.1f min" % (dest, size / 1e9, (time.time() - t0) / 60))


if __name__ == "__main__":
    main()
