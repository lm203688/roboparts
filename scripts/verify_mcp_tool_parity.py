#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 工具集对等闸门（P0-11）—— npm 包（mcp-server/）与托管服务（functions/mcp.js）工具名对等。

为什么必须对等
--------------
两个 MCP 面是**同一产品**的两张脸：
  - hosted（functions/mcp.js，streamable-http）：26 个工具，引擎在线上（compose_core、
    URDF lint、共装判定等跑在服务器）。
  - npm（mcp-server/index.js，stdio）：16 个工具，本地 stdio 服务，从 roboparts.cc/api
    拉取**预计算**产物。

此前两者**静默漂移**：hosted 有 15 个工具 npm 不暴露（Agent 走 npm 就调不到），
npm 有 5 个工具 hosted 不暴露（线上面调不到）。这正是本项目反复踩的
「同一产品两个口径」病根。且 16/26 之差从未有闸门看住，改一个面不会让任何机器响。

本闸门判据（硬不变量）
----------------------
  ① hosted 工具名集合必须**等于** npm 工具名集合，在扣除**显式声明的意图分歧**后：
        hosted - npm ⊆ HOSTED_ONLY（带理由的清单）
        npm - hosted ⊆ NPM_ONLY（带理由的清单）
  ② 清单不得含**已不存在**的工具（清单过期 → 判红，防止"永远记着一条不存在的差异"）。
  ③ 清单不得含**已对等**的工具（清单夸大 → 判红，防止"用清单掩盖已完成的对等"）。
  ④ 任何**未登记**的差异 → 判红（新增工具必须两面对等或显式登记，防止再度静默漂移）。

为什么用"显式清单"而不是强推 15 个工具立刻镜像：
  hosted-only 工具（explain_* / lint_urdf / check_co_mount / get_parameter_semantics 等）
  需要线上引擎或在线判据，npm 本地 stdio 服务只拉预计算 api/*.json，无法本地重演引擎。
  **强行在 npm 里造假实现 = 两个面给出不同答案**，比不暴露更糟。所以：
  这些工具必须**显式登记为"hosted-only，需在线"**，而不是静默缺失。
  这是"诚实声明缺失"（同本项目 quarantine 铁律），不是掩盖。

用法
----
    python scripts/verify_mcp_tool_parity.py          # 非零退出 = 判红
    python scripts/verify_mcp_tool_parity.py --list   # 打印两套工具名
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTED = os.path.join(ROOT, 'functions', 'mcp.js')
NPM = os.path.join(ROOT, 'mcp-server', 'index.js')

# ---------------------------------------------------------------- 意图分歧清单
# 每条 = 工具名 : 理由。理由必须说明"为什么这一侧没有/有而另一侧没有"。
# 注意：**新增**工具若未在此登记，闸门会判红 —— 这是防再度漂移的机制。
HOSTED_ONLY = {
    # hosted 有、npm 无 —— 需要在线引擎或在线判据，本地 stdio 服务无法重演。
    'get_parameter_semantics': '参数语义由 compose 引擎现算，本地 stdio 只拉预计算产物，无法重演；须在线',
    'bom_compatibility_check': 'BOM 兼容判定由在线 bom/check 服务现算，本地无该引擎；须在线',
    'semantic_search': '语义检索由在线语义索引现算，本地无该索引；须在线',
    'get_standard_audit': '标准审计由在线审计器现算（standard-audit.json 为在线产物）；须在线',
    'review_compatibility': '兼容性复核由在线裁决引擎现算；须在线',
    'lint_urdf': 'URDF lint 需本地文件系统+XML Schema，stdio 服务无该能力；须在线',
    'explain_compose_frontier': '组成前沿解释由在线 compose 引擎现算；须在线',
    'explain_evidence_cohort': '证据队列解释由在线判据现算；须在线',
    'explain_evidence_mdv': '证据多值解释由在线判据现算；须在线',
    'explain_connector_types': '连接器类型解释由在线判据现算；须在线',
    'get_research_progress': '研究进度由在线状态台账现算；须在线',
    'check_co_mount': '共装判定由在线共装引擎现算；须在线',
    'get_robot_tool_side': '机器人/工具侧判定由在线引擎现算；须在线',
    'get_behavior_evidence': '行为证据由在线判据现算；须在线',
    'get_body_binding': '机体绑定由在线判据现算；须在线',
}

NPM_ONLY = {
    # npm 有、hosted 无 —— 本地客户端专属助手，不依赖托管服务。
    'dialects_list': '方言清单为本地 dialects 模块能力，hosted 不暴露（20260909-24 审查：dialects 暂不接调用链）',
    'dialects_evaluate': '方言评估为本地 dialects 模块能力，hosted 不暴露',
    'export_bom': 'BOM 导出为本地生成器，hosted 走 HTTP 下载端点，不暴露为工具',
    'plan_assembly': '装配规划为本地生成器（bom/export），hosted 走 HTTP 端点，不暴露为工具',
    'preflight_check': '部署预检为本地 CLI 能力，hosted 无此概念',
}


def _extract_tools(path: str) -> set:
    """提取**工具定义**名（形态 `name: 'x',` 紧跟 `description:`/`inputSchema:`/`handler:`）。

    不用裸 `name: 'x'`：会误匹配 schema 键/夹具里的同名 key（如 mcp.js 里
    `text: 'keyword', name: 'keyword', kw: 'keyword'` 是夹具，不是工具）。
    """
    if not os.path.exists(path):
        return set()
    src = open(path, encoding='utf-8').read()
    return set(re.findall(
        r"name:\s*'([a-z_][a-z0-9_]*)',\s*\n\s*(?:description|inputSchema|handler)\s*:", src))


def main() -> int:
    hosted = _extract_tools(HOSTED)
    npm = _extract_tools(NPM)
    if not hosted:
        print('!! 从 functions/mcp.js 解析到 0 个工具名（解析失配，闸门失效）')
        return 1
    if not npm:
        print('!! 从 mcp-server/index.js 解析到 0 个工具名（解析失配，闸门失效）')
        return 1

    if '--list' in sys.argv:
        print('hosted (%d): %s' % (len(hosted), ', '.join(sorted(hosted))))
        print('npm    (%d): %s' % (len(npm), ', '.join(sorted(npm))))
        print('hosted-only (%d): %s' % (len(hosted - npm), ', '.join(sorted(hosted - npm))))
        print('npm-only    (%d): %s' % (len(npm - hosted), ', '.join(sorted(npm - hosted))))
        return 0

    errs = []

    # ① hosted - npm 必须 ⊆ HOSTED_ONLY
    unexpected_hosted = sorted(hosted - npm - set(HOSTED_ONLY))
    if unexpected_hosted:
        errs.append('hosted 有、npm 无 且未登记: %s（两面对等或登记 HOSTED_ONLY）'
                    % ', '.join(unexpected_hosted))

    # ② npm - hosted 必须 ⊆ NPM_ONLY
    unexpected_npm = sorted(npm - hosted - set(NPM_ONLY))
    if unexpected_npm:
        errs.append('npm 有、hosted 无 且未登记: %s（两面对等或登记 NPM_ONLY）'
                    % ', '.join(unexpected_npm))

    # ③ 清单含已不存在的工具（过期）
    stale_hosted = sorted(set(HOSTED_ONLY) - hosted)
    if stale_hosted:
        errs.append('HOSTED_ONLY 登记已不存在的工具: %s（清单过期，须删除）' % ', '.join(stale_hosted))
    stale_npm = sorted(set(NPM_ONLY) - npm)
    if stale_npm:
        errs.append('NPM_ONLY 登记已不存在的工具: %s（清单过期，须删除）' % ', '.join(stale_npm))

    # ④ 清单含已对等的工具（夸大）
    over_hosted = sorted(set(HOSTED_ONLY) & npm)
    if over_hosted:
        errs.append('HOSTED_ONLY 登记已对等的工具（npm 已暴露）: %s（清单夸大，须删除）'
                    % ', '.join(over_hosted))
    over_npm = sorted(set(NPM_ONLY) & hosted)
    if over_npm:
        errs.append('NPM_ONLY 登记已对等的工具（hosted 已暴露）: %s（清单夸大，须删除）'
                    % ', '.join(over_npm))

    if errs:
        print('MCP 工具集对等: FAIL')
        for e in errs:
            print('  ❌', e)
        return 1

    print('MCP 工具集对等: ✅ hosted=%d / npm=%d，意图分歧均已显式登记（hosted-only=%d, npm-only=%d）'
          % (len(hosted), len(npm), len(hosted - npm), len(npm - hosted)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
