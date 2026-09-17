#!/usr/bin/env python3
"""构建 `api/external_signals.json`：从 SwarmLabs 拉取与 RoboParts 神经/机器人域相关的外部情报。

设计要点：
- 只走 SwarmLabs 公开 HTTPS API（`.env.local` 的 SWARMLABS_API_KEY），零源文件共享，零反向依赖
- **诚实映射**：RoboParts 域标签与 SwarmLabs OpenAlex 概念标签无法直接 join，
  所以本脚本用一组显式关键词（NEURO_TERMS）做情报 feed，而不是硬凑 join
- 幂等锚定：`meta.source_digest` = sha256(原始响应拼接)，与部署时间无关
- 空结果诚实标注：`total:0` 保留下来，说明"这个关键词在 SwarmLabs 数据源里真的没有"

产出 `api/external_signals.json` 结构：
  meta: {
    generated_at, source_digest, queries: [...],
    independence: {project: "roboparts", integration: "https only",
                   rule: "no source file sharing, no reverse dependency"}
  },
  signals: {
    <keyword>: {
      total, kind_filter, top: [{id, kind, name/title, confidence, updated_at, ...}]
    }
  }
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

# 同目录的客户端
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swarmlabs_client import SwarmLabsClient, SwarmLabsError, sha256  # noqa: E402

CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(CWD, "api", "external_signals.json")

# RoboParts 神经域关键词 —— 从 neurorobotics/source.json 的 GAP 描述中提取
# 只选 SwarmLabs OpenAlex 数据源里**真实存在**的词（避免虚假零结果当"发现"）
NEURO_TERMS = [
    ("neural", None, "神经科学 / 神经网络"),
    ("spiking", None, "脉冲神经（SNN 基础）"),
    ("neuromorphic", None, "神经形态计算（可能 0 命中——诚实标注）"),
    ("soft robotics", None, "软体机器人（跨域桥接候选）"),
    ("brain", None, "脑科学（连接组研究基础）"),
    ("machine learning", None, "ML 通用基线"),
]

# 补充查询：SwarmLabs 已知存在的 OpenAlex 概念域，直接按 domain 拉 gaps/trends
DOMAIN_QUERIES = [
    "cs",       # 计算机科学（SwarmLabs 数据主体）
    "bio",      # 生物学
]

QUERY_LIMIT = 15  # 每关键词 top N
DOMAIN_LIMIT = 10  # 每 domain top N


def fetch_signals(client: SwarmLabsClient) -> Dict[str, Any]:
    """跑所有关键词 + 域查询，返回原始结果 dict。"""
    signals: Dict[str, Any] = {}

    # 关键词搜索
    for term, kind_filter, note in NEURO_TERMS:
        try:
            r = client.search(q=term, kind=kind_filter, limit=QUERY_LIMIT)
            hits = r.get("results", [])
            top: List[Dict[str, Any]] = []
            for hit in hits:
                top.append({
                    "id": hit.get("id"),
                    "kind": hit.get("kind"),
                    "name_or_title": hit.get("name") or hit.get("title"),
                    "confidence": hit.get("confidence"),
                    "updated_at": hit.get("updated_at"),
                    "sources": hit.get("sources", [])[:2],  # 保留最多 2 个来源
                    "year": hit.get("year"),
                })
            signals[f"search:{term}"] = {
                "note": note,
                "total": r.get("total", 0),
                "returned": r.get("returned", 0),
                "top": top,
                "honest_empty": r.get("total", 0) == 0,
            }
        except SwarmLabsError as e:
            # 失败不掩盖——记入 signals，让 meta 里也能看到
            signals[f"search:{term}"] = {
                "note": note,
                "error": str(e),
                "request_id": getattr(e, "request_id", None),
                "http_status": getattr(e, "status", None),
            }

    # Domain 查询
    for domain in DOMAIN_QUERIES:
        try:
            gaps_resp = client.gaps(domain=domain, limit=DOMAIN_LIMIT)
            gaps = []
            for g in gaps_resp.get("gaps", []):
                gaps.append({
                    "id": g.get("id"),
                    "name": g.get("name"),
                    "confidence": g.get("confidence"),
                    "signal_strength": g.get("signal_strength"),
                    "updated_at": g.get("updated_at"),
                })
            trends_resp = client.trends(domain=domain, limit=DOMAIN_LIMIT)
            trends = []
            for t in trends_resp.get("trends", []):
                trends.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "confidence": t.get("confidence"),
                    "n": t.get("n"),
                    "updated_at": t.get("updated_at"),
                })
            signals[f"domain:{domain}"] = {
                "gaps": gaps,
                "gaps_total": len(gaps),
                "trends": trends,
                "trends_total": len(trends),
            }
        except SwarmLabsError as e:
            signals[f"domain:{domain}"] = {
                "error": str(e),
                "request_id": getattr(e, "request_id", None),
                "http_status": getattr(e, "status", None),
            }

    return signals


def build_meta(signals: Dict[str, Any], health: Dict[str, Any]) -> Dict[str, Any]:
    """构造 meta：新鲜度锚定原始响应 sha256，独立性硬约束显式声明。"""
    # source_digest = sha256 of canonical JSON of signals
    source_digest = sha256(json.dumps(signals, sort_keys=True, ensure_ascii=False))

    # 关键词命中/未命中统计
    kw_hits = 0
    kw_miss = 0
    kw_errors = 0
    for k, v in signals.items():
        if k.startswith("search:"):
            if "error" in v:
                kw_errors += 1
            elif v.get("total", 0) > 0:
                kw_hits += 1
            else:
                kw_miss += 1

    return {
        "name": "RoboParts External Signals — SwarmLabs feed",
        "version": "v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime()),
        "source_digest": source_digest,
        "independence": {
            "project": "roboparts",
            "integration_mode": "HTTPS public API only",
            "key_scope": "sk-swlm-rbprts-*",
            "rule": "RoboParts 不共享 SwarmLabs 源文件，不读 SwarmLabs KV/DB，不克隆仓库；"
                    "本文件唯一数据来源是 https://swarmlabs.tools/api/* 的 GET 响应",
        },
        "upstream_health": {
            "url": "https://swarmlabs.tools/api/health",
            "status": health.get("status"),
            "key_ok": health.get("key_ok"),
            "project": health.get("project"),
            "entity_count": health.get("entity_count"),
            "upstream_time": health.get("time"),
        },
        "counts": {
            "keywords_hit": kw_hits,
            "keywords_empty": kw_miss,
            "keywords_error": kw_errors,
            "domain_queries": len(DOMAIN_QUERIES),
            "total_signal_blocks": len(signals),
        },
        "queries": {
            "neuro_terms": [t[0] for t in NEURO_TERMS],
            "domains": DOMAIN_QUERIES,
            "per_query_limit": QUERY_LIMIT,
            "per_domain_limit": DOMAIN_LIMIT,
        },
        "honest_limits": {
            "note": "本文件是情报 feed，不是 join。RoboParts 机械兼容声明与 SwarmLabs OpenAlex 概念无"
                    "直接 ID 对齐，硬凑 join 会制造假关联。用户应把这里当作『外部生态正在讨论什么』"
                    "的信号面，与 api/neurorobotics.json 的 GAP-G1..G7 交叉阅读。",
            "cross_domain_semantics": "关键词命中=SwarmLabs 数据源里出现了这个词的论文/概念；"
                                       "不代表该论文已解决 RoboParts 侧的某个 GAP。",
            "rate_limit_headroom": "60/min · 10000/day · 20/10s burst（spec §3）",
            "cache_policy": "s-maxage=3600；本文件 meta.source_digest 是新鲜度锚点，"
                            "与部署时间无关——避免漂移快照病。",
        },
    }


def write_output(meta: Dict[str, Any], signals: Dict[str, Any]) -> str:
    """幂等写入：内容与上次一致则不写（防止 deploy 每次漂移）。"""
    payload = {"meta": meta, "signals": signals}
    new_text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            old_text = f.read()
        if old_text == new_text:
            return f"[idempotent] {OUT_PATH} unchanged ({len(new_text)} bytes)"

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(new_text)
    return f"[written] {OUT_PATH} ({len(new_text)} bytes)"


def main() -> int:
    client = SwarmLabsClient()

    # 先探针
    try:
        health = client.health()
    except SwarmLabsError as e:
        print(f"[FAIL] /api/health probe failed: {e}", file=sys.stderr)
        return 1

    if health.get("key_ok") is not True:
        print(f"[FAIL] key not accepted: {health}", file=sys.stderr)
        return 2

    print(f"[ok] health status={health.get('status')} project={health.get('project')}")
    print(f"[fetch] running {len(NEURO_TERMS)} keyword queries + {len(DOMAIN_QUERIES)} domain queries...")

    signals = fetch_signals(client)
    meta = build_meta(signals, health)
    result = write_output(meta, signals)
    print(result)
    print(f"[counts] {json.dumps(meta['counts'], ensure_ascii=False)}")
    print(f"[digest] source_digest={meta['source_digest'][:16]}...")

    # 简单自证：跑两次应完全一致（幂等锚定）
    signals2 = fetch_signals(client)
    meta2 = build_meta(signals2, health)
    if meta2["source_digest"] != meta["source_digest"]:
        print(f"[warn] source_digest changed between fetches: {meta['source_digest'][:16]} -> {meta2['source_digest'][:16]}")
        print("       (可能上游在同 15s 内刷新了数据；不影响本文件，只提醒)")
    else:
        print("[verify] second fetch produced identical source_digest — idempotent ✓")

    return 0


if __name__ == "__main__":
    sys.exit(main())
