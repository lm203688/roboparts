#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_designations_in_use.py — designations_in_use 现算刷新器

【为什么要有这个文件】
mechanical_interfaces.json 里的 designations_in_use 区块原是
scripts/curate_flange_registry_20260811.py 这个**一次性采编脚本**在 2026-08-11
写死的快照，此后实体库与登记表都在动，它再没重算过。2026-09-16 实测偏差：

  存盘快照                          实际现算
  total_tokens_in_use = 3           4 个在用标号
  unregistered_count = 2            0 个
  used_by_entity_ids = [ACT-028,    15 个实体（GRIP-001/002/006/007/009/012/014、
                                   SENS-047/049/31/37/852/854/855、ACT-028、
                                   BIONIC-HAND-002）

其中 unregistered_count=2 是**对外假陈述**：31.5-4-M5 与 40-4-M6 两行自
commit 11af550 起就已登记进 flange_designations（source_tier B，
Industrial Robotics Hub），且二者的 aliases 精确含实体侧写法。
成因：075e96b 那次提交同时新增了 aliases 与本区块——当时两行还不存在，
故当时判 unregistered 是对的；两行后来补上，区块没跟上。

与 api/demand-signal.json、api/semantic_index.json 同源病：**派生物一旦对外，
就必须和真相源同一时刻更新，否则它就是一份「看起来有出处」的过期快照**。
本脚本即该区块的唯一现算实现，挂入部署链 0b5。

【纪律】
- 幂等：重复运行产出字节一致（排序固定、不写部署时间戳）
- 只读 entities.json + mechanical_interfaces.json，只回写后者的 designations_in_use 区块
- 不发明标准行（L1.77：未读到 ISO 9409-1:2004 原文即不替标准发明条目）
- 保留原区块的 unregistered_policy 原文（那是 L1.77 的纪律声明，不是派生数据）
- 归一化口径与 grammar.designation_forms.normalize_rule 一致；与
  build_derived_features.py 的 join 是否同结论由回归 L1.95 交叉钉住
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
from typing import Any, Dict, Set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MECH = os.path.join(ROOT, "api", "mechanical_interfaces.json")
ENT = os.path.join(ROOT, "api", "entities.json")

# 与 grammar.designation_forms.normalize_rule 同一口径：查表用，不承载等价断言
TOK_RE = re.compile(r"^ISO9409-1-(\d+(?:\.\d+)?)-(\d+)-M(\d+)$")

# 从原区块原文迁入，保持 L1.77 纪律声明不被脚本改写
UNREGISTERED_POLICY = (
    "不为消除缺口而凭空补行。按本项目纪律（L1.77），未读到 "
    "ISO 9409-1:2004 原文即不替标准发明条目；缺口在此显式列出，"
    "待取得标准原文或 OEM 一手尺寸图后再补规范行。"
)


def normalize(s: Any) -> str:
    return re.sub(r"ISO9409-1-A", "ISO9409-1-", str(s).upper().replace(" ", ""))


def read_json(path: str) -> Any:
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def entity_tokens(ents: list) -> Dict[str, Dict[str, Set[Any]]]:
    """实体侧 ISO 9409 标号的使用面。单值/多值双吃：
    mechanical_interface.standard 既可能是字符串也可能是数组（L1.74 p4）。
    """
    out: Dict[str, Dict[str, Set[Any]]] = {}
    for e in ents:
        mi = e.get("mechanical_interface") or {}
        for key in ("standard", "flange", "tool_side", "tool_side_flange"):
            v = mi.get(key)
            if not v:
                continue
            vals = v if isinstance(v, list) else [v]
            for tok in vals:
                if not isinstance(tok, str) or "9409" not in tok:
                    continue
                slot = out.setdefault(tok, {"entity_ids": set(), "sides": set()})
                slot["entity_ids"].add(e.get("id"))
                slot["sides"].add("tool" if key.startswith("tool_side") else "robot")
    return out


def classify(tok: str, norm: str, reg_index: Dict[str, str]) -> Dict[str, Any]:
    """三态分类。bare 标准号不是「未登记缺口」，是粒度不足，二者不可混为一谈。"""
    m = TOK_RE.match(norm)
    if m:
        parsed = {"d1_mm": float(m.group(1)), "bolt_count": int(m.group(2)),
                  "thread": "M" + m.group(3)}
    else:
        parsed = None

    hit = reg_index.get(norm)
    if hit:
        status = "registered"
    elif parsed is None:
        # 只有标准号本身，没给 (PCD, 孔数, 螺纹)：厂商未声明到可判定粒度
        status = "unparseable_bare_standard"
    else:
        status = "unregistered_gap"

    return {"token_as_written": tok,
            "normalized": norm,
            "parsed": parsed,
            "registry_row": hit,
            "status": status,
            "entity_count": None,  # 调用方填
            "declared_sides": None,
            "used_by_entity_ids": None}


def build_block(reg: Dict[str, Any], ents: list) -> Dict[str, Any]:
    rows = reg.get("flange_designations") or []
    # join 索引：id 与全部 aliases 都入表
    reg_index: Dict[str, str] = {}
    for row in rows:
        rid = row.get("id")
        if not rid:
            continue
        reg_index.setdefault(normalize(rid), rid)
        for a in (row.get("aliases") or []):
            reg_index.setdefault(normalize(a), rid)

    used = entity_tokens(ents)
    entries = []
    for tok in sorted(used):
        e = classify(tok, normalize(tok), reg_index)
        e["entity_count"] = len(used[tok]["entity_ids"])
        e["declared_sides"] = sorted(used[tok]["sides"])
        e["used_by_entity_ids"] = sorted(used[tok]["entity_ids"])
        entries.append(e)

    return {
        "description": (
            "从 api/entities.json 现算：实体库正在引用的 ISO 9409-1 编码，"
            "以及每个编码在本表是否有规范行。registry_row=null 且 status=unregistered_gap "
            "即「在用但未登记」；status=unparseable_bare_standard 则是厂商未声明到可判定"
            "粒度，不是可补的缺口。"
        ),
        "computed_from": (
            "/api/entities.json → mechanical_interface.{standard,flange,tool_side,tool_side_flange}"
        ),
        "join_rule": (
            "去空格、大写、并删除尺寸段前的 'A' 前缀，即 "
            "re.sub(r'ISO9409-1-A', 'ISO9409-1-', s.upper().replace(' ', ''))"
        ),
        "total_tokens_in_use": len(entries),
        "unregistered_count": sum(1 for e in entries if e["status"] == "unregistered_gap"),
        "unparseable_bare_count": sum(1 for e in entries if e["status"] == "unparseable_bare_standard"),
        "registered_count": sum(1 for e in entries if e["status"] == "registered"),
        "entities_scanned": len(ents),
        "entities_touched": len({i for e in entries for i in e["used_by_entity_ids"]}),
        "unregistered_policy": UNREGISTERED_POLICY,
        "entries": entries,
        "regenerated_by": (
            "scripts/refresh_designations_in_use.py（挂入部署链 0b5，每次部署现算；"
            "此前由 curate_flange_registry_20260811.py 一次性写死，2026-09-16 起改现算）"
        ),
        "regeneration_note": (
            "本区块 2026-08-11 起为冻结快照：当时 31.5-4-M5 / 40-4-M6 两行尚未登记，"
            "故判 unregistered 无误；两行于 commit 11af550 补入后区块未再重算，"
            "导致对外长期声称「2 个在用编码无规范行」。api/standard-audit.json 的 "
            "4 条 unverified_mechanical_claim 亦为此快照的连带假报。"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印将写入的内容，不落盘")
    args = ap.parse_args()

    reg = read_json(MECH)
    ents_doc = read_json(ENT)
    ents = ents_doc.get("entities") or []

    block = build_block(reg, ents)
    # 空输入自检：实体库有 declared 条目时 entries 不应为空
    if not block["entries"]:
        raise SystemExit(
            "designations_in_use 为空 —— 实体库有 declared 机械声明，取数路径必然写错"
            "（空输入下平凡成立的自检等于没自检，见 L1.88）"
        )

    print(f"[designations_in_use] tokens={block['total_tokens_in_use']} "
          f"(registered={block['registered_count']} "
          f"unregistered_gap={block['unregistered_count']} "
          f"bare={block['unparseable_bare_count']}) "
          f"entities_scanned={block['entities_scanned']} "
          f"entities_touched={block['entities_touched']}")
    for e in block["entries"]:
        print(f"  {e['status']:<26} {e['token_as_written']:<22} "
              f"{e['entity_count']} entities -> {e['registry_row'] or '—'}")

    if args.dry_run:
        print("dry-run: 未写盘")
        return 0

    old = reg.get("designations_in_use")
    if old == block:
        print("unchanged（幂等）")
        return 0

    reg["designations_in_use"] = block
    with io.open(MECH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    if isinstance(old, dict):
        print(f"  刷新：tokens {old.get('total_tokens_in_use')}->{block['total_tokens_in_use']}, "
              f"unregistered {old.get('unregistered_count')}->{block['unregistered_count']}")
    else:
        print("  首次写入 designations_in_use 区块")
    print(f"written -> {os.path.relpath(MECH, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
