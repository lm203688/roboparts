#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2-6 MCP 双版本 + Trace 回放契约校验

审计报告 §4.4 要求：
  "MCP 要做双版本适配与可回放任务。工具输入输出全部引用 project_id +
   revision + evidence_version；长任务返回任务句柄、进度、可取消状态和
   最终结果；把'为什么 unknown''哪条证据导致冲突'作为标准工具；为每次
   外部 Agent 调用保存可去敏回放的评估轨迹。"

本脚本 4 条 check（离线）：
  1. schema_integrity  —— index.js 里 6 个新工具的定义 + trace.js 导出
  2. version_negotiation —— PROTOCOL_VERSIONS + CAPABILITIES_BY_VERSION
                            + experimental.roboparts 声明完整性
  3. trace_recording —— CallTool handler 每次调用自动 recordTrace + 挂
                       trace_id / evidence_version；元工具（trace_export
                       / start_long_task / trace_replay）本身也进 trace
  4. honest_boundary —— capabilities.experimental.roboparts.honest_limits
                       三条齐全（no_server_side_persistence /
                       no_hard_cancel / no_multi_tenant_isolation）

自证对照（--self-test）：
  - baseline：全绿
  - missing_tool：从 index.js 里删掉一个工具定义，schema_integrity 应红
  - missing_trace_hook：CallTool 里删掉 recordTrace 调用，trace_recording 应红
  - missing_honest_limit：honest_limits 少一条，honest_boundary 应红
  - missing_version：PROTOCOL_VERSIONS 只留一个版本，version_negotiation 应红
  - static_parser_bug：注释行 / 引号风格混用不引起假绿（防 2026-10-27 P2-3 教训）

运行：
  python scripts/verify_mcp_dual_version.py                    # 线上/仓库校验
  python scripts/verify_mcp_dual_version.py --self-test        # 阴阳自证
  python scripts/verify_mcp_dual_version.py --offline          # 离线模式
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MCP_INDEX = os.path.join(ROOT, 'mcp-server', 'index.js')
MCP_TRACE = os.path.join(ROOT, 'mcp-server', 'trace.js')
MCP_PKG = os.path.join(ROOT, 'mcp-server', 'package.json')
MCP_README = os.path.join(ROOT, 'mcp-server', 'README.md')
MCP_DOCS = os.path.join(ROOT, 'docs', 'mcp-tools.md')
MCP_HOSTED = os.path.join(ROOT, 'functions', 'mcp.js')

EXPECTED_VERSIONS = ['2024-11-05', '2025-03-26', '2025-11-25']
EXPECTED_NEW_TOOLS = [
    'explain_unknown',
    'start_long_task',
    'get_task_status',
    'cancel_task',
    'trace_export',
    'trace_replay',
]
EXPECTED_HONEST_LIMITS = [
    'no_server_side_persistence',
    'no_hard_cancel',
    'no_multi_tenant_isolation',
]
# hosted 端点专属边界（Cloudflare Workers 无跨请求持久化）
EXPECTED_HOSTED_EXTRA_LIMITS = [
    'no_trace_buffer_across_requests',
    'no_task_handles_across_requests',
]
EXPECTED_HOSTED_REAL_IMPL_TOOLS = [
    'explain_unknown',   # 读 entity map 现算
    'trace_replay',      # 处理当前请求内的 json_lines
]
EXPECTED_HOSTED_HINT_TOOLS = [
    'start_long_task',
    'get_task_status',
    'cancel_task',
    'trace_export',
]
EXPECTED_SERVER_VERSION = '1.2.0'
EXPECTED_TRACE_EXPORTS = [
    'PROTOCOL_VERSIONS',
    'CAPABILITIES_BY_VERSION',
    'toolAvailableAt',
    'filterToolsByVersion',
    'recordTrace',
    'exportTraces',
    'replayTrace',
    'redact',
    'startLongTask',
    'getTaskStatus',
    'cancelTask',
    'listTasks',
]

CHECKS = ['schema_integrity', 'version_negotiation', 'trace_recording', 'honest_boundary', 'hosted_sync']


def strip_comments(source: str) -> str:
    """逐行剥注释，防静态扫描被 // 或 /* */ 骗过（2026-10-27 P2-3 教训）。"""
    lines = source.splitlines()
    out = []
    in_block = False
    for line in lines:
        if in_block:
            m = re.search(r'\*/', line)
            if m:
                line = line[m.end():]
                in_block = False
            else:
                continue
        # 单行注释
        # 支持 'x' /* block */ 'y'
        # 简化：不处理字符串内的 //（本仓库源码没有这种极端场景）
        # 去掉行尾 // 注释
        # 找到不在字符串里的 //
        stripped = ''
        i = 0
        while i < len(line):
            c = line[i]
            if c == '/' and i + 1 < len(line) and line[i+1] == '/':
                break  # 单行注释
            if c == '/' and i + 1 < len(line) and line[i+1] == '*':
                in_block = True
                break
            if c in ('"', "'", '`'):
                quote = c
                stripped += c
                i += 1
                while i < len(line):
                    ch = line[i]
                    stripped += ch
                    if ch == '\\':
                        i += 1
                        if i < len(line):
                            stripped += line[i]
                        continue
                    if ch == quote:
                        i += 1
                        break
                    i += 1
                continue
            stripped += c
            i += 1
        out.append(stripped)
    return '\n'.join(out)


def find_tool_decl(name: str, source: str) -> bool:
    """在 ListTools handler 里查找工具定义。"""
    pattern = re.compile(
        r"name\s*:\s*['\"]" + re.escape(name) + r"['\"]",
    )
    return bool(pattern.search(source))


def find_case_dispatch(name: str, source: str) -> bool:
    """在 CallTool 分发里查找该工具的分发入口。

    hosted 端点（functions/mcp.js）用 `else if (name === 'xxx')` 链分发，
    stdio（mcp-server/index.js）用 switch-case。两者都必须识别，否则
    hosted 同步校验会出现「格式表达力」假红（工具已实现但校验不认）。
    同时保持对 switch-case 与 if/else-if 链的匹配，避免放宽成"只认字符串出现"。
    """
    patterns = [
        # switch-case: case 'name': / case name:
        re.compile(r"case\s+['\"]?" + re.escape(name) + r"['\"]?\s*:"),
        # if/else-if 链: (else )?if (name === 'name')
        re.compile(
            r"(?:else\s+)?if\s*\(\s*name\s*===\s*['\"]" +
            re.escape(name) + r"['\"]\s*\)"
        ),
    ]
    return any(p.search(source) for p in patterns)


def check_schema_integrity(index_src: str, trace_src: str, pkg: dict) -> dict:
    """6 个新工具的定义 + trace.js 导出 + 版本一致。"""
    clean_index = strip_comments(index_src)
    errors = []
    for tool in EXPECTED_NEW_TOOLS:
        if not find_tool_decl(tool, clean_index):
            errors.append(f"missing_tool_decl: {tool} 未在 ListTools 定义中")
        if not find_case_dispatch(tool, clean_index):
            errors.append(f"missing_case_dispatch: {tool} 未在 CallTool switch 中")

    # trace.js 必须导出所有符号
    for export_name in EXPECTED_TRACE_EXPORTS:
        if not re.search(rf"\bexport\s+(?:const|function)\s+{re.escape(export_name)}\b", trace_src):
            errors.append(f"missing_trace_export: {export_name}")

    # package.json 版本号必须匹配 index.js 的 PKG_VERSION
    idx_pkg = re.search(r"const\s+PKG_VERSION\s*=\s*['\"]([^'\"]+)['\"]", clean_index)
    if not idx_pkg:
        errors.append("missing_pkg_version_const: index.js 未定义 PKG_VERSION")
    elif pkg.get('version') != idx_pkg.group(1):
        errors.append(
            f"pkg_version_mismatch: package.json={pkg.get('version')} "
            f"vs index.js PKG_VERSION={idx_pkg.group(1)}"
        )

    # files 白名单必须包含 trace.js
    files_list = pkg.get('files', [])
    if 'trace.js' not in files_list:
        errors.append("missing_trace_js_in_files_whitelist: index.js 会 import trace.js，files 未列")

    return {'pass': len(errors) == 0, 'errors': errors, 'tools_checked': len(EXPECTED_NEW_TOOLS)}


def check_version_negotiation(index_src: str, trace_src: str) -> dict:
    """PROTOCOL_VERSIONS + CAPABILITIES_BY_VERSION + experimental.roboparts 完整性。"""
    errors = []
    clean_trace = strip_comments(trace_src)
    clean_index = strip_comments(index_src)

    # 明确解析 PROTOCOL_VERSIONS 数组，检查三个版本都在数组里（防字面量残留假绿）
    pv_match = re.search(
        r"export\s+const\s+PROTOCOL_VERSIONS\s*=\s*\[([^\]]+)\]",
        clean_trace
    )
    if not pv_match:
        errors.append("missing_protocol_versions_array: PROTOCOL_VERSIONS 未导出")
        protocol_versions_found = []
    else:
        pv_body = pv_match.group(1)
        protocol_versions_found = re.findall(r"['\"]([^'\"]+)['\"]", pv_body)
        for v in EXPECTED_VERSIONS:
            if v not in protocol_versions_found:
                errors.append(f"missing_protocol_version: {v}（实际: {protocol_versions_found}）")

    # CAPABILITIES_BY_VERSION 里必须至少列出 2024-11-05 与 2025-11-25 两个 key
    cbv_match = re.search(
        r"export\s+const\s+CAPABILITIES_BY_VERSION\s*=\s*\{",
        clean_trace
    )
    if not cbv_match:
        errors.append("missing_capabilities_by_version: CAPABILITIES_BY_VERSION 未导出")
    else:
        # 从 export const CAPABILITIES_BY_VERSION 开始扫描到下一个顶层 const 或 EOF
        tail = clean_trace[cbv_match.end():]
        next_export = re.search(r"\n\s*(?:export\s+const|/\*)", tail)
        cbv_block = tail[:next_export.start()] if next_export else tail
        for v_key in ['2024-11-05', '2025-11-25']:
            if not re.search(rf"['\"]{re.escape(v_key)}['\"]\s*:", cbv_block):
                errors.append(f"missing_capability_key: {v_key}")

    # index.js 必须 import trace.js 的所有新符号
    required_imports = ['PROTOCOL_VERSIONS', 'CAPABILITIES_BY_VERSION',
                        'toolAvailableAt', 'filterToolsByVersion',
                        'recordTrace', 'exportTraces', 'replayTrace',
                        'startLongTask', 'getTaskStatus', 'cancelTask']
    import_block_match = re.search(
        r"import\s*\{[^}]+\}\s*from\s*['\"]\./trace\.js['\"]",
        clean_index
    )
    if not import_block_match:
        errors.append("missing_trace_import: index.js 未 import ./trace.js")
    else:
        for imp in required_imports:
            if not re.search(rf"\b{re.escape(imp)}\b", import_block_match.group(0)):
                errors.append(f"missing_import: {imp}")

    # index.js 必须把 PROTOCOL_VERSIONS + CAPABILITIES_BY_VERSION 暴露到 experimental.roboparts
    if 'protocol_versions_supported' not in clean_index:
        errors.append("missing_experimental_field: protocol_versions_supported")
    if 'capabilities_by_version' not in clean_index:
        errors.append("missing_experimental_field: capabilities_by_version")

    # capabilities 结构里带 tasks
    if not re.search(r"tasks\s*:\s*\{", clean_index):
        errors.append("missing_tasks_capability: capabilities 未声明 tasks")

    return {
        'pass': len(errors) == 0,
        'errors': errors,
        'versions_declared': protocol_versions_found or [],
    }


def check_trace_recording(index_src: str) -> dict:
    """CallTool handler 必须自动 recordTrace + 挂 trace_id + evidence_version；
    元工具本身也进 trace。"""
    clean = strip_comments(index_src)
    errors = []

    # 1) 必须调用 recordTrace
    if not re.search(r"recordTrace\s*\(", clean):
        errors.append("missing_record_trace_call: CallTool handler 未调用 recordTrace")

    # 2) 必须挂 trace_id + evidence_version 到返回结果
    if 'result.trace_id' not in clean:
        errors.append("missing_trace_id_injection: 结果未挂 trace_id")
    if 'result.evidence_version' not in clean:
        errors.append("missing_evidence_version_injection: 结果未挂 evidence_version")

    # 3) recordTrace 调用里必须传 tool / args / result / evidence_version
    record_match = re.search(r"recordTrace\s*\(\s*\{([^}]+)\}", clean)
    if record_match:
        call_body = record_match.group(1)
        for field in ['tool', 'args', 'result', 'evidence_version']:
            if not re.search(rf"\b{re.escape(field)}\s*:", call_body):
                errors.append(f"missing_record_trace_field: {field}")
    else:
        # 可能是多行
        errors.append("record_trace_call_not_found: 未匹配到 recordTrace({...}) 调用")

    # 4) traceStart 计时起点必须存在（防假绿：duration_ms 硬编码）
    if 'traceStart' not in clean:
        errors.append("missing_traceStart: 缺少 traceStart 起点变量，duration_ms 无法计时")

    # 5) 元工具本身也进 trace：不能对 trace_export / start_long_task / trace_replay
    #    做 early return 跳过 recordTrace
    # 简化判据：recordTrace 调用在 switch 之后、return 之前，没有针对元工具的白名单跳过
    meta_skip_patterns = [
        r"if\s*\(\s*name\s*===\s*['\"]trace_export['\"]\s*\)[^{]*return",
        r"trace_export.*skip.*trace",
        r"TRACE_META_TOOLS.*includes\(name\)",
    ]
    for pat in meta_skip_patterns:
        if re.search(pat, clean):
            errors.append(f"meta_tool_trace_skip: 元工具被跳过 recordTrace（防假绿失败）")
            break

    return {'pass': len(errors) == 0, 'errors': errors}


def check_honest_boundary(index_src: str) -> dict:
    """capabilities.experimental.roboparts.honest_limits 三条齐全。"""
    clean = strip_comments(index_src)
    errors = []

    if 'honest_limits' not in clean:
        errors.append("missing_honest_limits: capabilities.experimental.roboparts 未声明 honest_limits")
        return {'pass': False, 'errors': errors}

    # 找到 honest_limits 数组的内容
    match = re.search(r"honest_limits\s*:\s*\[([^\]]+)\]", clean)
    if not match:
        errors.append("honest_limits_array_not_found: 未找到 honest_limits: [...] 结构")
        found = []
    else:
        arr_body = match.group(1)
        found = []
        for m in re.finditer(r"['\"]([^'\"]+)['\"]", arr_body):
            found.append(m.group(1))
        for expected in EXPECTED_HONEST_LIMITS:
            if expected not in found:
                errors.append(f"missing_honest_limit: {expected}（实际: {found}）")

    return {'pass': len(errors) == 0, 'errors': errors, 'found': found}


def check_hosted_sync(hosted_src: str) -> dict:
    """hosted 端点（functions/mcp.js）与 stdio 能力同步。

    审计报告 §4.4："保留旧客户端兼容层，新增协议版本协商，不做一次性破坏升级"。
    要求：线上 hosted 端点必须能看到新版本号 + 新工具 + 新边界声明，
    客户端才能感知能力升级。stdio 落地后 hosted 不同步 = 一半完成。
    """
    clean = strip_comments(hosted_src)
    errors = []

    # 1. SERVER_VERSION 必须升到 1.2.0（与 stdio 的 PKG_VERSION 一致）
    sv_match = re.search(r"const\s+SERVER_VERSION\s*=\s*['\"]([^'\"]+)['\"]", clean)
    if not sv_match:
        errors.append("missing_server_version: hosted 未声明 SERVER_VERSION")
    elif sv_match.group(1) != EXPECTED_SERVER_VERSION:
        errors.append(
            f"server_version_mismatch: hosted SERVER_VERSION={sv_match.group(1)} "
            f"≠ {EXPECTED_SERVER_VERSION}（stdio 已升，hosted 未同步）"
        )

    # 2. SUPPORTED_PROTOCOLS 数组必须含 2025-11-25
    sp_match = re.search(
        r"const\s+SUPPORTED_PROTOCOLS\s*=\s*\[([^\]]+)\]",
        clean
    )
    if not sp_match:
        errors.append("missing_supported_protocols: hosted 未声明 SUPPORTED_PROTOCOLS")
    else:
        sp_body = sp_match.group(1)
        found_versions = re.findall(r"['\"]([^'\"]+)['\"]", sp_body)
        if '2025-11-25' not in found_versions:
            errors.append(
                f"missing_2025_11_25: SUPPORTED_PROTOCOLS={found_versions} "
                f"未含 2025-11-25"
            )

    # 3. CAPABILITIES_BY_VERSION 常量必须存在
    if 'CAPABILITIES_BY_VERSION' not in clean:
        errors.append("missing_capabilities_by_version: hosted 未声明 CAPABILITIES_BY_VERSION")

    # 4. HOSTED_HONEST_LIMITS 常量必须存在 + 5 条齐全（stdio 3 + hosted 2）
    if 'HOSTED_HONEST_LIMITS' not in clean:
        errors.append("missing_hosted_honest_limits: hosted 未声明 HOSTED_HONEST_LIMITS")
    else:
        hh_match = re.search(r"HOSTED_HONEST_LIMITS\s*=\s*\[([^\]]+)\]", clean)
        if not hh_match:
            errors.append("hosted_honest_limits_array_not_found")
        else:
            hh_body = hh_match.group(1)
            hh_found = re.findall(r"['\"]([^'\"]+)['\"]", hh_body)
            all_expected = EXPECTED_HONEST_LIMITS + EXPECTED_HOSTED_EXTRA_LIMITS
            for e in all_expected:
                if e not in hh_found:
                    errors.append(f"missing_hosted_limit: {e}（实际: {hh_found}）")

    # 5. initialize 响应必须暴露 experimental.roboparts（含 protocol_versions_supported 等）
    if 'protocol_versions_supported' not in clean:
        errors.append("missing_experimental_field: protocol_versions_supported")
    if 'capabilities_by_version' not in clean:
        errors.append("missing_experimental_field: capabilities_by_version")

    # 6. TOOLS 数组必须含 6 个新工具
    for tool in EXPECTED_NEW_TOOLS:
        if not find_tool_decl(tool, clean):
            errors.append(f"missing_tool_decl_hosted: {tool}")

    # 7. 真实现工具必须调用真实实现函数（不能只是 honest_note 兜底）
    for tool in EXPECTED_HOSTED_REAL_IMPL_TOOLS:
        if not find_case_dispatch(tool, clean):
            errors.append(f"missing_dispatch_hosted: {tool}")
    # explain_unknown 必须真调用 toolExplainUnknown
    if not re.search(r"toolExplainUnknown\s*\(", clean):
        errors.append("missing_toolExplainUnknown_impl: 真实现函数未定义或未被调用")
    if not re.search(r"toolTraceReplayHosted\s*\(", clean):
        errors.append("missing_toolTraceReplayHosted_impl: 真实现函数未定义或未被调用")

    # 8. hint 工具必须返回 honest_note（防"过度声称"）
    for tool in EXPECTED_HOSTED_HINT_TOOLS:
        if not find_case_dispatch(tool, clean):
            errors.append(f"missing_dispatch_hosted: {tool}")
    # hosted_hint 分支必须至少 4 处出现 honest_note
    hint_count = len(re.findall(r"honest_note", clean))
    if hint_count < 4:
        errors.append(
            f"insufficient_honest_note: hosted 应有 ≥4 处 honest_note "
            f"（4 个 hint 工具各一处），实际 {hint_count} 处"
        )
    # hint 分支必须显式引导到 stdio
    if 'stdio_command' not in clean:
        errors.append("missing_stdio_redirect: hint 工具未引导到 stdio_command")

    return {'pass': len(errors) == 0, 'errors': errors}


def run_checks(index_src: str, trace_src: str, pkg: dict) -> dict:
    # P2-6 收口：hosted 端点（functions/mcp.js）与 stdio 能力同步。
    # 之前 run_checks 从未读取 MCP_HOSTED，也未调用 check_hosted_sync，
    # 导致 CHECKS 里的 'hosted_sync' 在 results['checks'] 中缺失 -> main() KeyError。
    # 这里补上读取与调用，使 hosted 同步校验真正生效。
    try:
        with open(MCP_HOSTED, encoding='utf-8') as f:
            hosted_src = f.read()
    except OSError:
        hosted_src = ''
    results = {
        'schema_integrity': check_schema_integrity(index_src, trace_src, pkg),
        'version_negotiation': check_version_negotiation(index_src, trace_src),
        'trace_recording': check_trace_recording(index_src),
        'honest_boundary': check_honest_boundary(index_src),
        'hosted_sync': check_hosted_sync(hosted_src),
    }
    all_pass = all(r['pass'] for r in results.values())
    return {'all_pass': all_pass, 'checks': results}


def self_test() -> int:
    """阴阳自证：baseline + 5 组变异。"""
    with open(MCP_INDEX, encoding='utf-8') as f:
        index_src = f.read()
    with open(MCP_TRACE, encoding='utf-8') as f:
        trace_src = f.read()
    with open(MCP_PKG, encoding='utf-8') as f:
        pkg = json.load(f)

    print('=== P2-6 自证对照 ===\n')

    # 0. baseline
    r = run_checks(index_src, trace_src, pkg)
    print(f"[baseline]        all_pass={r['all_pass']}")
    assert r['all_pass'], f"baseline 应全绿：{[k for k, v in r['checks'].items() if not v['pass']]}"

    # 1. missing_tool_decl
    mutated = re.sub(
        r"name\s*:\s*['\"]explain_unknown['\"]",
        "name: '__removed__'",
        index_src,
        count=1
    )
    if mutated == index_src:
        mutated = index_src.replace("'explain_unknown'", "'__removed__'", 1)
    r = run_checks(mutated, trace_src, pkg)
    print(f"[missing_tool]    schema_integrity.pass={r['checks']['schema_integrity']['pass']}")
    assert not r['checks']['schema_integrity']['pass'], "missing_tool 应红"

    # 2. missing_trace_hook
    mutated2 = index_src.replace('recordTrace(', 'XDISABLEDTX(', 1)
    r = run_checks(mutated2, trace_src, pkg)
    print(f"[no_trace_hook]   trace_recording.pass={r['checks']['trace_recording']['pass']}")
    assert not r['checks']['trace_recording']['pass'], "no_trace_hook 应红"

    # 3. missing_honest_limit
    mutated3 = index_src.replace("'no_hard_cancel'", "'no_hard_cancel__removed__'", 1)
    r = run_checks(mutated3, trace_src, pkg)
    print(f"[no_honest_limit] honest_boundary.pass={r['checks']['honest_boundary']['pass']}")
    assert not r['checks']['honest_boundary']['pass'], "no_honest_limit 应红"

    # 4. missing_version
    mutated4 = trace_src.replace("'2025-11-25'", "'__removed__'", 1)
    r = run_checks(index_src, mutated4, pkg)
    print(f"[no_version]      version_negotiation.pass={r['checks']['version_negotiation']['pass']}")
    assert not r['checks']['version_negotiation']['pass'], "no_version 应红"

    # 5. static_parser_bug: 引号风格混用
    #    把 explain_unknown 的引号从 ' 改成 "，静态扫描应仍能识别
    mutated5 = index_src.replace("'explain_unknown'", '"explain_unknown"', 1)
    r = run_checks(mutated5, trace_src, pkg)
    print(f"[quote_style]     schema_integrity.pass={r['checks']['schema_integrity']['pass']}")
    assert r['checks']['schema_integrity']['pass'], "quote_style 假绿防护：改引号后仍应识别"

    # 6. comment_masked_bug: 把工具声明写在注释里，静态扫描不应识别（防注释假绿）
    mutated6 = index_src.replace(
        "name: 'explain_unknown',",
        "// name: 'explain_unknown',",
        1
    )
    if mutated6 == index_src:
        mutated6 = index_src.replace(
            "      name: 'explain_unknown',",
            "      // name: 'explain_unknown',",
            1
        )
    r = run_checks(mutated6, trace_src, pkg)
    print(f"[comment_masked]  schema_integrity.pass={r['checks']['schema_integrity']['pass']}")
    assert not r['checks']['schema_integrity']['pass'], "comment_masked 应红：注释不能算声明"

    print('\n✅ 6/6 自证对照通过')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    print('=== P2-6 MCP 双版本 + Trace 契约校验 ===\n')

    for path, label in [(MCP_INDEX, 'index.js'), (MCP_TRACE, 'trace.js'), (MCP_PKG, 'package.json')]:
        if not os.path.exists(path):
            print(f'❌ 缺失 {label}: {path}')
            return 1

    with open(MCP_INDEX, encoding='utf-8') as f:
        index_src = f.read()
    with open(MCP_TRACE, encoding='utf-8') as f:
        trace_src = f.read()
    with open(MCP_PKG, encoding='utf-8') as f:
        pkg = json.load(f)

    results = run_checks(index_src, trace_src, pkg)

    for check_name in CHECKS:
        r = results['checks'][check_name]
        status = '✅' if r['pass'] else '❌'
        extra = ''
        if 'errors' in r and not r['pass']:
            extra = '\n  errors:\n    - ' + '\n    - '.join(r['errors'])
        print(f'{status} {check_name}{extra}')

    all_pass = results['all_pass']
    print(f'\n============ 判定 ============')
    print(f'Checks: {sum(1 for c in CHECKS if results["checks"][c]["pass"])} / {len(CHECKS)} 通过')
    print(f'结果: {"✅ 契约通过" if all_pass else "❌ 契约失败"}')
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
