#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 / 刷新三个**面向外部目录与 agent 的公开清单**，所有数字现算，不手打。

    1. server.json              —— 官方 MCP Registry / Glama 的元数据来源
    2. smithery.yaml            —— Smithery 目录清单
    3. .well-known/mcp.json     —— MCP 目录友好型发现文件

为什么需要生成器
----------------
本仓在「静态数字」上已经踩过三轮同一个坑：

  * 20260805  mcp-server FILE_MAP 只列 7/11 品类 → 580 vs 对外 688
  * 20260918  FILE_MAP 与 functions/mcp.js 的 CATEGORIES 都停在 11/20
  * 20260918  server.json 仍写 "688"（Glama 线上条目正是取它当简介）、
              smithery.yaml 仍写 "688 条" 且只列 5/10 个工具

共同点：**文案里的数字与工具清单都是手写的，没有任何机制在数据变化时
把它们拉回来。** 人不会记得，所以让机器生成 + 让 --check 红灯。

真相源（全部为单一来源，本脚本不做二次推导）
--------------------------------------------
    实体总数/分类构成   scripts/onboarding_block.py 的 facts()
    品类个数            api/entities.json 的 meta.categories
    托管端点版本        functions/mcp.js 的 SERVER_VERSION
    工具清单            skills/manifest.json（本身由 TOOLS 生成）

用法
----
    python3 scripts/gen_public_manifests.py            # 刷新
    python3 scripts/gen_public_manifests.py --check    # 只校验是否漂移（CI 用）
"""

import argparse
import importlib.util
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES = os.path.join(BASE, "api", "entities.json")
MCP_JS = os.path.join(BASE, "functions", "mcp.js")
SKILLS = os.path.join(BASE, "skills", "manifest.json")
SERVER_JSON = os.path.join(BASE, "server.json")
SMITHERY = os.path.join(BASE, "smithery.yaml")
WELL_KNOWN = os.path.join(BASE, ".well-known", "mcp.json")
ONBOARDING = os.path.join(BASE, "scripts", "onboarding_block.py")

SITE = "https://roboparts.cc"
REPO = "https://github.com/lm203688/roboparts"


def load_facts():
    spec = importlib.util.spec_from_file_location("onboarding_block", ONBOARDING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.facts()


def load_category_count():
    with open(ENTITIES, encoding="utf-8") as f:
        cats = json.load(f).get("meta", {}).get("categories") or []
    if not cats:
        raise SystemExit("❌ api/entities.json 的 meta.categories 为空 —— 真相源异常，拒绝生成。")
    return len(cats)


def load_server_version():
    """从托管端点取版本，避免 server.json 与 SERVER_VERSION 两处各写一份。"""
    with open(MCP_JS, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"SERVER_VERSION\s*=\s*['\"]([^'\"]+)['\"]", src)
    if not m:
        raise SystemExit("❌ 从 functions/mcp.js 读不到 SERVER_VERSION —— 真相源缺失，拒绝生成。")
    return m.group(1)


def load_tools():
    """工具清单取自 skills/manifest.json（它本身由 functions/mcp.js 的 TOOLS 生成）。

    返回 (工具名, 简述)。简述取 description 的前 1-2 句 —— 既保持「从真相源派生」，
    又比裸 title 更有信息量（目录页的读者只看到这一行）。
    """
    with open(SKILLS, encoding="utf-8") as f:
        skills = json.load(f).get("skills") or []
    out = []
    for s in skills:
        if s.get("type") != "mcp_tool":
            continue
        out.append((s["tool"], _short(s.get("description") or s.get("title") or "")))
    if not out:
        raise SystemExit("❌ skills/manifest.json 里没有 mcp_tool 条目 —— 真相源缺失，拒绝生成。")
    return out


def _short(desc, limit=110, max_sentences=2):
    """取前 N 句中文句子，超长则截断。确定性，便于 --check 比对。"""
    parts = [p.strip() for p in desc.split("。") if p.strip()]
    acc = ""
    for p in parts[:max_sentences]:
        cand = acc + p + "。"
        if acc and len(cand) > limit:
            break
        acc = cand
    acc = acc or desc
    return acc if len(acc) <= limit else acc[:limit].rstrip() + "…"


# --------------------------------------------------------------- server.json
def render_server_json(f, cats, version):
    doc = {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": "cc.roboparts/roboparts",
        "title": "RoboParts 机器人零部件兼容性",
        "description": (
            f"{f['total_entities']} humanoid/bionic robot component entities across "
            f"{cats} categories, with protocol / electrical / mechanical / software "
            f"compatibility checking. Vendor-neutral."
        ),
        "version": version,
        "websiteUrl": SITE,
        "repository": {"url": REPO, "source": "github"},
        "remotes": [{"type": "streamable-http", "url": f"{SITE}/mcp"}],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


# -------------------------------------------------------------- smithery.yaml
SMITHERY_TEMPLATE = """\
# Smithery 目录清单 —— RoboParts hosted MCP
#
# ⚠️ 数字与工具集由 scripts/gen_public_manifests.py 现算生成，手改会被 --check 打回。
#    （本条目的简介曾长期停在 688 条 / 5 个工具，而真值已是 798 / 10。）
#
# 我方走 hosted Streamable HTTP 端点而非 npm 包分发：
# 用户侧成本从「装包 + 领 key + 起进程」降到「粘贴一个 URL」。
# 端点免鉴权只读，因此不需要 configSchema。
startCommand:
  type: http
  url: {site}/mcp
  configSchema:
    type: object
    properties: {{}}
    required: []

name: roboparts
displayName: RoboParts 机器人零部件兼容性
description: >-
{desc_lines}
homepage: {site}
documentation: {site}/mcp-guide
license: MIT
icon: {site}/favicon.ico

tags:
{tags}

tools:
{tools}
"""

SMITHERY_TAGS = [
    "robotics",
    "humanoid-robot",
    "hardware",
    "compatibility",
    "bom",
    "embodied-ai",
    "actuator",
    "sensor",
]


def _fold(sentences, indent="  "):
    return "\n".join(f"{indent}{s}" for s in sentences)


def render_smithery(f, cats):
    desc_lines = _fold([
        f"仿生/人形机器人零部件兼容性数据层。{f['total_entities']} 条实体、{cats} 个品类。",
        "支持 protocol / electrical / mechanical / ROS2 四维兼容判定与参数口径可比性核对。",
        "中立数据层：既不生产也不转售任何零部件；兼容性结论基于厂商公开声明字段的规则推断",
        "而非实测，未声明维度显式标为「无法判定」。",
    ])
    return SMITHERY_TEMPLATE.format(
        site=SITE,
        desc_lines=desc_lines,
        tags="\n".join(f"  - {t}" for t in SMITHERY_TAGS),
        tools="\n".join(
            # 用 json.dumps 生成双引号标量：YAML 是 JSON 的超集，
            # 这样 description 里的 ':' '（' 等字符不会把 YAML 解析搞坏。
            f"  - name: {name}\n    description: {json.dumps(desc, ensure_ascii=False)}"
            for name, desc in load_tools()
        ),
    )


# ------------------------------------------------------- .well-known/mcp.json
def render_well_known(f, tools):
    doc = {
        "mcpVersion": "2025-06-18",
        "servers": [
            {
                "name": "roboparts",
                "title": "RoboParts 机器人零部件兼容性",
                "description": (
                    f"仿生/人形机器人零部件兼容性数据层：{f['total_entities']} 条实体"
                    f"（{f['component_entities']} 实物零部件 / {f['specification_entities']} 接口规范 / "
                    f"{f['software_entities']} AI 模型软件 / {f['organization_entities']} 企业主体 / "
                    f"{f['market_intelligence_entities']} 市场情报），支持协议/电气/机械/ROS2 四维兼容判定。"
                    f"中立数据层 —— 既不生产也不转售任何零部件。"
                ),
                "transport": "streamable-http",
                "url": f"{SITE}/mcp",
                "authentication": "none",
                "readOnly": True,
                "tools": [name for name, _ in tools],
                "documentation": f"{SITE}/mcp-guide",
                "provider": {"name": "RoboParts", "url": SITE},
                "boundaries": [
                    "只读、免鉴权、不设 cookie、不存储调用方数据",
                    "兼容性结论基于厂商公开声明字段的规则推断，非实验室实测",
                    "厂商未声明的维度记为无法判定，不计入兼容也不计入不兼容",
                    "与任何零部件厂商无商业绑定",
                ],
            }
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验是否漂移，不落盘")
    args = ap.parse_args()

    f = load_facts()
    cats = load_category_count()
    version = load_server_version()
    tools = load_tools()

    targets = [
        (SERVER_JSON, render_server_json(f, cats, version)),
        (SMITHERY, render_smithery(f, cats)),
        (WELL_KNOWN, render_well_known(f, tools)),
    ]

    drift = []
    for path, want in targets:
        cur = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                cur = fh.read()
        if cur != want:
            drift.append(os.path.relpath(path, BASE))

    if args.check:
        if drift:
            print("❌ 公开清单与真相源已漂移：")
            for d in drift:
                print(f"    - {d}")
            print("  修法：运行 python3 scripts/gen_public_manifests.py")
            return 1
        print(
            f"✓ 公开清单与真相源一致（{f['total_entities']} 条实体 / {cats} 个品类 / "
            f"{len(tools)} 个工具 / v{version}）"
        )
        return 0

    for (path, want), rel in zip(targets, [os.path.relpath(p, BASE) for p, _ in targets]):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(want)
        print(f"✓ 已刷新 {rel}")

    print(
        f"\n数字现算：{f['total_entities']} 条实体（{f['component_entities']} 实物 / "
        f"{f['specification_entities']} 规范 / {f['software_entities']} 软件 / "
        f"{f['organization_entities']} 企业 / {f['market_intelligence_entities']} 情报）"
        f"｜{cats} 个品类｜{len(tools)} 个工具｜v{version}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
