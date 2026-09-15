#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOM 提交入口校验器（原名 BOM Backfill）。

── 20260915 重写：本脚本此前是第二个"造声明"的机器 ──
旧版把一张 (名称→法兰) 的硬编码表写进 ops/seed-bom.json：

    SOURCES = [
        {"name": "UR5e", "src": "Universal Robots", "flange": "ISO 9409-1-50-4-M6", "ok": True},
        ...
    ]
    entries.append({"entity_name": s["name"],
                    "source_url": s["src"],          # ← 是公司名，不是 URL
                    "mechanical_interface": {"standard": s["flange"],
                                             "status": <直接标成已声明>,
                                             "source_evidence": f"{s['src']} official documentation"}})

三个独立缺陷叠在一起：
  1) 声明不是从任何文档读出来的，是源码里写死的常量；
  2) source_url 塞的是公司名（'Universal Robots'），组织不起一次真实核验；
  3) 标为已声明 —— 而"已声明"是对外发布的判据，llms.txt / MCP / api 正被
     AI 爬虫抓走。

── 现在的职责边界 ──
  · 只做**入口结构校验**：提交条目是否有 id/category、机械声明是否带 source_url。
  · **不判定证据**：source_url 是否落在厂商官域白名单、ISO 编码是否挂出处，
    一律交给贡献层构建器 build_flywheel_layer.mjs —— 它加载共享判据模块
    scripts/mech_evidence.mjs（真相源 scripts/mech_evidence_contract.json）。
    判据只允许存在一份；Python 侧再实现一遍就是第二套口径，正是要根治的病。
  · **不产出任何条目**：没有提交就没有产出。本脚本不生成 seed-bom.json，
    只读它。旧版每次运行都覆写提交入口，等于用机器产物顶掉人的提交。
"""
import os
import sys
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_BOM = os.path.join(ROOT, "ops", "seed-bom.json")

# 贡献层构建器与共享判据（本脚本的判定外包对象，仅用于提示）
BUILDER = "scripts/build_flywheel_layer.mjs"
CONTRACT = "scripts/mech_evidence_contract.json"
CONTRACT_MODULE = "scripts/mech_evidence.mjs"


def load_truth():
    try:
        with open(os.path.join(ROOT, "api", "entities.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("meta", {}).get("mechanical_interface_coverage", {})
    except Exception:
        return {}


def load_inbox():
    """读提交入口。返回 (entries, error)。不存在 = 空入口，不是错误。"""
    if not os.path.exists(SEED_BOM):
        return [], None
    try:
        with open(SEED_BOM, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        return [], str(e)
    if isinstance(doc, list):
        return doc, None
    items = doc.get("components") or doc.get("entities") or doc.get("entries") or []
    return (items if isinstance(items, list) else []), None


def validate_structure(entry):
    """入口结构校验。只查"提交是否完整"，不查"声明是否可信"。"""
    problems = []
    if not entry.get("id"):
        problems.append("缺 id（贡献层按 id 去重并合并，无 id 无法入层）")
    if not entry.get("category"):
        problems.append("缺 category（贡献层按类目映射，无类目无法归位）")
    mech = entry.get("mechanical_interface")
    if isinstance(mech, dict) and (mech.get("standard") or mech.get("flange")):
        if not entry.get("source_url"):
            problems.append("带机械声明但缺 source_url（无出处，贡献层将拒收）")
    return problems


def main():
    print("[BOM-INBOX] %s" % datetime.now().isoformat())

    truth = load_truth()
    print("  当前真相源 fill_pct: %s%%（declared %s / partial %s / applicable %s）"
          % (truth.get("fill_pct", "?"), truth.get("declared", "?"),
             truth.get("partial", "?"), truth.get("applicable", "?")))

    entries, err = load_inbox()
    if err:
        print("  ⚠️ 提交入口解析失败: %s" % err)
        return 1
    if not entries:
        print("  提交入口为空（ops/seed-bom.json 无条目或不存在）")
        print("  ⇒ 本脚本产出 0 条。没有提交就没有声明；不代为生成。")
        return 0

    ok, bad = 0, []
    with_claim = 0
    for i, e in enumerate(entries):
        probs = validate_structure(e if isinstance(e, dict) else {})
        if probs:
            bad.append((i, e if isinstance(e, dict) else {"_raw": e}, probs))
        else:
            ok += 1
        mech = (e or {}).get("mechanical_interface") if isinstance(e, dict) else None
        if isinstance(mech, dict) and (mech.get("standard") or mech.get("flange")):
            with_claim += 1

    print("  提交条目 %d 条：结构通过 %d / 结构不合规 %d；其中带机械声明 %d 条"
          % (len(entries), ok, len(bad), with_claim))
    for i, e, probs in bad:
        print("    · #%d %s" % (i, e.get("id") or e.get("entity_name") or "<无标识>"))
        for p in probs:
            print("        - %s" % p)

    if with_claim:
        print("\n  下一步（判定不在本脚本）：")
        print("    node %s   # 加载 %s 逐条判定出处与编码" % (BUILDER, CONTRACT_MODULE))
        print("    判据真相源：%s" % CONTRACT)
    print("\n  权威产出：本脚本不生成/不改写 ops/seed-bom.json。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
