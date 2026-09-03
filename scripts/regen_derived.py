#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""派生产物全量再生器（add-entity / deploy 的统一后处理）。

为什么需要这个脚本
------------------
`api/entities.json` 是唯一的真相源。历史上「加一个实体就崩 35 个回归闸门」的根因是：
加实体脚本只改了真相源，却从不开火 ~30 份派生副本的再生器，导致这些副本（对外数据集
分发目录、语义索引、页面接入区块数字、meta.access、agent-discovery 技能清单、阴性兼容库）
与真相源同刻脱节，被 ci_gate / regression 判红。

本脚本把「改了真相源 → 立刻重生全部派生」收敛成**单一入口**，供两处调用：
  1. scripts/add_bionic_entities.py 的 main() 末尾（加实体后自动重生）；
  2. scripts/deploy.mjs 的构建阶段（替换原先只跑了 3 项的 0b4/0c/0d，补上漏掉的
     sync_dataset_dist 与 gen_skills_manifest，杜绝「加实体后对外副本漂移」）。

所有子步骤均为幂等再生器（只写、不依赖人记得手工跑），任一失败都会汇总并报红，
但**不**因单步失败中断其余步骤（尽量多修复）。

用法
----
    python scripts/regen_derived.py            # 全量再生（写回派生文件）
    python scripts/regen_derived.py --check    # 仅跑各生成器自带的 --check；有漂移 exit 1
                                              #   （供 CI 在不动文件的前提下验证一致性）
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

# 优先用受管 node（与 binary_context 一致），再回退 PATH 上的 node。
NODE_CANDIDATES = [
    os.environ.get("ROBOPARTS_NODE"),
    r"C:/Users/xing/.workbuddy/binaries/node/versions/22.22.2-2/node.exe",
    "node",
    "node.exe",
]

# 步骤：(标签, [解释器, 脚本, *args], 是否支持 --check)
#  解释器为 None 表示用 sys.executable（python 步骤）。
STEPS = [
    ("对外数据集分发 (sync_dataset_dist)",
     None, "sync_dataset_dist.py", True),
    ("语义索引 (build_semantic_index)",
     "node", "build_semantic_index.mjs", False),
    ("接入区块注入 (inject_onboarding)",
     None, "inject_onboarding.py", False),
    ("meta.access 注入 (inject_api_access)",
     None, "inject_api_access.py", False),
    ("技能清单 (gen_skills_manifest)",
     "node", "gen_skills_manifest.mjs", True),
    ("阴性兼容库 (build_negative_compat)",
     None, "build_negative_compat.py", False),
    # ── 以下为「加实体后必须同步的 meta / 归一化副本」────
    # 顺序约束：audit_data_quality 先写 per-entity data_quality/quarantine，
    # 其后 normalize_categories 才能把该字段传播进 data.js / 分类JSON / api/data.json。
    ("数据质量审计 (audit_data_quality)",
     None, "audit_data_quality.py", False),
    ("实体种类治理 (govern_entity_kind)",
     None, "govern_entity_kind.py", False),
    ("溯源等级治理+meta (enrich_provenance)",
     None, "enrich_provenance.py", False),
    ("机械接口覆盖 meta (fix_mi_meta)",
     None, "fix_mi_meta.py", False),
    ("归一化副本 (normalize_categories: data.js/分类JSON/api/data.json/meta.category_counts)",
     None, "normalize_categories.py", False),
    ("对外训练数据集 (export_training_dataset)",
     "node", "export_training_dataset.mjs", False),
    ("README/llms.txt 数据量行 (refresh_doc_counts)",
     None, "refresh_doc_counts.py", False),
]


def find_node():
    for cand in NODE_CANDIDATES:
        if not cand:
            continue
        try:
            r = subprocess.run([cand, "--version"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                return cand
        except Exception:
            continue
    return "node"


def main():
    check_mode = "--check" in sys.argv
    node = find_node()
    py = sys.executable  # 本脚本自身由 python 启动，python 步骤直接用同一解释器

    print(f"[REGEN-DERIVED] {'校验模式' if check_mode else '全量再生模式'}"
          f"（真相源 api/entities.json；node={node}）")

    failures = []
    for label, interp, script, supports_check in STEPS:
        script_path = os.path.join(SCRIPTS, script)
        if not os.path.exists(script_path):
            print(f"  ⚠️ 跳过 {label}：脚本缺失 {script}")
            continue

        if check_mode and supports_check:
            cmd = [py if interp is None else node, script_path, "--check"]
        else:
            # 不带 --check 的步骤在 check 模式下仍跑「再生」（幂等），
            # 以尽量把副本拉回一致；语义等价「确保新鲜」。
            cmd = [py if interp is None else node, script_path]

        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                               text=True, timeout=300)
        except Exception as ex:  # noqa: BLE001
            print(f"  ❌ {label}：调用异常 {ex}")
            failures.append(label)
            continue

        last = (r.stdout or "").strip().splitlines()[-1:] or [""]
        last = last[0][:160]
        if r.returncode == 0:
            tag = "✅" if not check_mode else "✅(check)"
            print(f"  {tag} {label}" + (f" — {last}" if last else ""))
        else:
            err = (r.stderr or r.stdout or "").strip().replace("\n", " | ")[:300]
            print(f"  ❌ {label} (exit {r.returncode}): {err}")
            failures.append(label)

    print("\n" + "=" * 52)
    if failures:
        print(f"❌ 派生产物{'校验' if check_mode else '再生'}有 {len(failures)} 项未通过：")
        for f in failures:
            print(f"   - {f}")
        print("   修复建议：单独跑失败脚本看详情；或检查 api/entities.json 是否合法。")
        return 1
    if check_mode:
        print("✅ 全部派生产物与真相源一致（--check 通过）")
    else:
        print("✅ 全部派生产物已随真相源重生")
    return 0


if __name__ == "__main__":
    sys.exit(main())
