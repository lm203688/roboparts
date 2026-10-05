#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_open_vla_and_behavior — 绑定层 + 行为层的自证。

遵循本项目已成型的范式：正/负/变异三对照 + 口径守卫。
重点守三件事：
  ① **绑定必须指向真实存在的实体**（绑到不存在的实体 = 凭空断言）
  ② **绑定强度不得过度声称**（adaptable ≠ validated）
  ③ **行为证据必须有对照组 + sim/real 分列 + 出处一手**
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MUTFAIL = []
FAILED = False
PASSED = 0


def ok(msg):
    global PASSED
    PASSED += 1
    print("  \u2713 %s" % msg)


def fail(msg):
    global FAILED
    FAILED = True
    print("  \u2717 %s" % msg)


def emit(msg):
    MUTFAIL.append(msg)


def _load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _errors(ov, bh, ents, rm):
    errs = []
    # ── ① 绑定的 body_robot 必须真实存在 ──
    ent_ids = {e["id"] for e in (ents.get("entities") or [])}
    for mid, b in (ov.get("bindings") or {}).items():
        for bid in b.get("body_robot") or []:
            if bid not in ent_ids:
                errs.append("%s 的 body_robot=%s 不在 entities.json —— "
                            "绑到不存在的实体是凭空断言" % (mid, bid))
        for cand in b.get("candidate_body_robot") or []:
            if cand in ent_ids:
                errs.append("%s 把 %s 记为「候选/阻塞」，但它其实已在库内 ⇒ "
                            "阻塞理由不成立，应直接绑定" % (mid, cand))
    # ── ② 强度分档：不得把非 validated 写成 validated ──
    ALLOWED = {"validated", "family", "adaptable", "category_only",
               "blocked_missing_body"}
    for mid, b in (ov.get("bindings") or {}).items():
        st = b.get("strength")
        if st not in ALLOWED:
            errs.append("%s 的 strength=%r 不在允许集合 %s"
                        % (mid, st, sorted(ALLOWED)))
        if not (b.get("strength_basis") or "").strip():
            errs.append("%s 缺 strength_basis —— 强度必须可被质疑" % mid)
        if st == "blocked_missing_body" and not b.get("blocked_by"):
            errs.append("%s 标为 blocked 但未登记 blocked_by" % mid)
        # ★ 跨字段自洽（实测：过度声称变异打空的地方）。
        #   只查 strength 是否在允许集合内 ⇒ adaptable 改成 validated 照样通过
        #   （值仍合法）⇒ 闸门是装饰。真正的过度声称判据是**语义自洽**：
        #   `validated` 的定义是「真机评测跑在该本体上」，
        #   而 body_robot=[] 时**没有任何本体** ⇒ 声明自相矛盾。
        if st in ("validated", "family") and not (b.get("body_robot") or []):
            errs.append("%s 标为 %s 但 body_robot 为空 —— "
                        "「%s」的定义要求有具体本体，声明自相矛盾"
                        "（过度声称：把可适配/类别说成已验证）"
                        % (mid, st, st))
        if st == "validated" and b.get("body_robot"):
            for bid in b["body_robot"]:
                if bid not in ent_ids:
                    errs.append("%s 标为 validated 但本体 %s 不存在" % (mid, bid))
    # ── ③ 口径守卫：只绑开源 VLA ──
    models = {m["id"]: m for m in (rm.get("models") or rm.get("data") or [])}
    for mid in (ov.get("bindings") or {}):
        m = models.get(mid)
        if m is not None and not m.get("open_source"):
            errs.append("%s 非开源模型却被绑定硬件 —— "
                        "给闭源模型编造绑定会污染 data_quality" % mid)
    # ── ④ source_url 不得是搜索链接 ──
    rem = ((ov.get("source_url_remediation") or {}).get("still_open")) or []
    if rem:
        errs.append("仍有 %d 条 source_url 是 google.com/search —— "
                    "搜索链接不可复现，违反出处纪律：%s" % (len(rem), rem[:3]))
    fixed = ((ov.get("source_url_remediation") or {}).get("fixed")) or []
    for mid in fixed:
        m = models.get(mid)
        if m and "google.com/search" in str(m.get("source_url") or ""):
            errs.append("%s 被记为已修正但 source_url 仍是搜索链接" % mid)
    # ★ caliber 是**字符串**，其余可能在 meta 的别的键。
    #   只取 meta["caliber"] 会漏掉 meta 里的其他自述字段。
    hl = json.dumps(ov.get("meta") or {}, ensure_ascii=False) + " " + \
        " ".join(ov.get("honest_limits") or [])
    for kw, why in (("不把「可适配」写成「已验证」", "强度分档必须自述"),
                    ("不绑", "阻塞/不绑的理由必须自述"),
                    ("闭源", "闭源不编造绑定必须自述")):
        if kw not in hl:
            errs.append("口径守卫：缺「%s」（%s）" % (kw, why))

    # ── ⑤ 行为证据：对照组 + sim/real 分列 + 出处 ──
    for mid, recs in (bh.get("records") or {}).items():
        for r in recs:
            if r.get("trial_kind") not in ("real", "sim"):
                errs.append("%s 的 trial_kind=%r 非法" % (mid, r.get("trial_kind")))
            if not r.get("source_url"):
                errs.append("%s 的记录缺 source_url" % mid)
            if r.get("value") is not None and not r.get("has_control"):
                errs.append("%s 的 %s 有数值但无对照组 —— 孤证不登记"
                            % (mid, r.get("metric")))
            ref = r.get("embodiment_ref")
            if ref and ref not in ent_ids:
                errs.append("%s 的 embodiment_ref=%s 不在 entities.json"
                            % (mid, ref))
            # 有真机数值时必须有 embodiment
            if (r.get("trial_kind") == "real" and r.get("value") is not None
                    and not r.get("embodiment")):
                errs.append("%s 的实机记录缺 embodiment —— 真机数字必须指明本体"
                            % mid)
    # ── ⑤b sim/real 分列必须**现算**（不能只查 trial_kind 合法性）──
    #   实测踩到第八次变异打空：把 sim 改成 real 后，
    #   `trial_kind in (real, sim)` 这条判据照样通过（值仍合法），
    #   只有 summary 计数守恒那条间接抓到 ⇒ **分列本身没被守**。
    #   仿真冒充真机是**过度声称**（读者会以为是真机成绩），
    #   必须有一条直接判据：summary 的 sim/real 计数须与 records 现算一致。
    _recs_all = [r for rs in (bh.get("records") or {}).values() for r in rs]
    _real = sum(1 for r in _recs_all
                if r.get("trial_kind") == "real" and r.get("value") is not None)
    _sim = sum(1 for r in _recs_all if r.get("trial_kind") == "sim")
    _null = sum(1 for r in _recs_all if r.get("value") is None)
    _s = bh.get("summary") or {}
    for label, got_v, want_v in (("real_with_value", _s.get("real_with_value"), _real),
                                 ("sim_records", _s.get("sim_records"), _sim),
                                 ("null_value_records", _s.get("null_value_records"), _null)):
        if got_v is not None and got_v != want_v:
            errs.append("summary.%s=%s，records 现算应为 %d —— "
                        "**sim/real 分列必须现算**。把 sim 记录标成 real 时"
                        "这条直接判红（只查 trial_kind 合法性会漏）"
                        % (label, got_v, want_v))

    s = bh.get("summary") or {}
    tot = s.get("records")
    parts = (s.get("real_with_value", 0) + s.get("sim_records", 0)
             + s.get("null_value_records", 0))
    if tot is not None and tot != parts:
        errs.append("行为记录计数不守恒：%d != %d+%d+%d"
                    % (tot, s.get("real_with_value"), s.get("sim_records"),
                       s.get("null_value_records")))
    if not bh.get("not_modelled"):
        errs.append("行为层缺 not_modelled —— 「不做什么」必须显式登记")
    bl = " ".join(bh.get("not_modelled") or []) + " ".join(
        bh.get("honest_limits") or [])
    for kw, why in (("不自建", "不自造日志的理由必须自述"),
                    ("孤证", "不收孤证的理由必须自述"),
                    ("仿真", "sim/real 分列必须自述"),
                    ("可复现", "本仓不可自行复现的事实必须自述")):
        if kw not in bl:
            errs.append("行为层口径守卫：缺「%s」（%s）" % (kw, why))
    return errs


# ═══════════════════════════════ 变异 ═══════════════════════════════
def _mut_bind_nonexistent(ov, bh, ents, rm):
    m = copy.deepcopy(ov)
    k = next(iter(m["bindings"]))
    m["bindings"][k]["body_robot"] = ["NOT-A-REAL-ENTITY-999"]
    return m, bh, ents, rm


def _mut_strength_overclaim(ov, bh, ents, rm):
    """把 adaptable/category_only 改成 validated ⇒ 过度声称必须判红。"""
    m = copy.deepcopy(ov)
    for b in m["bindings"].values():
        if b.get("strength") in ("adaptable", "category_only",
                                 "blocked_missing_body"):
            b["strength"] = "validated"
            return m, bh, ents, rm
    return m, bh, ents, rm


def _mut_closed_source_bind(ov, bh, ents, rm):
    """给闭源模型加绑定 ⇒ 必须判红。"""
    m = copy.deepcopy(rm)
    m2 = copy.deepcopy(ov)
    for mm in (m.get("models") or m.get("data") or []):
        if not mm.get("open_source"):
            m2["bindings"][mm["id"]] = {
                "body_robot": [], "strength": "family",
                "strength_basis": "编造的绑定",
                "source_url": "https://example.com", "source_tier": "C",
                "confidence": 0.1}
            return m2, bh, ents, m
    return m2, bh, ents, m


def _mut_search_link(ov, bh, ents, rm):
    m = copy.deepcopy(ov)
    m["source_url_remediation"]["still_open"] = ["LLM-999"]
    return m, bh, ents, rm


def _mut_drop_honesty(ov, bh, ents, rm):
    m = copy.deepcopy(bh)
    m["not_modelled"] = []
    m["honest_limits"] = []
    return ov, m, ents, rm


def _mut_behavior_no_control(ov, bh, ents, rm):
    m = copy.deepcopy(bh)
    for recs in m["records"].values():
        for r in recs:
            if r.get("value") is not None:
                r["has_control"] = False
                return ov, m, ents, rm
    return ov, m, ents, rm


def _mut_behavior_embodiment_fake(ov, bh, ents, rm):
    m = copy.deepcopy(bh)
    for recs in m["records"].values():
        for r in recs:
            r["embodiment_ref"] = "FAKE-BODY-001"
            return ov, m, ents, rm
    return ov, m, ents, rm


def _mut_behavior_sim_real_mix(ov, bh, ents, rm):
    """把 sim 标成 real ⇒ 仿真冒充真机必须判红。"""
    m = copy.deepcopy(bh)
    for recs in m["records"].values():
        for r in recs:
            if r.get("trial_kind") == "sim":
                r["trial_kind"] = "real"
                return ov, m, ents, rm
    return ov, m, ents, rm


def _mut_behavior_count_break(ov, bh, ents, rm):
    m = copy.deepcopy(bh)
    m["summary"]["records"] = 999
    return ov, m, ents, rm


MUTATIONS = [
    ("绑定指向不存在的实体", _mut_bind_nonexistent),
    ("绑定强度过度声称（adaptable→validated）", _mut_strength_overclaim),
    ("给闭源模型加绑定", _mut_closed_source_bind),
    ("source_url 仍是搜索链接", _mut_search_link),
    ("行为层「不做什么」被抹掉", _mut_drop_honesty),
    ("行为记录去掉对照组（孤证）", _mut_behavior_no_control),
    ("行为记录 embodiment 指向不存在实体", _mut_behavior_embodiment_fake),
    ("仿真记录被标成真机", _mut_behavior_sim_real_mix),
    ("行为记录计数不守恒", _mut_behavior_count_break),
]


def main():
    print("verify_open_vla_and_behavior — 绑定层 + 行为层自证")
    ov = _load("api/open_vla_binding.json")
    bh = _load("api/behavior_evidence.json")
    ents = _load("api/entities.json")
    rm = _load("api/robot_ai_models.json")
    if not ov or not bh:
        fail("产物缺失（api/open_vla_binding.json / api/behavior_evidence.json）")
        return 1

    print("\n[阴性] 空产物必须判红")
    e = _errors({}, {}, ents, rm)
    if e:
        ok("空产物判红（%d 项）" % len(e))
    else:
        fail("空产物被判绿 —— 空闸门")

    print("\n[阳性] 真实产物判据")
    errs = _errors(ov, bh, ents, rm)
    if errs:
        for x in errs[:6]:
            fail("真实产物被判红：" + x)
    else:
        s = ov["summary"]
        ok("绑定 %d 个｜诚实阻塞 %d｜source_url 修正 %d｜残留搜索链接 %d"
           % (s["bound_now"], s["bound_blocked_missing_body"],
              s["source_url_fixed"], s["source_url_still_search_link"]))
        bs = bh["summary"]
        ok("行为证据 %d 条：真机有值 %d / 仿真 %d / 刻意 null %d（严格分列）"
           % (bs["records"], bs["real_with_value"], bs["sim_records"],
              bs["null_value_records"]))
        ok("口径守卫：强度分档 + 闭源不编造 + 不自造日志 + 孤证不收 + 不可复现 均已自述")

    print("\n[变异] %d 项（每项都必须判红）" % len(MUTATIONS))
    for name, fn in MUTATIONS:
        o, b, en, r = fn(ov, bh, ents, rm)
        got = _errors(o, b, en, r)
        if got:
            for g in got[:2]:
                emit("%s → %s" % (name, g))
            ok("捕获：%s" % name)
        else:
            fail("★ 变异未被捕获（闸门是装饰）：%s" % name)

    print("\n结果：%s" % ("PASS" if not FAILED else "FAIL"))
    if MUTFAIL:
        print("变异触发 %d 条断言" % len(MUTFAIL))
    print("真实产物判绿项 %d" % PASSED)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())
