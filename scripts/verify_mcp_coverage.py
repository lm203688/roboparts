#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验两个 MCP 服务端的品类集合，覆盖 api/entities.json 声明的全部品类。

为什么需要这个脚本
------------------
「品类」这条线上，同一个根因已经复发三次，每次都是**手写清单不会被强制更新**：

  * 20260805  mcp-server FILE_MAP 只列 7 个品类 = 580 条，对外口径却是 688 条
  * 20260918  mcp-server FILE_MAP 仍只列 11/20，静默漏 68 条 —— 漏的正是采购端
              最常查的 grippers(23) / bionic_mechanisms(17) / reducers(14)
  * 20260918  functions/mcp.js 的 CATEGORIES 也停在 11/20，而且它是**托管端点**：
              schema enum 只放行 11 个值，凡遵守 JSON Schema 的客户端
              （Claude / Cursor / LobeHub …）根本传不进 grippers ——
              数据加载全了也没用。托管端点是 LobeHub cloudEndpoint、
              Glama、官方 Registry 与全部远程用户实际打的那个口。

三处的修法一致：把「覆盖不全」变成红灯，而不是静默少数据。
人不会记得新增品类后回头改这几张表，所以让机器记。

真相源：api/entities.json 的 meta.categories / meta.category_counts。
品类覆盖只是「能不能查」，不保证条数正确 —— 故另有一条 covered_total == total
断言，防止 category_counts 与实体数据本身不同步。

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
ENTITIES = os.path.join(BASE, "api", "entities.json")
API_DIR = os.path.join(BASE, "api")

# 两个服务端各有一份「我能提供哪些品类」的声明，都要对账：
#   stdio  —— npm 包，用户本机起进程；映射到按品类拆分的 JSON 文件
#   hosted —— Streamable HTTP，远程用户与各家目录直接打这个
STDIO_JS = os.path.join(BASE, "mcp-server", "index.js")
HOSTED_JS = os.path.join(BASE, "functions", "mcp.js")

SERVER_FILES = [
    ("stdio  (mcp-server/index.js)", STDIO_JS),
    ("hosted (functions/mcp.js)", HOSTED_JS),
]


def _src(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_file_map(path):
    """从 FILE_MAP 对象字面量里抽出 {category: filename}。

    刻意用正则而不是 import：这个文件是 stdio MCP server，顶层有副作用且依赖
    1.6MB 数据，无法在纯校验场景里安全加载。表本身是简单的 'key': 'value'，
    正则足够稳；一旦写法变了会解析出空表 -> 直接红灯，不会静默通过。
    """
    m = re.search(r"const\s+FILE_MAP\s*=\s*\{(.*?)\n\};", _src(path), re.S)
    if not m:
        raise SystemExit(
            "❌ mcp-server/index.js 里找不到 FILE_MAP 对象字面量（写法可能变了）。"
            "请更新本脚本的正则，不要绕过校验。"
        )
    body = re.sub(r"//[^\n]*", "", m.group(1))
    pairs = re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", body)
    return {k: v for k, v in pairs}


def parse_categories_array(path):
    """抽出 `const CATEGORIES = [ ... ];` 里的字符串列表。"""
    m = re.search(r"const\s+CATEGORIES\s*=\s*\[(.*?)\];", _src(path), re.S)
    if not m:
        raise SystemExit(
            "❌ functions/mcp.js 里找不到 CATEGORIES 数组字面量（写法可能变了）。"
            "请更新本脚本的正则，不要绕过校验。"
        )
    body = re.sub(r"//[^\n]*", "", m.group(1))
    return re.findall(r"['\"]([^'\"]+)['\"]", body)


def enum_references_categories(path):
    """hosted 的 tool schema 必须**直接引用** CATEGORIES，不许另抄一份 enum。

    只要 schema 写成 `enum: CATEGORIES`，改一处就同时改到对外契约；
    若有人图省事把品类再抄一遍成字面量，两份就会各自漂移。
    """
    return bool(re.search(r"enum:\s*CATEGORIES\b", _src(path)))


def find_hardcoded_category_counts(path):
    """找出文案里写死的品类数，如「等 10 个品类」。

    同一个坑的另一种形态：`api/entities.json` 真值已是 20 个品类，
    而文案仍宣布 10 个 —— 每个 agent 都会被喂一遍错误事实。
    INSTRUCTIONS_STATIC 上方早已写明「此处刻意不写任何库存数字」，
    却没管住品类数。正确做法是 `${CATEGORIES.length}` 现算。
    """
    hits = []
    for i, line in enumerate(_src(path).splitlines(), 1):
        # 排除注释行：注释里可能出现「不写死数字」这类讨论
        if line.lstrip().startswith(("//", "*", "/*")):
            continue
        for m in re.finditer(r"\d+\s*个品类", line):
            hits.append((i, m.group(0), line.strip()[:110]))
    return hits


def check_coverage(label, covered, declared, counts):
    """对一个服务端的品类集合做缺失/多余对账，返回 problem 列表。"""
    problems = []
    missing = [c for c in declared if c not in covered]
    extra = [c for c in covered if c not in declared]

    if missing:
        lost = sum(counts.get(c, 0) for c in missing)
        problems.append(
            f"{label} 漏掉 {len(missing)} 个品类，共 {lost} 条实体对外不可检索"
            f"（schema 不放行 / 数据不加载）：\n"
            + "\n".join(f"    - {c} ({counts.get(c, 0)} 条)" for c in missing)
        )
    if extra:
        problems.append(
            f"{label} 含 {len(extra)} 个真相源里没有的品类（拼写错或已下线）：\n"
            + "\n".join(f"    - {c}" for c in extra)
        )
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    file_map = parse_file_map(STDIO_JS)
    if not file_map:
        print("❌ FILE_MAP 解析结果为空 —— 解析器或被改坏，红灯退出。")
        return 1

    hosted_cats = parse_categories_array(HOSTED_JS)
    if not hosted_cats:
        print("❌ CATEGORIES 解析结果为空 —— 解析器或被改坏，红灯退出。")
        return 1

    with open(ENTITIES, encoding="utf-8") as f:
        meta = json.load(f).get("meta", {})
    declared = meta.get("categories") or []
    counts = meta.get("category_counts") or {}
    total = meta.get("total") or meta.get("total_entities")

    if not declared:
        print("❌ api/entities.json 的 meta.categories 为空 —— 真相源异常，红灯退出。")
        return 1

    problems = []

    # ---- 1. 两个服务端的品类集合都要等于真相源 ----
    problems += check_coverage("stdio", list(file_map.keys()), declared, counts)
    problems += check_coverage("hosted", hosted_cats, declared, counts)

    # ---- 2. schema enum 必须引用 CATEGORIES，而不是另抄一份 ----
    if not enum_references_categories(HOSTED_JS):
        problems.append(
            "hosted 的 tool schema 不再直接引用 CATEGORIES（找不到 `enum: CATEGORIES`）。\n"
            "    另抄一份字面量会让 schema 与 CATEGORIES 各自漂移 —— "
            "请改回 `enum: CATEGORIES`。"
        )

    # ---- 3. 文案里不许写死品类数 ----
    for label, path in SERVER_FILES:
        hits = find_hardcoded_category_counts(path)
        if hits:
            problems.append(
                f"{label} 文案里写死了品类数（真值 {len(declared)} 个）：\n"
                + "\n".join(f"    L{ln}: 「{txt}」 — {ctx}" for ln, txt, ctx in hits)
                + "\n    改用 `${CATEGORIES.length}` 现算，别让静态数字继续失修。"
            )

    # ---- 4. stdio 映射的文件必须真实存在（品类与文件名不同名时最易写错）----
    missing_files = [
        (c, fn) for c, fn in file_map.items()
        if not os.path.exists(os.path.join(API_DIR, fn))
    ]
    if missing_files:
        problems.append(
            "stdio 的 FILE_MAP 指向的文件不存在：\n"
            + "\n".join(f"    - {c} -> {fn}" for c, fn in missing_files)
        )

    if args.verbose:
        print("品类对账表（真相源 api/entities.json）")
        print(f"  {'品类':<22}{'条数':>6}  {'stdio':>7}{'hosted':>8}")
        for c in declared:
            print(
                f"  {c:<22}{counts.get(c, 0):>6}  "
                f"{'✓' if c in file_map else '✗':>7}{'✓' if c in hosted_cats else '✗':>8}"
            )
        print(f"  {'合计':<22}{total:>6}  —— 声明 {len(declared)} 个品类")

    if problems:
        print("❌ MCP 品类覆盖校验失败：\n")
        for p in problems:
            print(f"  {p}\n")
        print("  修法：补齐 / 修正对应服务端的品类声明，")
        print("        真相源是 api/entities.json 的 meta.categories。")
        return 1

    # ---- 5. 覆盖条数必须等于声明总数（防 category_counts 与实体数据不同步）----
    covered_total = sum(counts.get(c, 0) for c in file_map if c in counts)
    if total is not None and covered_total != total:
        print(
            f"❌ stdio 覆盖的品类条数合计 {covered_total} ≠ 声明总数 {total}。\n"
            f"   品类集合一致但计数对不上，说明 category_counts 与实体数据不同步，需先查数据层。"
        )
        return 1

    print(
        f"✓ MCP 品类覆盖校验通过：stdio {len(file_map)}/{len(declared)}、"
        f"hosted {len(hosted_cats)}/{len(declared)} 个品类，"
        f"{covered_total}/{total} 条实体对外可检索；文案无写死品类数。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
