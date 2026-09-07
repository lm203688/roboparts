#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 外部几何/标准件摄取器：step.parts（MIT 协议，16,847 条 STEP 零件）

为什么做这个
------------
我们自己有两条结构性缺口，恰好被这个项目补上：

1. P0「机械接口声明率 0.48%」——418 条 applicable 实体里只有 2 条 declared。
   根因是厂商不公布法兰几何，而人工查手册不可规模化。
   step.parts 给的不是手册，是 **STEP 几何本体**：CubeMars（27）、myactuator（18）、
   LeaderDrive（25）、达妙（9）、RobStride（9）、SteadyWin（10）、HEBI（12）
   全在人形/仿生机器人主流 QDD 执行器清单上，且每条都带可下载的 STEP。
   几何可程序化抽取安装孔阵列 → 反推 PCD / 孔数 / 孔径。这是填 P0 的自动化路径。

2. 81 条法兰裁决里 72 条判 adapter_required，但裁决只写「两侧分别按各自 PCD/孔数/螺纹开孔」——
   没有说到底用哪颗螺栓。step.parts 有 2,118 条紧固件、37 种标准号，
   M3/M5/M6/M8/M12/M16（我们 9 档法兰的全部螺纹需求）均有 ISO 标准件可直接引用。

口径纪律（沿用 ingest_oss.mjs）
------------------------------
- 只摄取白名单品类，不整库搬运：我们不做 CAD 模型库（那是 step.parts 的活），
  只取「能推进兼容性判定」的那部分。
- 缩水闸门：条目数较上一版缩水 > 10% 拒写（防止抓取半截把库冲掉）。
- 本脚本不修改任何页面数字；新增产物只入 api/step_parts.json，不动 facts()。

用法
----
    python scripts/ingest_step_parts.py                # 在线拉取并写盘
    python scripts/ingest_step_parts.py --dry-run      # 只统计不写盘
    SP_CACHE=.tmp_scan/sp_index.json python scripts/ingest_step_parts.py   # 用本地缓存
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "api" / "step_parts.json"
COMPAT = ROOT / "api" / "negative_compat.json"
DEFAULT_CACHE = ROOT / ".tmp_scan" / "sp_index.json"

INDEX_URL = "https://api.step.parts/v1/catalog/parts.index.json"
# 注意：本机在中国大陆，直连 github.com:443 被封，但 api.step.parts 走 Vercel，实测可达。
# TLS 需 --tlsv1.3 --ssl-no-revoke（TLS-intercepting 代理），详见 MEMORY.md。

# 白名单品类：只取能推进「兼容性判定」的部分
CATEGORY_KEEP = {
    "actuator",          # 执行器 —— 法兰几何抽取源，填 P0
    "fastener",          # 紧固件 —— 转接盘螺栓规格
    "bearing",           # 轴承 —— 轴系接口
    "motion",            # 直线运动
    "power-transmission",  # 齿轮/同步带/联轴器 —— 传动接口
    "spacer",            # 间隔件 —— 转接盘常用
    "profile",           # 型材
}

# 螺纹 + 长度解析： "ISO 10642 hex socket countersunk screw, M3 x 6" → (M3, 6)
THREAD_LEN = re.compile(r"\bM(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)")
THREAD_ONLY = re.compile(r"\bM(\d+(?:\.\d+)?)\b")


def fetch_index(cache: Path | None) -> dict:
    """优先用本地缓存（离线可复现），否则 curl 拉取并顺手落缓存。"""
    if cache and cache.exists():
        print(f"[cache] 使用本地索引 {cache}（{cache.stat().st_size/1048576:.1f} MB）")
        return json.loads(cache.read_text(encoding="utf-8"))

    import subprocess
    print(f"[net ] 拉取 {INDEX_URL} ...")
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
    # curl 而非 requests：本机 TLS 被拦截，Node fetch / requests 均需额外处理
    proc = subprocess.run(
        ["curl", "-s", "--tlsv1.3", "--ssl-no-revoke", "-m", "120", INDEX_URL],
        capture_output=True,
    )
    raw = proc.stdout
    if not raw:
        sys.exit("[fail] 索引拉取为空：网络不可达或索引地址变更")
    data = json.loads(raw.decode("utf-8"))
    if cache:
        cache.write_bytes(raw)
        print(f"[cache] 已缓存到 {cache}")
    return data


def parse_thread(name: str) -> tuple[str | None, float | None]:
    m = THREAD_LEN.search(name)
    if m:
        return f"M{m.group(1)}", float(m.group(2))
    m = THREAD_ONLY.search(name)
    if m:
        return f"M{m.group(1)}", None
    return None, None


def load_flange_thread_needs() -> dict[str, int]:
    """从 negative_compat 现算 9 档法兰的螺纹需求（不读硬编码，避免口径漂移）。"""
    if not COMPAT.exists():
        return {}
    d = json.loads(COMPAT.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for r in d.get("rulings", []):
        ids.update(r.get("pair", []))
    return dict(Counter(i.split("-")[-1] for i in ids if "-" in i))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计不写盘")
    ap.add_argument("--cache", default=os.environ.get("SP_CACHE", str(DEFAULT_CACHE)))
    args = ap.parse_args()

    data = fetch_index(Path(args.cache) if args.cache else None)
    items = data.get("items", [])
    declared = data.get("catalog", {}).get("partCount", len(items))
    print(f"[src ] step.parts 声明 {declared} 条，索引实到 {len(items)} 条")

    kept = []
    for it in items:
        cat = it.get("category")
        if cat not in CATEGORY_KEEP:
            continue
        name = it.get("name", "")
        thread, length = parse_thread(name)
        kept.append({
            "id": it.get("id"),
            "name": name,
            "category": cat,
            "family": it.get("family"),
            "standard": it.get("standard"),
            "thread": thread,
            "length_mm": length,
            "tags": it.get("tags", []),
            "aliases": it.get("aliases", []),
            "pageUrl": it.get("pageUrl"),
            "apiUrl": it.get("apiUrl"),
            "pngUrl": it.get("pngUrl"),
            # stepUrl 需再查 apiUrl 详情，索引层不含，避免上万次请求
        })

    by_cat = Counter(k["category"] for k in kept)
    std_n = sum(1 for k in kept if k.get("standard"))
    thread_n = sum(1 for k in kept if k.get("thread"))

    print(f"[keep] 白名单品类 {len(kept)} 条（占比 {len(kept)/max(len(items),1)*100:.1f}%）")
    for c, n in by_cat.most_common():
        print(f"        {c:20s} {n}")
    print(f"[keep] 带标准号 {std_n} 条 | 可解析螺纹 {thread_n} 条")

    # ---- 对账 1：法兰螺纹需求覆盖率（这决定转接盘螺栓表能否落地）----
    needs = load_flange_thread_needs()
    if needs:
        fast = [k for k in kept if k["category"] == "fastener" and k.get("thread")]
        have = Counter(k["thread"] for k in fast)
        print("\n[账1] 9 档 ISO 9409-1 法兰所需螺纹 vs step.parts 紧固件库存：")
        covered = 0
        for th, want in sorted(needs.items(), key=lambda x: -x[1]):
            got = have.get(th, 0)
            ok = got > 0
            covered += ok
            print(f"        {th:4s} 需求档位 {want:2d} | 库存 {got:4d} 条 | {'OK' if ok else 'MISSING'}")
        print(f"      → 覆盖 {covered}/{len(needs)} 档螺纹"
              f"（{'全部可落地' if covered == len(needs) else '存在缺口'}）")

    # ---- 对账 2：执行器厂商来源（决定 P0 几何抽取的可寻址目标数）----
    acts = [k for k in kept if k["category"] == "actuator"]
    fam = Counter(k.get("family") for k in acts)
    print(f"\n[账2] 可寻址执行器 {len(acts)} 条，厂商分布 top12：")
    for f, n in fam.most_common(12):
        print(f"        {str(f):22s} {n}")

    if args.dry_run:
        print("\n[dry ] --dry-run，未写盘")
        return 0

    # ---- 缩水闸门（沿用 ingest_oss.mjs 的 10% 纪律）----
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            prev_n = prev.get("counts", {}).get("items", 0)
        except Exception:
            prev_n = 0
        if prev_n and len(kept) < prev_n * 0.9:
            sys.exit(
                f"[abort] 条目数 {len(kept)} 较上一版 {prev_n} 缩水 "
                f"{(1 - len(kept)/prev_n)*100:.1f}% > 10%，拒写（疑似抓取半截）"
            )

    payload = {
        "schema": "step_parts/v1",
        "source": {
            "name": "step.parts",
            "index_url": INDEX_URL,
            "license": "MIT（原始项目材料）；第三方 STEP 文件遵循各自 THIRD_PARTY_NOTICES",
            "upstream_part_count": declared,
        },
        "truth_source": "由 scripts/ingest_step_parts.py 现算生成，禁止手改",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "selection_policy": {
            "kept_categories": sorted(CATEGORY_KEEP),
            "rationale": "只摄取能推进兼容性判定的品类；不做通用 CAD 模型库",
        },
        "counts": {
            "items": len(kept),
            "by_category": dict(by_cat.most_common()),
            "with_standard": std_n,
            "with_thread": thread_n,
            "actuator_vendors": len([f for f in fam if f]),
        },
        "flange_thread_coverage": {
            "required": needs,
            "available": dict(Counter(
                k["thread"] for k in kept
                if k["category"] == "fastener" and k.get("thread")
            ).most_common()),
        },
        "items": kept,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[out ] 写入 {OUT.relative_to(ROOT)}（{len(kept)} 条，"
          f"{OUT.stat().st_size/1048576:.2f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
