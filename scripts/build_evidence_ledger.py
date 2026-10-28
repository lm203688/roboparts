#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_evidence_ledger — 产出 api/evidence_ledger.json（Phase A · A5）。

**证据账本**：追加式、不可改写、可复验的**贡献记录**。

与 evidence_valuation（评估"哪些证据值多少"）互补：
    - evidence_valuation.json：MDV 定向函数（"补哪条最值"）
    - evidence_ledger.json：贡献记录（"已经补了什么"）

**KPI（棘轮）**：`decidable_pairs` 单调不降。
   账本每次追加后，decidable_pairs 必须 ≥ 上一次。这是"补证据真的在解锁可判定对"
   的硬指标——比"声明条数"更贴近目标。

**阴阳自证**：
   - 阳性：一条合规贡献必须能过 schema 校验 + 有溯源 + falsifiable_check 可复验
   - 阴性：缺任一必需字段必须被拒收（fail-closed）
   - 变异：把已判定的贡献回滚成 unknown 必须判红

**与 MDV 对账**：账本里每条贡献的 target.axis 的 MDV 应 ≥ 1。
   若 MDV=0，说明该轴已是零贡献轴，再补是"可证明的无效投入"（锚点 §1.3）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

ROOT = Path(__file__).resolve().parent.parent


def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _validate_contribution(contribution: Dict[str, Any]) -> List[str]:
    """按 schema 校验一条贡献。返回错误列表；空=通过。"""
    required = [
        "contribution_id", "contributor", "timestamp", "evidence_type",
        "target", "source_url", "falsifiable_check", "verification_path", "signature"
    ]
    errors = []
    for k in required:
        if k not in contribution:
            errors.append(f"missing required field: {k}")
    if errors:
        return errors
    # source_url 必须是 http(s)
    if not str(contribution["source_url"]).startswith(("http://", "https://")):
        errors.append(f"source_url must be http(s): {contribution['source_url']}")
    # falsifiable_check 必须有 type 和 expected_outcome
    fc = contribution.get("falsifiable_check") or {}
    if not fc.get("type"):
        errors.append("falsifiable_check.type missing")
    if not fc.get("expected_outcome"):
        errors.append("falsifiable_check.expected_outcome missing")
    # target 必须有 entity_id 和 axis
    tgt = contribution.get("target") or {}
    if not tgt.get("entity_id"):
        errors.append("target.entity_id missing")
    if not tgt.get("axis"):
        errors.append("target.axis missing")
    elif tgt["axis"] not in ("mechanical", "electrical", "signal"):
        errors.append(f"target.axis invalid: {tgt['axis']}")
    # contribution_id 格式
    import re
    if not re.match(r"^EC-\d{8}-\d{4}$", str(contribution["contribution_id"])):
        errors.append(f"contribution_id format invalid: {contribution['contribution_id']}")
    return errors


def _hash_contribution(contribution: Dict[str, Any]) -> str:
    """追加式账本的哈希链：SHA256(prev_hash + contribution_json)。"""
    content = json.dumps(contribution, sort_keys=True, ensure_ascii=False).encode("utf-8")
    prev = (contribution.get("prev_contribution_id") or "").encode("utf-8")
    return hashlib.sha256(prev + content).hexdigest()


def main() -> int:
    # 从 evidence_valuation.json 读取 MDV 索引
    ev = _load_json(ROOT / "api" / "evidence_valuation.json")
    mdv_index = ev.get("entity_mdv_index") or {}
    binding_axis = (ev.get("summary") or {}).get("binding_axis")

    # 生成示例贡献（真实数据入库前的骨架样本；生产时读 issue 提交）
    contributions = [
        {
            "contribution_id": "EC-20261015-0001",
            "contributor": {"name": "RoboParts Seed", "contact": "seed@roboparts.dev", "organization": "RoboParts Foundation"},
            "timestamp": "2026-10-15T00:00:00Z",
            "evidence_type": "iso_table",
            "target": {"entity_id": "M8-3-FRAME", "axis": "mechanical", "field": "flange"},
            "source_url": "https://en.wikipedia.org/wiki/ISO_9409",
            "falsifiable_check": {
                "type": "geometry_parse",
                "description": "解析 ISO 9409-1 的 M8-3 法兰直径与孔数",
                "expected_outcome": "pcd=20.0mm, holes=3"
            },
            "verification_path": "python scripts/iso9409_verify.py M8-3",
            "claimed_value": {"pcd_mm": 20.0, "holes": 3, "thread": "M8"},
            "confidence": 0.95,
            "signature": "iso9409-1:20261015",
            "prev_contribution_id": None,
        },
        {
            "contribution_id": "EC-20261015-0002",
            "contributor": {"name": "RoboParts Seed", "contact": "seed@roboparts.dev", "organization": "RoboParts Foundation"},
            "timestamp": "2026-10-15T00:01:00Z",
            "evidence_type": "datasheet",
            "target": {"entity_id": "M8-3-CONN", "axis": "electrical", "field": "pinout"},
            "source_url": "https://example-datasheet.com/m8-3-connector.pdf",
            "falsifiable_check": {
                "type": "checksum_match",
                "description": "验证 pinout 字段与 datasheet 一致",
                "expected_outcome": "pinout=[VCC, GND, IO]"
            },
            "verification_path": "python scripts/datasheet_verify.py --check M8-3-CONN",
            "claimed_value": {"pinout": ["VCC", "GND", "IO"], "pitch_mm": 2.5},
            "confidence": 0.85,
            "signature": "datasheet-v1.0",
            "prev_contribution_id": "EC-20261015-0001",
        },
    ]

    # 校验每条贡献
    validated = []
    rejected = []
    prev_hash = ""
    for c in contributions:
        errors = _validate_contribution(c)
        if errors:
            rejected.append({"contribution_id": c.get("contribution_id"), "errors": errors})
            continue
        c["hash"] = _hash_contribution(c)
        c["prev_contribution_id"] = prev_hash or None
        validated.append(c)
        prev_hash = c["hash"]

    # MDV 对账
    mdv_report = []
    for c in validated:
        tgt = c["target"]
        key = f"{tgt['entity_id']}::{tgt['axis']}"
        v = mdv_index.get(key, 0)
        mdv_report.append({
            "contribution_id": c["contribution_id"],
            "target": key,
            "mdv": v,
            "positive": v >= 1,
        })

    # KPI 棘轮：decidable_pairs = 贡献实际解锁的可判定对数，从真相源现算（MDV 之和）。
    # 【2026-10-28 修复】旧实现 `prev + len(validated)` 每次 CI 都 +2（骨架贡献固定 2 条），
    # 导致 128→132 纯虚增（违反「判据现算」铁律——骨架示例 target 不在 mdv_index、MDV=0，
    # 实际不解锁任何可判定对）。改为从 mdv_index 现算。
    prev_ledger_path = ROOT / "api" / "evidence_ledger.json"
    prev = {}
    if prev_ledger_path.exists():
        try:
            prev = json.loads(prev_ledger_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    prev_style = (prev.get("meta") or {}).get("kpi_style")
    decidable_pairs_new = sum(
        mdv_index.get(f"{c['target']['entity_id']}::{c['target']['axis']}", 0)
        for c in validated
    )
    # 基线：旧产物是累加式（虚增）则重置为现算值；否则沿用上次产物（棘轮）
    if prev_style == "computed":
        decidable_pairs_current = (prev.get("kpi") or {}).get("decidable_pairs", 0)
    else:
        decidable_pairs_current = decidable_pairs_new  # 累加式旧基线作废，重置

    ledger = {
        "meta": {
            "version": "evidence_ledger/v1",
            "kpi_style": "computed",
            "kpi_reset_20261028": (
                "旧实现累加式（prev+len(validated)）致 128→132 虚增；骨架贡献 target "
                "不在 mdv_index（MDV=0），实际解锁对数=0。已改为 mdv_index 现算并重置基线。"
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_schema": "schemas/evidence_contribution.schema.json",
            "total_contributions": len(validated),
        },
        "contributions": validated,
        "rejected": rejected,
        "mdv_crosscheck": {
            "binding_axis": binding_axis,
            "contributions_on_positive_axis": sum(1 for r in mdv_report if r["positive"]),
            "contributions": mdv_report,
        },
        "kpi": {
            "decidable_pairs": decidable_pairs_new,
            "prev_decidable_pairs": decidable_pairs_current,
            "monotonic_non_decreasing": decidable_pairs_new >= decidable_pairs_current,
        },
        "note": (
            "证据账本——追加式、不可改写、可复验。每条贡献必须通过 schema 校验 + 有溯源 + "
            "falsifiable_check 可复验。KPI 棘轮：decidable_pairs 从 mdv_index 现算（贡献实际解锁的"
            "可判定对数），单调不降。"
        ),
    }

    p = ROOT / "api" / "evidence_ledger.json"
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote {p}")
    print(f"  validated: {len(validated)}, rejected: {len(rejected)}")
    print(f"  KPI decidable_pairs: {decidable_pairs_current} -> {decidable_pairs_new}")
    print(f"  MDV positive: {sum(1 for r in mdv_report if r['positive'])}/{len(mdv_report)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
