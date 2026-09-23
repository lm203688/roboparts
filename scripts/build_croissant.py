#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_croissant.py — 方向锚点 v2.1 Phase A1：Croissant 数据集元数据 + CITATION.cff。

定位（docs/PROJECT_DIRECTIONS_V2.md §2）：Croissant 是**副产品**（引用入口），
不占方向位。判据要求：所有计数一律由 `onboarding_block.facts()` 与 entities.json
**现算**，禁止手写副本 —— 全站数字唯一真相源纪律同样适用于本文件。

产出：
  api/croissant.json  — Croissant 1.0 风格元数据（@context 用 MLCommons 官方词表）
  CITATION.cff        — CFF 1.2.0 引用文件（不含任何计数，杜绝数字腐烂面）

诚实边界（锚点 §6.2，必须随元数据一起传播）：
  - 数据是**声明值**（厂商公开字段 + 规则推断），非实测 benchmark；
  - 兼容判定四维中未声明维度显式「无法判定」（三态诚实）；
  - 机械声明率仅 5.69%，且其低值由 (i) 未公开规格 / (ii) 自研接口 两种
    **未区分**成因构成 —— 下游引用者必须知道这一点。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from onboarding_block import facts  # noqa: E402

CROISSANT_CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "cr": "http://mlcommons.org/croissant/",
    "dct": "http://purl.org/dc/terms/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "fileObject": "cr:fileObject",
    "fileSet": "cr:fileSet",
    "recordSet": "cr:recordSet",
    "dataSource": "cr:dataSource",
    "references": "cr:references",
    "format": "cr:format",
    "dataType": "cr:dataType",
    "prov": "http://www.w3.org/ns/prov#",
    "rp": "https://roboparts.cc/vocab/croissant#",  # 本项目扩展词表（计数与诚实边界）
}

LIVE_BASE = "https://roboparts.cc"


def build():
    f = facts()
    ents = json.loads((ROOT / "api" / "entities.json").read_text(encoding="utf-8"))["entities"]

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 诚实边界里的三态：统计每个实体的机械声明形态（现算），并与 facts() 交叉校验。
    # 不一致 = 两个真相源分叉 ⇒ fail-fast（宁可崩，不可假绿 —— 本仓静默补偿教训）。
    tri_state = {"declared": 0, "partial": 0, "not_declared": 0, "n_a": 0}
    for e in ents:
        mi = (e.get("mechanical_interface") or {})
        st = mi.get("status") if isinstance(mi, dict) else None
        if st not in tri_state:
            raise SystemExit(
                f"❌ entities.json 出现未知 mechanical_interface.status={st!r} "
                f"(entity {e.get('id')}) —— 判据分叉，拒绝生成"
            )
        tri_state[st] += 1
    expected = {
        "declared": f["mech_full_declared"],
        "partial": f["mech_partial"],
        "not_declared": f["mech_not_declared"],
        "n_a": f["mech_n_a"],
    }
    if tri_state != expected:
        raise SystemExit(
            f"❌ 机械声明计数与 facts() 不一致：现算 {tri_state} vs facts {expected} —— 拒绝生成"
        )

    croissant = {
        "@context": CROISSANT_CONTEXT,
        "@type": "Dataset",
        "@id": f"{LIVE_BASE}/api/croissant.json",
        "name": "RoboParts Embodied-Components Registry",
        "description": (
            f"Vendor-neutral registry of {f['total_entities']} robotic/embodied-system entities "
            "(actuators, sensors, platforms, controllers, AI/LLM models, protocols, "
            "interfaces and market intelligence) with rule-based compatibility "
            "verdicts across protocol/electrical/mechanical/ROS2 dimensions. "
            "All verdicts are derived from manufacturer-declared public fields, "
            "NOT from physical testing: undeclared dimensions are explicitly "
            "reported as 'cannot determine' (three-state honesty). The mechanical "
            f"declaration rate is {f['mech_pct']}% (computed live), composed of two "
            "UNDISCRIMINATED causes: (i) vendors not publishing specs (true data gap) and (ii) parts "
            "using proprietary interfaces (ecosystem fragmentation, not a gap). "
            "Downstream users MUST treat this as a declaration-coverage map, "
            "not a benchmark."
        ),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "url": f"{LIVE_BASE}/api/croissant.json",
        "citeAs": "Li, Xing (2026). RoboParts Embodied-Components Registry (v2026.09). Zenodo / roboparts.cc. https://roboparts.cc/",
        "keywords": [
            "robotics", "embodied AI", "compatibility", "morphology graph",
            "provenance", "ISO 9409-1", "neuromorphic", "humanoid",
        ],
        "distribution": [
            {
                "@type": cr_type("FileObject"),
                "@id": f"{LIVE_BASE}/api/entities.json",
                "name": "entities.json",
                "contentUrl": f"{LIVE_BASE}/api/entities.json",
                "encodingFormat": "application/json",
            },
            {
                "@type": cr_type("FileObject"),
                "@id": f"{LIVE_BASE}/api/morphology_graph.json",
                "name": "morphology_graph.json",
                "contentUrl": f"{LIVE_BASE}/api/morphology_graph.json",
                "encodingFormat": "application/json",
            },
            {
                "@type": cr_type("FileObject"),
                "@id": f"{LIVE_BASE}/api/provenance.json",
                "name": "provenance.json",
                "contentUrl": f"{LIVE_BASE}/api/provenance.json",
                "encodingFormat": "application/json",
            },
        ],
        "recordSet": {
            "@type": "cr:RecordSet",
            "name": "entities",
            "description": "One record per registry entity.",
            "field": [
                {"@type": "cr:Field", "name": "id", "dataType": "sc:Text"},
                {"@type": "cr:Field", "name": "name", "dataType": "sc:Text"},
                {"@type": "cr:Field", "name": "category", "dataType": "sc:Text"},
                {"@type": "cr:Field", "name": "manufacturer", "dataType": "sc:Text"},
                {"@type": "cr:Field", "name": "mechanical_interface.status",
                 "dataType": "sc:Text",
                 "description": "full | partial | absent (three-state honesty)"},
            ],
        },
        "version": "2026.09",
        "dateModified": generated_at,
        "prov:wasGeneratedBy": {
            "@type": "prov:Activity",
            "prov:endedAtTime": generated_at,
            "description": "scripts/build_croissant.py — counts computed live from facts(), never hand-written",
        },
        "rp:counts": {
            "total_entities": f["total_entities"],
            "component_entities": f["component_entities"],
            "specification_entities": f["specification_entities"],
            "software_entities": f["software_entities"],
            "organization_entities": f["organization_entities"],
            "market_intelligence_entities": f["market_intelligence_entities"],
            "categories": len(f["category_counts"]),
            "per_category": f["category_counts"],
            "mechanical_declaration": tri_state,
        },
        "rp:honesty_limits": [
            "Declaration values, not measured benchmarks.",
            "Three-state verdicts: undeclared dimensions are 'cannot determine', never 'compatible'.",
            "Mechanical declaration rate 5.69% conflates (i) unpublished specs and "
            "(ii) proprietary interfaces; cause classification is ongoing research.",
        ],
    }
    return croissant


def cr_type(name):
    """Croissant 词表内类型：@vocab 指向 schema.org，cr: 前缀类型需显式展开。"""
    return {
        "FileObject": "cr:FileObject",
        "FileSet": "cr:FileSet",
    }[name]


def write_citation_cff():
    return """\
cff-version: 1.2.0
message: "If you use the RoboParts registry, please cite it as follows."
title: "RoboParts Embodied-Components Registry"
abstract: >-
  A vendor-neutral registry of robotic and embodied-system entities with
  rule-based, three-state compatibility verdicts (declared / partial /
  cannot-determine) across protocol, electrical, mechanical and ROS2
  dimensions, plus a morphology graph and a cross-layer provenance record.
  Verdicts derive from manufacturer-declared public fields, not measurements.
authors:
  - family-names: Li
    given-names: Xing
version: 2026.09
date-released: "2026-09-23"
license: CC-BY-4.0
repository-code: "https://github.com/lm203688/roboparts"
urls:
  - "https://roboparts.cc/"
keywords:
  - robotics
  - embodied AI
  - compatibility
  - morphology graph
  - provenance
"""


def main():
    out_api = ROOT / "api" / "croissant.json"
    out_api.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (ROOT / "CITATION.cff").write_text(write_citation_cff(), encoding="utf-8")
    print(f"✅ api/croissant.json + CITATION.cff 已生成（计数现算，@{out_api.stat().st_size}B）")


if __name__ == "__main__":
    main()
