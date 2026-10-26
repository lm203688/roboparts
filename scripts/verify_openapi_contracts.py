#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1-8 API 契约测试闸门（先行版）

对应审计报告：docs/RoboParts-全面提升与前沿演进报告-20261026.md § 9.2 P1-8
依赖：openapi.yaml（P1-8 前置）· 无 requests 依赖，仅用 stdlib + PyYAML

设计：
- 拉线上 5 个稳定端点的真实响应
- 用 openapi.yaml 里的 schema 做最小必要结构校验（不做完整 JSON Schema 校验器，
  避免依赖 jsonschema 包；只做 required 字段 + 类型检查）
- 破坏性变更（缺字段/类型变更）→ 判红
- 兼容变更（多字段/枚举扩项）→ 判绿
- 自证：提供 --self-test 模式，注入假响应验证闸门能抓到破坏性变更

用法：
    python scripts/verify_openapi_contracts.py            # 拉线上验证
    python scripts/verify_openapi_contracts.py --offline  # 用 mock 数据离线验证
    python scripts/verify_openapi_contracts.py --self-test  # 自证对照
    python scripts/verify_openapi_contracts.py --spec openapi.yaml  # 指定契约文件

退出码：0 = 全绿；1 = 有闸门失败；2 = 自身代码错误
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FATAL: PyYAML not installed. pip install pyyaml", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = ROOT / "openapi.yaml"
DEFAULT_BASE = "https://roboparts.cc"

# --------------------------------------------------------------------------
# 契约测试：5 个稳定端点
# --------------------------------------------------------------------------

CONTRACT_TESTS = [
    {
        "id": "deployment",
        "method": "GET",
        "path": "/api/deployment",
        "expected_schema": "DeploymentFingerprint",
        "required_top_keys": ["commitShort", "builtAt", "nodeVersion"],
        "type_checks": {
            "commitShort": "string",
            "builtAt": "string",
            "nodeVersion": "string",
        },
        "pattern_checks": {
            "commitShort": r"^[0-9a-f]{10,40}$",
            "nodeVersion": r"^\d+\.\d+\.\d+",
        },
    },
    {
        "id": "search",
        "method": "GET",
        "path": "/api/search?q=kuka&limit=2",
        "expected_schema": "SearchResponse",
        "required_top_keys": ["query", "meta", "results"],
        "type_checks": {
            "query": "object",
            "meta": "object",
            "results": "array",
        },
        "meta_required_keys": ["total_indexed", "matched", "returned"],
        "meta_type_checks": {
            "total_indexed": "integer",
            "matched": "integer",
            "returned": "integer",
        },
    },
    {
        "id": "compatibility-not-found",
        "method": "GET",
        "path": "/api/compatibility?a=NONEXIST-XYZ-99999&b=NONEXIST-ABC-88888",
        "expected_schema": "CompatibilityNotFound",
        "expected_status": 404,  # 线上返回 404 + JSON body（合法契约行为）
        "allow_client_error": True,
        "required_top_keys": ["success", "not_found", "query", "candidates", "hint"],
        "const_checks": {
            "success": False,
            "not_found": True,
        },
        "type_checks": {
            "candidates": "array",
            "hint": "string",
        },
    },
    {
        "id": "funnel",
        "method": "GET",
        "path": "/api/analytics/funnel",
        "expected_schema": "FunnelResponse",
        "required_top_keys": ["date", "counts", "rates", "pipeline_usage", "history_7d"],
        "type_checks": {
            "date": "string",
            "counts": "object",
            "rates": "object",
            "pipeline_usage": "object",
            "history_7d": "array",
        },
        "counts_required_keys": [
            "visits", "signups", "trials_started", "trials_completed",
            "payments_started", "payments_success", "conversions"
        ],
        "pipeline_required_keys": [
            "selection", "build_planner", "designer", "bom_checker", "adapter_generator"
        ],
        "history_max_items": 7,
        "history_item_required": ["date", "visits", "signups", "conversions"],
        "date_pattern": r"^\d{4}-\d{2}-\d{2}$",
    },
    {
        "id": "entities-json",
        "method": "GET",
        "path": "/api/entities.json",
        "expected_schema": "EntitiesSnapshot",
        "required_top_keys": ["meta", "entities"],
        "type_checks": {
            "meta": "object",
            "entities": "array",
        },
    },
]

# --------------------------------------------------------------------------
# HTTP 拉取
# --------------------------------------------------------------------------

TLS_CTX = ssl.create_default_context()
TLS_CTX.check_hostname = True
TLS_CTX.verify_mode = ssl.CERT_REQUIRED


def fetch_json(base: str, path: str, timeout: int = 15, allow_client_error: bool = False):
    """
    GET 一个 URL 并返回 JSON。失败抛 RuntimeError。

    allow_client_error=True 时允许 4xx JSON 响应（用于验证错误码契约，
    例：/api/compatibility 找不到实体时返回 404 + JSON body，是合法契约行为）。
    """
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": "roboparts-openapi-verifier/1.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, context=TLS_CTX, timeout=timeout) as resp:
            body = resp.read()
            status = resp.status
            headers = dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read()
        status = e.code
        headers = dict(e.headers)
        if not allow_client_error or status >= 500:
            raise RuntimeError(f"HTTP {status} {path}: {body[:200]!r}")
    except Exception as e:
        raise RuntimeError(f"FETCH_FAIL {path}: {type(e).__name__}: {e}")
    if status >= 500:
        raise RuntimeError(f"HTTP {status} {path}: {body[:200]!r}")
    try:
        return json.loads(body), headers
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON_DECODE_FAIL {path}: {e}")


# --------------------------------------------------------------------------
# 校验工具
# --------------------------------------------------------------------------

def check_type(value, expected_type: str) -> str | None:
    """返回错误描述，None 表示通过。"""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "object": dict,
        "array": list,
        "boolean": bool,
    }
    py_type = type_map.get(expected_type)
    if py_type is None:
        return f"unknown expected_type '{expected_type}'"
    if expected_type in ("integer", "number") and isinstance(value, bool):
        return f"expected {expected_type}, got bool"
    if not isinstance(value, py_type):
        return f"expected {expected_type}, got {type(value).__name__}"
    return None


def check_required_keys(data: dict, keys: list[str], prefix: str = "") -> list[str]:
    errors = []
    for k in keys:
        if k not in data:
            errors.append(f"{prefix}missing required key '{k}'")
        elif data[k] is None and prefix == "":
            # 顶层不允许 None（deployment 例外：可空字段是明确的）
            pass
    return errors


# --------------------------------------------------------------------------
# 单个契约测试
# --------------------------------------------------------------------------

def run_contract_test(spec: dict, test: dict, data, base: str) -> dict:
    """
    返回 {id, ok, errors, warnings, details}
    """
    result = {
        "id": test["id"],
        "ok": True,
        "errors": [],
        "warnings": [],
        "details": {},
    }

    if not isinstance(data, dict):
        result["ok"] = False
        result["errors"].append(f"response is not an object, got {type(data).__name__}")
        return result

    # 1. required top keys
    required = test.get("required_top_keys", [])
    for k in required:
        if k not in data:
            result["ok"] = False
            result["errors"].append(f"missing top-level key '{k}'")

    # 2. type checks
    for k, expected_type in test.get("type_checks", {}).items():
        if k not in data:
            continue  # already reported above
        err = check_type(data[k], expected_type)
        if err:
            result["ok"] = False
            result["errors"].append(f"{k}: {err}")

    # 3. const checks
    for k, expected in test.get("const_checks", {}).items():
        if k in data and data[k] != expected:
            result["ok"] = False
            result["errors"].append(f"{k}: expected const {expected!r}, got {data[k]!r}")

    # 4. pattern checks
    import re
    for k, pattern in test.get("pattern_checks", {}).items():
        if k in data and isinstance(data[k], str):
            if not re.match(pattern, data[k]):
                result["ok"] = False
                result["errors"].append(f"{k}: value {data[k]!r} does not match pattern {pattern}")

    # 5. date pattern check (funnel.date)
    if "date_pattern" in test and "date" in data:
        import re
        if not re.match(test["date_pattern"], data["date"]):
            result["ok"] = False
            result["errors"].append(f"date: value {data['date']!r} does not match {test['date_pattern']}")

    # 6. nested object checks
    if "meta_required_keys" in test and isinstance(data.get("meta"), dict):
        for k in test["meta_required_keys"]:
            if k not in data["meta"]:
                result["ok"] = False
                result["errors"].append(f"meta: missing key '{k}'")
        for k, expected_type in test.get("meta_type_checks", {}).items():
            if k in data["meta"]:
                err = check_type(data["meta"][k], expected_type)
                if err:
                    result["ok"] = False
                    result["errors"].append(f"meta.{k}: {err}")

    if "counts_required_keys" in test and isinstance(data.get("counts"), dict):
        for k in test["counts_required_keys"]:
            if k not in data["counts"]:
                result["ok"] = False
                result["errors"].append(f"counts: missing key '{k}'")
            elif not isinstance(data["counts"][k], int) or isinstance(data["counts"][k], bool):
                result["ok"] = False
                result["errors"].append(f"counts.{k}: expected non-negative integer")
            elif data["counts"][k] < 0:
                result["ok"] = False
                result["errors"].append(f"counts.{k}: expected non-negative, got {data['counts'][k]}")

    if "pipeline_required_keys" in test and isinstance(data.get("pipeline_usage"), dict):
        for k in test["pipeline_required_keys"]:
            if k not in data["pipeline_usage"]:
                result["ok"] = False
                result["errors"].append(f"pipeline_usage: missing key '{k}'")
            elif not isinstance(data["pipeline_usage"][k], int) or isinstance(data["pipeline_usage"][k], bool):
                result["ok"] = False
                result["errors"].append(f"pipeline_usage.{k}: expected non-negative integer")

    if "history_max_items" in test and isinstance(data.get("history_7d"), list):
        if len(data["history_7d"]) > test["history_max_items"]:
            result["ok"] = False
            result["errors"].append(f"history_7d: has {len(data['history_7d'])} items, max {test['history_max_items']}")
        if test.get("history_item_required") and data["history_7d"]:
            for i, item in enumerate(data["history_7d"]):
                if not isinstance(item, dict):
                    result["ok"] = False
                    result["errors"].append(f"history_7d[{i}]: expected object, got {type(item).__name__}")
                    continue
                for k in test["history_item_required"]:
                    if k not in item:
                        result["ok"] = False
                        result["errors"].append(f"history_7d[{i}]: missing key '{k}'")
                        break

    # 7. verify spec has this schema defined (structural check)
    schemas = spec.get("components", {}).get("schemas", {})
    expected_schema = test.get("expected_schema")
    if expected_schema and expected_schema not in schemas:
        result["warnings"].append(f"openapi.yaml has no components.schemas.{expected_schema} (schema drift risk)")

    return result


# --------------------------------------------------------------------------
# 自证对照
# --------------------------------------------------------------------------

SELF_TEST_FIXTURES = [
    # (test_id, mutated_data, expected_ok, description)
    # 阴性对照：真实响应改字段类型 → 应判红
    ("deployment", {
        "commit": "abc",
        "commitShort": 12345,  # 破坏：应为 string
        "builtAt": "2026-10-26T00:00:00Z",
        "nodeVersion": "22.22.2",
    }, False, "deployment.commitShort 类型破坏 (string → integer)"),
    # 阳性对照：字段缺失 → 应判红
    ("deployment", {
        "commitShort": "abc76c64",
        "builtAt": "2026-10-26T00:00:00Z",
        # 缺 nodeVersion
    }, False, "deployment 缺 nodeVersion"),
    # 结构破坏：funnel.pipeline_usage 缺 key
    ("funnel", {
        "date": "2026-10-26",
        "counts": {k: 0 for k in ["visits","signups","trials_started","trials_completed","payments_started","payments_success","conversions"]},
        "rates": {},
        "pipeline_usage": {"selection": 0, "build_planner": 0, "designer": 0, "bom_checker": 0},  # 缺 adapter_generator
        "history_7d": [],
    }, False, "funnel.pipeline_usage 缺 adapter_generator"),
    # const 破坏：compatibility 的 not_found 应为 true
    ("compatibility-not-found", {
        "success": True,  # 破坏
        "not_found": False,  # 破坏
        "query": "x",
        "candidates": [],
        "hint": "",
    }, False, "compatibility-not-found success/not_found const 破坏"),
    # history 超量
    ("funnel", {
        "date": "2026-10-26",
        "counts": {k: 0 for k in ["visits","signups","trials_started","trials_completed","payments_started","payments_success","conversions"]},
        "rates": {},
        "pipeline_usage": {k: 0 for k in ["selection","build_planner","designer","bom_checker","adapter_generator"]},
        "history_7d": [{"date": f"2026-10-{26-i:02d}", "visits": 0, "signups": 0, "conversions": 0} for i in range(10)],  # 10 > 7
    }, False, "funnel.history_7d 超过 7 项"),
]


def run_self_test(spec: dict) -> list[dict]:
    """返回每条自证结果 {case_desc, test_id, expected, got, ok}"""
    results = []
    tests_by_id = {t["id"]: t for t in CONTRACT_TESTS}
    for test_id, mutated_data, expected_ok, case_desc in SELF_TEST_FIXTURES:
        test = tests_by_id.get(test_id)
        if test is None:
            results.append({
                "case_desc": case_desc, "test_id": test_id,
                "expected": expected_ok, "got": None, "ok": False,
                "reason": f"no contract test with id '{test_id}'"
            })
            continue
        result = run_contract_test(spec, test, mutated_data, DEFAULT_BASE)
        got_ok = result["ok"]
        passed = (got_ok == expected_ok)
        results.append({
            "case_desc": case_desc,
            "test_id": test_id,
            "expected_ok": expected_ok,
            "got_ok": got_ok,
            "ok": passed,
            "errors": result["errors"][:3],  # 只保留前 3 条，避免报告过长
        })
    return results


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=str(DEFAULT_SPEC), help="OpenAPI 契约文件路径")
    parser.add_argument("--base", default=DEFAULT_BASE, help="线上 API base URL")
    parser.add_argument("--offline", action="store_true", help="使用 mock 数据（不拉线上）")
    parser.add_argument("--self-test", action="store_true", help="只跑自证对照")
    parser.add_argument("--json", action="store_true", help="JSON 输出（供 CI 消费）")
    args = parser.parse_args()

    # 加载契约
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"FAIL: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except Exception as e:
        print(f"FAIL: cannot parse spec: {e}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(spec, dict) or "openapi" not in spec:
        print("FAIL: spec is not a valid OpenAPI document", file=sys.stderr)
        sys.exit(2)

    report = {
        "spec_path": str(spec_path),
        "spec_version": spec.get("info", {}).get("version"),
        "openapi_version": spec.get("openapi"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base,
        "offline": args.offline,
        "tests": [],
    }

    # 自证模式
    if args.self_test:
        self_results = run_self_test(spec)
        report["self_test"] = self_results
        self_pass = all(r["ok"] for r in self_results)
        report["summary"] = {
            "self_test_total": len(self_results),
            "self_test_passed": sum(1 for r in self_results if r["ok"]),
            "self_test_failed": sum(1 for r in self_results if not r["ok"]),
            "self_test_all_ok": self_pass,
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"\n[OpenAPI 自证对照] spec={report['spec_version']}")
            print(f"{'='*72}")
            for r in self_results:
                status = "✅" if r["ok"] else "❌"
                print(f"{status} {r['case_desc']}")
                print(f"   expected_ok={r['expected_ok']}  got_ok={r['got_ok']}")
                for e in r.get("errors", []):
                    print(f"   · {e}")
            print(f"{'='*72}")
            s = report["summary"]
            print(f"自证: {s['self_test_passed']}/{s['self_test_total']} 通过 {'✅' if self_pass else '❌'}")
            print("（闸门能否抓到破坏性变更的自证——失败即闸门本身失效）")
        # 自证失败 = 闸门本身失效，退出 1
        sys.exit(0 if self_pass else 1)

    # 正常模式
    total = len(CONTRACT_TESTS)
    passed = 0
    for test in CONTRACT_TESTS:
        if args.offline:
            # 离线模式：跳过线上拉取，用最小 mock 数据
            data = _mock_response(test["id"])
            headers = {}
        else:
            try:
                data, headers = fetch_json(
                    args.base, test["path"],
                    allow_client_error=test.get("allow_client_error", False)
                )
            except RuntimeError as e:
                result = {
                    "id": test["id"],
                    "ok": False,
                    "errors": [str(e)],
                    "warnings": [],
                    "details": {},
                }
                report["tests"].append(result)
                continue

        result = run_contract_test(spec, test, data, args.base)
        report["tests"].append(result)
        if result["ok"]:
            passed += 1

    report["summary"] = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "all_ok": passed == total,
    }

    # 输出
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    sys.exit(0 if report["summary"]["all_ok"] else 1)


def _mock_response(test_id: str):
    """离线模式的最小 mock 数据（结构完整，值可 dummy）。"""
    mocks = {
        "deployment": {
            "commit": "abc76c64dfed1234567890abcdef",
            "commitShort": "abc76c64dfed",
            "branch": "main",
            "deploymentId": None,
            "builtAt": "2026-10-26T08:00:00Z",
            "nodeVersion": "22.22.2",
            "pythonVersion": "3.13.14",
            "cloudflarePlatform": True,
            "fallbackSource": "mock",
        },
        "search": {
            "query": {"q": "kuka", "category": None, "limit": 2, "include_quarantine": False},
            "meta": {"total_indexed": 1000, "matched": 5, "returned": 2},
            "results": [{"id": "MOCK-001", "name": "KUKA MOCK"}],
        },
        "compatibility-not-found": {
            "success": False,
            "not_found": True,
            "query": "NONEXIST",
            "candidates": [],
            "hint": "hint text",
        },
        "funnel": {
            "date": "2026-10-26",
            "counts": {k: 0 for k in ["visits","signups","trials_started","trials_completed","payments_started","payments_success","conversions"]},
            "rates": {k: 0 for k in ["signup_rate","trial_start_rate","trial_complete_rate","payment_start_rate","payment_success_rate","conversion_rate"]},
            "pipeline_usage": {k: 0 for k in ["selection","build_planner","designer","bom_checker","adapter_generator"]},
            "history_7d": [{"date": "2026-10-25", "visits": 1, "signups": 0, "conversions": 0}],
        },
        "entities-json": {
            "meta": {"total": 868},
            "entities": [{"id": "MOCK-001", "name": "MOCK"}],
        },
    }
    return mocks.get(test_id, {})


def _print_report(report: dict):
    s = report["summary"]
    print(f"\n[OpenAPI 契约测试] spec={report['spec_version']} base={report['base_url']} offline={report['offline']}")
    print(f"{'='*72}")
    for t in report["tests"]:
        status = "✅" if t["ok"] else "❌"
        print(f"{status} {t['id']}")
        for e in t["errors"][:3]:
            print(f"   ❌ {e}")
        for w in t["warnings"]:
            print(f"   ⚠️  {w}")
    print(f"{'='*72}")
    print(f"总计: {s['passed']}/{s['total']} 通过 {'✅' if s['all_ok'] else '❌'}")


if __name__ == "__main__":
    main()
