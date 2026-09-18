#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验 mcp-server 这个 npm 包「发出去之后还能跑」——即 package.json 的 files
白名单必须覆盖入口及其全部本地依赖。

为什么需要这个脚本
------------------
`app = 发布物` 与 `app = 仓库工作树` 是两个不同的东西。仓库里跑得通不代表装得上：
npm 只把 files 白名单（+ package.json/README/LICENSE 等固定项）打进 tarball，
白名单外的本地模块**不会**被带上。

20260918 实测踩到：index.js 早已 `import { dialectManager } from './dialects.js'`，
而 files 仍是 `["index.js","README.md"]` —— 发出去就是个**一装就崩**的包
（ERR_MODULE_NOT_FOUND），本地和 CI 却全绿。这个包当时从未发布过该版本，
所以缺陷一直没被外部暴露，只会在第一次发布时炸在用户那边。

根因同 FILE_MAP 那次：**手写的清单不会被强制更新**。人不会记得，让机器记。

真相源：package.json 的 files / main / bin，以及源码里的相对 import 本身。

用法
----
    python3 scripts/verify_mcp_package.py            # 校验，不符则 exit 1
    python3 scripts/verify_mcp_package.py --verbose  # 打印可达模块清单
"""

import argparse
import json
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(BASE, "mcp-server")
PKG_JSON = os.path.join(PKG_DIR, "package.json")

# 相对引用：import ... from './x.js' / import './x.js' / import('./x.js') / require('./x.js')
REL_IMPORT = re.compile(
    r"""(?:from\s*|import\s*|require\s*\(\s*)['"](\.\.?/[^'"]+)['"]"""
)

# npm 无论 files 怎么写都会带上这些固定项，不需要（也不能）列进白名单
ALWAYS_INCLUDED_SUFFIXES = ("package.json",)


def local_imports(src):
    """抽出源码里的相对 import 目标（只保留模块名，去掉 query/hash）。"""
    out = []
    for raw in REL_IMPORT.findall(src):
        target = raw.split("?")[0].split("#")[0]
        out.append(target)
    return out


def resolve(spec, from_file):
    """把 './x.js' 相对 from_file 解析成磁盘上真实存在的文件。

    ESM 要求写全扩展名，但我们仍然兜一层 .js/index.js，防止有人写成
    './dialects' —— 那种写法在 ESM 下本身就会运行时报错，这里解析不到
    即视为「依赖缺失」，同样红灯，不会静默放过。
    """
    cand = os.path.normpath(os.path.join(os.path.dirname(from_file), spec))
    for c in (cand, cand + ".js", cand + ".mjs", os.path.join(cand, "index.js")):
        if os.path.isfile(c):
            return c
    return None


def entry_points(manifest):
    """main + bin 指向的入口文件（bin 可能是字符串或对象）。"""
    entries = []
    if manifest.get("main"):
        entries.append(manifest["main"])
    b = manifest.get("bin")
    if isinstance(b, str):
        entries.append(b)
    elif isinstance(b, dict):
        entries.extend(b.values())
    if not entries:
        entries = ["index.js"]
    return entries


def tracked_files():
    """返回 git 已跟踪的 mcp-server/ 文件集合；git 不可用时返回 None（跳过该项）。

    .gitignore 里写着 `mcp-server/`，但 index.js / package.json 早在加这条规则
    **之前**就被跟踪了 —— 忽略规则不影响已跟踪文件。于是同一个目录里「老文件在
    版本库里、新文件被静默忽略」。20260918 实测：dialects.js 因此从未进仓，
    而 index.js 却在 import 它，**克隆下来直接跑不起来**。
    这与 tarball 缺文件同源（「能跑」与「被记录」是两件事），所以一并盯住。
    """
    try:
        r = subprocess.run(
            ["git", "-C", BASE, "ls-files", "mcp-server"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return {line.strip() for line in r.stdout.splitlines() if line.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(PKG_JSON):
        print(f"❌ 找不到 {os.path.relpath(PKG_JSON, BASE)}，红灯退出。")
        return 1

    with open(PKG_JSON, encoding="utf-8") as f:
        manifest = json.load(f)

    allowed = list(manifest.get("files") or [])
    if not allowed:
        print(
            "❌ package.json 没有 files 白名单 —— 此时 npm 会按默认规则打包整个目录，\n"
            "   行为随目录内容漂移。请显式声明白名单。"
        )
        return 1

    problems = []

    # 1) 白名单里的条目必须真实存在（写错文件名 = 悄悄少发一个文件）
    for rel in allowed:
        if not os.path.exists(os.path.join(PKG_DIR, rel)):
            problems.append(f"files 白名单里的 {rel} 在磁盘上不存在")

    def in_allowlist(rel_path):
        rel = rel_path.replace("\\", "/")
        if rel in ALWAYS_INCLUDED_SUFFIXES:
            return True
        for a in allowed:
            a_norm = a.replace("\\", "/").rstrip("/")
            if rel == a_norm or rel.startswith(a_norm + "/"):
                return True
        return False

    # 2) 从入口出发做可达性遍历，任何本地依赖都必须在白名单内
    reachable = []
    seen = set()
    queue = []
    for e in entry_points(manifest):
        p = os.path.join(PKG_DIR, e)
        if not os.path.isfile(p):
            problems.append(f"入口文件 {e} 不存在")
        else:
            queue.append(os.path.normpath(p))

    missing_deps = []
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        rel = os.path.relpath(cur, PKG_DIR).replace("\\", "/")
        reachable.append(rel)
        if not in_allowlist(rel):
            problems.append(
                f"{rel} 被运行时依赖，但不在 files 白名单里 —— 装包后会 ERR_MODULE_NOT_FOUND"
            )
        try:
            with open(cur, encoding="utf-8") as f:
                src = f.read()
        except OSError as ex:
            problems.append(f"读取 {rel} 失败: {ex}")
            continue
        for spec in local_imports(src):
            resolved = resolve(spec, cur)
            if resolved is None:
                missing_deps.append(f"{rel} -> {spec}")
            else:
                queue.append(resolved)

    if missing_deps:
        problems.append(
            "源码里引用了不存在的本地模块（ESM 要求写全扩展名）：\n"
            + "\n".join(f"    - {m}" for m in missing_deps)
        )

    # 3) 可达模块必须已进 git：否则仓库是「能跑但没记录」，克隆即坏
    tracked = tracked_files()
    untracked = []
    if tracked is None:
        print("⚠️  git 不可用，跳过「是否已进版本库」检查。")
    else:
        untracked = [
            rel for rel in reachable
            if f"mcp-server/{rel}" not in tracked
        ]
        if untracked:
            problems.append(
                "以下模块被运行时依赖，却没有进 git（.gitignore 的 `mcp-server/`\n"
                "    会静默吞掉该目录下**新建**的文件，克隆下来无法启动）：\n"
                + "\n".join(f"    - {u}" for u in untracked)
                + "\n    修法：git add -f mcp-server/<file>（该目录已被忽略，必须 -f）"
            )

    if args.verbose:
        print(f"包目录 mcp-server/ · files 白名单 {len(allowed)} 项")
        print(f"  {'可达模块':<28}{'白名单':<8}git")
        for rel in sorted(reachable):
            in_wl = "✓" if in_allowlist(rel) else "✗"
            in_git = "?" if tracked is None else ("✓" if f"mcp-server/{rel}" in tracked else "✗")
            print(f"  {rel:<28}{in_wl:<8}{in_git}")

    if problems:
        print("❌ MCP 包完整性校验失败：\n")
        for p in problems:
            print(f"  {p}\n")
        print("  修法：按上面每条的具体提示修（补 files 白名单 / git add -f 补进仓 /")
        print("        修 import 路径）。判据是「源码里的相对 import」本身，改完重跑本脚本。")
        return 1

    print(
        f"✓ MCP 包完整性校验通过：入口可达 {len(reachable)} 个本地模块，"
        f"全部在白名单内（files {len(allowed)} 项）。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
