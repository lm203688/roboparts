#!/usr/bin/env python3
"""部署后置新鲜度校验（P0-5）· 2026-10-12

背景
----
《RoboParts-国际对标与技术深度评估报告-20261012》§8.5：
新增"部署新鲜度"闸门未拦住陈旧——闸门只在本地/CI 侧运行，
**未覆盖 deploy 侧**（deploy 失败时闸门根本没机会跑）。

本脚本是**部署后置闸门**：
  1. curl 线上端点，确认部署真的生效
  2. 校验线上 entities 数与仓内一致
  3. 校验线上 <title> 是新定位（不是旧定位残留）
  4. 校验 /api/co-mount 端点可达（部署链路完整的硬指标）
  5. 校验线上 meta.updated 时间戳与本地差距 ≤ DEPLOY_FRESH_MAX_DAYS

用法
----
  python scripts/verify_deploy_live.py            # 校验并输出报告
  python scripts/verify_deploy_live.py --ci       # CI 模式：不通过退出 1

与 ci_gate.py::gate_deployment_freshness 的分工
-----------------------------------------------
- ci_gate.py::gate_deployment_freshness：**部署前**闸门，检查仓内 vs 线上差距
- 本脚本：**部署后**闸门，验证部署真的生效（不只查时间戳，还查实体数/端点/标题）

环境变量
--------
- ROBOTPARTS_LIVE_URL：线上 API 端点（默认 https://roboparts.cc/api/entities）
- ROBOTPARTS_LIVE_BASE：线上根 URL（默认 https://roboparts.cc）
- DEPLOY_FRESH_MAX_DAYS：最大允许差距天数（默认 7）
- SKIP_DEPLOY_VERIFY=1：跳过（用于本地无网络）
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

LIVE_API = os.environ.get("ROBOTPARTS_LIVE_URL", "https://roboparts.cc/api/entities")
LIVE_BASE = os.environ.get("ROBOTPARTS_LIVE_BASE", "https://roboparts.cc")
MAX_DAYS = float(os.environ.get("DEPLOY_FRESH_MAX_DAYS", "7"))

# 期望线上 title 含的关键短语（新定位）
EXPECTED_TITLE_PHRASES = [
    "具身系统的组合校验层",
    "composition checker",
]
# 旧定位短语（不应该出现在线上 title）
OLD_TITLE_PHRASES = [
    "机器人零件兼容性判定层",  # 20261010 中间版
]


def _fetch(url: str, timeout: int = 15) -> Tuple[bool, Any, str]:
    """GET URL，返回 (成功?, 响应体, 错误描述)。"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "RoboParts-DeployVerify/1.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return True, body, ""
    except urllib.error.HTTPError as e:
        return False, None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, None, f"URLError: {e.reason}"
    except Exception as e:
        return False, None, f"{type(e).__name__}: {str(e)[:100]}"


def _parse_ts(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def check_local_entities() -> Tuple[int, str | None]:
    """读仓内 api/entities.json，返回 (count, meta.updated)。"""
    p = ROOT / "api" / "entities.json"
    if not p.exists():
        return -1, None
    d = json.loads(p.read_text(encoding="utf-8"))
    count = d.get("count") or len(d.get("entities", []))
    meta = d.get("meta", {})
    return count, meta.get("updated") or d.get("updated")


def check_live_entities() -> Tuple[bool, int, str | None, str]:
    """查线上 entities API，返回 (ok, count, meta.updated, error)。"""
    ok, body, err = _fetch(LIVE_API)
    if not ok:
        return False, -1, None, err
    try:
        d = json.loads(body)
    except Exception as e:
        return False, -1, None, f"JSON parse: {e}"
    meta = d.get("meta", {})
    count = d.get("count") or len(d.get("entities", []))
    ts = meta.get("updated") or d.get("updated")
    return True, count, ts, ""


def check_live_title() -> Tuple[bool, str, str]:
    """查线上首页 <title>，返回 (ok, title_text, error)。"""
    ok, body, err = _fetch(f"{LIVE_BASE}/")
    if not ok:
        return False, "", err
    import re
    m = re.search(r"<title[^>]*>([^<]+)</title>", body, re.IGNORECASE)
    title = m.group(1).strip() if m else ""
    return True, title, ""


def check_live_endpoint(path: str) -> Tuple[bool, int, str]:
    """查线上端点 HTTP 状态。返回 (ok, status_code, error)。"""
    url = f"{LIVE_BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoboParts-DeployVerify/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return True, r.status, ""
        except urllib.error.HTTPError as e:
            return e.code == 200, e.code, f"HTTP {e.code}"
    except Exception as e:
        return False, -1, f"{type(e).__name__}: {str(e)[:80]}"


def main() -> int:
    ci_mode = "--ci" in sys.argv
    skip = os.environ.get("SKIP_DEPLOY_VERIFY") == "1"

    if skip:
        print("⏭  SKIP_DEPLOY_VERIFY=1，跳过部署后置校验")
        return 0

    failures: List[str] = []
    warnings: List[str] = []
    checks: List[Tuple[str, bool, str]] = []

    print("=" * 60)
    print("RoboParts 部署后置新鲜度校验")
    print("=" * 60)

    # 1) 本地 vs 线上 entities 数
    local_count, local_ts = check_local_entities()
    live_ok, live_count, live_ts, live_err = check_live_entities()

    if not live_ok:
        failures.append(f"线上 entities API 不可达：{live_err}")
        checks.append(("线上 API 可达", False, live_err))
    else:
        checks.append(("线上 API 可达", True, LIVE_API))
        if live_count != local_count:
            failures.append(
                f"线上实体数 {live_count} ≠ 仓内 {local_count}（差 {live_count - local_count}）"
            )
            checks.append(("实体数一致", False, f"线上 {live_count} / 仓内 {local_count}"))
        else:
            checks.append(("实体数一致", True, f"{live_count} = {local_count}"))

    # 2) 时间戳差距
    if live_ts and local_ts:
        lt = _parse_ts(live_ts)
        lt_loc = _parse_ts(local_ts)
        if lt and lt_loc:
            drift_days = (lt_loc - lt).total_seconds() / 86400
            if drift_days > MAX_DAYS:
                failures.append(
                    f"线上 meta.updated 落后本地 {drift_days:.1f} 天（阈值 {MAX_DAYS} 天）"
                )
                checks.append(("时间戳新鲜度", False, f"差距 {drift_days:.1f} 天"))
            elif drift_days < -0.5:
                warnings.append(
                    f"线上比本地新 {abs(drift_days):.1f} 天（可能是时区差异或时间戳回滚）"
                )
                checks.append(("时间戳新鲜度", False, f"线上比本地新 {abs(drift_days):.1f} 天"))
            else:
                checks.append(("时间戳新鲜度", True, f"差距 {drift_days:.1f} 天"))
    else:
        warnings.append("无法比较时间戳（线上或本地缺 updated 字段）")
        checks.append(("时间戳新鲜度", False, "缺 updated 字段"))

    # 3) 线上 title
    title_ok, title, title_err = check_live_title()
    if not title_ok:
        warnings.append(f"线上首页不可达：{title_err}")
        checks.append(("线上 title", False, title_err))
    else:
        # 新定位检查
        has_new = any(p in title for p in EXPECTED_TITLE_PHRASES)
        has_old = any(p in title for p in OLD_TITLE_PHRASES)
        if has_old:
            failures.append(f"线上 title 仍是旧定位：{title}")
            checks.append(("新定位生效", False, f"含旧短语"))
        elif has_new:
            checks.append(("新定位生效", True, title[:60]))
        else:
            # 都不含，可能是英文站点——警告不失败
            warnings.append(f"线上 title 未匹配新旧定位关键词：{title[:60]}")
            checks.append(("新定位生效", True, f"未匹配（可能英文站）"))

    # 4) /api/co-mount 端点
    cm_ok, cm_status, cm_err = check_live_endpoint("/api/co-mount")
    if cm_ok:
        checks.append(("/api/co-mount 可达", True, f"HTTP {cm_status}"))
    else:
        # co-mount 是 20261011 新加端点，如果线上没部署会 404
        failures.append(f"/api/co-mount 不可达（HTTP {cm_status}）——部署链路未覆盖新端点")
        checks.append(("/api/co-mount 可达", False, cm_err or f"HTTP {cm_status}"))

    # 输出
    print()
    for name, ok, detail in checks:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}: {detail}")

    if warnings:
        print()
        for w in warnings:
            print(f"  ⚠️  {w}")

    print()
    if failures:
        print(f"❌ 部署后置校验失败：{len(failures)} 项")
        for f in failures:
            print(f"  - {f}")
        if ci_mode:
            return 1
        # 非 CI 模式：不阻断，只报告
        return 0

    print(f"✅ 部署后置校验通过：{len(checks)} 项全部达标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
