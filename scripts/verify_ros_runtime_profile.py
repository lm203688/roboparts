#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2-3 ROSRuntimeProfile 契约校验闸门（2026-10-27 落地）

对应审计报告：docs/RoboParts-全面提升与前沿演进报告-20261026.md § 9.3 P2-3
"ROSRuntimeProfile 与启动测试：参考构建在目标 ROS 2 环境实际启动，驱动/消息/QoS 可追"

三态诚实边界（本闸门守的核心）：
- **不越界**：本闸门验证 profile 的**契约完整性**，不验证 ROS 2 环境真的能启动。
  真启动测试需 Docker + ROS 2 镜像，超出本会话范围。
- **不假装**：任何 profile 默认 `validated=false` + `validation_status='inferred_from_metadata'`；
  若有人改 `validated=true` 但没 evidence，闸门判红（假绿防护）。
- **显式登记**：`evidence_gaps` 必须非空——不填 = 假装知道。

四条 check：
1. schema_integrity  — 端点源码里的常量表结构完整（5 个映射表）
2. mapping_consistency — 各映射表键一致性（e.g. CONTROLLERS_BY_ROBOT_TYPE 6 个 type 都在）
3. honest_boundary    — 默认 validated=false、validation_status 三态、evidence_gaps 非空
4. live_endpoint_contract — 线上 /api/urdf/runtime-profile?id=... 响应结构与 schema 对齐

自证：--self-test 提供 5 条对照（基线 / 缺 distro 映射 / 非法 validation_status /
      假绿 validated=true / 缺 evidence_gaps）。

用法：
    python scripts/verify_ros_runtime_profile.py              # 线上验证
    python scripts/verify_ros_runtime_profile.py --offline    # 只跑源码静态检查
    python scripts/verify_ros_runtime_profile.py --self-test  # 自证对照
    python scripts/verify_ros_runtime_profile.py --json       # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://roboparts.cc"
ENDPOINT_PATH = "/api/urdf/runtime-profile"

# 期望的常量键（与端点源文件一一对应）
EXPECTED_KEYS = {
    "SUPPORTED_DISTROS_BY_LEVEL": ["full", "partial", "community", "unknown"],
    "CONTROLLERS_BY_ROBOT_TYPE": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
    "MESSAGE_TYPES_BY_ROBOT_TYPE": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
    "QOS_PROFILES": ["command", "state", "telemetry"],
    "VALIDATION_STATUSES": ["inferred_from_metadata", "community_verified", "tested"],
}

TLS_CTX = ssl.create_default_context()


def fetch(url: str, timeout: int = 15, method: str = "GET"):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": "roboparts-ros-runtime-verifier/1.0",
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
# 源码静态解析
# ---------------------------------------------------------------------------

def parse_endpoint_constants(js_path: Path) -> dict:
    """
    正则从 runtime-profile.js 提取关键常量表。
    只做文本扫描，不做 JS 执行。
    """
    if not js_path.exists():
        raise RuntimeError(f"source not found: {js_path}")
    src = js_path.read_text(encoding="utf-8")

    result = {
        "schema_version": None,
        "supported_distros_keys": [],
        "controllers_keys": [],
        "message_types_keys": [],
        "qos_keys": [],
        "driver_packages": {},
        "default_validated": None,
        "default_validation_status": None,
        "evidence_gaps": [],
    }

    # 1. schema version
    m = re.search(r'PROFILE_SCHEMA_VERSION\s*=\s*"([^"]+)"', src)
    if m:
        result["schema_version"] = m.group(1)

    # 2. SUPPORTED_DISTROS_BY_LEVEL 的键
    block = re.search(r'SUPPORTED_DISTROS_BY_LEVEL\s*=\s*\{(.*?)\};', src, re.DOTALL)
    if block:
        body = re.sub(r"//.*", "", block.group(1))
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        for k in re.finditer(r"^\s*(\w+)\s*:", body, re.MULTILINE):
            result["supported_distros_keys"].append(k.group(1))

    # 3. CONTROLLERS_BY_ROBOT_TYPE 的键
    block = re.search(r'CONTROLLERS_BY_ROBOT_TYPE\s*=\s*\{(.*?)\};', src, re.DOTALL)
    if block:
        body = re.sub(r"//.*", "", block.group(1))
        for k in re.finditer(r"^\s*(\w+)\s*:", body, re.MULTILINE):
            result["controllers_keys"].append(k.group(1))

    # 4. MESSAGE_TYPES_BY_ROBOT_TYPE 的键
    block = re.search(r'MESSAGE_TYPES_BY_ROBOT_TYPE\s*=\s*\{(.*?)\};', src, re.DOTALL)
    if block:
        body = re.sub(r"//.*", "", block.group(1))
        for k in re.finditer(r"^\s*(\w+)\s*:", body, re.MULTILINE):
            result["message_types_keys"].append(k.group(1))

    # 5. QOS_PROFILES 的键（只取顶层键：缩进 2 空格 + 无嵌套对象）
    block = re.search(r'QOS_PROFILES\s*=\s*\{(.*?)\n\};', src, re.DOTALL)
    if block:
        body = re.sub(r"//.*", "", block.group(1))
        # 顶层键：只匹配以 2 空格开头的 `xxx:`，排除 4 空格缩进的子字段
        for k in re.finditer(r"^  (\w+)\s*:", body, re.MULTILINE):
            result["qos_keys"].append(k.group(1))

    # 6. DRIVER_PACKAGE_BY_AUTHOR 的映射（author → package 名）
    # 兼容单/双引号：JS 源用双引号，正则兼容两种
    block = re.search(r'DRIVER_PACKAGE_BY_AUTHOR\s*=\s*\{(.*?)\n\};', src, re.DOTALL)
    if block:
        body = re.sub(r"//.*", "", block.group(1))
        # 双引号优先（JS 源风格），单引号兜底
        for m in re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', body):
            result["driver_packages"][m.group(1)] = m.group(2)
        for m in re.finditer(r"'([^']+)'\s*:\s*'([^']+)'", body):
            result["driver_packages"][m.group(1)] = m.group(2)

    # 7. 默认 validated / validation_status / evidence_gaps
    # 只在 buildRuntimeProfile 函数体里找默认值，避免误匹配 schema_summary 里的描述
    build_fn = re.search(r'function buildRuntimeProfile.*?\n\}', src, re.DOTALL)
    fn_body = build_fn.group(0) if build_fn else src
    m = re.search(r'validated\s*:\s*(true|false)', fn_body)
    if m:
        result["default_validated"] = (m.group(1) == "true")
    # validation_status 兼容单/双引号
    m = re.search(r"validation_status\s*:\s*['\"]([^'\"]+)['\"]", fn_body)
    if m:
        result["default_validation_status"] = m.group(1)
    # evidence_gaps 数组（含字符串列表）
    block = re.search(r'evidence_gaps\s*:\s*\[(.*?)\]', fn_body, re.DOTALL)
    if block:
        for m in re.finditer(r"['\"]([^'\"]+)['\"]", block.group(1)):
            result["evidence_gaps"].append(m.group(1))

    return result


# ---------------------------------------------------------------------------
# 四条 check
# ---------------------------------------------------------------------------

def check_schema_integrity(consts: dict) -> dict:
    """PROFILE_SCHEMA_VERSION + 常量表结构完整性"""
    errors = []
    if not consts.get("schema_version"):
        errors.append("PROFILE_SCHEMA_VERSION not found in source")
    elif not re.match(r"^\d+\.\d+$", consts["schema_version"]):
        errors.append(f"schema_version '{consts['schema_version']}' not semver")

    for table, expected in EXPECTED_KEYS.items():
        if table == "VALIDATION_STATUSES":
            continue  # 枚举，不在 source 里定义
        key_attr = {
            "SUPPORTED_DISTROS_BY_LEVEL": "supported_distros_keys",
            "CONTROLLERS_BY_ROBOT_TYPE": "controllers_keys",
            "MESSAGE_TYPES_BY_ROBOT_TYPE": "message_types_keys",
            "QOS_PROFILES": "qos_keys",
        }[table]
        actual = consts.get(key_attr, [])
        for k in expected:
            if k not in actual:
                errors.append(f"{table} missing key '{k}'")
    return {"ok": len(errors) == 0, "errors": errors, "warnings": []}


def check_mapping_consistency(consts: dict) -> dict:
    """
    各映射表键一致性：controllers 和 message_types 的 6 个 robot_type 必须完全相同。
    防止有人加了 robot_type 但忘了配消息类型。
    """
    errors = []
    ctrl = consts.get("controllers_keys", [])
    msg = consts.get("message_types_keys", [])
    if set(ctrl) != set(msg):
        diff_ctrl_only = set(ctrl) - set(msg)
        diff_msg_only = set(msg) - set(ctrl)
        if diff_ctrl_only:
            errors.append(f"robot_type in CONTROLLERS but not MESSAGE_TYPES: {sorted(diff_ctrl_only)}")
        if diff_msg_only:
            errors.append(f"robot_type in MESSAGE_TYPES but not CONTROLLERS: {sorted(diff_msg_only)}")
    # driver_packages 至少要有 3 家知名厂商
    dp = consts.get("driver_packages", {})
    known = {"KUKA", "Universal Robots", "Franka Emika", "Unitree Robotics"}
    have_known = known & set(dp.keys())
    if len(have_known) < 3:
        errors.append(
            f"DRIVER_PACKAGE_BY_AUTHOR covers {len(have_known)}/4 known brands "
            f"(have {sorted(have_known)}, missing {sorted(known - have_known)})"
        )
    return {"ok": len(errors) == 0, "errors": errors, "warnings": []}


def check_honest_boundary(consts: dict) -> dict:
    """
    三态诚实边界：
    - 默认 validated 必须是 false（不许默认 true）
    - 默认 validation_status 必须是三态之一（inferred_from_metadata / community_verified / tested）
    - evidence_gaps 必须非空且至少包含 'no_runtime_test_performed'
    """
    errors = []
    if consts.get("default_validated") is None:
        errors.append("could not parse default validated from source")
    elif consts.get("default_validated") is True:
        errors.append("default validated=true 但无 evidence——假绿")

    status = consts.get("default_validation_status")
    if status not in EXPECTED_KEYS["VALIDATION_STATUSES"]:
        errors.append(
            f"default validation_status='{status}' not in {EXPECTED_KEYS['VALIDATION_STATUSES']}"
        )

    gaps = consts.get("evidence_gaps", [])
    if not gaps:
        errors.append("evidence_gaps 空——违反三态诚实（'不知道'必须显式可见）")
    elif "no_runtime_test_performed" not in gaps:
        errors.append(
            "evidence_gaps 缺 'no_runtime_test_performed'——当前无 Docker 测试环境，"
            "必须显式登记"
        )
    return {"ok": len(errors) == 0, "errors": errors, "warnings": []}


def check_live_endpoint_contract(base: str) -> dict:
    """
    拉线上 /api/urdf/runtime-profile?id=URDF-001（存在则拉，不存在则拉无 id 模式），
    验证响应结构与 schema 对齐。
    """
    errors = []
    warnings = []
    details = {}

    # 1. 无 id 模式：拿契约描述
    try:
        status, body, headers = fetch(f"{base}{ENDPOINT_PATH}")
        if status != 200:
            errors.append(f"GET {ENDPOINT_PATH} returned HTTP {status}")
            return {"ok": False, "errors": errors, "warnings": warnings, "details": details}
        body_data = json.loads(body)
        details["contract_mode_schema"] = body_data.get("profile_schema_version")
        details["requires_id"] = body_data.get("meta", {}).get("requires_id_param")
        # 必须有 schema_summary.honest_boundary
        summary = body_data.get("schema_summary", {})
        if not summary.get("honest_boundary"):
            errors.append("contract response missing schema_summary.honest_boundary")
        # 响应头必须有 X-RoboParts-ProfileSchema
        hdr_schema = None
        for k, v in headers.items():
            if k.lower() == "x-roboparts-profileschema":
                hdr_schema = v.strip()
                break
        if not hdr_schema:
            errors.append("missing X-RoboParts-ProfileSchema response header")
        elif hdr_schema != details["contract_mode_schema"]:
            errors.append(
                f"header X-RoboParts-ProfileSchema={hdr_schema} "
                f"!= body.profile_schema_version={details['contract_mode_schema']}"
            )
        # X-Data-Version 头
        hdr_dv = None
        for k, v in headers.items():
            if k.lower() == "x-data-version":
                hdr_dv = v.strip()
                break
        if not hdr_dv:
            errors.append("missing X-Data-Version response header")
        details["data_version"] = hdr_dv
    except Exception as e:
        errors.append(f"contract mode fetch failed: {e}")
        return {"ok": False, "errors": errors, "warnings": warnings, "details": details}

    # 2. id 模式：拿具体 profile（可能 404 但也算通过契约）
    try:
        status, body, headers = fetch(f"{base}{ENDPOINT_PATH}?id=URDF-001")
        details["sample_status"] = status
        if status == 200:
            sample = json.loads(body)
            # 验证 profile 结构完整性
            required_top = ["profile_schema_version", "meta", "ros2", "qos",
                          "validated", "validation_status", "evidence_gaps", "honest_limits"]
            for f in required_top:
                if f not in sample:
                    errors.append(f"profile missing required field '{f}'")
            # ros2 子结构
            ros2 = sample.get("ros2", {})
            for f in ["compat_level", "supported_distros", "controllers", "message_types", "details"]:
                if f not in ros2:
                    errors.append(f"profile.ros2 missing '{f}'")
            # qos 三档
            qos = sample.get("qos", {})
            for f in ["command", "state", "telemetry"]:
                if f not in qos:
                    errors.append(f"profile.qos missing '{f}'")
                else:
                    sub = qos[f]
                    for qf in ["reliability", "durability", "history", "depth"]:
                        if qf not in sub:
                            errors.append(f"profile.qos.{f} missing '{qf}'")
            # 诚实边界
            if sample.get("validated") is True:
                errors.append("profile.validated=true 但无 evidence——假绿")
            if sample.get("validation_status") not in EXPECTED_KEYS["VALIDATION_STATUSES"]:
                errors.append(f"profile.validation_status '{sample.get('validation_status')}' invalid")
            if not sample.get("evidence_gaps"):
                errors.append("profile.evidence_gaps empty——违反三态诚实")
            details["sample_validated"] = sample.get("validated")
            details["sample_validation_status"] = sample.get("validation_status")
            details["sample_evidence_gaps"] = sample.get("evidence_gaps")
        elif status == 404:
            # URDF-001 不存在也算通过——契约端点本身工作正常
            warnings.append("URDF-001 not found (404), contract endpoint still OK")
        else:
            errors.append(f"sample fetch returned unexpected HTTP {status}")
    except Exception as e:
        errors.append(f"sample fetch failed: {e}")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "details": details}


# ---------------------------------------------------------------------------
# 自证对照
# ---------------------------------------------------------------------------

SELF_TEST_FIXTURES = [
    (
        "baseline_normal",
        {
            "schema_version": "1.0",
            "supported_distros_keys": ["full", "partial", "community", "unknown"],
            "controllers_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "message_types_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "qos_keys": ["command", "state", "telemetry"],
            "driver_packages": {"KUKA": "x", "Universal Robots": "x", "Franka Emika": "x", "Unitree Robotics": "x"},
            "default_validated": False,
            "default_validation_status": "inferred_from_metadata",
            "evidence_gaps": ["no_runtime_test_performed"],
        },
        True,
        "正常基线：5 表完整 + 三态诚实",
    ),
    (
        "missing_distro_unknown",
        {
            "schema_version": "1.0",
            "supported_distros_keys": ["full", "partial", "community"],  # 缺 unknown
            "controllers_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "message_types_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "qos_keys": ["command", "state", "telemetry"],
            "driver_packages": {"KUKA": "x", "Universal Robots": "x", "Franka Emika": "x", "Unitree Robotics": "x"},
            "default_validated": False,
            "default_validation_status": "inferred_from_metadata",
            "evidence_gaps": ["no_runtime_test_performed"],
        },
        False,
        "SUPPORTED_DISTROS_BY_LEVEL 缺 'unknown' 键（会让 unknown 分支走 fallback）",
    ),
    (
        "invalid_validation_status",
        {
            "schema_version": "1.0",
            "supported_distros_keys": ["full", "partial", "community", "unknown"],
            "controllers_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "message_types_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "qos_keys": ["command", "state", "telemetry"],
            "driver_packages": {"KUKA": "x", "Universal Robots": "x", "Franka Emika": "x", "Unitree Robotics": "x"},
            "default_validated": False,
            "default_validation_status": "guaranteed",  # 非法值
            "evidence_gaps": ["no_runtime_test_performed"],
        },
        False,
        "validation_status='guaranteed' 不在三态枚举",
    ),
    (
        "false_green_validated_true",
        {
            "schema_version": "1.0",
            "supported_distros_keys": ["full", "partial", "community", "unknown"],
            "controllers_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "message_types_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "qos_keys": ["command", "state", "telemetry"],
            "driver_packages": {"KUKA": "x", "Universal Robots": "x", "Franka Emika": "x", "Unitree Robotics": "x"},
            "default_validated": True,  # 假绿
            "default_validation_status": "inferred_from_metadata",
            "evidence_gaps": ["no_runtime_test_performed"],
        },
        False,
        "假绿防护：default validated=true 但 status 还是 inferred_from_metadata",
    ),
    (
        "empty_evidence_gaps",
        {
            "schema_version": "1.0",
            "supported_distros_keys": ["full", "partial", "community", "unknown"],
            "controllers_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "message_types_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "qos_keys": ["command", "state", "telemetry"],
            "driver_packages": {"KUKA": "x", "Universal Robots": "x", "Franka Emika": "x", "Unitree Robotics": "x"},
            "default_validated": False,
            "default_validation_status": "inferred_from_metadata",
            "evidence_gaps": [],  # 空 = 假装知道
        },
        False,
        "evidence_gaps 空——违反三态诚实",
    ),
    (
        "mapping_drift_ctrl_vs_msg",
        {
            "schema_version": "1.0",
            "supported_distros_keys": ["full", "partial", "community", "unknown"],
            "controllers_keys": ["humanoid", "quadruped", "arm", "hand", "gripper", "amr"],
            "message_types_keys": ["humanoid", "quadruped", "arm", "hand", "gripper"],  # 缺 amr
            "qos_keys": ["command", "state", "telemetry"],
            "driver_packages": {"KUKA": "x", "Universal Robots": "x", "Franka Emika": "x", "Unitree Robotics": "x"},
            "default_validated": False,
            "default_validation_status": "inferred_from_metadata",
            "evidence_gaps": ["no_runtime_test_performed"],
        },
        False,
        "映射漂移：CONTROLLERS 有 amr 但 MESSAGE_TYPES 缺 amr",
    ),
]


def run_self_test() -> list[dict]:
    results = []
    for name, mutated, expected_ok, desc in SELF_TEST_FIXTURES:
        si = check_schema_integrity(mutated)
        mc = check_mapping_consistency(mutated)
        hb = check_honest_boundary(mutated)
        got_ok = si["ok"] and mc["ok"] and hb["ok"]
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
    parser.add_argument("--offline", action="store_true", help="只跑源码静态检查")
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
            print(f"\n[ROSRuntimeProfile 自证对照]")
            print(f"{'='*72}")
            for r in results:
                status = "✅" if r["ok"] else "❌"
                print(f"{status} {r['description']}")
                print(f"   expected_ok={r['expected_ok']}  got_ok={r['got_ok']}")
            print(f"{'='*72}")
            print(f"自证: {sum(1 for r in results if r['ok'])}/{len(results)} 通过 "
                  f"{'✅' if all_ok else '❌'}")
        sys.exit(0 if all_ok else 1)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base,
        "offline": args.offline,
        "checks": [],
    }

    # 静态源码检查
    try:
        consts = parse_endpoint_constants(ROOT / "functions" / "api" / "urdf" / "runtime-profile.js")
        report["constants"] = {
            "schema_version": consts["schema_version"],
            "supported_distros_keys": consts["supported_distros_keys"],
            "controllers_keys": consts["controllers_keys"],
            "message_types_keys": consts["message_types_keys"],
            "qos_keys": consts["qos_keys"],
            "driver_package_count": len(consts["driver_packages"]),
            "default_validated": consts["default_validated"],
            "default_validation_status": consts["default_validation_status"],
            "evidence_gaps": consts["evidence_gaps"],
        }
    except Exception as e:
        report["checks"].append({"id": "parse_source", "ok": False, "errors": [str(e)]})
        _output(report, args.json)
        sys.exit(1)

    report["checks"].append({"id": "schema_integrity", **check_schema_integrity(consts)})
    report["checks"].append({"id": "mapping_consistency", **check_mapping_consistency(consts)})
    report["checks"].append({"id": "honest_boundary", **check_honest_boundary(consts)})

    if not args.offline:
        report["checks"].append({
            "id": "live_endpoint_contract",
            **check_live_endpoint_contract(args.base),
        })
    else:
        report["checks"].append({
            "id": "live_endpoint_contract",
            "ok": None, "errors": [], "warnings": [],
            "message": "SKIPPED (offline mode)",
        })

    real_checks = [c for c in report["checks"] if c.get("ok") is not None]
    passed = sum(1 for c in real_checks if c["ok"])
    total = len(real_checks)
    report["summary"] = {
        "total": total, "passed": passed,
        "failed": total - passed, "all_ok": passed == total,
    }

    _output(report, args.json)
    sys.exit(0 if report["summary"]["all_ok"] else 1)


def _output(report: dict, as_json: bool):
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"\n[ROSRuntimeProfile 契约校验] offline={report.get('offline')} base={report.get('base_url')}")
    print(f"{'='*72}")
    consts = report.get("constants", {})
    print(f"schema_version={consts.get('schema_version')}")
    print(f"supported_distros_keys={consts.get('supported_distros_keys')}")
    print(f"controllers_keys={consts.get('controllers_keys')}")
    print(f"message_types_keys={consts.get('message_types_keys')}")
    print(f"qos_keys={consts.get('qos_keys')}")
    print(f"driver_package_count={consts.get('driver_package_count')}")
    print(f"default_validated={consts.get('default_validated')}")
    print(f"default_validation_status={consts.get('default_validation_status')}")
    print(f"evidence_gaps={consts.get('evidence_gaps')}")
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
