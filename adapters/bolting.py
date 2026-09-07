#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
转接板螺栓物料清单（BOM）—— 把「几何」补完到「可下单的物料」

为什么单独成模块
----------------
`gen_adapter.py` 负责几何（CadQuery → STEP/STL），但它输出的是一块板，
不包含「装这块板要用哪颗螺丝」。用户拿到 STEP 后的下一个问题是：
买什么螺栓、多长、什么标准、几颗。

这个模块只做一件事：给定两侧法兰 + 板厚 → 输出可直接下单的螺栓条目。
不依赖 CadQuery / OCCT，因此可以：
  · 被 gen_adapter.py 在 --bom 时调用（几何 + 物料一次出齐）；
  · 被网站 / API 直接调用（无重型依赖，CF Pages 也能跑）。

数据源与借鉴
------------
- 法兰几何：api/negative_compat.json（我们自己的 81 条裁决，唯一真相源，现算）
- 螺栓实体：api/step_parts.json（step.parts，MIT，16,847 条 STEP 零件的白名单子集）
  之所以引用它而不是自己造一张螺栓表：它有 ISO 4762 / 7380 / 10642 / 4017 等
  37 种标准号 + M2~M24 全规格 + 可下载 STEP，而我们 9 档法兰需要的
  M3/M5/M6/M8/M12/M16 **全部有库存**（摄取器已对账 6/6）。

诚实边界
--------
- 旋合长度取 1.2×d（ISO 262 常用下限区间 1.0~1.5d），未计垫圈、被连接件孔深与倒角。
- 选用「ISO 4762 内六角圆柱头」为默认头型；若库存无该标准同规格，退而求其次时
  会在条目里标 `standard` 实际值，不伪装成 4762。
- 板厚若由调用方传入，则按该值计算；本模块**不**替你决定板厚是否够强度。

用法
----
    python adapters/bolting.py --list                          # 列出 9 档法兰
    python adapters/bolting.py --a A40 --b A63 --thick 6.3     # 输出物料清单
    python adapters/bolting.py --a A40 --b A63 --thick 6.3 --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMPAT = ROOT / "api" / "negative_compat.json"
STEP_PARTS = ROOT / "api" / "step_parts.json"

ENGAGEMENT = 1.2   # 旋合长度倍数（×d）
DEFAULT_HEAD_STD = "ISO 4762"  # 内六角圆柱头，转接板最常用


def load_designations() -> dict[str, dict]:
    """从 81 条裁决现算 9 档法兰几何。禁止硬编码：口径以裁决库为准。"""
    if not COMPAT.exists():
        sys.exit(f"[fail] 缺少 {COMPAT}，请先跑 scripts/build_negative_compat.py")
    d = json.loads(COMPAT.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for r in d.get("rulings", []):
        a, b = r.get("side_a"), r.get("side_b")
        for pid, side in zip(r.get("pair", []), (a, b)):
            if side and pid not in out:
                out[pid] = {
                    "id": pid,
                    "pcd_mm": side["pcd_mm"],
                    "bolt_count": side["bolt_count"],
                    "thread": side["thread"],
                }
    return out


def short_key(pid: str) -> str:
    m = re.match(r"ISO9409-1-(A[\w.]+)-", pid)
    return m.group(1) if m else pid


def thread_nominal(thread: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)", thread or "")
    return float(m.group(1)) if m else 6.0


def pick_fastener(thread: str, need_len: float, prefer_std: str = DEFAULT_HEAD_STD):
    """从 step.parts 库存挑最接近的标准紧固件；无库存文件时返回 None。"""
    if not STEP_PARTS.exists():
        return None
    try:
        sp = json.loads(STEP_PARTS.read_text(encoding="utf-8"))
    except Exception:
        return None
    cands = [
        it for it in sp.get("items", [])
        if it.get("category") == "fastener"
        and it.get("thread") == thread
        and it.get("length_mm") is not None
    ]
    if not cands:
        return None
    # 同标准优先（避免把内六角换成沉头），其次就近长度，宁长勿短
    def key(c):
        std_penalty = 0 if c.get("standard") == prefer_std else 1
        short = max(0.0, need_len - c["length_mm"])
        return (std_penalty, short, abs(c["length_mm"] - need_len))
    best = min(cands, key=key)
    return {
        "name": best["name"],
        "standard": best.get("standard"),
        "thread": best["thread"],
        "length_mm": best["length_mm"],
        "page": best.get("pageUrl"),
        "fits": best["length_mm"] >= need_len,
        "head_std_as_requested": best.get("standard") == prefer_std,
    }


def bolt_line(side: dict, thick: float) -> dict:
    d = thread_nominal(side["thread"])
    eng = round(ENGAGEMENT * d, 1)
    need = round(thick + eng, 1)
    f = pick_fastener(side["thread"], need)
    return {
        "side": side["id"],
        "thread": side["thread"],
        "count": side["bolt_count"],
        "pcd_mm": side["pcd_mm"],
        "engagement_mm": eng,
        "min_length_mm": need,
        "fastener": f,
    }


def build_bom(a: dict, b: dict, thick: float) -> dict:
    return {
        "schema": "adapter_bolting/v1",
        "pair": [a["id"], b["id"]],
        "plate_thickness_mm": thick,
        "engagement_rule": f"1.2×d（ISO 262 常用下限区间 1.0~1.5d），未计垫圈/孔深",
        "lines": [bolt_line(a, thick), bolt_line(b, thick)],
        "honest_limits": [
            "螺栓长度按板厚 + 旋合现算，未计垫圈、被连接件孔深与倒角",
            "板厚由调用方给定，本模块不判断其强度是否足够",
            "标准件来自 step.parts 库存快照，采购前请核对供应商现货",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="转接板螺栓物料清单")
    ap.add_argument("--list", action="store_true", help="列出已登记法兰")
    ap.add_argument("--a", help="侧 A 短标号，如 A40")
    ap.add_argument("--b", help="侧 B 短标号，如 A63")
    ap.add_argument("--thick", type=float, required=False, help="板厚 mm")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    desg = load_designations()
    by_short = {short_key(k): v for k, v in desg.items()}

    if args.list:
        print(f"已登记 {len(desg)} 档 ISO 9409-1 法兰：")
        for k, v in sorted(desg.items(), key=lambda x: x[1]["pcd_mm"]):
            print(f"  {short_key(k):6s} PCD {v['pcd_mm']:6.1f}mm  {v['bolt_count']}×{v['thread']}")
        return 0

    if not (args.a and args.b and args.thick is not None):
        ap.print_help()
        return 1
    if args.a not in by_short or args.b not in by_short:
        sys.exit(f"[fail] 未知标号（用 --list 查看）；a={args.a} b={args.b}")

    bom = build_bom(by_short[args.a], by_short[args.b], args.thick)
    if args.json:
        print(json.dumps(bom, ensure_ascii=False, indent=1))
        return 0

    print(f"转接板 {args.a} → {args.b}｜板厚 {args.thick}mm")
    for ln in bom["lines"]:
        f = ln["fastener"]
        head = f["name"] if f else "（无库存匹配，先跑 scripts/ingest_step_parts.py）"
        std = f["standard"] if f else "-"
        ok = "OK" if (f and f["fits"]) else "偏短/缺"
        print(f"  {ln['side'].split('-')[-3]:6s} {ln['count']}×{ln['thread']} "
              f"PCD{ln['pcd_mm']:g}  需长≥{ln['min_length_mm']}mm  → {head} [{std}] {ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
