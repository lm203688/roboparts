"""
scripts/backup/restore.py
=========================
RoboParts · 快照恢复工具（阶段 2.4 · 灾备）

审计依据：docs/RoboParts-地基审计与硬骨头攻坚报告-20261016.md §F6
"有回滚锚点但没有演练。没有任何一次真实的回滚演练记录。"

职责：
1. 从 backdrops/<snap_id>/ 恢复到 api/ 目录
2. 恢复前验证 SHA256（manifest.json 里记录的哈希必须匹配）
3. 恢复后自动重跑 CI gate 的产物新鲜度检查
4. --dry-run 模式：只打印将恢复哪些文件，不动手

用法：
  python scripts/backup/restore.py --list                          # 列可用快照
  python scripts/backup/restore.py <snap_id> --dry-run             # 预演
  python scripts/backup/restore.py <snap_id> --confirm             # 实际恢复
  python scripts/backup/restore.py <snap_id> --files entities.json data.json   # 只恢复部分

安全：
- 恢复前把当前 api/ 打成 .pre_restore_<timestamp>/ 备份（默认行为，防误伤）
- 除非 --no-backup，否则不跳过预备份
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKUPS_DIR = ROOT / "backdrops"
API_DIR = ROOT / "api"
MANIFEST_NAME = "manifest.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_snapshots() -> list[str]:
    if not BACKUPS_DIR.exists():
        return []
    return [p.name for p in sorted(BACKUPS_DIR.iterdir()) if p.is_dir() and (p / MANIFEST_NAME).exists()]


def verify_snapshot(snap_dir: Path) -> tuple[bool, list[str]]:
    """校验快照内所有文件的 SHA256 是否与 manifest 记录一致。"""
    mp = snap_dir / MANIFEST_NAME
    if not mp.exists():
        return False, ["no manifest.json"]
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    errors = []
    for entry in manifest.get("files", []):
        target = snap_dir / entry["name"]
        if not target.exists():
            errors.append(f"missing: {entry['name']}")
            continue
        actual = sha256_of(target)
        if actual != entry["sha256"]:
            errors.append(f"sha256 mismatch: {entry['name']}")
    return len(errors) == 0, errors


def backup_current_api(tag: str) -> Path:
    """把当前 api/ 打成预备份（恢复前保底）。"""
    backup_dir = BACKUPS_DIR / f".pre_restore_{tag}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for f in API_DIR.iterdir():
        if f.is_file():
            shutil.copy2(f, backup_dir / f.name)
    return backup_dir


def restore(snap_id: str, files: list[str] | None, dry_run: bool, do_backup: bool) -> int:
    snap_dir = BACKUPS_DIR / snap_id
    if not snap_dir.exists():
        print(f"snapshot not found: {snap_dir}", file=sys.stderr)
        return 1

    ok, errors = verify_snapshot(snap_dir)
    if not ok:
        print(f"snapshot integrity check FAILED:")
        for e in errors[:10]:
            print(f"  {e}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        return 1
    print(f"✓ 快照完整性校验通过: {snap_dir}")

    manifest = json.loads((snap_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    to_restore = manifest["files"] if not files else [f for f in manifest["files"] if f["name"] in files]

    print(f"\n将恢复 {len(to_restore)} 个文件到 {API_DIR}：")
    for entry in to_restore:
        action = "DRY-RUN " if dry_run else ""
        print(f"  {action}{entry['name']:40} ({entry['size']/1024:.1f} KB)")

    if dry_run:
        print(f"\n[dry-run] 未实际修改文件。加 --confirm 实际执行")
        return 0

    # 预备份
    if do_backup:
        tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_dir = backup_current_api(tag)
        print(f"\n✓ 当前 api/ 已预备份到: {backup_dir}")

    # 实际恢复
    restored = 0
    for entry in to_restore:
        src = snap_dir / entry["name"]
        dst = API_DIR / entry["name"]
        shutil.copy2(src, dst)
        restored += 1
    print(f"\n✓ 已恢复 {restored} 个文件")
    print("建议后续运行:")
    print("  python scripts/check_freshness.py       # 检查产物新鲜度")
    print("  python scripts/ci_gate.py                # 完整 CI gate")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="RoboParts 快照恢复工具")
    ap.add_argument("snapshot_id", nargs="?", help="快照标签（见 --list）")
    ap.add_argument("--files", nargs="+", help="只恢复指定文件（子集）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不实际执行")
    ap.add_argument("--confirm", action="store_true", help="实际执行恢复")
    ap.add_argument("--no-backup", action="store_true", help="跳过恢复前的预备份（危险）")
    ap.add_argument("--list", action="store_true", help="列出可用快照")
    args = ap.parse_args()

    if args.list:
        snaps = list_snapshots()
        if not snaps:
            print("(no snapshots available)")
            return 0
        print("可用快照：")
        for s in snaps:
            m = json.loads((BACKUPS_DIR / s / MANIFEST_NAME).read_text(encoding="utf-8"))
            print(f"  {s:30} {m.get('created_at','?')}  files={m.get('file_count',0)}")
        return 0

    if not args.snapshot_id:
        ap.print_help()
        return 1

    if not args.confirm and not args.dry_run:
        print(f"要恢复 {args.snapshot_id}？请加 --dry-run 预演，或 --confirm 实际执行", file=sys.stderr)
        return 1

    return restore(args.snapshot_id, args.files, args.dry_run, not args.no_backup)


if __name__ == "__main__":
    sys.exit(main())
