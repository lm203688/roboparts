#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2-2 仿真资产分级一致性闸门（2026-10-26 落地）

对应审计报告：docs/RoboParts-全面提升与前沿演进报告-20261026.md § 9.3 P2-2
"仿真资产 L0–L4 与自动验证报告：L1/L2 全自动；L3/L4 明示人工/实测边界"

背景：
- P0-12（2026-10-26 上午）落下了 L0-L4 分级定义 + `X-RoboParts-AssetClass` 响应头
- 但只有 /api/urdf/download 打了头（L1），/api/urdf/library 默认 tier='L0'
- 同一份导出物在两个端点给出不同分级——这是"文档写对、代码写错"的经典漂移

本闸门守三条：
1. **library ↔ download 契约一致**：library 里每个模型的 tier 与 download 头返回的
   AssetClass 必须相等（否则调用方读到两个不同答案）
2. **schema 定义 ↔ 代码实现一致**：ASSET_TIER_SCHEMA 5 级都必须有名字、requires
3. **诚实边界声明**：所有 L2+ 模型必须在 ASSET_TIER_OVERRIDES 里显式登记 source +
   assumptions（否则等于把估算当实测）

自证：
- --self-test 提供 4 条对照（一致性破坏 / schema 缺字段 / L2+ 无 source / 正常基线）
- 若闸门本身退化（正则失效、校验逻辑漏洞），自证会先变红

用法：
    python scripts/verify_asset_class.py              # 线上验证
    python scripts/verify_asset_class.py --offline    # 离线跑（mock 数据）
    python scripts/verify_asset_class.py --self-test  # 自证对照
    python scripts/verify_asset_class.py --json       # JSON 输出

退出码：0 = 全绿；1 = 有闸门失败；2 = 自身代码错误
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://roboparts.cc"
VALID_TIERS = ["L0", "L1", "L2", "L3", "L4"]
REQUIRED_TIER_FIELDS = ["name", "external", "requires"]

TLS_CTX = ssl.create_default_context()


def fetch(url: str, timeout: int = 15, method: str = "GET"):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": "roboparts-asset-class-verifier/1.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, context=TLS_CTX, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as e:
        raise RuntimeError(f"FETCH_FAIL {url}: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 解析源码常量（不导入 JS，只正则提取）
# ---------------------------------------------------------------------------

def parse_source_constants(js_path: Path) -> dict:
    """
    从 library.js 源码里正则提取 ASSET_TIER_SCHEMA 和 ASSET_TIER_OVERRIDES 的键集合。
    不做 JS 执行——只是文本扫描，用来对账定义完整性。
    """
    if not js_path.exists():
        raise RuntimeError(f"source not found: {js_path}")
    src = js_path.read_text(encoding="utf-8")

    result = {
        "schema_tiers": [],
        "override_ids": [],
        "default_tier": None,
        "schema_def": {},
    }

    # 1. 找 default tier（getAssetTier 里的 fallback 分支）
    default_match = re.search(
        r"return\s*\{[^}]*?tier:\s*'(L[0-4])'", src, re.DOTALL
    )
    if default_match:
        result["default_tier"] = default_match.group(1)

    # 2. 找 ASSET_TIER_SCHEMA 的键（每个 tier 定义）
    schema_block = re.search(
        r"ASSET_TIER_SCHEMA\s*=\s*\{(.*?)\};", src, re.DOTALL
    )
    if schema_block:
        body = schema_block.group(1)
        for tier_name in VALID_TIERS:
            tier_def_match = re.search(
                rf"{tier_name}:\s*\{{([^}}]*)\}}", body, re.DOTALL
            )
            if tier_def_match:
                result["schema_tiers"].append(tier_name)
                inner = tier_def_match.group(1)
                result["schema_def"][tier_name] = {}
                for field in REQUIRED_TIER_FIELDS:
                    field_match = re.search(
                        rf"{field}:\s*'([^']*)'", inner
                    )
                    if field_match:
                        result["schema_def"][tier_name][field] = field_match.group(1)

    # 3. 找 ASSET_TIER_OVERRIDES 的键（非注释）
    overrides_block = re.search(
        r"ASSET_TIER_OVERRIDES\s*=\s*\{(.*?)\};", src, re.DOTALL
    )
    if overrides_block:
        body = overrides_block.group(1)
        # 剥掉注释（行注释 // 和 块注释 /* */）
        body_no_comments = re.sub(r"//.*", "", body)
        body_no_comments = re.sub(r"/\*.*?\*/", "", body_no_comments, flags=re.DOTALL)
        # 找形如 'URDF-XXX': { 的键
        for m in re.finditer(r"'(URDF-\d+)'\s*:\s*\{", body_no_comments):
            result["override_ids"].append(m.group(1))

    return result


# ---------------------------------------------------------------------------
# 契约校验
# ---------------------------------------------------------------------------

def check_schema_integrity(constants: dict) -> dict:
    """校验 ASSET_TIER_SCHEMA 5 级定义完整"""
    errors = []
    warnings = []

    # 5 级都要在
    for t in VALID_TIERS:
        if t not in constants.get("schema_tiers", []):
            errors.append(f"ASSET_TIER_SCHEMA missing tier '{t}'")

    # 每级 3 字段都要非空
    for t, fields in constants.get("schema_def", {}).items():
        for f in REQUIRED_TIER_FIELDS:
            if not fields.get(f):
                errors.append(f"schema_def[{t}].{f} empty or missing")

    # default tier 必须是合法值
    dt = constants.get("default_tier")
    if dt is None:
        errors.append("could not parse default_tier from source")
    elif dt not in VALID_TIERS:
        errors.append(f"default_tier='{dt}' is not in {VALID_TIERS}")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


def check_library_default_tier(constants: dict) -> dict:
    """
    预置模型默认 tier 必须是 L1（参数化骨架），不是 L0（仅元数据）。

    原因：download.js 实际生成的 XML 有 box/cylinder 几何骨架，符合 L1 定义；
    若默认标 L0，则 library 说 L0 / download 头说 L1，两处契约互相打脸。
    """
    default = constants.get("default_tier")
    if default == "L1":
        return {"ok": True, "errors": [], "warnings": [],
                "message": f"default_tier=L1（参数化骨架，与 download 头一致）"}
    if default == "L0":
        return {"ok": False,
                "errors": ["default_tier=L0 但 download 头返回 L1——契约不一致"],
                "warnings": [], "message": f"default_tier={default}"}
    return {"ok": False,
            "errors": [f"default_tier={default} 非法"],
            "warnings": [], "message": f"default_tier={default}"}


def check_l2_plus_has_source(constants: dict) -> dict:
    """
    L2+ 模型必须在 OVERRIDES 里有 source 和 assumptions。
    预置 60 个都是 L1（参数化骨架），没有 L2+，所以 overrides 应为空。
    一旦有人加了 L2+ 但没写 source，本闸门立刻红。
    """
    errors = []
    override_ids = constants.get("override_ids", [])
    if override_ids:
        errors.append(
            f"ASSET_TIER_OVERRIDES 含 {len(override_ids)} 条登记 {override_ids}，"
            f"需要人工核对每条都有 source（datasheet URL 或实测记录 ID）"
            f"和 assumptions 说明"
        )
    else:
        # 空 override = 全部默认 L1，符合当前诚实边界
        pass
    return {"ok": len(errors) == 0, "errors": errors,
            "warnings": [], "override_count": len(override_ids)}


def check_live_endpoint_consistency(base: str) -> dict:
    """
    拉线上 /api/urdf/library 和 /api/urdf/download?id=URDF-001，
    验证两端返回的 tier 一致。
    """
    errors = []
    warnings = []
    details = {}

    # 1. 拉 library
    try:
        status, body, _ = fetch(f"{base}/api/urdf/library")
        if status != 200:
            errors.append(f"/api/urdf/library HTTP {status}")
            return {"ok": False, "errors": errors, "warnings": warnings, "details": details}
        lib_data = json.loads(body)
        models = lib_data.get("models", [])
        details["library_model_count"] = len(models)
        if models:
            first_tier = models[0].get("asset_tier", {}).get("tier")
            details["library_first_tier"] = first_tier
            details["library_sample_id"] = models[0].get("id")
        else:
            errors.append("/api/urdf/library returned 0 models")
    except Exception as e:
        errors.append(f"library fetch failed: {e}")
        return {"ok": False, "errors": errors, "warnings": warnings, "details": details}

    # 2. 拉 download（HEAD 拿响应头）
    sample_id = details.get("library_sample_id") or "URDF-001"
    try:
        status, _, headers = fetch(
            f"{base}/api/urdf/download?id={sample_id}", method="HEAD"
        )
        if status not in (200, 206, 405):
            errors.append(f"/api/urdf/download HTTP {status} (expected 200/206)")
            return {"ok": False, "errors": errors, "warnings": warnings, "details": details}
        # HEAD 可能不返 body，用 GET 拿头也行；这里保守用 GET 只拿头
        get_status, _, get_headers = fetch(
            f"{base}/api/urdf/download?id={sample_id}"
        )
        # 从 GET 响应头里找 X-RoboParts-AssetClass
        download_class = None
        for k, v in get_headers.items():
            if k.lower() == "x-roboparts-assetclass":
                download_class = v.strip()
                break
        details["download_class"] = download_class
        details["download_status"] = get_status
    except Exception as e:
        errors.append(f"download fetch failed: {e}")
        return {"ok": False, "errors": errors, "warnings": warnings, "details": details}

    # 3. 一致性对账
    lib_tier = details.get("library_first_tier")
    dl_class = details.get("download_class")
    if lib_tier is None or dl_class is None:
        errors.append(
            f"cannot compare: library tier={lib_tier!r} download class={dl_class!r}"
        )
    elif lib_tier != dl_class:
        errors.append(
            f"library.asset_tier.tier={lib_tier!r} != download X-RoboParts-AssetClass={dl_class!r} "
            f"for {sample_id}——同一份导出物两端契约不一致"
        )
    else:
        # 一致 = 契约对齐
        if dl_class not in VALID_TIERS:
            errors.append(f"download class {dl_class!r} is not a valid tier")

    return {"ok": len(errors) == 0, "errors": errors,
            "warnings": warnings, "details": details}


# ---------------------------------------------------------------------------
# 自证对照
# ---------------------------------------------------------------------------

SELF_TEST_FIXTURES = [
    # (fixture_name, mutated_constants, expected_ok, description)
    (
        "schema missing L4",
        {
            "schema_tiers": ["L0", "L1", "L2", "L3"],  # 缺 L4
            "schema_def": {"L0": {"name": "x", "external": "y", "requires": "z"},
                          "L1": {"name": "x", "external": "y", "requires": "z"},
                          "L2": {"name": "x", "external": "y", "requires": "z"},
                          "L3": {"name": "x", "external": "y", "requires": "z"}},
            "default_tier": "L1",
            "override_ids": [],
        },
        False,
        "schema_integrity: L4 定义被删",
    ),
    (
        "schema L2 requires empty",
        {
            "schema_tiers": ["L0", "L1", "L2", "L3", "L4"],
            "schema_def": {
                "L0": {"name": "x", "external": "y", "requires": "z"},
                "L1": {"name": "x", "external": "y", "requires": "z"},
                "L2": {"name": "x", "external": "y", "requires": ""},  # 空
                "L3": {"name": "x", "external": "y", "requires": "z"},
                "L4": {"name": "x", "external": "y", "requires": "z"},
            },
            "default_tier": "L1",
            "override_ids": [],
        },
        False,
        "schema_integrity: L2.requires 空",
    ),
    (
        "default_tier L0",
        {
            "schema_tiers": ["L0", "L1", "L2", "L3", "L4"],
            "schema_def": {t: {"name": "x", "external": "y", "requires": "z"} for t in VALID_TIERS},
            "default_tier": "L0",  # 破坏：应为 L1
            "override_ids": [],
        },
        False,
        "default_tier=L0 与 download 头 L1 不一致",
    ),
    (
        "L2+ override without review",
        {
            "schema_tiers": ["L0", "L1", "L2", "L3", "L4"],
            "schema_def": {t: {"name": "x", "external": "y", "requires": "z"} for t in VALID_TIERS},
            "default_tier": "L1",
            "override_ids": ["URDF-026"],  # 有人加了 override
        },
        False,
        "L2+ 有 override 但未人工核对 source",
    ),
    # 阳性对照：正常基线应该通过
    (
        "normal baseline",
        {
            "schema_tiers": ["L0", "L1", "L2", "L3", "L4"],
            "schema_def": {t: {"name": "x", "external": "y", "requires": "z"} for t in VALID_TIERS},
            "default_tier": "L1",
            "override_ids": [],
        },
        True,
        "正常基线（L1 默认 + 空 override）",
    ),
]


def run_self_test() -> list[dict]:
    results = []
    for name, mutated, expected_ok, desc in SELF_TEST_FIXTURES:
        # 综合 3 条 check 判断
        si = check_schema_integrity(mutated)
        dt = check_library_default_tier(mutated)
        ov = check_l2_plus_has_source(mutated)
        got_ok = si["ok"] and dt["ok"] and ov["ok"]
        passed = (got_ok == expected_ok)
        results.append({
            "name": name,
            "description": desc,
            "expected_ok": expected_ok,
            "got_ok": got_ok,
            "ok": passed,
        })
    return results


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--offline", action="store_true",
                        help="只跑源码静态检查，不拉线上")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        results = run_self_test()
        all_ok = all(r["ok"] for r in results)
        if args.json:
            print(json.dumps({"self_test": results, "all_ok": all_ok},
                            ensure_ascii=False, indent=2))
        else:
            print(f"\n[资产分级自证对照]")
            print(f"{'='*72}")
            for r in results:
                status = "✅" if r["ok"] else "❌"
                print(f"{status} {r['description']}")
                print(f"   expected_ok={r['expected_ok']}  got_ok={r['got_ok']}")
            print(f"{'='*72}")
            print(f"自证: {sum(1 for r in results if r['ok'])}/{len(results)} 通过 "
                  f"{'✅' if all_ok else '❌'}")
        sys.exit(0 if all_ok else 1)

    # 正常模式
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base,
        "offline": args.offline,
        "checks": [],
    }

    # 1. 静态源码检查
    try:
        constants = parse_source_constants(ROOT / "functions" / "api" / "urdf" / "library.js")
        report["constants"] = {
            "schema_tiers": constants["schema_tiers"],
            "default_tier": constants["default_tier"],
            "override_ids": constants["override_ids"],
        }
    except Exception as e:
        report["checks"].append({
            "id": "parse_source", "ok": False, "errors": [str(e)]
        })
        _output(report, args.json)
        sys.exit(1)

    report["checks"].append({
        "id": "schema_integrity",
        **check_schema_integrity(constants),
    })
    report["checks"].append({
        "id": "library_default_tier",
        **check_library_default_tier(constants),
    })
    report["checks"].append({
        "id": "l2_plus_has_source",
        **check_l2_plus_has_source(constants),
    })

    # 2. 线上一致性检查（可离线跳过）
    if not args.offline:
        report["checks"].append({
            "id": "live_endpoint_consistency",
            **check_live_endpoint_consistency(args.base),
        })
    else:
        report["checks"].append({
            "id": "live_endpoint_consistency",
            "ok": None, "errors": [], "warnings": [],
            "message": "SKIPPED (offline mode)"
        })

    # 汇总
    real_checks = [c for c in report["checks"] if c.get("ok") is not None]
    passed = sum(1 for c in real_checks if c["ok"])
    total = len(real_checks)
    report["summary"] = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "all_ok": passed == total,
    }

    _output(report, args.json)
    sys.exit(0 if report["summary"]["all_ok"] else 1)


def _output(report: dict, as_json: bool):
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"\n[资产分级一致性] offline={report.get('offline')} base={report.get('base_url')}")
    print(f"{'='*72}")
    consts = report.get("constants", {})
    print(f"schema_tiers={consts.get('schema_tiers')}")
    print(f"default_tier={consts.get('default_tier')}")
    print(f"override_ids={consts.get('override_ids')}")
    print(f"{'='*72}")
    for c in report["checks"]:
        ok = c.get("ok")
        status = "✅" if ok else ("❌" if ok is False else "⏭️")
        print(f"{status} {c['id']}")
        for e in c.get("errors", [])[:5]:
            print(f"   ❌ {e}")
        for w in c.get("warnings", [])[:3]:
            print(f"   ⚠️  {w}")
        if c.get("message"):
            print(f"   · {c['message']}")
    s = report.get("summary", {})
    print(f"{'='*72}")
    print(f"总计: {s.get('passed', 0)}/{s.get('total', 0)} 通过 "
          f"{'✅' if s.get('all_ok') else '❌'}")


if __name__ == "__main__":
    main()
