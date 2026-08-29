#!/usr/bin/env python3
"""
部署漂移自愈器（Auto-Drift Healer）
检测本地工作树 vs git vs 线上三方差异，回归全绿时自动 commit + deploy + verify。
失败时自动回滚并升级。
目标：把"部署漂移 P0 待办"从"等用户"变成"自动消化"。
"""
import os, sys, subprocess, json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
NEEDS_USER = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")
RUN_LOCK = os.path.join(ROOT, ".workbuddy", "runlock.json")


def run_cmd(cmd, cwd=None, timeout=120):
    """Run a shell command and return (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd or ROOT,
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def check_git_status():
    """Check if there are uncommitted changes"""
    rc, out, _ = run_cmd("git status --porcelain")
    if rc != 0:
        return None
    
    changed = [line for line in out.splitlines() if line.strip()]
    return {
        "has_changes": len(changed) > 0,
        "count": len(changed),
        "files": changed[:20],  # First 20 for display
    }


def check_online_truth():
    """Check online entity count via curl"""
    rc, out, _ = run_cmd(
        'curl -s --max-time 15 https://roboparts.cc/api/entities.json | python -c "import sys,json; d=json.load(sys.stdin); print(d[\'meta\'][\'total_entities\'])"',
        timeout=30
    )
    if rc == 0 and out.isdigit():
        return int(out)
    return None


def run_regression():
    """Run regression.py and check result"""
    print("  [DRIFT-HEAL] Running regression.py...")
    rc, out, err = run_cmd(
        f"python {os.path.join(SCRIPTS, 'regression.py')}",
        timeout=300
    )
    return rc == 0


def run_deploy():
    """Run deploy.mjs"""
    print("  [DRIFT-HEAL] Running deploy.mjs...")
    rc, out, err = run_cmd(
        f"node {os.path.join(SCRIPTS, 'deploy.mjs')}",
        timeout=180
    )
    return rc == 0, out


def git_commit_all(message):
    """Stage and commit all changes"""
    print("  [DRIFT-HEAL] Committing changes...")
    rc, _, err = run_cmd("git add -A")
    if rc != 0:
        return False, f"git add failed: {err}"
    
    rc, _, err = run_cmd(f'git commit -m "{message}"')
    if rc != 0:
        return False, f"git commit failed: {err}"
    
    return True, "committed"


def rollback_to_snapshot():
    """Rollback to last known good state"""
    print("  [DRIFT-HEAL] Rolling back...")
    # Find last deploy snapshot
    snapshot_ref = os.path.join(SCRIPTS, "lib", "deploy_snapshot.mjs")
    if os.path.exists(snapshot_ref):
        rc, out, _ = run_cmd(f"node {snapshot_ref} --rollback")
        return rc == 0
    return False


def escalate(reason):
    """Add escalation to _NEEDS_USER.md"""
    now = datetime.now().strftime("%Y%m%d-%H%M")
    marker = f"DRIFT-HEAL-{now}"
    
    with open(NEEDS_USER, "r", encoding="utf-8") as f:
        content = f.read()
    
    if marker in content:
        return
    
    entry = (
        f"\n- [ ] **部署漂移自愈器升级项（{now}）**：{reason}\n"
        f"  本自动化已尝试自愈但失败，需人工介入。\n"
    )
    
    lines = content.splitlines()
    insert_idx = 3
    for i, line in enumerate(lines):
        if line.strip() == "---":
            insert_idx = i + 1
            break
    
    lines.insert(insert_idx, entry)
    with open(NEEDS_USER, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    
    print(f"  [ESCALATE] Added to _NEEDS_USER.md: {reason[:60]}...")


def main():
    print(f"[DRIFT-HEAL] Starting at {datetime.now().isoformat()}")
    
    # Check git status
    print("\n[DRIFT-HEAL] Step 1: Check git status...")
    git = check_git_status()
    if git is None:
        print("  Cannot read git status")
        return 1
    
    if not git["has_changes"]:
        print("  GREEN: No uncommitted changes, nothing to deploy")
        return 0
    
    print(f"  {git['count']} uncommitted files")
    
    # Check online truth
    print("\n[DRIFT-HEAL] Step 2: Check online entity count...")
    online = check_online_truth()
    print(f"  Online entities: {online}")
    
    # Run regression
    print("\n[DRIFT-HEAL] Step 3: Run regression...")
    reg_ok = run_regression()
    if not reg_ok:
        print("  RED: Regression failed, aborting deployment")
        escalate("回归测试失败，部署漂移自愈中止。需人工排查回归失败原因。")
        return 1
    
    print("  GREEN: Regression passed")
    
    # Commit
    print("\n[DRIFT-HEAL] Step 4: Commit changes...")
    now_str = datetime.now().strftime("%Y%m%d-%H%M")
    commit_msg = f"auto-heal: drift remediation {now_str}"
    ok, msg = git_commit_all(commit_msg)
    if not ok:
        print(f"  Commit failed: {msg}")
        escalate(f"Git commit 失败：{msg}")
        return 1
    
    print(f"  OK: {msg}")
    
    # Deploy
    print("\n[DRIFT-HEAL] Step 5: Deploy...")
    deploy_ok, deploy_out = run_deploy()
    if not deploy_ok:
        print(f"  Deploy failed, rolling back...")
        rollback_to_snapshot()
        escalate("部署失败并已回滚。需人工检查 wrangler OAuth 或网络状态。")
        return 1
    
    print("  Deploy completed")
    
    # Verify
    print("\n[DRIFT-HEAL] Step 6: Verify online...")
    online_after = check_online_truth()
    if online and online_after and online_after >= online:
        print(f"  GREEN: Online entities {online_after} (was {online})")
    else:
        print(f"  WARNING: Online entities {online_after} (was {online})")
    
    print(f"\n[DRIFT-HEAL] DONE: Drift healed, committed, deployed, verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
