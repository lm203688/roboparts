/**
 * MCP Server 端到端自检（模拟真实 npm 安装场景）
 *
 * 为什么需要它：包 tarball 里不含 ../api/*.json，而旧实现读不到就静默返空，
 * 于是「装上能启动、查什么都是 0 条」——从外部看毫无异常。
 * 本自检把包复制到一个没有 ../api 的临时目录再跑，专门复现那个场景。
 *
 * 用法：node selftest.mjs
 */
import { spawn } from 'child_process';
import { mkdtempSync, copyFileSync, mkdirSync, rmSync, existsSync, symlinkSync, readFileSync, unlinkSync } from 'fs';
import { tmpdir } from 'os';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

function stage() {
  const dir = mkdtempSync(join(tmpdir(), 'rp-mcp-'));
  const pkg = join(dir, 'pkg');
  mkdirSync(pkg);
  // 【20260918】此前这里硬编码 ['index.js', 'package.json']，与 package.json 的 files
  // 白名单各写各的：index.js 早已 `import './dialects.js'`，而 dialects.js 既没进白名单
  // 也没进沙箱 —— 结果**发出去的包一装就 ERR_MODULE_NOT_FOUND，自检却照绿**。
  // 现在把 files 白名单当唯一真相源，自检才真的等价于「npm 安装后的现场」。
  const manifest = JSON.parse(readFileSync(join(__dirname, 'package.json'), 'utf8'));
  for (const f of new Set(['package.json', ...(manifest.files || [])])) {
    const src = join(__dirname, f);
    if (existsSync(src)) copyFileSync(src, join(pkg, f));
  }
  // 依赖沿用本地 node_modules（ESM 不认 NODE_PATH，必须落在解析路径上），
  // 仅隔离「../api 不存在」这一个变量。
  symlinkSync(join(__dirname, 'node_modules'), join(pkg, 'node_modules'), 'junction');
  return { dir, pkg };
}

function rpc(id, method, params) {
  return JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n';
}

async function run() {
  const { dir, pkg } = stage();
  if (existsSync(join(pkg, '..', 'api'))) {
    throw new Error('隔离失败：临时目录里不该存在 ../api');
  }
  console.log('沙箱目录:', pkg, '（../api 不存在，等同 npm 安装后的现场）');

  const child = spawn(process.execPath, [join(pkg, 'index.js')], {
    cwd: pkg,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, NODE_PATH: join(__dirname, 'node_modules') }
  });

  let out = '', err = '';
  let exited = false, exitInfo = '';
  child.stdout.on('data', d => { out += d; });
  child.stderr.on('data', d => { err += d; });
  child.on('exit', (code, sig) => { exited = true; exitInfo = `code=${code} signal=${sig}`; });

  // 【20260805-23】原实现用固定 sleep(6s) 等预载完成，属于计时竞态而非判据：
  // 加上退避重试后启动可能超过 6s，闸门就会把「慢」误报成「坏」。
  // 本机实测同一份可用代码 3 次里失败 1 次 —— 一个会随机误报的闸门，
  // 比没有闸门更糟：它会训练人忽略红灯。改为等待真实就绪信号与 RPC 响应。
  async function waitFor(label, predicate, capMs) {
    const t0 = Date.now();
    while (Date.now() - t0 < capMs) {
      if (predicate()) return true;
      if (exited) throw new Error(`子进程在「${label}」期间退出（${exitInfo}）\n--- stderr ---\n${err}`);
      await new Promise(r => setTimeout(r, 200));
    }
    return false;
  }

  function replyOk(id) {
    return out.split('\n').some(line => {
      if (!line.trim().startsWith('{')) return false;
      try { const m = JSON.parse(line); return m.id === id && (m.result || m.error); }
      catch { return false; }
    });
  }

  child.stdin.write(rpc(1, 'initialize', {
    protocolVersion: '2024-11-05', capabilities: {},
    clientInfo: { name: 'selftest', version: '1.0.0' }
  }));

  // 就绪 = index.js 打出「已加载 N 条实体」。给足重试与慢网络的余量。
  const ready = await waitFor('预载数据', () => /已加载 \d+ 条实体/.test(err), 90000);
  if (!ready) console.log('⚠️  90s 内未见预载就绪信号，继续走判定以便暴露真实状态');

  child.stdin.write(rpc(2, 'tools/list', {}));
  await waitFor('tools/list 响应', () => replyOk(2), 30000);

  child.stdin.write(rpc(3, 'tools/call', {
    name: 'search_components',
    arguments: { category: 'actuators', keyword: '', limit: 3 }
  }));
  await waitFor('tools/call 响应', () => replyOk(3), 30000);
  child.kill();

  console.log('\n--- stderr ---\n' + (err.trim() || '(空)'));

  const loaded = /已加载 (\d+) 条实体/.exec(err);
  const toolsOk = out.includes('search_components');
  let hits = null;
  for (const line of out.split('\n')) {
    if (!line.trim().startsWith('{')) continue;
    try {
      const m = JSON.parse(line);
      if (m.id === 3 && m.result) {
        const txt = m.result.content?.[0]?.text || '';
        const j = JSON.parse(txt);
        hits = j.total_found ?? j.results?.length ?? null;
      }
    } catch { /* 非完整 JSON 行，跳过 */ }
  }

  const pass = loaded && Number(loaded[1]) > 0 && toolsOk && hits > 0;

  console.log('\n============ 判定 ============');
  console.log('1) 无 ../api 仍能加载数据 :', loaded ? `✅ ${loaded[1]} 条` : '❌ 未加载');
  console.log('2) 工具列表可用           :', toolsOk ? '✅' : '❌');
  console.log('3) 实际查询返回非空       :', hits ? `✅ ${hits} 条` : `❌ ${hits}`);
  console.log(pass ? '\n✅ 自检通过：可安全发布' : '\n❌ 自检失败：禁止发布');

  // 【20260918】收尾**绝不参与判定**：此前 rmSync 紧跟 child.kill() 直接跑，
  // Windows 下子进程未退 + node_modules 是 junction ⇒ EBUSY ⇒ 一个「判定已通过」
  // 的自检以异常退出，是典型假红（假红会训练人忽略红灯，比漏报更糟）。
  await killAndWait(child);
  cleanup(dir);
  process.exit(pass ? 0 : 1);
}

async function killAndWait(child) {
  if (child.exitCode === null && child.signalCode === null) child.kill();
  await new Promise(r => {
    if (child.exitCode !== null || child.signalCode !== null) return r();
    child.once('exit', r);
    setTimeout(r, 5000);
  });
}

function cleanup(dir) {
  // junction 必须先摘：unlink 只删链接本身，不会递归进真实 node_modules。
  const j = join(dir, 'pkg', 'node_modules');
  try { if (existsSync(j)) unlinkSync(j); } catch { /* 尽力而为 */ }
  try {
    rmSync(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 150 });
  } catch (e) {
    console.warn(`⚠️  临时目录清理失败（不影响判定）: ${e.code || e.message}`);
  }
}

run().catch(e => { console.error('自检异常:', e); process.exit(1); });
