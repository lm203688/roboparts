#!/usr/bin/env node
/**
 * 机械声明证据契约 · JS 侧消费者（单一真相源 = scripts/mech_evidence_contract.json）
 *
 * 为什么要有这个文件：
 *   20260915 审计发现贡献层与主库各有一套 implicit 判据 —— 主库 L1.78 要求
 *   「白名单主机名 + 表内 ISO 编码」，而 build_flywheel_layer.mjs 的 fromBom()
 *   只校验 source_url 非空（'Universal Robots' 这种非 URL 字符串也放行）。
 *   判据分叉 = 同一条数据在主库被拒、在贡献层被收，P0 数字就成了两套口径拼出来的。
 *   现把判据收敛为「一个 JSON + 一个 JS 模块」，主库读 JSON、贡献层 import 本模块，
 *   再由回归 L1.79 用行为探针证明两者一致。
 *
 * 本模块只做判定，不产生数据 —— 无出处即不采信（fail-closed），绝不代为编造。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const CONTRACT_PATH = path.join(HERE, 'mech_evidence_contract.json');

/** 读取证据契约。缺失或结构不合法时**抛出**（而非静默降级为空判据 = 全放行）。 */
export function loadContract(p = CONTRACT_PATH) {
  const raw = fs.readFileSync(p, 'utf8');
  const c = JSON.parse(raw);
  if (!Array.isArray(c.source_hosts) || c.source_hosts.length === 0) {
    throw new Error('证据契约缺 source_hosts（空表 = 判据全放行，比没有更危险）');
  }
  if (!c.std_token_evidence || typeof c.std_token_evidence !== 'object'
      || Object.keys(c.std_token_evidence).length === 0) {
    throw new Error('证据契约缺 std_token_evidence（空表 = 任意 ISO 编码可自造）');
  }
  return c;
}

/** 主机名是否落在厂商官域白名单（含子域）。 */
export function hostAllowed(url, hosts) {
  const m = /^https:\/\/([^/]+)\//i.exec(String(url || ''));
  if (!m) return false;                      // 非 https 深链一律不算
  const host = m[1].toLowerCase();
  return hosts.some((h) => host === String(h).toLowerCase()
    || host.endsWith('.' + String(h).toLowerCase()));
}

/**
 * 判定一条 mechanical_interface 是否够格声明为 declared。
 * @returns {{ok: boolean, violations: string[]}}
 */
export function validateDeclared(item, contract = loadContract()) {
  const violations = [];
  const mi = (item && item.mechanical_interface) || {};
  const url = String(item && item.source_url || '');

  if (!url) {
    violations.push('缺 source_url（无出处 = 凭空断言）');
  } else if (!hostAllowed(url, contract.source_hosts)) {
    violations.push('出处主机名不在白名单: ' + JSON.stringify(url));
  }

  const std = mi.standard == null ? []
    : (Array.isArray(mi.standard) ? mi.standard : [mi.standard]);
  const hasFlange = !!(mi.flange && (typeof mi.flange !== 'string' || mi.flange.trim()));
  if (std.length === 0 && !hasFlange) {
    violations.push('既无 standard 也无 flange（标签绿、内容空）');
  }
  for (const tok of std) {
    const t = String(tok);
    if (t.toUpperCase().startsWith('ISO 9409-1') && !(t in contract.std_token_evidence)) {
      violations.push('自造/未挂出处的 ISO 编码: ' + t);
    }
  }
  return { ok: violations.length === 0, violations };
}

// 允许直接 CLI 自测：node scripts/mech_evidence.mjs --selftest
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
    && process.argv.includes('--selftest')) {
  const c = loadContract();
  const cases = [
    [{ id: 'A', source_url: 'Universal Robots', mechanical_interface: { standard: 'ISO 9409-1-50-4-M6' } }, false],
    [{ id: 'B', source_url: 'https://mimrobotic.com/news/1', mechanical_interface: { standard: 'ISO 9409-1-50-4-M6' } }, false],
    [{ id: 'C', source_url: 'https://assets.robotiq.com/a.pdf', mechanical_interface: { standard: 'ISO 9409-1-56-8-M4' } }, false],
    [{ id: 'D', source_url: 'https://assets.robotiq.com/a.pdf', mechanical_interface: { standard: 'ISO 9409-1-50-4-M6' } }, true],
    [{ id: 'E', source_url: 'https://schunk.com/konfigurator-elg', mechanical_interface: { standard: 'ISO 9409-1-160-11-M12' } }, true],
    [{ id: 'F', source_url: 'https://schunk.com/x', mechanical_interface: { standard: 'ISO 9409-1-200-6-M12' } }, false],
  ];
  let pass = 0, nReject = 0, nAccept = 0;
  for (const [item, want] of cases) {
    const got = validateDeclared(item, c).ok;
    const ok = got === want;
    if (ok) pass++;
    if (want) nAccept++; else nReject++;
    console.log(`  ${ok ? 'OK ' : 'BAD'} ${item.id} expect=${want} got=${got}`);
  }
  // 机读行刻意用纯 ASCII：本行会被 Python 回归闸门按串解析，
  // 带 emoji/中文会在 Windows 默认编码下被搞坏，导致"看起来跑了其实没判"。
  console.log(`SELFTEST total=${cases.length} pass=${pass} fail=${cases.length - pass} `
    + `rejected_cases=${nReject} accepted_cases=${nAccept}`);
  console.log(`CONTRACT hosts=${c.source_hosts.length} tokens=${Object.keys(c.std_token_evidence).length}`);
  process.exit(pass === cases.length ? 0 : 1);
}
