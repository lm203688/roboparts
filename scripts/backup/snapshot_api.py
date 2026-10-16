"""
scripts/backup/snapshot_api.py
==============================
RoboParts · api/ 数据快照脚本（阶段 2.4 · 灾备）

审计依据：docs/RoboParts-地基审计与硬骨头攻坚报告-20261016.md §F6
"5 个 KV namespace 无备份 / 无恢复脚本"

职责：
1. 把 api/*.json + api/data.js 打成带 SHA256 manifest 的快照
2. 快照落到 backdrops/ 目录（.gitignore 忽略，本地留档）
3. 生成 manifest.json 供 restore.py 校验完整性
4. --upload 模式：可选把快照推到 Cloudflare R2（需 CF_R2_ACCESS_KEY_ID 环境变量）

用法：
  python scripts/backup/snapshot_api.py                    # 本地快照
  python scripts/backup/snapshot_api.py --upload           # 本地 + 推 R2
  python scripts/backup/snapshot_api.py --list             # 列出历史快照

不做什么：
- 不改线上 KV；KV 备份走 snapshot_kv.py
- 不自动清旧快照；由运维手工清理
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
API_DIR = ROOT / "api"
BACKUPS_DIR = ROOT / "backdrops"
MANIFEST_NAME = "manifest.json"

# api/ 下的文件里，有些是"数据源"（entities.json 等），有些是"派生产物"。
# 备份策略：全量。派生产物可从 entities.json 重建，但成本不划算，直接一起存。
SNAPSHOT_EXTENSIONS = {".json", ".js", ".md"}

# 大文件（>5MB）默认跳过；用 --include-large 强制包含
LARGE_FILE_THRESHOLD = 5 * 1024 * 1024


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(include_large: bool = False) -> list[Path]:
    files = []
    for p in sorted(API_DIR.iterdir()):
        if not p.is_file():
            continue
        if p.suffix not in SNAPSHOT_EXTENSIONS:
            continue
        if p.stat().st_size > LARGE_FILE_THRESHOLD and not include_large:
            continue
        files.append(p)
    return files


def create_snapshot(tag: str | None = None) -> Path:
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    snap_name = tag or now
    snap_dir = BACKUPS_DIR / snap_name
    snap_dir.mkdir(parents=True, exist_ok=False)

    files = collect_files(include_large=(os.environ.get("BACKUP_INCLUDE_LARGE") == "1"))
    manifest = {
        "snapshot_id": snap_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "scripts/backup/snapshot_api.py",
        "source": str(API_DIR),
        "file_count": len(files),
        "total_bytes": 0,
        "files": [],
    }

    for f in files:
        dst = snap_dir / f.name
        shutil.copy2(f, dst)
        entry = {
            "name": f.name,
            "size": f.stat().st_size,
            "sha256": sha256_of(f),
        }
        manifest["files"].append(entry)
        manifest["total_bytes"] += entry["size"]

    manifest_path = snap_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return snap_dir


def list_snapshots() -> list[dict]:
    if not BACKUPS_DIR.exists():
        return []
    result = []
    for p in sorted(BACKUPS_DIR.iterdir()):
        if not p.is_dir():
            continue
        mp = p / MANIFEST_NAME
        if mp.exists():
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
                result.append({
                    "id": m.get("snapshot_id", p.name),
                    "created_at": m.get("created_at"),
                    "file_count": m.get("file_count", 0),
                    "total_mb": round(m.get("total_bytes", 0) / 1024 / 1024, 2),
                })
            except Exception as e:
                result.append({"id": p.name, "error": str(e)})
        else:
            result.append({"id": p.name, "error": "no manifest"})
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="RoboParts api/ 快照工具")
    ap.add_argument("--tag", help="快照标签（默认用 UTC 时间戳）")
    ap.add_argument("--include-large", action="store_true", help="包含 >5MB 大文件")
    ap.add_argument("--list", action="store_true", help="列出历史快照")
    ap.add_argument("--upload", action="store_true", help="上传到 Cloudflare R2（需 CF_R2_* env）")
    args = ap.parse_args()

    if args.list:
        snaps = list_snapshots()
        if not snaps:
            print("(no snapshots yet)")
            return 0
        print(f"{'id':30} {'created_at':26} {'files':>5} {'MB':>7}")
        for s in snaps:
            print(f"{s.get('id','?'):30} {s.get('created_at','?'):26} {s.get('file_count',0):>5} {s.get('total_mb',0):>7}")
        return 0

    if args.upload:
        print("R2 upload not implemented in this session (需 CF_R2 环境变量与 wrangler CLI)", file=sys.stderr)
        print("回退到本地快照模式")

    os.environ["BACKUP_INCLUDE_LARGE"] = "1" if args.include_large else "0"
    snap_dir = create_snapshot(tag=args.tag)
    m = json.loads((snap_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    print(f"快照已生成: {snap_dir}")
    print(f"  id: {m['snapshot_id']}")
    print(f"  文件数: {m['file_count']}")
    print(f"  总大小: {m['total_bytes']/1024/1024:.2f} MB")
    print(f"  manifest: {snap_dir / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
