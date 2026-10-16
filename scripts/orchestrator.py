#!/usr/bin/env python3
"""
Master Orchestrator v2 - runs ALL automation scripts in correct order
Target: 100% autonomous operation with zero human intervention
Schedule: runs daily, calls all sub-scripts in dependency order
"""
import os, sys, subprocess, json
from datetime import datetime

# Fix Windows GBK encoding issues
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
RESULTS = os.path.join(ROOT, "ops", "results")

# Pipeline organized by phases
PIPELINE = [
    # Phase 1: Monitoring & Detection
    {"name": "1占位追平", "script": "auto_fill_stubs.py", "critical": False, "phase": "monitoring"},
    {"name": "2状态刷新", "script": "closure_status.py", "critical": False, "phase": "monitoring"},
    {"name": "3数字保鲜自愈", "script": "auto_freshness_heal.py", "critical": True, "phase": "monitoring"},
    {"name": "4部署漂移自愈", "script": "auto_drift_heal.py", "critical": True, "phase": "monitoring"},
    {"name": "5回归门禁", "script": "regression.py", "critical": True, "phase": "monitoring"},

    # Phase 2: Data Collection
    {"name": "6社区监听(离线)", "script": "intel_offline.py", "critical": False, "phase": "collection"},
    {"name": "7社区监听(完整)", "script": "community_listener.py", "critical": False, "phase": "collection"},
    {"name": "8URDF抽取", "script": "urdf_auto_extractor.py", "critical": False, "phase": "collection"},
    {"name": "9BOM反喂", "script": "bom_backfill.py", "critical": False, "phase": "collection"},

    # Phase 3: Ecosystem Building
    {"name": "10兼容性矩阵", "script": "compatibility_matrix.py", "critical": False, "phase": "ecosystem"},
    {"name": "11参考项目实体", "script": "add_reference_entities.py", "critical": False, "phase": "ecosystem"},
    {"name": "12仿生机械实体", "script": "add_bionic_entities.py", "critical": False, "phase": "ecosystem"},

    # Phase 4: Content & Distribution
    {"name": "13社交发稿", "script": "social_auto_poster.py", "critical": False, "phase": "distribution"},
    {"name": "14SEO提交", "script": "promote.mjs", "critical": False, "phase": "distribution"},

    # Phase 5: Operations
    {"name": "15KPI日报", "script": "kpi_daily_report.py", "critical": False, "phase": "operations"},
    {"name": "16通知推送", "script": "notify_webhook.py", "critical": False, "phase": "operations"},
    {"name": "17部署令牌", "script": "deploy_token_setup.py", "critical": False, "phase": "operations"},
    {"name": "18DNS配置", "script": "dns_auto_config.py", "critical": False, "phase": "operations"},
    {"name": "19支付自检", "script": "payment_auto_verify.py", "critical": False, "phase": "operations"},
]

# Scripts that need more than default timeout
TIMEOUT_OVERRIDES = {
    "intel_offline.py": 180,  # 3 minutes for multiple API calls
    "regression.py": 300,     # 5 minutes for full regression
    "community_listener.py": 180,
}

PHASE_NAMES = {
    "monitoring": "Phase 1: Monitoring & Detection",
    "collection": "Phase 2: Data Collection",
    "distribution": "Phase 3: Content & Distribution",
    "operations": "Phase 4: Operations",
}


def run_script(script_name, timeout=120):
    """Run a single script and capture output"""
    path = os.path.join(SCRIPTS, script_name)
    if not os.path.exists(path):
        return -1, "", "Script not found: {}".format(script_name)

    # Use override timeout if specified
    actual_timeout = TIMEOUT_OVERRIDES.get(script_name, timeout)

    # Choose interpreter based on file extension
    if script_name.endswith(".mjs") or script_name.endswith(".js"):
        cmd = ["node", path]
    else:
        cmd = [sys.executable, path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=actual_timeout, cwd=ROOT,
            encoding='utf-8', errors='replace'
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return result.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def main():
    start = datetime.now()
    print("[ORCHESTRATOR] Starting full pipeline at {}".format(start.isoformat()))
    print("[ORCHESTRATOR] {} scripts in {} phases\n".format(
        len(PIPELINE), len(PHASE_NAMES)
    ))

    results = []
    current_phase = None

    for step in PIPELINE:
        if step["phase"] != current_phase:
            current_phase = step["phase"]
            print("\n" + "=" * 60)
            print("{}".format(PHASE_NAMES.get(current_phase, current_phase)))
            print("=" * 60)

        print("\n--- {} ---".format(step["name"]))
        rc, stdout, stderr = run_script(step["script"])

        status = "OK" if rc == 0 else "FAIL"
        if rc == -1 and "timeout" in stderr:
            status = "TIMEOUT"

        results.append({
            "name": step["name"],
            "script": step["script"],
            "status": status,
            "rc": rc,
            "phase": step["phase"],
            "critical": step["critical"],
            "stdout_lines": len(stdout.splitlines()) if stdout else 0,
            "stderr_preview": (stderr[:200] if stderr else ""),
        })

        if stdout:
            for line in stdout.splitlines()[:5]:
                print("  {}".format(line))
        if rc != 0 and stderr:
            print("  [STDERR] {}".format(stderr[:150]))

    elapsed = (datetime.now() - start).total_seconds()

    print("\n" + "=" * 60)
    print("[ORCHESTRATOR] Pipeline complete in {:.1f}s".format(elapsed))

    # Phase summary
    phase_stats = {}
    for r in results:
        p = r["phase"]
        if p not in phase_stats:
            phase_stats[p] = {"ok": 0, "fail": 0, "total": 0}
        phase_stats[p]["total"] += 1
        if r["status"] == "OK":
            phase_stats[p]["ok"] += 1
        else:
            phase_stats[p]["fail"] += 1

    print("\nPhase Summary:")
    for phase, stats in phase_stats.items():
        name = PHASE_NAMES.get(phase, phase)
        print("  {}: {}/{} OK".format(name.split(":")[1].strip(), stats["ok"], stats["total"]))

    ok_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    print("\nTotal: {}/{} OK ({:.0f}%)".format(
        ok_count, len(results), 100 * ok_count / len(results)
    ))

    if fail_count:
        print("Failed scripts:")
        for r in results:
            if r["status"] == "FAIL":
                critical = " [CRITICAL]" if r["critical"] else ""
                print("  - {}{}: {}".format(
                    r["name"], critical, r["stderr_preview"][:80]
                ))

    report = {
        "timestamp": start.isoformat(),
        "elapsed_seconds": elapsed,
        "total": len(results),
        "ok": ok_count,
        "fail": fail_count,
        "phase_stats": phase_stats,
        "results": results,
    }

    report_path = os.path.join(
        RESULTS, "_orchestrator-{}.json".format(start.strftime("%Y%m%d"))
    )
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\nReport: {}".format(report_path))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


# ── Phase B: DAG-based pipeline (stages/dag.py migration) ────────────

def run_dag_pipeline(dry_run=False):
    """Run pipeline using stages.dag (Phase B migration).
    
    This is the new DAG-based orchestrator that replaces the legacy PIPELINE.
    It provides:
      - Topological sorting (Kahn's algorithm)
      - Parallel batch execution
      - Cycle detection
      - Checkpoint saving for replay
    
    Args:
        dry_run: If True, validate structure without executing scripts.
    
    Returns:
        DAGReport with execution results, or None if stages.dag unavailable.
    """
    try:
        from stages.dag import build_default_dag, check_dag, save_checkpoint
    except ImportError:
        print('[ORCHESTRATOR] stages.dag not available, skipping DAG pipeline')
        return None
    
    dag = build_default_dag()
    
    # Validate DAG before executing
    check_result = check_dag(dag)
    if not check_result['ok']:
        print('[ORCHESTRATOR] DAG validation failed:')
        for err in check_result['errors']:
            print(f'  - {err}')
        return None
    
    print(f'[ORCHESTRATOR] DAG validated: {check_result["stage_count"]} stages')
    
    # Execute DAG
    report = dag.execute(dry_run=dry_run)
    
    # Save checkpoint for replay
    RESULTS_DIR = os.path.join(ROOT, "ops", "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    checkpoint_path = save_checkpoint(report, path=os.path.join(RESULTS_DIR, 'dag_checkpoint_latest.json'))
    print(f'[ORCHESTRATOR] Checkpoint saved: {checkpoint_path}')
    
    # Print summary
    print(f'[ORCHESTRATOR] Pipeline complete: {report.stages_ok} ok, {report.stages_fail} fail, {report.stages_skip} skip')
    if report.critical_failures:
        print(f'[ORCHESTRATOR] Critical failures: {report.critical_failures}')
    
    return report


def convert_pipeline_to_stages(pipeline=None):
    """Convert legacy PIPELINE dict list to stages.dag Stage objects.
    
    Args:
        pipeline: Legacy PIPELINE list (defaults to module-level PIPELINE).
    
    Returns:
        List of Stage objects.
    """
    try:
        from stages.dag import Stage
    except ImportError:
        print('[ORCHESTRATOR] stages.dag not available')
        return []
    
    if pipeline is None:
        pipeline = PIPELINE
    
    stages = []
    for item in pipeline:
        stage = Stage(
            name=item['name'],
            script=item['script'],
            critical=item.get('critical', False),
            phase=item.get('phase', 'default'),
            depends_on=item.get('depends_on', []),
            timeout=item.get('timeout', 120),
            priority=item.get('priority', 0),
        )
        stages.append(stage)
    
    return stages
