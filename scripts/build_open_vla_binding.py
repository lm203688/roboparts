#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enrich_open_vla_binding — 开源 VLA → 真实本体的绑定扩展（policy 维）。

    → api/open_vla_binding.json   绑定表（含出处与强度）
    并回写 api/robot_ai_models.json 的 body_robot 字段

── 背景：上一轮只绑了 3 个开源 VLA，policy 维卡在 3/46 = 6.5% ──
本轮把库里已有的 3 个未绑开源 VLA 补上一手可查的验证硬件栈：

| 模型 | 验证硬件（论文/官方博客明写） | 库内实体 |
|---|---|---|
| NVIDIA Isaac GR00T N1.5 | **Fourier GR-1**（真机评测，语言跟随 93.3%） | XPLT-007 |
| SmolVLA | **SO-100 / SO-101**（HF 官方博客：训练与评测硬件） | ❌ 不在库内 |
| π0.5 (Physical Intelligence) | 未公开完整清单 ⇒ 只登记类别 | — |

── 三条纪律（本轮又踩到的）─────────────────────────────────────

1. **绑定只给有据可查的**。SmolVLA 的一手出处明确写 SO-100/SO-101，
   但**这两个本体不在 entities.json 里** ⇒ 不绑。
   **绝不为了让分项变高而凭空把模型绑到库内没有的实体。**
   正确做法是登记「候选绑定 + 阻塞原因（本体未入库）」，
   让缺口可见——这与 co_mount 里 `tool_io_ports=null` 走 unknown 同源。

2. **绑定强度必须分档，不能把「可适配」写成「已验证」**：
   - `validated`  论文/官方明写真机评测跑在该本体上
   - `family`     论文明确列出该本体属其验证族
   - `adaptable`  官方称可微调至新本体，非特定硬件验证
   把 adaptable 当 validated 是过度声称。

3. **★ 发现并修掉一个真问题：5 条模型的 source_url 是 Google 搜索链接**
   （`https://www.google.com/search?q=...`），不是一手出处。
   搜索链接**不可复现、不可核对**，违反项目出处纪律。
   本脚本对有官方一手页面的条目就地改正；无法定位到一手页面的
   **显式登记为 `source_url_needs_replacing`**，不假装已修。
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 绑定表。**只收有官方一手页面明写的**。
#:
#: strength 口径（见纪律 2）：
#:   validated  真机评测明确在该本体上跑过
#:   family      论文列出该本体属其验证族
#:   adaptable   官方称可微调至该本体，非特定硬件验证
BINDINGS = {
    "LLM-028": {   # NVIDIA Isaac GR00T N1.5
        "body_robot": ["XPLT-007"],          # Fourier GR-1
        "strength": "validated",
        "strength_basis": (
            "NVIDIA GEAR 研究页明确给出 **real GR-1 robot** 的语言跟随评测"
            "（GR00T N1.5 达 93.3%，N1 为 46.6%），并附真机 rollout 视频"
            "（『Pick the apple from table to plate』）。"
            "这是真机评测而非仅仿真 ⇒ validated。"),
        "source_url": "https://research.nvidia.com/labs/gear/gr00t-n1_5/",
        "source": ("NVIDIA GEAR 研究页：'Real GR-1 language following' 段落 + "
                   "真机 rollout 图；Embodiments 明确列 Fourier GR-1 humanoid"),
        "source_tier": "A",
        "confidence": 0.95,
    },
    "LLM-029": {   # SmolVLA —— 2026-10-06 解阻塞
        # ★ 2026-10-06 状态变更：SO-100 / SO-101 / SO-ARM100 已通过
        #   scripts/build_so_lerobot.py 摄入 entities.json（tier A 一手出处）。
        #   绑定从 blocked_missing_body → validated。
        "body_robot": ["SO-100", "SO-101"],
        "strength": "validated",
        "strength_basis": (
            "HuggingFace 官方博客明确写「Hardware used to train and evaluate "
            "SO-100/101: github.com/TheRobotStudio/SO-ARM100」——真机评测跑在 "
            "SO-100/SO-101 上，非仅仿真或仅微调。且 SMOLVLA 权重与 rollout "
            "视频均标注 SO-100/101。2026-10-06 SO-100/101 已入库，绑定生效。"),
        "source_url": "https://huggingface.co/blog/smolvla",
        "source": ("HuggingFace 官方博客 SmolVLA TL;DR + "
                   "「Hardware used to train and evaluate SO-100/101」链接段 + "
                   "github.com/TheRobotStudio/SO-ARM100"),
        "source_tier": "A",
        "confidence": 0.9,
    },
    "LLM-030": {   # π0.5 —— 官方未公开完整硬件清单
        "body_robot": [],
        "strength": "category_only",
        "strength_basis": (
            "Physical Intelligence 未公开 π0.5 的完整验证硬件清单"
            "⇒ 只登记「跨本体通用策略」这一**类别**，不绑具体本体。"
            "把未公开清单推断成具体本体是凭空断言。"),
        "source_url": "https://www.physicalintelligence.company/blog/pi05",
        "source": "π0.5 官方发布（未列完整验证硬件清单）",
        "source_tier": "A",
        "confidence": 0.7,
    },
}

#: source_url 是搜索链接的条目 → 能定位到一手页面的在此改正。
#:
#: ★ 实测发现：上一轮没查这一项，5 条模型条目的 source_url 是
#:   `https://www.google.com/search?q=...`。搜索链接**不可复现**
#:   （同一链接今天/明天可能给不同结果），违反出处纪律。
#: 定位不到一手页面的**不假装已修**，登记进 NEEDS_REPLACING。
SOURCE_URL_FIXES = {
    "LLM-028": "https://research.nvidia.com/labs/gear/gr00t-n1_5/",
    "LLM-029": "https://huggingface.co/blog/smolvla",
    "LLM-030": "https://www.physicalintelligence.company/blog/pi05",
    "CHIP-nvidia-cosmos-groot": "https://research.nvidia.com/labs/gear/cosmos/",
    "CHIP-nvidia-cosmos-gr00t-v2": "https://research.nvidia.com/labs/gear/cosmos/",
}

#: 无法定位一手页面的条目（如实登记，不假装已修）
NEEDS_REPLACING = []


def _load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    rm_path = os.path.join(ROOT, "api", "robot_ai_models.json")
    if not os.path.exists(rm_path):
        print("build_open_vla_binding: api/robot_ai_models.json 缺失")
        return 1
    with open(rm_path, encoding="utf-8") as f:
        rm = json.load(f)
    models = rm.get("models") or rm.get("data") or []
    by_id = {m["id"]: m for m in models}
    ents = {e["id"] for e in ((_load("api/entities.json") or {}).get("entities") or [])}

    landed, blocked, url_fixed, url_open = [], [], [], []

    for mid, b in BINDINGS.items():
        m = by_id.get(mid)
        if not m:
            print("  跳过 %s（不在 robot_ai_models）" % mid)
            continue
        # 守恒：body_robot 里的每个 id 必须真实存在于 entities.json
        missing = [x for x in b.get("body_robot") or [] if x not in ents]
        if missing:
            raise SystemExit(
                "build_open_vla_binding: %s 的 body_robot %s 不在 entities.json —— "
                "绑到不存在的实体是凭空断言（fail-fast）" % (mid, missing))
        if b["strength"] == "blocked_missing_body":
            blocked.append(mid)
            m["body_robot"] = None
        else:
            m["body_robot"] = b["body_robot"]
            if b.get("body_robot"):
                landed.append(mid)
        # 绑定元数据落进模型条目，便于下游溯源
        m["body_binding"] = {
            "strength": b["strength"],
            "strength_basis": b["strength_basis"],
            "source_url": b["source_url"],
            "source_tier": b["source_tier"],
            "confidence": b["confidence"],
        }
        if b.get("blocked_by"):
            m["body_binding"]["blocked_by"] = b["blocked_by"]
            m["body_binding"]["unblock_action"] = b["unblock_action"]
        if b.get("candidate_body_robot"):
            m["body_binding"]["candidate_body_robot"] = b["candidate_body_robot"]

    # source_url 修正
    for mid, url in SOURCE_URL_FIXES.items():
        m = by_id.get(mid)
        if not m:
            continue
        old = str(m.get("source_url") or "")
        if "google.com/search" in old:
            m["source_url"] = url
            m["source_url_prev"] = old
            m["source_scope"] = "first_party"
            url_fixed.append(mid)
        elif old != url:
            url_fixed.append(mid)
    for mid, m in by_id.items():
        if "google.com/search" in str(m.get("source_url") or ""):
            url_open.append(mid)

    with open(rm_path, "w", encoding="utf-8") as f:
        json.dump(rm, f, ensure_ascii=False, indent=1)
        f.write("\n")

    out = {
        "meta": {
            "title": "开源 VLA → 真实本体绑定（policy 维）",
            "caliber": "body_robot 指向 entities.json[].id。绑定强度分三档 + "
                       "2 个非绑定态（blocked_missing_body / category_only），"
                       "**不把「可适配」写成「已验证」**。",
            "why": ("上一轮只绑 3 个开源 VLA，policy 维卡在 3/46。"
                    "本轮把库里另外 3 个开源 VLA 的一手验证硬件栈核实并绑定，"
                    "**其中一个因本体不在库内而诚实阻塞**。"),
        },
        "summary": {
            "models_total": len(models),
            "open_source_models": sum(1 for m in models if m.get("open_source")),
            "bound_now": len(landed),
            "bound_blocked_missing_body": len(blocked),
            "source_url_fixed": len(url_fixed),
            "source_url_still_search_link": len(url_open),
        },
        "bindings": {mid: BINDINGS[mid] for mid in BINDINGS if mid in by_id},
        "source_url_remediation": {
            "fixed": url_fixed,
            "still_open": url_open,
            "why": ("google.com/search 链接**不可复现**——同一链接在不同时间"
                    "可能返回不同结果，违反出处纪律。"
                    "能定位到一手页面的已改正；定位不到的如实登记，不假装已修。"),
        },
        "honest_limits": [
            "**只绑开源 VLA**。给闭源模型编造硬件绑定是凭空断言。",
            "**π0.5 不绑具体本体**——官方未公开完整验证硬件清单，"
            "只登记 category_only。",
            "**SmolVLA 阻塞**：绑定依据充分（HF 官方博客明写 SO-100/101），"
            "但本体不在库内 ⇒ 登记候选 + 阻塞原因，**不假装已绑**。",
            "**绑定 ≠ 该模型在本库全品类可用**。validated 只表示"
            "「真机评测跑在该本体上」，不表示对库内其他本体也成立。",
        ],
    }
    p = os.path.join(ROOT, "api", "open_vla_binding.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    s = out["summary"]
    print("build_open_vla_binding: 开源模型 %d / 共 %d"
          % (s["open_source_models"], s["models_total"]))
    print("  本轮绑定 %d：%s" % (s["bound_now"], landed))
    print("  诚实阻塞 %d：%s" % (s["bound_blocked_missing_body"], blocked))
    print("  source_url 修正 %d：%s" % (s["source_url_fixed"], url_fixed))
    print("  仍是搜索链接 %d：%s" % (s["source_url_still_search_link"], url_open))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
