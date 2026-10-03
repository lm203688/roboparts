#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_compose_frontier — 共装前沿层的阴阳自证（挂 ci_gate）。

为什么这层必须挂闸
----------------
本层输出的是**诊断性结论**：「composed=0 是关系类型错配，不是数据缺口」。
这类结论的危险在于：它读起来像一个定理，却可能只是**样本不够**。

所以闸门守三件事：
  ① 算术自洽：L3 ⊆ L2 ⊆ L1，法兰计数与节点画像一致；
  ② **口径守卫（关键）**：本层必须**始终以「强假说」措辞**输出，
     且 sample_caveat 必须在场。若哪天有人把它改成断言口径，
     闸门必须判红——**因为一个被过度声称的诊断比没有诊断更坏**。
  ③ 变异检测：注入 5 种变异（含「L2 混入 signal 非 compatible 的对」
     这个真实破口），必须逐一判红。
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_compose_frontier as bcf  # noqa: E402

FAILED: list = []
_MUTFAIL: list = []


def fail(msg: str) -> None:
    FAILED.append(msg)
    print(f"  [FAIL] {msg}")


def _mutfail(msg: str) -> None:
    _MUTFAIL.append(msg)


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def check_arithmetic(out, sink=None) -> None:
    """算术自洽 + 口径守卫。sink 指定失败收集器（变异体传 _mutfail）。"""
    emit = sink or fail
    s = out.get("summary") or {}
    l1, l2, l3 = s.get("l1_pairs"), s.get("l2_pairs"), s.get("l3_pairs")
    for name, v in (("l1", l1), ("l2", l2), ("l3", l3)):
        if not isinstance(v, int) or v < 0:
            emit(f"{name}_pairs 非法：{v!r}")
            return
    if not (l1 >= l2 >= l3):
        emit(f"层级不单调：L1={l1} L2={l2} L3={l3}（必须 L1⊇L2⊇L3）")
    else:
        ok(f"层级单调 L1={l1:,} ⊇ L2={l2} ⊇ L3={l3}")

    # L2 的 signal 必须全 compatible（由 roles 保证），否则口径与引擎分叉
    sh = s.get("l2_signal_histogram") or {}
    if sh.get("compatible", 0) != l2:
        emit(f"L2 的 signal 非全 compatible（{sh}），L1∩mechanical 定义被破坏")
    else:
        ok("L2 signal 全 compatible（口径自洽）")

    # L2 节点数 ≤ L1 节点数
    if s.get("l2_nodes", 0) > s.get("l1_cross_role_nodes", 0):
        emit(f"l2_nodes {s.get('l2_nodes')} > l1_cross_role_nodes "
             f"{s.get('l1_cross_role_nodes')}")
    else:
        ok(f"l2_nodes {s.get('l2_nodes')} <= l1_cross_role_nodes "
           f"{s.get('l1_cross_role_nodes')}")

    # 法兰画像之和应等于 L2 节点数（同节点可能多法兰 → 只判 <= 与 >0）
    fl = s.get("co_mount_flange_profile") or {}
    tot = sum(fl.values())
    if not fl or tot < s.get("l2_nodes", 0):
        emit(f"法兰画像合计 {tot} 与 l2_nodes {s.get('l2_nodes')} 不自洽")
    else:
        ok(f"法兰画像合计 {tot} >= l2_nodes {s.get('l2_nodes')}")

    # frontier_nodes 条数 == l2_nodes
    fn = out.get("frontier_nodes") or []
    if len(fn) != s.get("l2_nodes"):
        emit(f"frontier_nodes {len(fn)} != l2_nodes {s.get('l2_nodes')}")
    else:
        ok(f"frontier_nodes {len(fn)} == l2_nodes")

    # ---- 口径守卫（本层特有）----
    #
    # 2026-10-04 修正：初版用「文本里能否找到『假说』」做守卫，
    # 结果**变异没被抓到**——因为 statement 里的「假说」被抹掉了，
    # 但 conclusion / sample_caveat / implication 里还有多处「假说」，
    # 子串搜索照样命中 ⇒ 守卫形同虚设。
    #
    # 这与已记录的教训同型：**断言要打在判据真正依据的那个字段上**，
    # 不能用「全文本里出现过某词」当判据。
    # 改为逐条要求**具体字段**携带具体标记：
    #   · statement  必须以【强假说…】开头
    #   · headline   必须含「不是已证定理」
    #   · 不得出现断言性措辞（"不是数据缺口"而不带"很可能"/"强假说"限定）
    thm = out.get("co_mount_theorem") or {}
    stmt = (thm.get("statement") or "")
    head = (out.get("meta") or {}).get("headline") or ""
    if not stmt.lstrip().startswith("【强假说"):
        emit("co_mount_theorem.statement 未以「【强假说」开头 —— "
             "本层结论由少量样本支撑，statement 字段必须自带限定词")
    if "不是已证定理" not in head:
        emit("meta.headline 缺「不是已证定理」—— "
             "headline 是最容易被单独引用的字段，必须自带限定")
    # 断言措辞黑名单。**必须排除否定式**（"不是已证定理" 是正确的限定语，
    # 不能因为它含「已证定理」四字就判红）——2026-10-04 实测踩过：
    # 第一版黑名单无脑匹配子串，把 headline 里的「不是已证定理」判成断言。
    # 判据改为：命中黑名单词 **且该处前后 6 字内没有否定词**。
    NEG = ("不", "非", "未", "无", "尚未", "很可能", "可能")
    for kw in ("确定是", "已证定理", "证明了", "必然不会", "就是"):
        for field_name, field in (("statement", stmt), ("headline", head)):
            idx = 0
            while True:
                idx = field.find(kw, idx)
                if idx < 0:
                    break
                window = field[max(0, idx - 6):idx]
                if not any(n in window for n in NEG):
                    emit(f"{field_name} 出现无否定的断言措辞「{kw}」"
                         f"（…{field[max(0,idx-10):idx+6]}…）—— 本层只作诊断，"
                         "不得写成已证结论")
                idx += 1
    if "sample_caveat" not in json.dumps(thm, ensure_ascii=False):
        emit("co_mount_theorem 缺 sample_caveat —— "
             "必须登记样本量限制与升级条件")
    if emit is fail:
        ok("口径守卫：statement 限定词 + headline 限定 + 无断言措辞 + sample_caveat")

    # honest_limits 必须在位
    hl = " ".join((out.get("meta") or {}).get("honest_limits") or [])
    for kw in ("不改", "Tier B", "多年期"):
        if kw not in hl:
            emit(f"honest_limits 缺少「{kw}」相关声明")
    if emit is fail:
        ok("honest_limits 三条在位（不改判定/Tier B 依赖/多年期不做）")


def _mut_l3_gt_l2(out, label):
    m = copy.deepcopy(out)
    m["summary"]["l3_pairs"] = m["summary"]["l2_pairs"] + 1
    return m


def _mut_layer_inversion(out, label):
    m = copy.deepcopy(out)
    m["summary"]["l1_pairs"] = 1
    return m


def _mut_signal_not_compatible(out, label):
    m = copy.deepcopy(out)
    m["summary"]["l2_signal_histogram"] = {"unknown": m["summary"]["l2_pairs"]}
    return m


def _mut_frontier_count(out, label):
    m = copy.deepcopy(out)
    if m.get("frontier_nodes"):
        m["frontier_nodes"] = m["frontier_nodes"][:-1]
    return m


def _mut_flange_blank(out, label):
    m = copy.deepcopy(out)
    m["summary"]["co_mount_flange_profile"] = {}
    return m


def _mut_hypothesis_to_assertion(out, label):
    """把「假说」改成断言 —— 口径守卫必须判红。"""
    m = copy.deepcopy(out)
    thm = m["co_mount_theorem"]
    thm["statement"] = thm["statement"].replace(
        "【强假说，非已证定理】", "").replace(
        "很可能不是数据缺口", "不是数据缺口").replace(
        "只作诊断不作断言", "是已证定理")
    m["meta"]["headline"] = m["meta"]["headline"].replace(
        "高度可能", "确定").replace("强假说", "定理").replace(
        "很可能不会", "不会")
    return m


def _mut_strip_caveat(out, label):
    m = copy.deepcopy(out)
    m["co_mount_theorem"]["empirical_support"].pop("sample_caveat", None)
    return m


MUTATIONS = [
    ("L3 > L2", _mut_l3_gt_l2),
    ("层级倒挂 L1 < L2", _mut_layer_inversion),
    ("L2 的 signal 非全 compatible", _mut_signal_not_compatible),
    ("frontier_nodes 条数不符", _mut_frontier_count),
    ("法兰画像被抹空", _mut_flange_blank),
    ("假说措辞被改成断言（口径守卫）", _mut_hypothesis_to_assertion),
    ("sample_caveat 被删", _mut_strip_caveat),
]


def check_mutations(out) -> None:
    print("\n[2/2] 变异检测（每个变异必须判红）")
    for label, fn in MUTATIONS:
        before = len(_MUTFAIL)
        check_arithmetic(fn(out, label), sink=_mutfail)
        if len(_MUTFAIL) == before:
            fail(f"变异未被捕获：{label}（闸门对该变异不敏感）")
        else:
            print(f"  [ok]   变异已捕获：{label}（触发 {len(_MUTFAIL)-before} 条断言）")


def check_consistency_with_compose() -> None:
    """跨层不变量：L3 必须等于 compose_semantics 的 composed 计数。"""
    print("\n[1/2] 跨层不变量：L3 vs compose_semantics.composed")
    cp = os.path.join(ROOT, "api", "compose_semantics.json")
    out = bcf.build()
    if not os.path.exists(cp):
        print("  [skip] compose_semantics.json 不存在")
        return
    with open(cp, encoding="utf-8") as f:
        cs = json.load(f)
    composed = (cs.get("aggregates") or {}).get("overall_counts", {}).get("composed", 0)
    l3 = out["summary"]["l3_pairs"]
    # 注意口径：compose 走 n² 有向含自配对，L3 走 C(n,2) 无序。
    # composed 计数在 n² 口径下应为 L3 的两倍（对称展开）。
    if composed == 0 and l3 == 0:
        ok(f"两侧均为 0（composed={composed} / L3={l3}）——口径一致")
    elif composed > 0 and l3 * 2 == composed:
        ok(f"口径一致：composed={composed} == L3({l3})×2（对称展开）")
    else:
        fail(f"口径不一致：compose composed={composed}（n² 有向）"
             f" vs frontier L3={l3}（C(n,2) 无序）。"
             f"期望 composed == L3×2 或 两侧同为 0")


def main() -> int:
    print("=" * 70)
    print("verify_compose_frontier — 共装前沿层阴阳自证")
    print("=" * 70)
    out = bcf.build()

    check_consistency_with_compose()
    before = len(FAILED)
    check_arithmetic(out)
    if len(FAILED) > before:
        print("\n真实产物未通过算术/口径自检，后续变异检测无意义。")
        return 1
    ok("baseline 干净（阴性对照成立）")

    check_mutations(out)

    print("\n" + "=" * 70)
    if FAILED:
        print(f"FAIL：{len(FAILED)} 项未通过")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("PASS：全部自证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
