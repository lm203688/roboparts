#!/usr/bin/env node
/**
 * push-gitdata-force-rewrite.mjs — 本地历史被 git filter-repo 等工具整体重写后，
 * 用 GitHub Git Data API 把**整条新历史**强制覆盖到远端。
 *
 * 与 push-gitdata.mjs 的区别：
 *  - 本脚本不做增量快进重放，而是从根提交开始逐条重放本地全部历史。
 *  - 收尾用 force=true 更新 ref（因本地与远端已无共同祖先）。
 *  - 支持断点续传：每成功创建一个远端提交后写入状态文件，网络中断可重跑。
 *  - 仅用于历史重写后的单次同步；日常推送仍用 push-gitdata.mjs。
 *
 * 用法：GITHUB_TOKEN=<token> node scripts/push-gitdata-force-rewrite.mjs [--dry-run] [--rewrite-acknowledged]
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const DRY = process.argv.includes('--dry-run');
const ACK = process.argv.includes('--rewrite-acknowledged');

function git(args, opts = {}) {
  return execFileSync('git', args, { maxBuffer: 1024 * 1024 * 256, ...opts });
}
function gitStr(args) {
  return git(args, { encoding: 'utf8' }).trim();
}

// ---------- 1. 解析仓库信息 ----------
const remoteUrl = gitStr(['remote', 'get-url', 'origin']);
const m = remoteUrl.match(/github\.com[/:]([^/]+)\/(.+?)(?:\.git)?$/);
if (!m) throw new Error(`无法从 remote 解析 owner/repo: ${remoteUrl}`);
const [, OWNER, REPO] = m;
const BRANCH = gitStr(['rev-parse', '--abbrev-ref', 'HEAD']);

// ---------- 2. 重写确认 ----------
const LEDGER_FILE = new URL('../ops/history_rewrite_ledger.json', import.meta.url);
let ledger = null;
try { ledger = JSON.parse(fs.readFileSync(LEDGER_FILE, 'utf8')); } catch {}
const pending = ledger?.events?.find((ev) => !ev.remote_synced_at) || null;
if (!pending) {
  console.log('未检测到待同步的历史重写事件，按普通 force-push 处理。');
} else {
  console.log(`检测到待同步重写事件：${pending.rewritten_at} 由 ${pending.tool} 执行`);
  console.log(`  旧 HEAD ${pending.old_head.slice(0, 8)} → 新 HEAD ${pending.new_head.slice(0, 8)}`);
}
if (pending && !ACK && !DRY) {
  throw new Error(
    '这是破坏性操作（公开仓整段历史将被替换）。\n'
    + '请确认后继续：node scripts/push-gitdata-force-rewrite.mjs --rewrite-acknowledged'
  );
}

// ---------- 3. 凭据 ----------
const TOKEN = process.env.GITHUB_TOKEN;
const OFFLINE_PLAN = !TOKEN && DRY;
if (!TOKEN && !DRY) throw new Error('未设置 GITHUB_TOKEN');

console.log(`repo=${OWNER}/${REPO} branch=${BRANCH} dry=${DRY} ack=${ACK}`);

// ---------- 4. API 封装（高重试 + 间隔） ----------
async function api(method, path, body, retries = 8) {
  for (let i = 0; i <= retries; i++) {
    try {
      // 每次请求前小间隔，降低连续 TLS 连接被重置的概率
      if (i === 0) await new Promise((r) => setTimeout(r, 300));
      const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'User-Agent': 'roboparts-gitdata-force-rewrite',
        },
        body: body ? JSON.stringify(body) : undefined,
        keepalive: false,
      });
      const text = await res.text();
      if (res.status >= 500 || res.status === 429) throw new Error(`${res.status}: ${text.slice(0, 200)}`);
      if (!res.ok) {
        const e = new Error(`GitHub API ${method} ${path} -> ${res.status}: ${text.slice(0, 400)}`);
        e.fatal = true;
        throw e;
      }
      return text ? JSON.parse(text) : null;
    } catch (e) {
      if (e.fatal || i === retries) throw e;
      const wait = 2500 * 2 ** i + Math.floor(Math.random() * 1000);
      console.log(`  ! ${e.message.slice(0, 120)} — ${wait}ms 后重试 (${i + 1}/${retries})`);
      await new Promise((r) => setTimeout(r, wait));
    }
  }
}

// ---------- 5. 列出待推送提交 ----------
const localSha = gitStr(['rev-parse', 'HEAD']);
const commits = gitStr(['rev-list', '--reverse', 'HEAD']).split('\n').filter(Boolean);
console.log(`本地 HEAD ${localSha.slice(0, 8)}，将从根重放 ${commits.length} 个提交`);

if (OFFLINE_PLAN) {
  const rootSha = gitStr(['rev-list', '--max-parents=0', 'HEAD']).split('\n')[0];
  const fileCount = gitStr(['ls-tree', '-r', '--name-only', 'HEAD']).split('\n').filter(Boolean).length;
  console.log('');
  console.log('===== 离线计划（未设置 GITHUB_TOKEN，全程没有联网）=====');
  console.log(`  目标仓库   ${OWNER}/${REPO}  分支 ${BRANCH}`);
  console.log(`  根提交     ${rootSha.slice(0, 8)}`);
  console.log(`  重放提交数 ${commits.length}`);
  console.log(`  HEAD 文件数 ${fileCount}（每个提交的变更 blob 会逐个 POST 上传）`);
  console.log(`  收尾动作   PATCH /git/refs/heads/${BRANCH} force=true —— 远端该分支历史将被整段替换`);
  console.log('');
  console.log('  ❔ 远端当前状态未核验（没有令牌就查不到远端 ref）。');
  console.log('     本次输出只说明「本地打算推什么」，不构成「推送可行」的结论。');
  console.log('     要真正预演请带令牌：GITHUB_TOKEN=<token> node scripts/push-gitdata-force-rewrite.mjs --dry-run');
  process.exit(0);
}

// 获取当前远端 ref（可能不存在）
let remoteSha = null;
try {
  const ref = await api('GET', `/git/refs/heads/${BRANCH}`);
  remoteSha = ref.object.sha;
  console.log(`远端 ${BRANCH} 当前 -> ${remoteSha.slice(0, 8)}（将被 force 覆盖）`);
} catch (e) {
  if (e.message.includes('404')) {
    console.log(`远端 ${BRANCH} 不存在，将新建 ref`);
  } else {
    throw e;
  }
}

// ---------- 6. 断点续传状态 ----------
const STATE_FILE = '.git/gitdata-force-rewrite-state.json';
let state = {
  localHeadSha: localSha,
  remoteShaBefore: remoteSha,
  commitMap: {},
  uploadedBlobs: {},
  lastProcessedLocalSha: null,
  parentSha: null,
  previousTreeSha: null,
};
let stateDirty = false;

function loadState() {
  try {
    const saved = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    if (saved.localHeadSha === localSha) {
      state = saved;
      console.log(`检测到断点状态，已从 ${state.lastProcessedLocalSha ? state.lastProcessedLocalSha.slice(0, 8) : '根提交前'} 重续`);
      return true;
    }
    console.log('断点状态与当前 HEAD 不一致，从头开始');
  } catch {}
  return false;
}

function saveState() {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2) + '\n');
  stateDirty = false;
}

if (!DRY) loadState();

let parentSha = state.parentSha;
let previousTreeSha = state.previousTreeSha;
const commitMap = new Map(Object.entries(state.commitMap));
const uploadedBlobs = new Set(Object.keys(state.uploadedBlobs || {}));

// ---------- 7. Blob 上传（带本地缓存 + 高重试） ----------
async function ensureBlobUploaded(sha, mode, path) {
  if (uploadedBlobs.has(sha)) {
    console.log(`    (blob ${sha.slice(0, 8)} 已在本轮/状态缓存中，跳过)`);
    return sha;
  }
  const buf = git(['cat-file', 'blob', sha]);
  // 大 blob 上传最容易被网络重置，单独拉高重试次数并加前置间隔
  await new Promise((r) => setTimeout(r, 80));
  const blob = await api('POST', '/git/blobs', {
    content: buf.toString('base64'),
    encoding: 'base64',
  }, 12);
  if (blob.sha !== sha) {
    throw new Error(`blob SHA 不一致：本地 ${sha.slice(0, 8)} != 远端 ${blob.sha.slice(0, 8)} (${path})`);
  }
  uploadedBlobs.add(sha);
  return blob.sha;
}

// ---------- 8. 逐提交重放 ----------
let skipped = 0;
let processed = 0;

for (const c of commits) {
  // 断点续传：已上传的提交跳过
  if (commitMap.has(c)) {
    skipped++;
    parentSha = commitMap.get(c);
    // 恢复 previousTreeSha：从本地提交取 tree，远端 tree 理论上与其相同
    previousTreeSha = gitStr(['rev-parse', `${c}^{tree}`]);
    continue;
  }

  const subject = gitStr(['log', '-1', '--format=%B', c]).trim();
  const raw = gitStr(['diff-tree', '--no-commit-id', '-r', '--root', '--no-renames', c]);

  const entries = [];
  for (const line of raw.split('\n').filter(Boolean)) {
    const mm = line.match(/^:(\d{6}) (\d{6}) [0-9a-f]{40} ([0-9a-f]{40}) ([A-Z])\d*\t(.+)$/);
    if (!mm) { console.log(`  ! 无法解析 diff 行，中止: ${line}`); process.exit(1); }
    const [, , newMode, newSha, status, pathRaw] = mm;
    const path = pathRaw.replace(/^"|"$/g, '');
    if (newMode === '160000') {
      // 子模块以 commit 类型进树，这样远端 tree SHA 才能与本地一致
      entries.push({ path, mode: '160000', type: 'commit', sha: newSha });
      console.log(`  S ${path} -> ${newSha.slice(0, 8)}`);
      continue;
    }

    if (status === 'D' || /^0+$/.test(newSha)) {
      entries.push({ path, mode: '100644', type: 'blob', sha: null });
      console.log(`  D ${path}`);
    } else if (DRY) {
      // --dry-run 必须真的不写远端。
      // 【20260811-12 修复】此前 blob 上传写在 `if (DRY)` 之前，带令牌预演会
      // 把每个变更 blob 都 POST 到用户仓库（虽是游离对象，仍是对远端的写入），
      // 与 _NEEDS_USER.md 里「先看清会推什么再决定给不给令牌」的承诺相悖。
      entries.push({ path, mode: newMode, type: 'blob', sha: newSha });
      console.log(`  ${status} ${path} （dry-run：未上传 blob）`);
    } else {
      const remoteBlobSha = await ensureBlobUploaded(newSha, newMode, path);
      entries.push({ path, mode: newMode, type: 'blob', sha: remoteBlobSha });
      console.log(`  ${status} ${path} -> ${remoteBlobSha.slice(0, 8)}`);
    }
  }

  if (!entries.length) {
    console.log(`  (空提交，跳过 ${c.slice(0, 8)})`);
    continue;
  }

  if (DRY) {
    console.log(`  [dry-run] 将提交: ${subject.split('\n')[0].slice(0, 60)}`);
    continue;
  }

  const treeBody = parentSha ? { base_tree: previousTreeSha, tree: entries } : { tree: entries };
  const tree = await api('POST', '/git/trees', treeBody);

  const commitBody = {
    message: subject,
    tree: tree.sha,
    parents: parentSha ? [parentSha] : [],
  };
  const commit = await api('POST', '/git/commits', commitBody);

  console.log(`  ✅ ${c.slice(0, 8)} -> ${commit.sha.slice(0, 8)}  ${subject.split('\n')[0].slice(0, 60)}`);

  // 完整性：重放后的 tree 必须与本地该提交的 tree 完全一致
  const localTree = gitStr(['rev-parse', `${c}^{tree}`]);
  if (tree.sha !== localTree) {
    throw new Error(`tree 不一致！本地 ${localTree} != 远端 ${tree.sha}（提交 ${c.slice(0, 8)}）`);
  }

  commitMap.set(c, commit.sha);
  parentSha = commit.sha;
  previousTreeSha = tree.sha;
  processed++;

  // 每成功一个提交就存状态，支持断点续传
  state.commitMap = Object.fromEntries(commitMap);
  state.uploadedBlobs = Object.fromEntries([...uploadedBlobs].map((s) => [s, true]));
  state.lastProcessedLocalSha = c;
  state.parentSha = parentSha;
  state.previousTreeSha = previousTreeSha;
  stateDirty = true;
  saveState();
}

console.log(`重放统计：已处理 ${processed} 个 / 跳过 ${skipped} 个 / 总计 ${commits.length} 个`);

if (DRY) {
  console.log('dry-run 结束：未实际修改远端');
  process.exit(0);
}

if (!parentSha) {
  throw new Error('没有产生任何远端提交');
}

// ---------- 8. 更新分支引用 ----------
if (remoteSha) {
  const upd = await api('PATCH', `/git/refs/heads/${BRANCH}`, { sha: parentSha, force: true });
  console.log(`ref 已 force 更新 -> ${upd.object.sha.slice(0, 8)}`);
} else {
  const upd = await api('POST', '/git/refs', { ref: `refs/heads/${BRANCH}`, sha: parentSha });
  console.log(`ref 已新建 -> ${upd.object.sha.slice(0, 8)}`);
}

// ---------- 9. 收尾校验 ----------
const finalTree = gitStr(['rev-parse', 'HEAD^{tree}']);
const remoteCommit = await api('GET', `/git/commits/${parentSha}`);
if (remoteCommit.tree.sha !== finalTree) {
  throw new Error(`最终 tree 不一致：本地 ${finalTree} != 远端 ${remoteCommit.tree.sha}`);
}
console.log(`✅ 校验通过：远端内容与本地 HEAD 完全一致 (tree ${finalTree.slice(0, 8)})`);

// ---------- 10. 更新台账 ----------
if (pending) {
  pending.remote_synced_at = new Date().toISOString();
  pending.remote_sha = parentSha;
  pending.local_sha = localSha;
  fs.writeFileSync(LEDGER_FILE, JSON.stringify(ledger, null, 2) + '\n');
  console.log(`📝 台账已更新：remote_synced_at = ${pending.remote_synced_at}`);
}

// ---------- 11. 清理状态文件 & 更新 remote-tracking ref ----------
try { fs.unlinkSync(STATE_FILE); } catch {}
try { git(['update-ref', `refs/remotes/origin/${BRANCH}`, localSha]); } catch (e) {
  console.log(`  (remote-tracking ref 未更新: ${String(e.message).slice(0, 80)})`);
}

console.log('DONE');
