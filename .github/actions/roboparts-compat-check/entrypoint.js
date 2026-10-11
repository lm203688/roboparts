#!/usr/bin/env node
/**
 * RoboParts Compatibility Check — GitHub Action 入口
 *
 * 定位：具身系统的「编译期类型检查器」。
 * 判定零件能否装配/共装/互换，输出可核验的三态结论。
 *
 * 使用外部 RoboParts API（roboparts.cc/api/bom/check、/api/co-mount、/api/urdf/lint），
 * 因此无需在 CI runner 上装任何依赖 —— 这是零成本触达所有开源机器人仓库的关键。
 *
 * 三态 fail-closed 语义：
 *   - compatible:      所有维度均兼容（正向证据链齐全）
 *   - incompatible:    至少一维度确认不兼容（明确证据链）
 *   - unknown:         证据不足（数据缺口，不是错误——是诚实的答案）
 *   - needs_review:    部分维度兼容、部分未声明
 *
 * strict=true 时 unknown 视为失败（默认 false，因为 unknown 是有效答案）。
 *
 * 2026-10-11 修复：
 *   1. import * as core/github（原写法把命名导出当单例解构，core 是 undefined，第一行就抛 TypeError）
 *   2. URDF 走 /api/urdf/lint，body 是 JSON {urdf_xml}（原走 /api/compatibility/validate + text/xml body，端点不接受 XML）
 *   3. BOM 改一次性 POST /api/bom/check（原走 N² 次串行 GET /api/compatibility，12 件即 66 请求）
 *   4. PR 评论用 getOctokit(GITHUB_TOKEN)，原直接 github.rest.issues 是错的（getOctokit 返回值才有 .rest）
 */
import * as core from '@actions/core';
import * as github from '@actions/github';
import * as fs from 'node:fs';

const API_BASE = (process.env.ROBOPARTS_API_BASE || 'https://roboparts.cc').replace(/\/$/, '');
const ctx = github.context;
// 关键修复：getOctokit 返回 Octokit 实例，.rest 挂在实例上，不在 github 模块上
const octokit = github.getOctokit(process.env.GITHUB_TOKEN || '');

const inputs = {
  mode: core.getInput('mode') || 'bom',
  bomPath: core.getInput('bom-path'),
  urdfPath: core.getInput('urdf-path'),
  hostId: core.getInput('host-id'),
  partA: core.getInput('part-a'),
  partB: core.getInput('part-b'),
  strict: core.getInput('strict') === 'true',
  failOnIncompatible: core.getInput('fail-on-incompatible') === 'true',
  commentOnPr: core.getInput('comment-on-pr') === 'true',
};

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: { 'Accept': 'application/json', ...(opts.headers || {}) },
  });
  const text = await res.text().catch(() => '');
  if (!res.ok) {
    throw new Error(`RoboParts API ${url} returned ${res.status}: ${text.slice(0, 500)}`);
  }
  try { return JSON.parse(text); }
  catch (e) { throw new Error(`RoboParts API ${url} 返回非 JSON：${text.slice(0, 200)}`); }
}

/**
 * BOM 模式：一次性 POST /api/bom/check。
 * 服务端已实现两两矩阵 + 可互换组 + 装配步骤 + 采购聚合，本地无需再重复算。
 * 输入 BOM JSON 支持三种形态：
 *   - { components: ["ACT-001", ...] }  —— 只给 ID 列表
 *   - { components: [{id, name, ...}] } —— ID + 附加字段
 *   - { parts: [...] } / 顶层数组       —— 兼容旧格式
 * 输出三态 counts + incompatible / unknown pairs + 服务端 summary 透传。
 */
async function runBomCheck() {
  const raw = fs.readFileSync(inputs.bomPath, 'utf-8');
  let bom;
  try { bom = JSON.parse(raw); } catch { throw new Error(`BOM 文件必须是合法 JSON: ${inputs.bomPath}`); }

  // 归一化 items：支持 components/parts/items 三种键 + 顶层数组
  let itemsRaw = bom.components || bom.parts || bom.items || bom;
  if (!Array.isArray(itemsRaw) || itemsRaw.length < 2) {
    throw new Error('BOM 至少需要 2 个零件（components/parts/items 数组）。');
  }

  // 归一化到 {id} 或 {protocol, interface, voltage, ros_support, name} 结构
  const items = itemsRaw.map((p, i) => {
    if (typeof p === 'string') return { id: p };
    if (p && typeof p === 'object' && p.id) return { ...p };
    return { id: `custom-${i}`, ...p };
  });

  const url = `${API_BASE}/api/bom/check`;
  const r = await fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  });

  // 从 matrix 里数三态：overall_compatible=true → compatible，false → incompatible，null → undecided(unknown)
  const matrix = r.matrix || [];
  const counts = {
    compatible: matrix.filter(m => m.overall_compatible === true).length,
    incompatible: matrix.filter(m => m.overall_compatible === false).length,
    unknown: matrix.filter(m => m.overall_compatible === null).length,
    needs_review: 0,
  };
  const incompatiblePairs = matrix.filter(m => m.overall_compatible === false).map(m => {
    const bad = m.dimensions.filter(d => d.compatible === false).map(d => d.dimension);
    return { a: m.a, b: m.b, blocked_by: bad, score: m.compatibility_score };
  });
  const unknownPairs = matrix.filter(m => m.overall_compatible === null).map(m => ({
    a: m.a, b: m.b, gap: 'insufficient_evidence_in_all_dimensions',
  }));

  return {
    counts,
    incompatiblePairs,
    unknownPairs,
    results: [
      { endpoint: '/api/bom/check', components: r.summary?.components, pairs: r.summary?.pairs, catalog_sources_ok: r.summary?.catalog_sources_ok },
    ],
    overall: deriveOverall(counts, inputs.strict),
    // 透传服务端元数据，便于 PR 评论展示装配步骤 / 采购建议
    server: {
      summary: r.summary,
      assembly_sequence_steps: r.assembly_sequence?.length || 0,
      assembly_notes: r.assembly_notes?.notes || r.assembly_notes,
      purchase_options: r.summary?.purchase_options || 0,
      catalog_sources_degraded: r.summary?.catalog_sources_degraded,
    },
  };
}

/**
 * URDF 模式：POST /api/urdf/lint，body 是 JSON {urdf_xml}（不接受 text/xml）。
 * lintUrdf 返回 {severity, robot_name, issues, summary, stats}，把 severity 映射成三态。
 */
async function runUrdfCheck() {
  const xml = fs.readFileSync(inputs.urdfPath, 'utf-8');
  const url = `${API_BASE}/api/urdf/lint`;
  const r = await fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urdf_xml: xml, check_level: 'all' }),
  });

  const issues = r.issues || [];
  const errors = issues.filter(i => i.severity === 'error');
  const warnings = issues.filter(i => i.severity === 'warning');

  // 三态映射：severity=error → incompatible；info/warning 无 error → compatible（带警告）；接口失败 → unknown
  const verdict = r.severity === 'error' ? 'incompatible' : (r.severity === 'warning' ? 'needs_review' : 'compatible');
  return {
    counts: { compatible: verdict === 'compatible' ? 1 : 0, incompatible: verdict === 'incompatible' ? 1 : 0, unknown: 0, needs_review: verdict === 'needs_review' ? 1 : 0 },
    incompatiblePairs: errors.map(e => ({ file: inputs.urdfPath, code: e.code, reason: e.message || e.message_zh || JSON.stringify(e) })),
    unknownPairs: [],
    results: [{ urdf: inputs.urdfPath, severity: r.severity, robot_name: r.robot_name, errors: errors.length, warnings: warnings.length, summary: r.summary, stats: r.stats }],
    overall: verdict,
    lint_issues: issues,
  };
}

/**
 * Compose 模式：共装查询。三段关系 A↔宿主↔B 走 /api/co-mount。
 * 返回四态：mountable / port_exhausted / type_error / unknown（诚实边界）。
 */
async function runCoMountCheck() {
  if (!inputs.hostId || !inputs.partA || !inputs.partB) {
    throw new Error('mode=compose 需要 host-id / part-a / part-b 三个输入。');
  }
  const url = `${API_BASE}/api/co-mount?host=${encodeURIComponent(inputs.hostId)}&a=${encodeURIComponent(inputs.partA)}&b=${encodeURIComponent(inputs.partB)}`;
  const r = await fetchJson(url);
  const verdict = r.verdict || 'unknown';
  // co-mount 的四态归一到三态视图：mountable→compatible；port_exhausted/type_error→incompatible；unknown→unknown
  const normalized = verdict === 'mountable' ? 'compatible' : (verdict === 'unknown' ? 'unknown' : 'incompatible');
  return {
    counts: { [normalized]: 1 },
    incompatiblePairs: verdict === 'port_exhausted' || verdict === 'type_error'
      ? [{ host: inputs.hostId, a: inputs.partA, b: inputs.partB, reason: r.reason, verdict }]
      : [],
    unknownPairs: verdict === 'unknown'
      ? [{ host: inputs.hostId, a: inputs.partA, b: inputs.partB, gap: r.gap_reason || 'insufficient_evidence' }]
      : [],
    results: [{ host: inputs.hostId, a: inputs.partA, b: inputs.partB, verdict, evidence: r.evidence || [] }],
    overall: normalized,
    co_mount_verdict: verdict,
  };
}

function deriveOverall(counts, strict) {
  if (counts.incompatible > 0) return 'incompatible';
  if (strict && counts.unknown > 0) return 'unknown';
  if (counts.compatible === 0 && counts.needs_review === 0) return 'unknown';
  if (counts.needs_review > 0) return 'needs_review';
  return 'compatible';
}

async function postPrComment(markdown) {
  if (!inputs.commentOnPr) return;
  const { owner, repo, pull_request } = ctx;
  if (!pull_request) {
    core.info('非 PR 上下文，跳过评论。');
    return;
  }
  try {
    await octokit.rest.issues.createComment({
      owner, repo,
      issue_number: pull_request.number,
      body: markdown,
    });
    core.info(`已发布 PR 评论 (#${pull_request.number})。`);
  } catch (e) {
    core.warning(`PR 评论失败：${e.message}`);
  }
}

function renderComment(out) {
  const { overall, counts, incompatiblePairs, unknownPairs, results, server, lint_issues, co_mount_verdict } = out;
  const emoji = { compatible: '✅', incompatible: '❌', unknown: '🤷', needs_review: '⚠️' }[overall] || '🔎';
  const lines = [
    `## ${emoji} RoboParts 组合校验结果：\`${overall}\``,
    '',
    `**三态裁决**：compatible=${counts.compatible || 0} · incompatible=${counts.incompatible || 0} · unknown=${counts.unknown || 0} · needs_review=${counts.needs_review || 0}`,
    '',
    '> 三态 fail-closed 语义：unknown 是**有效答案**（证据缺口），不是错误——RoboParts 公开登记答不出来的部分。',
    '> 我们不卖零件，所以没有理由骗你选一个。详见 https://roboparts.cc 。',
  ];

  // BOM 服务端摘要
  if (server && server.summary) {
    const s = server.summary;
    lines.push('', `**服务端统计**：${s.components} 组件 · ${s.pairs} 配对 · ${s.interchangeable_groups || 0} 可互换组 · ${s.purchase_options || 0} 采购渠道 · 目录源 ${s.catalog_sources_ok || '?'}`);
    if (server.assembly_sequence_steps) lines.push(`装配步骤：${server.assembly_sequence_steps} 步`);
    if (s.catalog_sources_degraded && s.catalog_sources_degraded.length) {
      lines.push('', `⚠️ 目录源降级：${s.catalog_sources_degraded.map(x => `${x.source}: ${x.reason}`).join(' · ')}`);
    }
  }

  // URDF lint 结果
  if (lint_issues && lint_issues.length) {
    const errs = lint_issues.filter(i => i.severity === 'error');
    const warns = lint_issues.filter(i => i.severity === 'warning');
    if (errs.length) lines.push('', `### ❌ URDF errors (${errs.length})`, '', '```json', JSON.stringify(errs.slice(0, 20), null, 2), '```');
    if (warns.length) lines.push('', `### ⚠️ URDF warnings (${warns.length})`, '', '```json', JSON.stringify(warns.slice(0, 10), null, 2), '```');
  }

  // co-mount 四态
  if (co_mount_verdict) {
    lines.push('', `**共装语义**：\`${co_mount_verdict}\``);
  }

  if (incompatiblePairs.length) {
    lines.push('', '### 不兼容配对', '', '```json', JSON.stringify(incompatiblePairs.slice(0, 15), null, 2), '```');
  }
  if (unknownPairs.length) {
    lines.push('', '### 证据缺口（unknown）', '', '```json', JSON.stringify(unknownPairs.slice(0, 15), null, 2), '```');
  }
  return lines.join('\n');
}

// ── 主流程 ──
try {
  let out;
  if (inputs.mode === 'bom') out = await runBomCheck();
  else if (inputs.mode === 'urdf') out = await runUrdfCheck();
  else if (inputs.mode === 'compose') out = await runCoMountCheck();
  else throw new Error(`未知 mode: ${inputs.mode}（支持 bom / urdf / compose）`);

  core.setOutput('verdict', out.overall);
  core.setOutput('verdict_counts', JSON.stringify(out.counts));
  core.setOutput('incompatible_pairs', JSON.stringify(out.incompatiblePairs));
  core.setOutput('unknown_pairs', JSON.stringify(out.unknownPairs));

  await postPrComment(renderComment(out));

  const failed = (inputs.failOnIncompatible && out.incompatiblePairs.length > 0)
    || (inputs.strict && out.overall === 'unknown');
  if (failed) {
    core.setFailed(`RoboParts 判定为 ${out.overall}（strict=${inputs.strict}, failOnIncompatible=${inputs.failOnIncompatible}）`);
  } else {
    core.info(`RoboParts 判定：${out.overall}`);
  }
} catch (e) {
  core.setFailed(e.message);
  await postPrComment(`❌ **RoboParts 组合校验失败**\n\n\`\`\`\n${e.message}\n\`\`\`\n\n查看文档：https://roboparts.cc/mcp-guide`);
}
