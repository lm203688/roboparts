#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""闭环唯一对外接口（"一个口子"）。

把所有闭环信号收敛成 **一份** `ops/results/_STATUS.md` + 一段 stdout 摘要：
  数据真值 · git 状态 · 单实例锁 · 占位哨兵 · regression 门禁 · 最近部署 · 待你操作(P0/P1/P2)

存在的理由：此前闭环状态散落在 _STATUS.md / _LATEST.md / _SUMMARY.md /
_DAILY_DIGEST-*.md / 180+ 份 roboparts-*.md 里，**四个文件各报各的**，多头对账
必然漂移（实证：旧 refresh_status.py 停在 20260820，报 729 实体 / 0 品类 / 1.59%，
与真值 798 / 20 / 1.52% 全错；且把同一条待办复制成 5 份）。本脚本把它压缩成
唯一一处可读，并作为唯一对外接口。

纪律（沿用 L1 系列，不得放宽）：
  - 事实全部**现取**（真跑 git / regression / facts()），不缓存、不手填、不猜；
  - 门禁以**真实退出码**为准；解析不出结论一律记 UNKNOWN，**UNKNOWN 不是绿灯**；
  - 占位哨兵用**行锚定**正则（文件"是"占位 ≠ 正文"提到"占位，区别在形式而非语义）；
  - 待办去重（按正文前 40 字归一化），杜绝同一项被刷成 N 份；
  - **门禁口径唯一**：`regression.py` 是唯一的发布/哈希闸门。本脚本的哈希探测只是
    更早的提示项，不参与结论与退出码——两套口径各自判灯，就会重现"多头对账漂移"；
  - 只写一份文件，其余报告保留为审计轨迹，但**不再是对外接口**。

用法：
  python scripts/closure_status.py             # 打印摘要（不落盘）
  python scripts/closure_status.py --write     # 生成/覆盖 ops/results/_STATUS.md
  python scripts/closure_status.py --write --skip-regression   # 跳过慢门禁
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "ops" / "results"
STATUS_MD = RESULTS / "_STATUS.md"
NEEDS_USER = RESULTS / "_NEEDS_USER.md"
LOCK_FILE = ROOT / ".run-lock.json"
# ops/ 是**独立的本地 git 仓**（无远端、在 .gitignore），报告里记的 "ops 仓 commit"
# 属于它。只查主仓会把真提交判成幽灵（实测 bceff77 即因此误报）。与 regression.py
# 的 `_repos = [ROOT, ops]` 保持一致。
OPS_REPO = ROOT / "ops"

# 行锚定：只有独占一行的注释才算真哨兵。正文里"提到"这个词永远不会整行相等。
SENTINEL_RE = re.compile(
    r"^<!--\s*ROBOPARTS-RUN-TRACE:(AUTO-STUB|RECONCILED)(?:\s+by=\S+)?\s*-->$"
)
# 「声称已提交」的哈希。规则与 regression.py 的 HASH_CTX 完全一致（不要另写一套，
# 两套口径必然漂移）：反引号包裹、7~10 位、前面 24 字符内出现提交语境词。
HASH_CTX = re.compile(
    r"(?:提交|commit|推送|push|HEAD)[^\n`；;。，,、]{0,24}`([0-9a-f]{7,10})`",
    re.I,
)
# 「记述一个假哈希」不等于「声称提交了它」。附近有这些词＝在**揭露**而非在声称，豁免。
GHOST_OK = ("不存在", "幽灵", "假声明", "伪造", "查无", "订正", "更正", "未生成")


# ---------------------------------------------------------------- 取值原语

def _git(*args: str) -> str:
    """跑 git；失败返回空串（调用方须按 UNKNOWN 处理，不得当绿灯）。"""
    try:
        p = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args],
            cwd=ROOT, capture_output=True, timeout=60,
        )
        if p.returncode != 0:
            return ""
        return p.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return ""


def load_facts() -> dict:
    """真值快照：优先 `onboarding_block.facts()`，失败则 UNKNOWN。

    键名取自 onboarding_block.facts() 的真实返回（实测核对过）：
      total_entities / category_counts(是 dict，不是 categories 列表!) /
      oss_total / mech_declared / mech_full_declared / mech_applicable / mech_pct

    旧 refresh_status.py 读 `facts_data.get("categories", [])` —— 该键根本不存在，
    于是品类数恒为 0，写进 _STATUS.md 三周没人发现。这里不再猜键名。
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from onboarding_block import facts  # type: ignore
        f = facts()
        return {
            "total_entities": f.get("total_entities", 0),
            "cat_count": len(f.get("category_counts") or {}),
            "oss_total": f.get("oss_total", 0),
            "mech_declared": f.get("mech_declared", 0),
            "mech_full_declared": f.get("mech_full_declared", 0),
            "mech_applicable": f.get("mech_applicable", 0),
            "mech_pct": f.get("mech_pct", 0.0),
            "ok": True,
        }
    except Exception as exc:
        return {"ok": False, "err": f"{type(exc).__name__}: {exc}"}


def git_head() -> str:
    return _git("rev-parse", "--short", "HEAD") or "UNKNOWN"


def git_head_subject() -> str:
    return _git("log", "--oneline", "-1") or "UNKNOWN"


def git_dirty() -> list[str]:
    out = _git("status", "--porcelain")
    if not out:
        return []
    # 派生产物纯时间戳漂移是部署自身制造的，不算"脏"（两级判据，见 deploy.mjs preflight）
    derived_prefixes = ("api/", "data.js", "roboparts-dataset-github/")
    src = [
        ln for ln in out.splitlines()
        if ln.strip() and not any(
            ln.lstrip()[2:].strip().strip('"').startswith(p) for p in derived_prefixes
        )
    ]
    return src


def git_dirty_derived() -> list[str]:
    out = _git("status", "--porcelain")
    if not out:
        return []
    derived_prefixes = ("api/", "data.js", "roboparts-dataset-github/")
    return [
        ln for ln in out.splitlines()
        if ln.strip() and any(
            ln.lstrip()[2:].strip().strip('"').startswith(p) for p in derived_prefixes
        )
    ]


def lock_state() -> str:
    if not LOCK_FILE.exists():
        return "FREE"
    try:
        import json
        data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        return f"HELD by pid={data.get('pid', '?')} @ {data.get('ts', '?')}"
    except Exception:
        return "HELD (不可解析)"


def scan_sentinels() -> tuple[list[str], list[str]]:
    """返回 (真 AUTO-STUB 占位, RECONCILED 补写) 文件名列表。行锚定，正文提及不算。"""
    stubs: list[str] = []
    reconciled: list[str] = []
    for p in sorted(RESULTS.glob("roboparts-*.md")):
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                m = SENTINEL_RE.match(line.strip())
                if m:
                    (stubs if m.group(1) == "AUTO-STUB" else reconciled).append(p.name)
                    break
        except Exception:
            continue
    return stubs, reconciled


def ghost_hashes() -> list[str]:
    """报告里「声称已提交」但仓库中查无的哈希（幽灵哈希）。

    判定必须复用 `scripts/lib/hash_history.py` 的 `resolve()`，**不能**自己写
    `git cat-file -e` / `rev-parse --verify`。原因有两条，都是实测踩出来的：

    1. 全仓做过一次历史清理，87 个提交哈希被整体重写（见
       `ops/history_rewrite_ledger.json`）。重写前每轮如实记录的哈希如今在对象库里
       "查无"，但它们是**真实存在过的**，台账里有映射。第一版把 77 个这类哈希全判成
       幽灵——闸门误报，且危害正是 L1.32 说的：逼下一轮去放宽它，亲手造出假绿。
       `resolve()` 返回 'rewritten' 即合法。
    2. 「记述一个假哈希」不等于「声称提交了它」。报告为了说明某个哈希是伪造的，
       会原样引用它；±120 字符内出现 GHOST_OK 关键词即判为**在揭露**，豁免。

    口径与 regression.py 的哈希闸门保持一致（HASH_CTX / GHOST_OK 同参数）。
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from lib import hash_history as hh  # type: ignore
    except Exception:
        return []
    cands: set[str] = set()
    files = sorted(RESULTS.glob("roboparts-*.md")) + [NEEDS_USER]
    for p in files:
        try:
            text = Path(p).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in HASH_CTX.finditer(text):
            h = m.group(1)
            if h.isdigit():                      # 排除 20260806 这类日期串
                continue
            window = text[max(0, m.start() - 120):m.end() + 120]
            if any(k in window for k in GHOST_OK):
                continue
            cands.add(h)
    ghosts: list[str] = []
    for h in sorted(cands):
        if hh.resolve(ROOT, h, [ROOT, OPS_REPO])[0] == "unknown":
            ghosts.append(h)
    return ghosts



def regression_verdict(skip: bool = False) -> tuple[str, list[str]]:
    """返回 (verdict, 失败条目)。verdict ∈ GREEN/RED/UNKNOWN。"""
    if skip:
        return "UNKNOWN(已跳过)", []
    try:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "regression.py")],
            cwd=ROOT, capture_output=True, timeout=600,
        )
    except Exception as exc:  # 跑不起来=不知道，绝不算通过
        return f"UNKNOWN(异常 {exc})", []
    # 以**真实退出码**为准；文本解析只用于给出明细，解析不出也必须照实判 RED。
    text = p.stdout.decode("utf-8", "replace")
    fails = [ln.strip() for ln in text.splitlines() if "❌" in ln]
    if p.returncode == 0:
        return "GREEN", []
    return "RED", fails or [f"(退出码 {p.returncode}，未能解析出失败明细)"]


def last_deploy() -> str:
    tags = _git("tag", "--sort=-creatordate")
    if not tags:
        return "UNKNOWN"
    for t in tags.splitlines():
        if t.startswith("deploy-"):
            return t
    return "UNKNOWN"


def open_items() -> list[str]:
    """从 _NEEDS_USER.md 抽取未完成项 `- [ ]`，并**去重**。

    去重是必须的：历史上 _NEEDS_USER.md 曾把同一条「部署漂移自愈器升级项」
    在 15:59/16:07/16:19/16:25/16:26 重复追加 5 次，旧刷新器原样抄进 _STATUS.md，
    把一个故障放大成"5 个待办"。按正文前 40 字归一化判重，保留首条。
    """
    if not NEEDS_USER.exists():
        return ["(_NEEDS_USER.md 缺失)"]
    items: list[str] = []
    seen: set[str] = set()
    for line in NEEDS_USER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("- [ ]"):
            continue
        body = line[len("- [ ]"):].strip()
        body = body.replace("**", "").replace("~~", "").strip()
        body = re.sub(r"\s+", " ", body)
        key = body[:40]
        if key in seen:
            continue
        seen.add(key)
        items.append(body)
    return items


def last_digest() -> str:
    f = RESULTS / "_last_digest.txt"
    if not f.exists():
        return "UNKNOWN"
    try:
        return f.read_text(encoding="utf-8").strip() or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


# ---------------------------------------------------------------- 渲染

def build_markdown(now: dt.datetime, reg: tuple[str, list[str]],
                   stubs: list[str], recon: list[str],
                   ghosts: list[str]) -> str:
    verdict, fails = reg
    dirty_src = git_dirty()
    dirty_derived = git_dirty_derived()
    items = open_items()
    facts_d = load_facts()

    blocking = []
    if verdict != "GREEN":
        blocking.append(f"regression 门禁 {verdict}")
    if stubs:
        blocking.append(f"{len(stubs)} 份未填写占位")
    if dirty_src:
        blocking.append(f"{len(dirty_src)} 个源文件未提交")
    # 注意：**不把 ghosts 计入门禁**。regression.py 才是唯一的哈希闸门（它额外做了
    # 台账解析、树/提交类型感知、双仓比对）。本文件的哈希探测只是更早的提示项；
    # 两套口径一旦各自判灯，就会重现「多头对账漂移」——正是本脚本要消除的问题。
    gate = "🔴 阻断发布" if blocking else "✅ 放行"

    L: list[str] = []
    L.append("# RoboParts · 闭环总览（唯一对外接口）")
    L.append("")
    L.append(f"> 生成于 {now:%Y-%m-%d %H:%M} ｜ 由 `scripts/closure_status.py` 现取生成，禁手改")
    L.append(f"> **门禁结论：{gate}**")
    if blocking:
        L.append(f"> 阻断项：{'；'.join(blocking)}")
    L.append("")
    L.append("**这是唯一对外接口**：所有闭环状态、待办、阻塞只看本文件；")
    L.append("`_LATEST.md` / `_SUMMARY.md` / 逐小时报告仅作审计轨迹，不再用于对账。")
    L.append("")
    L.append("## 一、数据真值快照（facts() 现算）")
    L.append("")
    if facts_d.get("ok"):
        L.append("| 指标 | 值 |")
        L.append("|---|---|")
        L.append(f"| 实体总数 | {facts_d['total_entities']} |")
        L.append(f"| 品类数 | {facts_d['cat_count']} |")
        L.append(f"| OSS 组件 | {facts_d['oss_total']} |")
        L.append(f"| 机械声明 applicable | {facts_d['mech_applicable']} |")
        L.append(f"| 机械声明 declared+partial | {facts_d['mech_declared']}"
                 f"（其中完整 declared {facts_d['mech_full_declared']}）|")
        L.append(f"| mech_pct（现算） | {facts_d['mech_pct']}% |")
        L.append("")
        L.append("> ⚠️ `mech_pct` 是 `declared+partial / applicable` 的现算值，"
                 "与**对外唯一口径 1.52%** 不是同一个分母。对外传播一律用 1.52%，"
                 "本表仅供内部看数据缺口，不得直接抄到页面/文案。")
    else:
        L.append(f"- ❌ facts() 取不到（{facts_d.get('err')}）—— 记 UNKNOWN，不报假数")
    L.append("")
    L.append("## 二、闭环状态")
    L.append("")
    L.append("| 项 | 值 | 判读 |")
    L.append("|---|---|---|")
    L.append(f"| git HEAD | `{git_head()}` | {git_head_subject()[:60]} |")
    L.append(f"| 源改动未提交 | {len(dirty_src)} | {'❌ 须先提交' if dirty_src else '✅ 干净'} |")
    L.append(f"| 派生时间戳漂移 | {len(dirty_derived)} | {'可随部署入库' if dirty_derived else '✅ 无'} |")
    L.append(f"| 单实例锁 | {lock_state()} | {'❌ 占用中' if lock_state() != 'FREE' else '✅ 空闲'} |")
    L.append(f"| regression 门禁 | {verdict} | {'✅ 放行' if verdict == 'GREEN' else '❌ 阻断'} |")
    L.append(f"| 未填写占位 | {len(stubs)} | {'❌ ' + ', '.join(stubs[:5]) if stubs else '✅ 无'} |")
    L.append(f"| RECONCILED 补写 | {len(recon)} | 审计轨迹 |")
    L.append(f"| 哈希可解析性（提示项·非闸门） | {len(ghosts)} | "
             f"{'⚠️ ' + ', '.join(ghosts[:5]) + ' 主仓+ops仓+重写台账均查无，请人工核' if ghosts else '✅ 全部可解析'} |")
    L.append(f"| 最近部署标记 | `{last_deploy()}` | 部署留痕 |")
    L.append(f"| 上次日报 | {last_digest()} | 节流用 |")
    L.append("")
    if fails:
        L.append("### 门禁失败明细")
        L.append("")
        for f in fails[:20]:
            L.append(f"- {f}")
        L.append("")
    L.append("## 三、待你操作（P0 / P1 / P2）")
    L.append("")
    if items:
        for it in items:
            L.append(f"- [ ] {it}")
    else:
        L.append("- （无）")
    L.append("")
    L.append("## 四、一个口子怎么用")
    L.append("")
    L.append("1. **问状态**＝读本文件；不要再去翻 `_LATEST` / `_SUMMARY` / 逐小时报告。")
    L.append("2. **跑一轮**＝`python scripts/closure_status.py --write` 刷新本文件。")
    L.append("3. **发布前**＝本文件门禁必须是 ✅ 放行；RED 时先修明细里的条目。")
    L.append("4. **新增待办**＝写进 `_NEEDS_USER.md` 的 `- [ ]` 行，本文件自动汇总。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("本文件不进 git（`ops/` 已忽略），纯本地对账用。")
    return "\n".join(L) + "\n"


def print_summary(md: str) -> None:
    for line in md.splitlines():
        if line.startswith((">", "|", "- [ ]", "- ❌", "- [x]")):
            print(line)


# ---------------------------------------------------------------- 入口

def main() -> int:
    ap = argparse.ArgumentParser(description="闭环唯一对外接口")
    ap.add_argument("--write", action="store_true", help="生成/覆盖 _STATUS.md")
    ap.add_argument("--skip-regression", action="store_true", help="跳过 regression 慢门禁")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    now = dt.datetime.now()
    stubs, recon = scan_sentinels()
    ghosts = ghost_hashes()
    reg = regression_verdict(skip=args.skip_regression)

    md = build_markdown(now, reg, stubs, recon, ghosts)

    if args.write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        STATUS_MD.write_text(md, encoding="utf-8")
        print(f"[closure] 已写入 {STATUS_MD.relative_to(ROOT)}")
    print_summary(md)

    verdict = reg[0]
    # 门禁口径唯一：只看 regression 与未填写占位。哈希探测是提示项，不参与退出码，
    # 否则本脚本会变成 regression 的第二套口径。
    return 0 if verdict == "GREEN" and not stubs else 1


if __name__ == "__main__":
    raise SystemExit(main())
