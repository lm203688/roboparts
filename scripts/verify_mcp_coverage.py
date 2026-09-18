#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验 mcp-server/index.js 的 FILE_MAP 覆盖了 api/entities.json 声明的全部品类。

为什么需要这个脚本
------------------
mcp-server/index.js 里的 FILE_MAP 是一张「品类 -> JSON 文件名」手写表。
它已经因此错过两次：

  * 20260805：只列 7 个品类 = 580 条，对外口径却是 688 条（+108 条不可检索）
  * 20260918：仍只列 11 个品类 = 730 条，而库内已 20 个品类 = 798 条，
             静默漏掉 68 条 —— 且漏的正是采购端最常查的 grippers(23) /
             bionic_mechanisms(17) / reducers(14)。

两次都是同一个根因：**新增品类时没有任何机制强制回头改这张表**。
人不会记得，所以让机器记：本脚本把「覆盖不全」变成红灯，而不是静默少数据。

真相源：api/entities.json 的 meta.categories / meta.category_counts。

用法
----
    python3 scripts/verify_mcp_coverage.py            # 校验，不符则 exit 1
    python3 scripts/verify_mcp_coverage.py --verbose  # 打印逐品类对账表
"""

import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_JS = os.path.join(BASE, "mcp-server", "index.js")
ENTITIES = os.path.join(BASE, "api", "entities.json")
API_DIR = os.path.join(BASE, "api")


def parse_file_map(path):
    """从 FILE_MAP 对象字面量里抽出 {category: filename}。

    刻意用正则而不是 require()：这个文件是 stdio MCP server，顶层没有副作用
    也要 1.6MB 数据依赖，无法在纯校验场景里安全 import。表本身是简单的
    'key': 'value' 形式，正则足够稳，且一旦写法变了会解析出空表 -> 直接红灯，
    不会静默通过。
    """
    with open(path, encoding="utf-8") as f:
        src = f.read()

    m = re.search(r"const\s+FILE_MAP\s*=\s*\{(.*?)\n\};", src, re.S)
    if not m:
        raise SystemExit(
            "❌ 找不到 FILE_MAP 对象字面量（写法可能变了）。"
            "请更新本脚本的正则，不要绕过校验。"
        )
    body = m.group(1)
    # 先剥掉行注释，避免注释里的 'xxx': 'yyy' 被误当条目
    body = re.sub(r"//[^\n]*", "", body)
    pairs = re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", body)
    return {k: v for k, v in pairs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    file_map = parse_file_map(SERVER_JS)
    if not file_map:
        print("❌ FILE_MAP 解析结果为空 —— 解析器或被改坏，红灯退出。")
        return 1

    with open(ENTITIES, encoding="utf-8") as f:
        meta = json.load(f).get("meta", {})
    declared = meta.get("categories") or []
    counts = meta.get("category_counts") or {}
    total = meta.get("total") or meta.get("total_entities")

    if not declared:
        print("❌ api/entities.json 的 meta.categories 为空 —— 真相源异常，红灯退出。")
        return 1

    covered = list(file_map.keys())
    missing = [c for c in declared if c not in file_map]
    extra = [c for c in covered if c not in declared]

    problems = []

    if missing:
        lost = sum(counts.get(c, 0) for c in missing)
        problems.append(
            f"FILE_MAP 漏掉 {len(missing)} 个品类，共 {lost} 条实体对 npm 用户不可检索：\n"
            + "\n".join(f"    - {c} ({counts.get(c, 0)} 条)" for c in missing)
        )

    if extra:
        problems.append(
            f"FILE_MAP 含 {len(extra)} 个真相源里没有的品类（拼写错或已下线）：\n"
            + "\n".join(f"    - {c} -> {file_map[c]}" for c in extra)
        )

    # 映射的文件必须在本地 api/ 存在；文件名与品类不同名时最容易写错
    missing_files = [
        (c, fn) for c, fn in file_map.items()
        if not os.path.exists(os.path.join(API_DIR, fn))
    ]
    if missing_files:
        problems.append(
            "FILE_MAP 指向的文件不存在：\n"
            + "\n".join(f"    - {c} -> {fn}" for c, fn in missing_files)
        )

    covered_total = sum(counts.get(c, 0) for c in covered if c in counts)

    if args.verbose:
        print("品类对账表（真相源 api/entities.json -> FILE_MAP）")
        print(f"  {'品类':<22}{'条数':>6}  覆盖")
        for c in declared:
            n = counts.get(c, 0)
            print(f"  {c:<22}{n:>6}  {'✓' if c in file_map else '✗ 缺失'}")
        print(f"  {'合计':<22}{covered_total:>6} / 声明总数 {total}")

    if problems:
        print("❌ MCP 品类覆盖校验失败：\n")
        for p in problems:
            print(f"  {p}\n")
        print("  修法：补齐 / 修正 mcp-server/index.js 的 FILE_MAP，")
        print("        真相源是 api/entities.json 的 meta.categories。")
        return 1

    if total is not None and covered_total != total:
        print(
            f"❌ 覆盖的品类条数合计 {covered_total} ≠ 声明总数 {total}。\n"
            f"   品类集合一致但计数对不上，说明 category_counts 与实体数据不同步，需先查数据层。"
        )
        return 1

    print(
        f"✓ MCP 品类覆盖校验通过：{len(covered)}/{len(declared)} 个品类，"
        f"{covered_total}/{total} 条实体全部可检索。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
