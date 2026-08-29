#!/usr/bin/env node
/**
 * push-gitdata-clean.mjs — 干净强推：把本地 6d48fc1..HEAD 这一正确支线，作为一条全新
 * 的、内容正确的链重放到远端 main。用于「远端历史与本地发散、无合法 graft 基点」的情况
 * （push-gitdata.mjs 的增量重放会因此产生错误 tree）。
 *
 * 做法：
 *  1. 以 LOCAL_BASE(6d48fc1) 的 tree 创建一个 ROOT 提交（远端新历史的起点）；
 *  2. 依次重放 6d48fc1..HEAD 的每个本地提交（base_tree 增量叠加，tree 必然 == 本地）；
 *  3. force PATCH refs/heads/main 到最终 sha；
 *  4. 校验远端最终 tree == 本地 HEAD tree；
 *  5. 写 gitdata-push-state.json（remote->local 映射）。
 *
 * 安全性：每个重放提交的 tree 都即时与本地该提交 tree 比对，不一致立即 throw，
 * 不会把错误内容落到 main。最终还有一道 tree 一致性闸。
 *
 * 用法： GITHUB_TOKEN=xxx node scripts/push-gitdata-clean.mjs
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const TOKEN = process.env.GITHUB_TOKEN;   // 仅在写模式校验；--dry-run 不需要凭据
if (!process.argv.includes('--dry-run') && !TOKEN) throw new Error('未设置 GITHUB_TOKEN');

const OWNER = 'lm203688';
const REPO = 'roboparts';
const BRANCH = 'main';
const LOCAL_BASE = '6d48fc1b391fc90fb2ce0c0fff32458af2599a6c'; // 与远端发散前的共同祖先

function git(args, opts = {}) {
  return execFileSync('git', args, { maxBuffer: 1024 * 1024 * 256, ...opts });
}
function gitStr(args) {
  return git(args, { encoding: 'utf8' }).trim();
}

/**
 * git 的路径引用：quotePath=false 时非 ASCII 原样输出，但仍可能用双引号包住
 * 含 " 或 \ 的路径，此时内部是 C 风格转义（\" \\）。JSON 字符串语法规则相同，
 * 故先按 JSON 解，失败再退化为裸去引号。
 */
function unquotePath(s) {
  if (s.length >= 2 && s[0] === '"' && s[s.length - 1] === '"') {
    try { return JSON.parse(s); } catch (_) { return s.slice(1, -1); }
  }
  return s;
}

async function api(method, path, body, retries = 4) {
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'User-Agent': 'roboparts-clean-push',
        },
        body: body ? JSON.stringify(body) : undefined,
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
      const wait = 1500 * 2 ** i;
      console.log(`  ! ${e.message.slice(0, 120)} — ${wait}ms 后重试`);
      await new Promise((r) => setTimeout(r, wait));
    }
  }
}

const BASE_TREE = gitStr(['rev-parse', `${LOCAL_BASE}^{tree}`]);
const localSha = gitStr(['rev-parse', 'HEAD']);
console.log(`base tree(local ${LOCAL_BASE.slice(0, 8)}) = ${BASE_TREE.slice(0, 8)}`);
console.log(`local HEAD = ${localSha.slice(0, 8)}`);

// 0. --dry-run：只在校验「路径解码 + blob sha」，不发任何写请求。
//    重放本身是 git 恒等式，唯一会出错的是路径解码与 blob 内容。
//    预检把这两件事在零 API 成本下先验一遍——2026-08-29 首次重放在第 6 个提交
//    才由 tree 闸发现 octal 转义未解码，代价是 4 分钟 + 一次失败。
const commitsAll = gitStr(['rev-list', '--reverse', `${LOCAL_BASE}..HEAD`]).split('\n').filter(Boolean);
if (process.argv.includes('--dry-run')) {
  let bad = 0;
  let checked = 0;
  for (const c of commitsAll) {
    const listing = new Map(
      gitStr(['-c', 'core.quotePath=false', 'ls-tree', '-r', '-z', c])
        .split('\u0000')
        .filter(Boolean)
        .map((l) => {
          const i = l.indexOf('\t');
          const sha = l.slice(0, i).split(' ')[2];
          return [l.slice(i + 1), sha];
        })
    );
    const raw = gitStr(['-c', 'core.quotePath=false', 'diff-tree',
                        '--no-commit-id', '-r', '--root', '--no-renames', c]);
    for (const line of raw.split('\n').filter(Boolean)) {
      const mm = line.match(/^:(\d{6}) (\d{6}) [0-9a-f]+ ([0-9a-f]+) ([A-Z])\d*\t(.+)$/);
      if (!mm) { console.log(`  ✗ 无法解析 diff 行: ${line}`); bad++; continue; }
      // 组序与主循环一致：1=旧mode 2=新mode 3=新sha 4=状态 5=路径
      // （RegexMatchArray 下标 0 是整串，多跳一个会取错，2026-08-29 dry-run 首跑踩到此坑）
      const [, , , newSha, , pathRaw] = mm;
      const path = unquotePath(pathRaw);
      checked++;
      const inTree = listing.has(path);
      if (/^0+$/.test(newSha)) {
        if (inTree) { console.log(`  ✗ ${c.slice(0, 8)} 删除项仍在树中: ${path}`); bad++; }
      } else if (listing.get(path) !== newSha) {
        console.log(`  ✗ ${c.slice(0, 8)} 路径/内容对不上: ${path}`
          + `（期望 ${newSha.slice(0, 8)}，树中 ${String(listing.get(path)).slice(0, 8)}）`);
        bad++;
      }
    }
  }
  console.log(`dry-run: 校验 ${checked} 条路径，异常 ${bad} 条`);
  if (bad) { console.log('✗ 预检失败，未发送任何写请求'); process.exit(1); }

  console.log('✅ 预检通过：路径解码与 blob sha 全部对齐，未发送任何写请求');
  process.exit(0);
}

// 1. ROOT 提交（远端新历史起点）
const rootCommit = await api('POST', '/git/commits', {
  message: 'chore: rebuild history (clean force-push of local main line)',
  tree: BASE_TREE,
  parents: [],
});
console.log(`✔ root commit ${rootCommit.sha.slice(0, 8)} (tree ${BASE_TREE.slice(0, 8)})`);
let parentSha = rootCommit.sha;
let baseTree = BASE_TREE;

// 2. 重放 6d48fc1..HEAD
const commits = gitStr(['rev-list', '--reverse', `${LOCAL_BASE}..HEAD`]).split('\n').filter(Boolean);
console.log(`待重放 ${commits.length} 个提交`);

for (const c of commits) {
  const subject = gitStr(['log', '-1', '--format=%B', c]).trim();
  // core.quotePath=false 是必须的：默认值下 git 会把非 ASCII 路径输出成
  // octal 转义（"RoboParts-\344\272\247…"），只去引号不解码会把字面 \344 当路径上传，
  // 造出错误 tree —— 2026-08-29 首次重放到含中文命名文件的提交时就栽在这里。
  const raw = gitStr(['-c', 'core.quotePath=false', 'diff-tree',
                      '--no-commit-id', '-r', '--root', '--no-renames', c]);
  const entries = [];
  for (const line of raw.split('\n').filter(Boolean)) {
    const mm = line.match(/^:(\d{6}) (\d{6}) [0-9a-f]+ ([0-9a-f]+) ([A-Z])\d*\t(.+)$/);
    if (!mm) { console.log(`  ! 无法解析 diff 行，中止: ${line}`); process.exit(1); }
    const [, , newMode, newSha, status, pathRaw] = mm;
    const path = unquotePath(pathRaw);
    if (newMode === '160000') { console.log(`  - 跳过子模块 ${path}`); continue; }
    if (status === 'D' || /^0+$/.test(newSha)) {
      entries.push({ path, mode: '100644', type: 'blob', sha: null });
      console.log(`  D ${path}`);
    } else {
      const buf = git(['cat-file', 'blob', newSha]);
      const blob = await api('POST', '/git/blobs', { content: buf.toString('base64'), encoding: 'base64' });
      entries.push({ path, mode: newMode, type: 'blob', sha: blob.sha });
    }
  }
  if (!entries.length) { console.log(`  (空提交，跳过 ${c.slice(0, 8)})`); continue; }

  const tree = await api('POST', '/git/trees', { base_tree: baseTree, tree: entries });
  const localTree = gitStr(['rev-parse', `${c}^{tree}`]);
  if (tree.sha !== localTree) {
    throw new Error(`tree 不一致！本地 ${localTree} != 远端 ${tree.sha}（提交 ${c.slice(0, 8)}）`);
  }
  const commit = await api('POST', '/git/commits', { message: subject, tree: tree.sha, parents: [parentSha] });
  console.log(`  ✅ ${c.slice(0, 8)} -> ${commit.sha.slice(0, 8)}  ${subject.split('\n')[0].slice(0, 60)}`);
  parentSha = commit.sha;
  baseTree = tree.sha;
}

// 3. force 更新 main
const upd = await api('PATCH', `/git/refs/heads/${BRANCH}`, { sha: parentSha, force: true });
console.log(`ref 已更新 -> ${upd.object.sha.slice(0, 8)}`);

// 4. 终态校验
const finalTree = gitStr(['rev-parse', 'HEAD^{tree}']);
const remoteCommit = await api('GET', `/git/commits/${upd.object.sha}`);
if (remoteCommit.tree.sha !== finalTree) {
  throw new Error(`最终 tree 不一致：本地 ${finalTree} != 远端 ${remoteCommit.tree.sha}`);
}
console.log(`✅ 校验通过：远端内容与本地 HEAD 完全一致 (tree ${finalTree.slice(0, 8)})`);

// 5. 写状态映射
const STATE_FILE = `${gitStr(['rev-parse', '--git-dir'])}/gitdata-push-state.json`;
fs.writeFileSync(STATE_FILE, JSON.stringify(
  { remote: upd.object.sha, local: localSha, tree: finalTree, at: new Date().toISOString() }, null, 2));
try { git(['update-ref', `refs/remotes/origin/${BRANCH}`, localSha]); } catch (e) {
  console.log(`  (remote-tracking ref 未更新: ${String(e.message).slice(0, 80)})`);
}
console.log('DONE');
