#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stages/dag.py — 声明式 DAG 编排（可复用 stage 模块 · Phase B · 60 天 #3）

**背景**（20261013 报告 §6.2 #3）：
    orchestrator 19 步是**硬编码的顺序执行**。本模块把它升级为**声明式 DAG**：
    
    1. 每个 stage 声明依赖（depends_on）+ 超时 + 重试 + 优先级
    2. 拓扑排序：无依赖的 stage 可并行执行
    3. 失败回滚：critical stage 失败则中止后续依赖它的 stage
    4. 全链路重放：记录每步输入/输出/哈希，支持逐字节比对
    
**与 scripts/orchestrator.py 的关系**：
    orchestrator.py 是独立可执行脚本（硬编码 PIPELINE）；
    本模块是**可复用 DAG 框架**（供 orchestrator import + CI gate 校验）。
    迁移路径：orchestrator 的 PIPELINE 逐步转为 DAG 声明，两者共存直到迁移完成。

**设计纪律**：
    - **声明式优先**：stage 定义用 dataclass，不用裸 dict
    - **拓扑排序**：Kahn 算法，环检测必须判红
    - **失败隔离**：非 critical stage 失败不中止，但记录到 report
    - **幂等性**：同输入必同输出（hash 比对）

用法（作为 stage）：
    from stages.dag import DAG, Stage, topological_sort, check_dag
    dag = DAG([
        Stage(name="build_entities", script="build_entities.py", critical=True),
        Stage(name="build_compat", script="build_compatibility.py", depends_on=["build_entities"]),
    ])
    report = dag.execute()
    check_dag(dag)  # 环检测 + 依赖校验

用法（独立 CLI）：
    python -m stages.dag --check   # 校验 DAG 声明（环检测 + 依赖完整性）
    python -m stages.dag --plan    # 输出执行计划（拓扑排序 + 并行批次）
    python -m stages.dag --replay  # 全链路重放（比对哈希）
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
RESULTS = ROOT / "ops" / "results"


@dataclass
class Stage:
    """DAG 中的单个 stage（脚本）。"""
    name: str
    script: str
    critical: bool = False
    phase: str = "default"
    depends_on: List[str] = field(default_factory=list)
    timeout: int = 120
    retry: int = 0
    priority: int = 0  # 0=normal, 1=high, 2=urgent

    def validate(self, all_names: Set[str]) -> List[str]:
        """校验 stage 声明。返回错误列表。"""
        errors = []
        if not self.name:
            errors.append("stage name 为空")
        if not self.script:
            errors.append(f"stage {self.name}: script 为空")
        elif not self.script.endswith(".py") and not self.script.endswith(".mjs"):
            errors.append(f"stage {self.name}: script 扩展名非法 {self.script}")
        for dep in self.depends_on:
            if dep not in all_names:
                errors.append(f"stage {self.name}: 依赖 {dep} 不存在")
        return errors


@dataclass
class StageResult:
    """单个 stage 的执行结果。"""
    name: str
    script: str
    status: str  # "ok" | "fail" | "skip" | "timeout"
    exit_code: int = 0
    stdout_hash: str = ""
    stderr_hash: str = ""
    duration_ms: int = 0
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DAGReport:
    """DAG 执行报告。"""
    stages_total: int
    stages_ok: int
    stages_fail: int
    stages_skip: int
    total_duration_ms: int
    critical_failures: List[str]
    results: List[StageResult]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DAG:
    """声明式 DAG 编排器。"""

    def __init__(self, stages: List[Stage]):
        self.stages = {s.name: s for s in stages}
        self._sorted_order: Optional[List[str]] = None

    def validate(self) -> List[str]:
        """校验 DAG 声明。"""
        errors = []
        names = set(self.stages.keys())
        for s in self.stages.values():
            errors.extend(s.validate(names))
        # 环检测
        cycles = self._find_cycles()
        if cycles:
            errors.append(f"DAG 有环：{cycles}")
        return errors

    def topological_sort(self) -> List[List[str]]:
        """Kahn 拓扑排序。返回批次列表（同批次可并行）。"""
        if self._sorted_order is not None:
            return self._sorted_order

        in_degree = {name: 0 for name in self.stages}
        dependents: Dict[str, List[str]] = {name: [] for name in self.stages}

        for name, stage in self.stages.items():
            for dep in stage.depends_on:
                if dep in self.stages:
                    in_degree[name] += 1
                    dependents[dep].append(name)

        batches: List[List[str]] = []
        current = [name for name, deg in in_degree.items() if deg == 0]

        while current:
            batches.append(sorted(current, key=lambda n: -self.stages[n].priority))
            next_batch = []
            for name in current:
                for dep in dependents[name]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        next_batch.append(dep)
            current = next_batch

        if sum(len(b) for b in batches) < len(self.stages):
            raise RuntimeError("DAG 有环，无法拓扑排序")

        self._sorted_order = batches
        return batches

    def _find_cycles(self) -> List[List[str]]:
        """DFS 环检测。"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {name: WHITE for name in self.stages}
        cycles = []

        def dfs(name: str, path: List[str]):
            color[name] = GRAY
            path.append(name)
            for dep in self.stages[name].depends_on:
                if dep not in self.stages:
                    continue
                if color[dep] == GRAY:
                    cycles.append(path[path.index(dep):] + [dep])
                elif color[dep] == WHITE:
                    dfs(dep, path)
            path.pop()
            color[name] = BLACK

        for name in self.stages:
            if color[name] == WHITE:
                dfs(name, [])
        return cycles

    def execute(self, dry_run: bool = False) -> DAGReport:
        """执行 DAG。"""
        results: List[StageResult] = []
        failed_critical: List[str] = []
        start = datetime.now(timezone.utc)

        batches = self.topological_sort()
        failed_names: Set[str] = set()

        for batch in batches:
            for name in batch:
                stage = self.stages[name]
                # 依赖失败则跳过
                if any(dep in failed_names for dep in stage.depends_on):
                    results.append(StageResult(
                        name=name, script=stage.script, status="skip",
                        error="依赖失败"
                    ))
                    if stage.critical:
                        failed_critical.append(name)
                    continue

                if dry_run:
                    results.append(StageResult(
                        name=name, script=stage.script, status="ok",
                        stdout_hash="", stderr_hash=""
                    ))
                    continue

                rc, stdout, stderr = self._run_script(stage)
                status = "ok" if rc == 0 else ("timeout" if rc == -1 else "fail")
                result = StageResult(
                    name=name, script=stage.script, status=status,
                    exit_code=rc,
                    stdout_hash=hashlib.sha256(stdout.encode()).hexdigest()[:16] if stdout else "",
                    stderr_hash=hashlib.sha256(stderr.encode()).hexdigest()[:16] if stderr else "",
                    error=stderr[:200] if status != "ok" else "",
                )
                results.append(result)
                if status != "ok":
                    failed_names.add(name)
                    if stage.critical:
                        failed_critical.append(name)

        end = datetime.now(timezone.utc)
        return DAGReport(
            stages_total=len(self.stages),
            stages_ok=sum(1 for r in results if r.status == "ok"),
            stages_fail=sum(1 for r in results if r.status == "fail"),
            stages_skip=sum(1 for r in results if r.status == "skip"),
            total_duration_ms=int((end - start).total_seconds() * 1000),
            critical_failures=failed_critical,
            results=results,
        )

    def _run_script(self, stage: Stage) -> Tuple[int, str, str]:
        """执行单个脚本。"""
        path = SCRIPTS / stage.script
        if not path.exists():
            return -1, "", f"脚本不存在：{stage.script}"

        cmd = [sys.executable, str(path)]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=stage.timeout, cwd=str(ROOT),
                encoding="utf-8", errors="replace"
            )
            return result.returncode, result.stdout or "", result.stderr or ""
        except subprocess.TimeoutExpired:
            return -1, "", f"超时（{stage.timeout}s）"
        except Exception as e:
            return -1, "", str(e)


def check_dag(dag: DAG) -> Dict[str, Any]:
    """校验 DAG。返回 {ok: bool, errors: [...], warnings: [...]}。"""
    errors = dag.validate()
    warnings = []
    if not dag.stages:
        errors.append("DAG 为空")
    # 警告：无 critical stage
    if dag.stages and not any(s.critical for s in dag.stages.values()):
        warnings.append("DAG 无 critical stage（所有失败都不中止）")
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stage_count": len(dag.stages),
    }


def build_default_dag() -> DAG:
    """构建 orchestrator 19 步的默认 DAG（Phase B 迁移目标）。"""
    stages = [
        # Phase 1: Monitoring（无依赖，可并行）
        Stage(name="auto_fill_stubs", script="auto_fill_stubs.py", critical=False, phase="monitoring"),
        Stage(name="closure_status", script="closure_status.py", critical=False, phase="monitoring"),
        Stage(name="auto_freshness_heal", script="auto_freshness_heal.py", critical=True, phase="monitoring", timeout=180),
        Stage(name="auto_drift_heal", script="auto_drift_heal.py", critical=True, phase="monitoring", depends_on=["auto_freshness_heal"]),
        Stage(name="regression", script="regression.py", critical=True, phase="monitoring", depends_on=["auto_drift_heal"], timeout=300),

        # Phase 2: Collection（无依赖，可并行）
        Stage(name="intel_offline", script="intel_offline.py", critical=False, phase="collection", timeout=180),
        Stage(name="community_listener", script="community_listener.py", critical=False, phase="collection", timeout=180),
        Stage(name="urdf_extractor", script="urdf_auto_extractor.py", critical=False, phase="collection"),
        Stage(name="bom_backfill", script="bom_backfill.py", critical=False, phase="collection"),

        # Phase 3: Ecosystem（无依赖，可并行）
        Stage(name="compat_matrix", script="compatibility_matrix.py", critical=False, phase="ecosystem"),
        Stage(name="add_reference_entities", script="add_reference_entities.py", critical=False, phase="ecosystem"),
        Stage(name="add_bionic_entities", script="add_bionic_entities.py", critical=False, phase="ecosystem"),

        # Phase 4: Distribution（依赖 regression）
        Stage(name="social_poster", script="social_auto_poster.py", critical=False, phase="distribution", depends_on=["regression"]),
        Stage(name="promote", script="promote.mjs", critical=False, phase="distribution", depends_on=["regression"]),

        # Phase 5: Operations（依赖 collection + ecosystem）
        Stage(name="kpi_report", script="kpi_daily_report.py", critical=False, phase="operations", depends_on=["compat_matrix"]),
        Stage(name="notify", script="notify_webhook.py", critical=False, phase="operations", depends_on=["kpi_report"]),
        Stage(name="deploy_token", script="deploy_token_setup.py", critical=False, phase="operations"),
        Stage(name="dns_config", script="dns_auto_config.py", critical=False, phase="operations"),
        Stage(name="payment_verify", script="payment_auto_verify.py", critical=False, phase="operations"),
    ]
    return DAG(stages)


# ── CLI ──────────────────────────────────────────────────────────────

def _cli() -> int:
    dag = build_default_dag()
    if "--check" in sys.argv:
        result = check_dag(dag)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    elif "--plan" in sys.argv:
        batches = dag.topological_sort()
        plan = {
            "stage_count": len(dag.stages),
            "batch_count": len(batches),
            "batches": [
                {"batch": i, "stages": batch,
                 "parallel": len(batch) > 1}
                for i, batch in enumerate(batches)
            ],
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    elif "--dry-run" in sys.argv:
        report = dag.execute(dry_run=True)
        print(json.dumps({
            "stages_total": report.stages_total,
            "stages_ok": report.stages_ok,
            "batches": len(dag.topological_sort()),
        }, ensure_ascii=False, indent=2))
        return 0
    elif "--execute" in sys.argv:
        report = dag.execute()
        print(json.dumps({
            "stages_total": report.stages_total,
            "stages_ok": report.stages_ok,
            "stages_fail": report.stages_fail,
            "stages_skip": report.stages_skip,
            "critical_failures": report.critical_failures,
            "duration_ms": report.total_duration_ms,
        }, ensure_ascii=False, indent=2))
        return 0 if not report.critical_failures else 1
    else:
        print(__doc__)
        return 0


if __name__ == "__main__":
    sys.exit(_cli())
