#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_croissant.py — Croissant 元数据闸门（方向锚点 v2.1 Phase A1 副产品）。

产物是**对外引用入口**，失效模式有两个：
  ① 计数与 facts() 脱节（手写副本腐烂）—— 引用者拿到的数字比库少/多；
  ② 诚实边界丢失 —— license/description 被改掉后，下游把它当 benchmark 用。
本闸门两趟：
  ① 审计：croissant 必备键、license=CC-BY-4.0、distribution 指到的文件真实存在、
     计数逐键对账 facts()（total/per_category/机械四态）、description 内嵌
     total 与 pct 必须等于现算值（抓"陈旧描述"）、CITATION.cff 存在且版本正确；
  ② 自证（阴阳/变异）：阳性 = 审计现建产物必须绿；变异 5 项 = 翻计数 / 改机械
     四态 / 换 license / 删 distribution / 抽掉 description 的现算数字 ——
     每个变异必须判红，否则闸门等于没闸门。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from onboarding_block import facts  # noqa: E402

CC_BY = "https://creativecommons.org/licenses/by/4.0/"
REQUIRED_KEYS = ["@context", "@type", "name", "description", "license",
                 "distribution", "recordSet", "version", "rp:counts",
                 "rp:honesty_limits"]


def audit(c: dict, *, with_files: bool = True):
    """返回失败原因列表；空列表 = 绿。with_files=False 供变异自证（不查盘上文件）。"""
    errs = []
    f = facts()

    for k in REQUIRED_KEYS:
        if k not in c:
            errs.append(f"缺必备键 {k}")

    if c.get("license") != CC_BY:
        errs.append(f"license 应为 CC-BY-4.0，实际 {c.get('license')!r}")

    counts = c.get("rp:counts", {})
    expect_counts = {
        "total_entities": f["total_entities"],
        "component_entities": f["component_entities"],
        "specification_entities": f["specification_entities"],
        "software_entities": f["software_entities"],
        "organization_entities": f["organization_entities"],
        "market_intelligence_entities": f["market_intelligence_entities"],
        "categories": len(f["category_counts"]),
        "per_category": f["category_counts"],
    }
    for k, want in expect_counts.items():
        if counts.get(k) != want:
            errs.append(f"rp:counts.{k} = {counts.get(k)!r}，facts() = {want!r}")

    expect_mech = {
        "declared": f["mech_full_declared"],
        "partial": f["mech_partial"],
        "not_declared": f["mech_not_declared"],
        "n_a": f["mech_n_a"],
    }
    if counts.get("mechanical_declaration") != expect_mech:
        errs.append(f"rp:counts.mechanical_declaration = {counts.get('mechanical_declaration')}，facts() = {expect_mech}")

    # description 必须内嵌现算 total 与 pct —— 抓"计数更新了、描述没更新"的陈旧态
    desc = c.get("description", "")
    if str(f["total_entities"]) not in desc:
        errs.append("description 未内嵌现算 total_entities（陈旧描述）")
    if str(f["mech_pct"]) not in desc:
        errs.append("description 未内嵌现算 mech_pct（陈旧描述）")
    if "not a benchmark" not in desc:
        errs.append("description 丢失「非 benchmark」诚实边界")

    if not c.get("rp:honesty_limits"):
        errs.append("rp:honesty_limits 为空 —— 诚实边界必须随元数据传播")

    if with_files:
        for d in c.get("distribution", []):
            url = d.get("contentUrl", "")
            rel = url.replace("https://roboparts.cc/", "")
            if not (ROOT / rel).exists():
                errs.append(f"distribution 指向不存在的文件 {rel}")
        cff = ROOT / "CITATION.cff"
        if not cff.exists():
            errs.append("CITATION.cff 不存在")
        else:
            txt = cff.read_text(encoding="utf-8")
            if "cff-version: 1.2.0" not in txt:
                errs.append("CITATION.cff 缺 cff-version: 1.2.0")
            if "CC-BY-4.0" not in txt:
                errs.append("CITATION.cff license 与数据许可不一致")
    return errs


def self_test():
    import build_croissant

    base = json.loads(json.dumps(build_croissant.build()))
    failures = []

    def expect(name, mutated, should_pass):
        errs = audit(mutated, with_files=False)
        ok = (len(errs) == 0) if should_pass else (len(errs) > 0)
        if not ok:
            failures.append(f"{name}: {'意外红 ' + str(errs) if should_pass else '变异未被捕获'}")

    expect("阳性·现建产物", base, True)

    m = json.loads(json.dumps(base)); m["rp:counts"]["total_entities"] += 1
    expect("变异1·total+1", m, False)

    m = json.loads(json.dumps(base)); m["rp:counts"]["mechanical_declaration"]["declared"] = 99
    expect("变异2·机械四态改写", m, False)

    m = json.loads(json.dumps(base)); m["license"] = "https://opensource.org/licenses/MIT"
    expect("变异3·license 换 MIT", m, False)

    m = json.loads(json.dumps(base)); m.pop("distribution")
    expect("变异4·删 distribution", m, False)

    m = json.loads(json.dumps(base))
    m["description"] = "Stale description without any live numbers."
    expect("变异5·描述去数字", m, False)

    m = json.loads(json.dumps(base)); m["rp:honesty_limits"] = []
    expect("变异6·清空诚实边界", m, False)

    return failures


def main():
    if "--self-test" in sys.argv:
        failures = self_test()
        if failures:
            print("❌ 自证失败：")
            for x in failures:
                print("  -", x)
            sys.exit(1)
        print("✅ 自证 7 项全过（1 阳性 + 6 变异）")
        return

    c = json.loads((ROOT / "api" / "croissant.json").read_text(encoding="utf-8"))
    errs = audit(c)
    if errs:
        if "--quiet" not in sys.argv:
            print("❌ croissant 审计失败：")
            for x in errs:
                print("  -", x)
        sys.exit(1)
    if "--quiet" not in sys.argv:
        print("✅ croissant 审计通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
