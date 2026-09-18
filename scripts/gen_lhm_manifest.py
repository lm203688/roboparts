#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 / 刷新 lhm.plugin.json —— LobeHub Marketplace 的 owner declaration。

为什么用生成器而不是手写
------------------------
LobeHub 的 lhm.plugin.json 里有两类内容：

  1. **内省结果**（tools / resources / prompts）—— 只能由
     `lhm plugin init` 连上真实 MCP server 抓取，本脚本不重造。
  2. **owner declaration**（name / description / tags / cloudEndpoint / i18n）
     —— 人工声明，但其中**文案里的数字必须现算**。

第 2 类里但凡写死数字，必然失修：本仓刚吃过一次教训 ——
mcp-server 的 FILE_MAP 与 tool schema enum 都曾停在「11 个品类」，
而库内已是 20 个品类，用户搜 gripper / reducer 得到 0 命中。
所以这里的 {total} / {categories} 占位符一律从
api/entities.json 的 meta 现算填入，不手打。

流程
----
    # 1) 工具集变了的时候，先用官方 CLI 重新内省（会覆盖 manifest）
    npx -y @lobehub/market-cli plugin init --force \\
        --stdio "node mcp-server/index.js" --dir .

    # 2) 再叠加上 owner declaration（本脚本；幂等，可反复跑）
    python3 scripts/gen_lhm_manifest.py

    # 3) 发布 / 更新
    npx -y @lobehub/market-cli plugin publish https://github.com/lm203688/roboparts --dir .
    # 版本号无变化时用 update（同版本号=原地合并，安全可重试）
    npx -y @lobehub/market-cli plugin update --dir .
"""

import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(BASE, "lhm.plugin.json")
ENTITIES = os.path.join(BASE, "api", "entities.json")

# ---------------------------------------------------------------- owner 声明
# 只在需要改动对外口径时才动这里。数字请用 {total}/{categories} 占位符。
OWNER = {
    "identifier": "lm203688-roboparts",
    # en-US 是「源语言」：LobeHub 原样展示、绝不机翻，其它语言由它自动翻译。
    # 因此这里写英文，中文用下面的 localizations 显式覆盖。
    "name": "RoboParts — Robot Component Compatibility",
    "description": (
        "Vendor-neutral compatibility data layer for humanoid and bionic robot "
        "components. Query {total} parts across {categories} categories and get "
        "protocol / electrical / mechanical / software compatibility judgments. "
        "We neither manufacture nor resell any part."
    ),
    "author": "RoboParts",
    "authorUrl": "https://github.com/lm203688",
    "homepage": "https://roboparts.cc",
    # 权威的远程部署地址：让用户不必自己跑 server，直接连这个端点。
    # 这是本 listing 相对纯 stdio 插件的核心增量。
    "cloudEndpoint": "https://roboparts.cc/mcp",
    "category": "developer",
    "icon": "🤖",
    "tags": [
        "robotics",
        "humanoid-robot",
        "robot-parts",
        "hardware",
        "components",
        "compatibility",
        "actuator",
        "sensor",
        "bom",
        "embodied-ai",
    ],
    # owner 提供的语种是权威的，翻译器与重爬都不会覆盖。
    "localizations": [
        {
            "locale": "zh-CN",
            "name": "RoboParts — 机器人零部件兼容性数据层",
            "description": (
                "厂商中立的仿生／人形机器人零部件兼容性数据层。可检索 {categories} 个品类"
                "共 {total} 条零部件，并给出协议／电气／机械／软件四维兼容性判定。"
                "我们既不生产也不转售任何零部件，数据层保持中立。"
            ),
        }
    ],
}


def load_counts():
    """从 api/entities.json 的 meta 现算对外数字（唯一真相源）。"""
    with open(ENTITIES, encoding="utf-8") as f:
        meta = json.load(f).get("meta", {})
    total = meta.get("total") or meta.get("total_entities")
    cats = len(meta.get("categories") or [])
    if not total or not cats:
        raise SystemExit(
            "❌ api/entities.json 的 meta 缺少 total/categories，"
            "无法现算对外数字。拒绝用占位数字发布。"
        )
    return {"total": total, "categories": cats}


def fill(s, counts):
    return s.format(**counts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run", action="store_true", help="只打印将要写入的内容，不落盘"
    )
    args = ap.parse_args()

    if not os.path.exists(MANIFEST):
        raise SystemExit(
            "❌ 找不到 lhm.plugin.json。请先跑一次官方内省：\n"
            '   npx -y @lobehub/market-cli plugin init --force '
            '--stdio "node mcp-server/index.js" --dir .'
        )

    with open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)

    counts = load_counts()

    # 内省产物必须原样保留 —— 本脚本不重造 tools。
    tools = m.get("tools") or []
    if not tools:
        raise SystemExit("❌ lhm.plugin.json 里没有 tools —— 内省结果缺失，先重跑 plugin init。")

    # version 跟随 package.json（npm 包版本），避免两处版本漂移
    pkg = os.path.join(BASE, "mcp-server", "package.json")
    pkg_version = None
    if os.path.exists(pkg):
        with open(pkg, encoding="utf-8") as f:
            pkg_version = json.load(f).get("version")

    out = {}
    out["identifier"] = OWNER["identifier"]
    out["name"] = OWNER["name"]
    out["version"] = pkg_version or m.get("version")
    out["description"] = fill(OWNER["description"], counts)
    out["author"] = OWNER["author"]
    out["authorUrl"] = OWNER["authorUrl"]
    out["homepage"] = OWNER["homepage"]
    out["cloudEndpoint"] = OWNER["cloudEndpoint"]
    out["category"] = OWNER["category"]
    out["icon"] = OWNER["icon"]
    out["tags"] = OWNER["tags"]
    out["localizations"] = [
        {
            "locale": loc["locale"],
            "name": fill(loc["name"], counts),
            "description": fill(loc["description"], counts),
        }
        for loc in OWNER["localizations"]
    ]
    # 内省产物（顺序与官方 init 一致：tools / resources / prompts）
    out["tools"] = tools
    out["resources"] = m.get("resources") or []
    out["prompts"] = m.get("prompts") or []

    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"

    if args.dry_run:
        print(text)
        return 0

    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write(text)

    print(
        f"✓ lhm.plugin.json 已刷新｜identifier={out['identifier']}｜"
        f"version={out['version']}｜tools={len(out['tools'])}｜"
        f"数字现算：{counts['total']} 实体 / {counts['categories']} 品类"
    )
    print(f"  cloudEndpoint={out['cloudEndpoint']}（远程用户免安装直连）")
    print(f"  i18n 语种：en-US(源) + {', '.join(l['locale'] for l in out['localizations'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
