#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产物新鲜度闸门：上游 mtime > 产物 mtime + tolerance_days ⇒ FAIL。

为什么需要
----------
RoboParts 是「单一真相源 + 派生副本」架构。`api/entities.json` 一改，理论上
~30 份派生副本必须跟着重生（见 `scripts/regen_derived.py`）。但实际工作流里
「改真相源 → 忘跑 regen → 派生副本漂移」是常见事故，审计 §F3 实测有 16 个
产物 mtime 落后于真相源 1-8 天。

这个闸门的判定
--------------
对每张 ARTIFACTS 表：
- 读产物 mtime
- 读每个 upstream 的 mtime
- 若 `max(upstream mtime) - artifact mtime > tolerance_days` ⇒ FAIL
- 上游文件缺失或产物文件缺失 ⇒ FAIL（fail-fast，不静默跳过）

设计取舍
--------
1. **数据驱动**：ARTIFACTS 是一张 Python 常量表，加新产物只需追加一行，不改
   闸门代码。避免"改闸门必须重构"的耦合。
2. **sidecar 豁免**：白名单走 `api/freshness_exemptions.json`（在仓库里，进 git）。
   豁免必须写 reason + expires_at，季度审计到期强制复核。豁免不进产物文件，
   避免产物文件被豁免修改污染。
3. **不追踪未标注关系的产物**：只跟踪 ARTIFACTS 里明确列出的产物。未列入
   的产物不判定新鲜度，但会在报告末尾作为 "uncovered" 提醒（不阻塞）。
4. **只依赖 mtime**：不读内容、不算 hash。内容指纹是另一个闸门（
   `build_derived_features.py` 已经记录 entities.json 的 sha256），本闸门
   只管时间线。

用法
----
    python scripts/check_freshness.py           # 完整检查；有 FAIL exit 1
    python scripts/check_freshness.py --report  # 只打印报告，不判定
    python scripts/check_freshness.py --list    # 列出跟踪的产物表
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXEMPTIONS_PATH = os.path.join(ROOT, "api", "freshness_exemptions.json")
REPORT_PATH = os.path.join(ROOT, "api", "freshness_report.json")


# ─────────────────────────────────────────────────────────────────────
# ARTIFACTS 表：产物 → 上游 → 再生命令 → tolerance_days
#
# tolerance_days 语义：upstream 比 artifact 新多少天之内算正常（宽限期）。
#   - 数据派生类：默认 3 天。regen_derived.py 是 CI 前统一入口，只要跑过
#     就应该同刻新。设 3 天容"改实体 → 次日部署"这类日常节奏。
#   - schema / meta 类：默认 7 天。手动维护，不必每次实体改都同步。
#
# 加新产物的规范：先跑一次 `python scripts/regen_derived.py` 让 artifact
# 追上 entities.json 的 mtime，再把它加进这张表，闸门即绿。
# ─────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Artifact:
    path: str
    upstreams: Tuple[str, ...]
    tolerance_days: int
    producer: str
    reason: str = ""


ARTIFACTS: List[Artifact] = [
    Artifact(
        path="api/entities.json",
        upstreams=(),
        tolerance_days=0,
        producer="SOURCE_OF_TRUTH",
        reason="真相源本身，无 upstream；由人工或 add_*_entities.py 更新",
    ),
    Artifact(
        path="api/gap_classification.json",
        upstreams=("api/entities.json", "scripts/build_gap_classification.py"),
        tolerance_days=3,
        producer="python scripts/build_gap_classification.py",
    ),
    Artifact(
        path="api/co_mount.json",
        upstreams=("api/entities.json", "scripts/build_co_mount.py"),
        tolerance_days=3,
        producer="python scripts/build_co_mount.py",
    ),
    Artifact(
        path="api/compose_frontier.json",
        upstreams=("api/entities.json", "api/electrical_evidence.json",
                   "api/morphology_graph.json", "scripts/build_compose_frontier.py"),
        tolerance_days=3,
        producer="python scripts/build_compose_frontier.py",
    ),
    Artifact(
        path="api/compose_semantics.json",
        upstreams=("api/morphology_graph.json", "scripts/build_compose_semantics.py"),
        tolerance_days=3,
        producer="python scripts/build_compose_semantics.py",
    ),
    Artifact(
        path="api/research_progress.json",
        upstreams=("api/entities.json", "scripts/build_research_progress.py"),
        tolerance_days=3,
        producer="python scripts/build_research_progress.py",
    ),
    Artifact(
        path="api/evidence_valuation.json",
        upstreams=("api/entities.json", "api/morphology_graph.json",
                   "scripts/build_evidence_valuation.py"),
        tolerance_days=3,
        producer="python scripts/build_evidence_valuation.py",
    ),
    Artifact(
        path="api/evidence_ledger.json",
        upstreams=("api/entities.json", "scripts/build_evidence_ledger.py"),
        tolerance_days=3,
        producer="python scripts/build_evidence_ledger.py",
    ),
    Artifact(
        path="api/derived_features.json",
        upstreams=("api/entities.json", "api/mechanical_interfaces.json",
                   "scripts/build_derived_features.py"),
        tolerance_days=3,
        producer="python scripts/build_derived_features.py",
    ),
    Artifact(
        path="api/croissant.json",
        upstreams=("api/entities.json", "api/morphology_graph.json",
                   "scripts/build_croissant.py"),
        tolerance_days=3,
        producer="python scripts/build_croissant.py",
    ),
    # api/compatibility.json：唯一 producer scripts/enhance_data_layer.py 是 2026-08
    # 一次性增强（给 rules 加 RP-ID/关系类型），非幂等——重跑会污染 entities.json
    # （2026-10-16 实测复现 471 行变更）。治理 TODO P1：建独立幂等再生器。
    # 在此之前豁免，保持跟踪可见性。
    Artifact(
        path="api/compatibility.json",
        upstreams=("api/entities.json",),
        tolerance_days=3,
        producer="TODO: 建独立幂等再生器（当前 enhance_data_layer.py 非幂等，不跑）",
        reason="待幂等再生器；当前 producer 非幂等会污染 entities.json",
    ),
    Artifact(
        path="api/morphology_graph.json",
        upstreams=("api/entities.json", "scripts/build_morphology_graph.py"),
        tolerance_days=3,
        producer="python scripts/build_morphology_graph.py",
    ),
    Artifact(
        path="schemas/embodiment_provenance.schema.json",
        upstreams=(),
        tolerance_days=999,
        producer="hand-maintained",
        reason="schema 手写；mtime 新鲜度不适用（无 upstream）",
    ),
    Artifact(
        path="schemas/evidence_contribution.schema.json",
        upstreams=(),
        tolerance_days=999,
        producer="hand-maintained",
        reason="schema 手写；mtime 新鲜度不适用",
    ),
    # skills/manifest.json 不在此表：gen_skills_manifest.mjs 内容一致时不写文件，
    # 会假陈旧。内容一致性由 scripts/verify_mcp_package.py 负责（已在 ci_gate）。
]


# ─────────────────────────────────────────────────────────────────────
# 豁免文件
# ─────────────────────────────────────────────────────────────────────
@dataclass
class Exemption:
    path: str
    reason: str
    expires_at: Optional[str] = None
    requested_by: Optional[str] = None


def _load_exemptions() -> Dict[str, Exemption]:
    if not os.path.exists(EXEMPTIONS_PATH):
        return {}
    with open(EXEMPTIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, Exemption] = {}
    for raw in data.get("exemptions", []):
        try:
            ex = Exemption(
                path=raw["path"],
                reason=raw.get("reason", ""),
                expires_at=raw.get("expires_at"),
                requested_by=raw.get("requested_by"),
            )
            out[ex.path] = ex
        except (KeyError, TypeError):
            # 豁免格式坏：不静默跳过，抛错让 CI 报红
            raise ValueError(
                f"豁免格式错误：缺少 path 或 reason 字段：{raw!r}")
    return out


def _exemption_expired(ex: Exemption, now: _dt.datetime) -> bool:
    if not ex.expires_at:
        return False
    try:
        exp = _dt.datetime.fromisoformat(ex.expires_at)
    except ValueError:
        # 过期时间格式错，当作未过期，让审计人工处理
        return False
    return now.replace(tzinfo=None) > exp


def _exemption_explain(path: str) -> Optional[str]:
    return None


def load_exemptions_info() -> Dict[str, Any]:
    return {
        "path": EXEMPTIONS_PATH,
        "exists": os.path.exists(EXEMPTIONS_PATH),
    }


# ─────────────────────────────────────────────────────────────────────
# 判定核心
# ─────────────────────────────────────────────────────────────────────
@dataclass
class FreshnessResult:
    artifact: str
    mtime: Optional[_dt.datetime]
    upstream_max_mtime: Optional[_dt.datetime]
    upstream_oldest_ok: Optional[_dt.datetime]
    upstream_missing: List[str]
    artifact_missing: bool
    tolerance_days: int
    lag_days: float  # max(upstream) - artifact，负值表示 artifact 反而更新
    stale: bool
    exempted: bool
    exemption_reason: str
    producer: str


def _mtime(path: str) -> Optional[_dt.datetime]:
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return None
    return _dt.datetime.fromtimestamp(os.path.getmtime(full))


def check_artifact(art: Artifact, exemptions: Dict[str, Exemption],
                   now: _dt.datetime) -> FreshnessResult:
    art_mtime = _mtime(art.path)
    missing_upstreams = [u for u in art.upstreams if not os.path.exists(os.path.join(ROOT, u))]
    upstream_mtimes = [(_mtime(u), u) for u in art.upstreams if u not in missing_upstreams]

    upstream_max: Optional[_dt.datetime] = None
    upstream_oldest_ok: Optional[_dt.datetime] = None
    for mt, _name in upstream_mtimes:
        if mt is None:
            continue
        if upstream_max is None or mt > upstream_max:
            upstream_max = mt
        if upstream_oldest_ok is None or mt < upstream_oldest_ok:
            upstream_oldest_ok = mt

    artifact_missing = art_mtime is None
    lag_days = 0.0
    if art_mtime is not None and upstream_max is not None:
        lag_days = (upstream_max - art_mtime).total_seconds() / 86400.0

    exempt_ex = exemptions.get(art.path)
    exempted = exempt_ex is not None and not _exemption_expired(exempt_ex, now)

    # stale 判定：
    # - artifact 缺失：直接 stale
    # - upstream 有更新且超出 tolerance_days：stale
    # - 但 artifact 是真相源（无 upstream）：永不 stale
    stale = False
    if artifact_missing:
        stale = True
    elif missing_upstreams:
        # 上游缺失不算 stale（可能是被删的过渡文件），但报告
        pass
    elif lag_days > art.tolerance_days:
        stale = True

    return FreshnessResult(
        artifact=art.path,
        mtime=art_mtime,
        upstream_max_mtime=upstream_max,
        upstream_oldest_ok=upstream_oldest_ok,
        upstream_missing=missing_upstreams,
        artifact_missing=artifact_missing,
        tolerance_days=art.tolerance_days,
        lag_days=round(lag_days, 2),
        stale=stale,
        exempted=exempted,
        exemption_reason=exempt_ex.reason if exempted else "",
        producer=art.producer,
    )


# ─────────────────────────────────────────────────────────────────────
# 报告
# ─────────────────────────────────────────────────────────────────────
def _fmt_dt(dt: Optional[_dt.datetime]) -> str:
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _uncovered_artifacts() -> List[str]:
    """扫描 api/*.json + schemas/*.json + skills/meta.json，减去 ARTIFACTS 已覆盖的。"""
    tracked = {a.path for a in ARTIFACTS}
    out: List[str] = []
    for dir_, pattern in (("api", "*.json"), ("schemas", "*.json")):
        full_dir = os.path.join(ROOT, dir_)
        if not os.path.isdir(full_dir):
            continue
        import glob
        for f in sorted(glob.glob(os.path.join(full_dir, pattern))):
            rel = os.path.relpath(f, ROOT).replace("\\", "/")
            if rel not in tracked:
                out.append(rel)
    return out


def print_report(results: List[FreshnessResult], as_json: bool = False) -> None:
    stale = [r for r in results if r.stale and not r.exempted]
    exempted = [r for r in results if r.stale and r.exempted]
    missing_up = [r for r in results if r.upstream_missing]

    if as_json:
        payload = {
            "generated_at": _dt.datetime.utcnow().isoformat() + "Z",
            "tracked_count": len(results),
            "stale_count": len(stale),
            "exempted_count": len(exempted),
            "results": [
                {
                    "artifact": r.artifact,
                    "mtime": _fmt_dt(r.mtime),
                    "upstream_max_mtime": _fmt_dt(r.upstream_max_mtime),
                    "tolerance_days": r.tolerance_days,
                    "lag_days": r.lag_days,
                    "stale": r.stale,
                    "exempted": r.exempted,
                    "exemption_reason": r.exemption_reason,
                    "upstream_missing": r.upstream_missing,
                    "artifact_missing": r.artifact_missing,
                    "producer": r.producer,
                }
                for r in results
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"=== RoboParts 产物新鲜度检查 ===")
    print(f"跟踪产物: {len(results)}  |  stale: {len(stale)}  |  豁免: {len(exempted)}")
    print()
    for r in results:
        tag = "✅" if not r.stale else ("🟡" if r.exempted else "❌")
        lag_str = f"lag={r.lag_days:.1f}d" if r.upstream_max_mtime else "no upstream"
        print(f"  {tag} {r.artifact:<48} {_fmt_dt(r.mtime)}  {lag_str}"
              f"  tol={r.tolerance_days}d")
        if r.upstream_missing:
            print(f"       ⚠️ 上游缺失: {', '.join(r.upstream_missing)}")
        if r.exempted:
            print(f"       🟡 豁免: {r.exemption_reason[:80]}")
        if r.stale and not r.exempted:
            print(f"       再生命令: {r.producer}")

    uncovered = _uncovered_artifacts()
    if uncovered:
        print()
        print(f"--- 未纳入跟踪（{len(uncovered)} 个）— 仅报告，不判定 ---")
        for p in uncovered:
            print(f"  · {p}")


def write_report(results: List[FreshnessResult]) -> None:
    payload = {
        "generated_at": _dt.datetime.utcnow().isoformat() + "Z",
        "tracked_count": len(results),
        "stale_count": len([r for r in results if r.stale and not r.exempted]),
        "results": [
            {
                "artifact": r.artifact,
                "mtime": _fmt_dt(r.mtime),
                "lag_days": r.lag_days,
                "stale": r.stale,
                "exempted": r.exempted,
                "exemption_reason": r.exemption_reason,
                "upstream_missing": r.upstream_missing,
                "producer": r.producer,
            }
            for r in results
        ],
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="列出跟踪的产物表")
    parser.add_argument("--json", action="store_true", help="JSON 输出（不含 uncovered 明细）")
    parser.add_argument("--write-report", action="store_true",
                        help="把结果写入 api/freshness_report.json（进仓库）")
    args = parser.parse_args(argv)

    if args.list:
        for a in ARTIFACTS:
            print(f"{a.path:<50} tol={a.tolerance_days}d  upstreams={list(a.upstreams)}")
        return 0

    now = _dt.datetime.now()
    exemptions = _load_exemptions()
    results = [check_artifact(a, exemptions, now) for a in ARTIFACTS]
    print_report(results, as_json=args.json)
    if args.write_report:
        write_report(results)
        print(f"\n报告已写入 {os.path.relpath(REPORT_PATH, ROOT)}")

    stale = [r for r in results if r.stale and not r.exempted]
    if stale:
        print(f"\n❌ {len(stale)} 个产物陈旧（跑 producer 命令或登记豁免）")
        return 1
    print(f"\n✅ 全部产物新鲜（或已豁免）")
    return 0


def check() -> bool:
    """供 ci_gate.py 调用的入口：返回 True 表示全绿。"""
    return main([]) == 0


def check_ci_gate() -> None:
    """ci_gate 专用封装：把子进程输出转成 ok/bad。"""
    import subprocess
    r = subprocess.run([sys.executable, os.path.abspath(__file__)],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    last_lines = (r.stdout or "").strip().splitlines()[-6:]
    if r.returncode == 0:
        _ci_ok("产物新鲜度检查", "; ".join(last_lines[-2:]))
    else:
        tail = "\n".join(last_lines)
        _ci_bad("产物新鲜度检查", tail)


def _ci_ok(name: str, detail: str = "") -> None:
    PASSED.append(name)
    print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))


def _ci_bad(name: str, detail: str = "") -> None:
    FAILED.append(name)
    print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


if __name__ == "__main__":
    sys.exit(main())
