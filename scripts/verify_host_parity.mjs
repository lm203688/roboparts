#!/usr/bin/env node
/**
 * verify_host_parity.mjs —— 「提交主机同源闸」
 *
 * 【为什么存在】2026-08-11 事故：百度站长验证的主机是 www.roboparts.cc，于是 promote.mjs
 * 把待推 URL 的主机统一改写成 www 再推送（这一步是对的，百度按主机精确匹配）。但没有任何
 * 环节验证过 www 这台主机到底在服务什么内容 —— 实测它 CNAME 指到 Pages 项目却**未注册为
 * 自定义域**，边缘把它路由到了一份三周前的旧站（RobotParts DB / robot.genetech.tools），
 * 且任意路径都返回 HTTP 200 + 同一页旧首页（软 404）。结果是 8-08/8-09/8-10 连续三天
 * 各 success:10，共 30 条 URL 被主动推给百度，抓回去的全是同一页旧首页。
 *
 * 教训：**「主机验证通过」只说明我们对这台主机有控制权，不说明这台主机在播我们的内容。**
 * 凡是要把 URL 主动提交给外部搜索引擎/目录的地方，提交前必须先证明该主机与本仓同源。
 *
 * 【判据】（全部以本仓文件为真相源，不写死字面量）
 *   1. GET https://<host>/            → 200 且 <title> 与本地 index.html 逐字一致
 *   2. GET https://<host>/<深链>       → 200 且 <title> 与该页本地文件一致，且 ≠ 首页 title
 *   3. GET https://<host>/<不存在路径>  → 必须 ≠ 200（软 404 检测：任意路径都 200 即判不同源）
 *
 * 用法：
 *   node scripts/verify_host_parity.mjs                # 校验 .env.local 的 BAIDU_SITE（缺省 roboparts.cc）
 *   node scripts/verify_host_parity.mjs www.roboparts.cc
 *   import { checkHostParity } from './verify_host_parity.mjs'
 * 退出码：0=同源；1=不同源；2=探测失败（网络层，不下同源结论）
 */
import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const UA = 'RoboPartsOps/1.0 (host-parity-check)';
const TIMEOUT_MS = 20000;

function localTitle(file) {
  const html = readFileSync(join(ROOT, file), 'utf8');
  const m = html.match(/<title>([\s\S]*?)<\/title>/i);
  return m ? m[1].trim() : null;
}

async function get(url) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: ctl.signal, redirect: 'follow' });
    const body = r.status === 200 ? await r.text() : '';
    return { status: r.status, body, finalUrl: r.url };
  } finally {
    clearTimeout(t);
  }
}

function titleOf(html) {
  const m = html.match(/<title>([\s\S]*?)<\/title>/i);
  return m ? m[1].trim() : null;
}

/**
 * @returns {{ok:boolean, host:string, reasons:string[], probes:object[], transportError:boolean}}
 */
export async function checkHostParity(hostRaw) {
  const host = String(hostRaw || '').replace(/^https?:\/\//, '').replace(/\/.*$/, '');
  const reasons = [];
  const probes = [];
  let transportError = false;

  const homeTitle = localTitle('index.html');
  const deepFile = 'bom-checker.html';
  const deepTitle = localTitle(deepFile);
  if (!homeTitle || !deepTitle) {
    return { ok: false, host, reasons: ['本地真相源缺 title（index.html / ' + deepFile + '）'], probes, transportError: true };
  }

  // 1) 首页同源
  try {
    const r = await get(`https://${host}/`);
    const t = titleOf(r.body);
    probes.push({ path: '/', status: r.status, title: t });
    if (r.status !== 200) reasons.push(`首页 HTTP ${r.status}（应 200）`);
    else if (t !== homeTitle) reasons.push(`首页 title 不同源：线上「${t}」≠ 本仓「${homeTitle}」`);
  } catch (e) {
    transportError = true;
    reasons.push(`首页探测失败（传输层）：${e.message}`);
  }

  // 2) 深链同源（/bom-checker 与 /bom-checker.html 任一命中即可）
  let deepOk = false;
  let deepSeen = null;
  for (const p of ['/bom-checker', '/bom-checker.html']) {
    try {
      const r = await get(`https://${host}${p}`);
      const t = titleOf(r.body);
      probes.push({ path: p, status: r.status, title: t });
      deepSeen = deepSeen || { status: r.status, title: t };
      if (r.status === 200 && t === deepTitle) { deepOk = true; break; }
    } catch (e) {
      transportError = true;
      probes.push({ path: p, error: e.message });
    }
  }
  if (!deepOk && !transportError) {
    reasons.push(`深链不同源：/bom-checker 线上「${deepSeen && deepSeen.title}」≠ 本仓「${deepTitle}」`);
    if (deepSeen && deepSeen.title === (probes[0] && probes[0].title)) {
      reasons.push('深链与首页返回同一页面 → 软 404（任意路径都回首页）');
    }
  }

  // 3) 软 404 闸：不存在的路径必须不是 200
  const nonce = '__rp_parity_' + Date.now().toString(36) + '_notexist';
  try {
    const r = await get(`https://${host}/${nonce}`);
    probes.push({ path: '/' + nonce, status: r.status, title: titleOf(r.body) });
    if (r.status === 200) reasons.push(`软 404：不存在路径 /${nonce} 返回 200（该主机把任意 URL 都当有效页）`);
  } catch (e) {
    transportError = true;
    probes.push({ path: '/' + nonce, error: e.message });
  }

  return { ok: reasons.length === 0, host, reasons, probes, transportError };
}

// CLI
if (import.meta.url === `file://${process.argv[1].replace(/\\/g, '/')}` || process.argv[1]?.endsWith('verify_host_parity.mjs')) {
  let host = process.argv[2];
  if (!host) {
    try {
      const raw = readFileSync(join(ROOT, '.env.local'), 'utf8');
      const m = raw.match(/^\s*BAIDU_SITE\s*=\s*(.+?)\s*$/m);
      host = m ? m[1] : 'roboparts.cc';
    } catch { host = 'roboparts.cc'; }
  }
  const res = await checkHostParity(host);
  console.log(`[主机同源闸] ${res.host} → ${res.ok ? '同源 PASS' : (res.transportError ? '探测失败 UNKNOWN' : '不同源 FAIL')}`);
  for (const p of res.probes) console.log(`   probe ${p.path} status=${p.status ?? '-'} title=${p.title ?? (p.error || '-')}`);
  for (const r of res.reasons) console.log(`   ✗ ${r}`);
  process.exit(res.ok ? 0 : (res.transportError ? 2 : 1));
}
