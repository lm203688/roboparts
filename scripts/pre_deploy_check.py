#!/usr/bin/env python3
"""RoboParts 预部署本地数字护栏。

扫描**本地**待部署内容（非线上），对照真相源 facts() 校验是否有与
实体总数/品类数矛盾的硬编码数字。若发现则 exit(1)，由 deploy.mjs 中止部署，
避免把过期数字（如 217 款执行器 / 768 实体）上线后再靠 verify 回探才发现
（红 → 被迫二次闭环）。

仅扫描会暴露硬编码品类数的散文类文件（html/md/txt）；JSON 派生产物由 regen
从真相源生成，可信，不在此扫描。
"""
import os
import sys
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from onboarding_block import facts
from verify_live_numbers import (
    expected_values,
    html_to_lines,
    number_mismatches,
    claim_mismatches,
)


def main() -> int:
    exp = expected_values(facts())
    files = ["llms.txt", "index.html", "bionic.html"]
    files += sorted(glob.glob("articles/*.html"))
    files += sorted(glob.glob("*.html"))
    files = sorted(set(files))

    violations = []
    for f in files:
        if not os.path.exists(f):
            continue
        try:
            text = open(f, encoding="utf-8").read()
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] 无法读取 {f}: {e}")
            continue
        lines = html_to_lines(text)
        v = number_mismatches(lines, exp)
        seen = {(a, d) for a, _, _, d, _ in v}
        v += [x for x in claim_mismatches(lines, exp) if (x[0], x[3]) not in seen]
        for row in v:
            violations.append((f, row[0], row[2], row[3], row[4]))

    if violations:
        print("PRE-DEPLOY NUMBER GUARD: FAILED — 本地内容存在与真相源矛盾的数字：")
        for f, ln, noun, got, want in violations:
            print(f"  {f}:{ln}  {noun} got={got} want={want}")
        return 1
    print("PRE-DEPLOY NUMBER GUARD: PASS（本地内容数字与真相源一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
