"""
scripts/backup/snapshot_kv.py
=============================
RoboParts · Cloudflare KV 快照脚本（阶段 2.4 · 灾备）

审计依据：docs/RoboParts-地基审计与硬骨头攻坚报告-20261016.md §F6
"5 个 KV namespace 里存着付费积分、API key、供应商数据。丢失 = 不可恢复。"

5 个 namespace（见 wrangler.toml）：
- USER_CREDITS        — 用户积分（付费墙核心）
- API_KEYS            — 用户 API Key
- SUPPLIERS           — 供应商目录
- SUPPLIER_INQUIRIES  — 供应商询价记录
- URDF_LIBRARY        — URDF 模型库

依赖：wrangler CLI（Cloudflare 官方，npx wrangler@latest）
凭据：CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID（env 或 wrangler config）

用法：
  python scripts/backup/snapshot_kv.py                          # 快照全部 5 个 namespace
  python scripts/backup/snapshot_kv.py --namespace USER_CREDITS  # 快照单个
  python scripts/backup/snapshot_kv.py --list                   # 列出历史 KV 快照
  python scripts/backup/snapshot_kv.py --restore USER_CREDITS backdrops/20261016-120000  # 从快照恢复

安全：
- 快照含 API_KEYS（敏感），快照目录**不进 git**（.gitignore 里 backdrops/）
- --restore 是破坏性操作，需 --confirm 二次确认
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKUPS_DIR = ROOT / "backdrops"

# 与 wrangler.toml 对齐
KV_NAMESPACES = [
    "USER_CREDITS",
    "API_KEYS",
    "SUPPLIERS",
    "SUPPLIER_INQUIRIES",
    "URDF_LIBRARY",
]


def check_wrangler() -> bool:
    try:
        r = subprocess.run(["npx", "wrangler", "--version"], capture_output=True, timeout=30, text=True)
        return r.returncode == 0
    except Exception:
        return False


def kv_export(namespace: str, out_dir: Path) -> int:
    """
    用 `wrangler kv:export` 导出单个 namespace。
    返回导出键数量。
    """
    out_file = out_dir / f"{namespace}.json"
    r = subprocess.run(
        ["npx", "wrangler", "kv", "export", namespace, "--binding", namespace, "--output", str(out_file)],
        capture_output=True, timeout=300, text=True,
    )
    if r.returncode != 0:
        print(f"[{namespace}] export FAILED:\n{r.stderr}", file=sys.stderr)
        return -1
    try:
        data = json.loads(out_file.read_text(encoding="utf-8"))
        return len(data.get("kv", []))
    except Exception as e:
        print(f"[{namespace}] parse failed: {e}", file=sys.stderr)
        return -1


def kv_restore(namespace: str, snapshot_dir: Path) -> bool:
    """用 `wrangler kv:import` 从快照恢复。"""
    src = snapshot_dir / f"{namespace}.json"
    if not src.exists():
        print(f"snapshot file not found: {src}", file=sys.stderr)
        return False
    r = subprocess.run(
        ["npx", "wrangler", "kv", "import", namespace, "--binding", namespace, "--input", str(src)],
        capture_output=True, timeout=600, text=True,
    )
    if r.returncode != 0:
        print(f"[{namespace}] restore FAILED:\n{r.stderr}", file=sys.stderr)
        return False
    print(f"[{namespace}] restored")
    return True


def list_kv_snapshots() -> list[dict]:
    if not BACKUPS_DIR.exists():
        return []
    result = []
    for p in sorted(BACKUPS_DIR.iterdir()):
        if not p.is_dir():
            continue
        kv_files = list(p.glob("*.json"))
        kv_files = [f for f in kv_files if f.name != "manifest.json" and f.name != "manifest_kv.json"]
        if kv_files:
            result.append({
                "id": p.name,
                "files": [f.name for f in kv_files],
                "created_at": str(p.stat().st_mtime),
            })
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="RoboParts KV 快照/恢复工具")
    ap.add_argument("--namespace", choices=KV_NAMESPACES, help="仅操作单个 namespace")
    ap.add_argument("--list", action="store_true", help="列出历史 KV 快照")
    ap.add_argument("--restore", nargs=2, metavar=("NAMESPACE", "SNAPSHOT_DIR"), help="从快照恢复 namespace")
    ap.add_argument("--confirm", action="store_true", help="--restore 二次确认（破坏性）")
    ap.add_argument("--tag", help="快照标签（默认 UTC 时间戳）")
    args = ap.parse_args()

    if args.list:
        snaps = list_kv_snapshots()
        if not snaps:
            print("(no kv snapshots yet)")
            return 0
        for s in snaps:
            print(f"{s['id']:30} {s['created_at']}  files={s['files']}")
        return 0

    if args.restore:
        ns, snap_dir = args.restore
        if not args.confirm:
            print(f"破坏性操作！要恢复 {ns} 到线上，请再次运行并加 --confirm", file=sys.stderr)
            return 1
        snap = Path(snap_dir)
        if not snap.is_absolute():
            snap = ROOT / snap
        return 0 if kv_restore(ns, snap) else 1

    # 默认：快照全部
    if not check_wrangler():
        print("wrangler CLI not available. Install with: npx wrangler --version", file=sys.stderr)
        return 1

    missing_env = [k for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
                   if not os.environ.get(k)]
    if missing_env:
        print(f"missing env: {missing_env}. Set them or run wrangler login", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    snap_name = args.tag or now
    snap_dir = BACKUPS_DIR / snap_name
    snap_dir.mkdir(parents=True, exist_ok=False)

    namespaces = [args.namespace] if args.namespace else KV_NAMESPACES
    manifest = {
        "snapshot_id": snap_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "scripts/backup/snapshot_kv.py",
        "namespaces": namespaces,
        "results": {},
    }

    for ns in namespaces:
        n = kv_export(ns, snap_dir)
        manifest["results"][ns] = {"key_count": n}
        print(f"  {ns}: {'FAILED' if n < 0 else f'{n} keys'}")

    (snap_dir / "manifest_kv.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nKV 快照已生成: {snap_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
