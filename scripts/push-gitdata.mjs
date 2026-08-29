#!/usr/bin/env node
/**
 * push-gitdata.mjs — 当 git wire protocol 被墙时，用 GitHub Git Data API 推送提交。
 *
 * 适用：`git push` 报 "Recv failure: Connection was reset" / DNS 失败，
 *       但 api.github.com 可达（curl https://api.github.com/ = 200）。
 *
 * 特性：
 *  - 自动从 git remote 解析 owner/repo/branch，无需手改常量
 *  - 自动从 git credential store 取 token（也可用 GITHUB_TOKEN 覆盖）
 *  - **逐个重放** remote..HEAD 的每个提交（保留提交历史与各自 message）
 *  - 文件内容从**该提交对象**读取（不是工作区）—— 多提交重放的正确性前提
 *  - 支持新增/修改/删除、可执行位、子模块跳过、二进制安全
 *  - 收尾校验：远端最终 tree SHA 必须 == 本地 HEAD tree SHA，否则判失败
 *
 * 用法： node scripts/push-gitdata.mjs [--dry-run]
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

const DRY = process.argv.includes('--dry-run');

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

// ---------- 1b. 历史重写预检（先于取凭据与任何网络调用）----------
// 20260810-18：用户执行 git filter-repo 清除运营文档在公开仓历史中的痕迹后，
// 本地 87 个提交哈希被整体重写，与远端**再无共同祖先** —— 逐提交重放毫无意义，
// 唯一正解是带着明确意图强制覆盖远端，而那是面向公开仓的破坏性操作，
// 不能由每小时的自动飞轮代劳。
//
// 判据用台账自身的同步状态（events[].remote_synced_at），不用"远端 SHA 在不在
// commit-map 里"：本仓走 Git Data API 重放，远端 SHA 由 API 现造、只存在于远端，
// 拿它去撞 commit-map 必然撞不到 —— 那样写出来的检测是个恒假的摆设。
//
// 位置也是判据的一部分：必须**先于**取凭据。实测先取凭据的版本会在
// `git credential fill` 处挂死（helper-selector 想弹窗、终端禁用交互），
// 真正的阻断原因被"拿不到 token"盖掉，下一轮拿到的是错误诊断。
function assertNoPendingRewrite() {
  let pend = null;
  try {
    const led = JSON.parse(fs.readFileSync(
      new URL('../ops/history_rewrite_ledger.json', import.meta.url), 'utf8'));
    pend = (led.events || []).find((ev) => !ev.remote_synced_at) || null;
  } catch { return; }   // 台账缺失 = 从未重写过，按常规路径走
  if (!pend || process.argv.includes('--rewrite-acknowledged')) return;
  throw new Error(
    `本地历史已于 ${pend.rewritten_at} 被 ${pend.tool} 重写（${pend.reason}），尚未同步到远端。\n`
    + `  旧 HEAD ${pend.old_head.slice(0, 8)} → 新 HEAD ${pend.new_head.slice(0, 8)}，`
    + `与远端已无共同祖先，逐提交重放无意义。\n`
    + `  强制覆盖公开仓属破坏性操作（且 GitHub 仍按 SHA 缓存旧提交，需 support ticket 才真正抹除），`
    + `自动飞轮拒绝代劳。\n`
    + `  处置见 ops/results/_NEEDS_USER.md「远端历史清理」条目；确认后加 --rewrite-acknowledged 重跑。`
  );
}
assertNoPendingRewrite();

let TOKEN = process.env.GITHUB_TOKEN;
if (!TOKEN) {
  const cred = execFileSync('git', ['credential', 'fill'], {
    input: 'protocol=https\nhost=github.com\n',
    encoding: 'utf8',
  });
  TOKEN = (cred.match(/^password=(.+)$/m) || [])[1];
}
if (!TOKEN) throw new Error('未取到 GitHub token：设置 GITHUB_TOKEN 或先配置 git credential');

console.log(`repo=${OWNER}/${REPO} branch=${BRANCH} dry=${DRY}`);

// ---------- 2. API 封装 ----------
async function api(method, path, body, retries = 3) {
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'User-Agent': 'roboparts-gitdata-push',
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

// ---------- 3. 确认待推送提交 ----------
// 重要：API 建的 commit 带自己的 committer 时间戳，SHA 必然 != 本地 SHA（tree 相同、commit 不同）。
// 所以远端 SHA 在本地根本不存在，不能直接做 ancestor 检查。
// 用状态文件把「远端 SHA -> 对应的本地 SHA」映射记下来，下次以本地等价物为基准。
const STATE_FILE = `${gitStr(['rev-parse', '--git-dir'])}/gitdata-push-state.json`;
let state = null;
try { state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); } catch {}

// ---------- 3a. 历史重写预检（先于任何网络调用，失败快且可离线自测）----------
// 20260810-18：用户执行 git filter-repo 清除运营文档历史后，本地 87 个提交哈希被
// 整体重写，与远端**再无共同祖先**。此时逐提交重放毫无意义，唯一正解是带着明确
// 意图强制覆盖远端 —— 那是破坏性且面向公开仓的操作，不能由每小时的自动飞轮代劳。
// 判据用台账自身的同步状态，不用"远端 SHA 在不在 commit-map 里"：本仓远端 SHA 由
// API 现造、只存在于远端，拿它撞台账必然撞不到，那种写法是恒假的摆设。
const ref = await api('GET', `/git/refs/heads/${BRANCH}`);
const remoteSha = ref.object.sha;
const localSha = gitStr(['rev-parse', 'HEAD']);
console.log(`remote ${BRANCH} -> ${remoteSha}`);
console.log(`local  HEAD    -> ${localSha}`);

// 求远端 SHA 的本地等价提交
let baseLocal = remoteSha;
if (state && state.remote === remoteSha && state.local) {
  baseLocal = state.local;
  console.log(`(状态文件命中：远端 ${remoteSha.slice(0, 8)} == 本地 ${baseLocal.slice(0, 8)})`);
}

let exists = true;
try { git(['cat-file', '-e', `${baseLocal}^{commit}`]); } catch { exists = false; }
if (!exists) {
  // 20260810-18：同一个"本地查无此远端 SHA"，有两种完全不同的成因，
  // 处置也完全相反 —— 误诊会让下一轮要么白等、要么把检查删掉硬推。
  //   (a) 远端被他处更新  → 先 fetch 对齐，绝不能覆盖；
  //   (b) 本地历史被重写（filter-repo）→ 远端拿的是**重写前**的历史，
  //       此时"对齐"是错的，唯一正解是带着明确意图强制覆盖远端。
  // 用重写台账把两者区分开：远端 SHA 命中台账 old 列 = 板上钉钉的 (b)。
  // 判据不能只看「远端 SHA 在不在台账里」：本仓走 Git Data API 重放，远端 SHA 是
  // API 现造的、**只存在于远端**，既不在本地对象库也不在 commit-map 里 —— 拿它去
  // 撞台账必然撞不到，那样写出来的检测是个恒假的摆设（假绿）。
  // 真正的判据是台账自身的同步状态：重写事件没有 remote_synced_at = 远端还停在旧历史。
  let rewriteHit = null;
  try {
    const led = JSON.parse(fs.readFileSync(
      new URL('../ops/history_rewrite_ledger.json', import.meta.url), 'utf8'));
    for (const ev of led.events || []) {
      if (!ev.remote_synced_at) { rewriteHit = ev; break; }
      if (ev.old_head === remoteSha || (ev.map || {})[remoteSha]) { rewriteHit = ev; break; }
    }
  } catch { /* 台账缺失就按 (a) 处理 */ }
  if (rewriteHit) {
    throw new Error(
      `远端 ${remoteSha.slice(0, 8)} 是**重写前**的历史（本地于 ${rewriteHit.rewritten_at} `
      + `执行 ${rewriteHit.tool}：${rewriteHit.reason}）。\n`
      + `  本地新 HEAD = ${rewriteHit.new_head.slice(0, 8)}，与远端已无共同祖先，逐提交重放无意义。\n`
      + `  这属于**必须由人确认**的破坏性操作（公开仓整段历史被替换，且 GitHub 仍会按 SHA \n`
      + `  缓存旧提交，需另开 support ticket 才能真正抹除）——本脚本拒绝自作主张。\n`
      + `  确认要覆盖时，见 ops/results/_NEEDS_USER.md 中的「远端历史清理」条目。`
    );
  }
  throw new Error(
    `远端 ${remoteSha.slice(0, 8)} 在本地不存在且无状态映射 —— 远端可能被他处更新，请人工核对后再推`
  );
}

// 内容级校验：远端 tree 必须等于本地基准的 tree（比 SHA 相等更本质）
const remoteBaseCommit = await api('GET', `/git/commits/${remoteSha}`);
const baseTreeLocal = gitStr(['rev-parse', `${baseLocal}^{tree}`]);
if (remoteBaseCommit.tree.sha !== baseTreeLocal) {
  throw new Error(
    `远端基准内容与本地不一致：远端 tree ${remoteBaseCommit.tree.sha} != 本地 ${baseTreeLocal} —— 拒绝覆盖`
  );
}

if (baseLocal === localSha) {
  console.log('内容已同步，无需推送');
  process.exit(0);
}

// 快进安全检查（对本地等价物做）
try {
  git(['merge-base', '--is-ancestor', baseLocal, localSha]);
} catch {
  throw new Error(`本地基准 ${baseLocal.slice(0, 8)} 不是 HEAD 的祖先 —— 拒绝非快进推送`);
}

const commits = gitStr(['rev-list', '--reverse', `${baseLocal}..HEAD`]).split('\n').filter(Boolean);
console.log(`待重放 ${commits.length} 个提交`);

// ---------- 4. 逐提交重放 ----------
let parentSha = remoteSha;
let baseTree = baseTreeLocal;

for (const c of commits) {
  const subject = gitStr(['log', '-1', '--format=%B', c]).trim();
  // --no-renames：关闭改名检测，保证 raw 行恒为「单路径」，解析确定
  const raw = gitStr(['diff-tree', '--no-commit-id', '-r', '--root', '--no-renames', c]);

  const entries = [];
  for (const line of raw.split('\n').filter(Boolean)) {
    // :<oldmode> <newmode> <oldsha> <newsha> <status>\t<path>
    const mm = line.match(/^:(\d{6}) (\d{6}) [0-9a-f]+ ([0-9a-f]+) ([A-Z])\d*\t(.+)$/);
    if (!mm) { console.log(`  ! 无法解析 diff 行，中止: ${line}`); process.exit(1); }
    const [, , newMode, newSha, status, pathRaw] = mm;
    const path = pathRaw.replace(/^"|"$/g, '');
    if (newMode === '160000') { console.log(`  - 跳过子模块 ${path}`); continue; }

    if (status === 'D' || /^0+$/.test(newSha)) {
      entries.push({ path, mode: '100644', type: 'blob', sha: null }); // 删除
      console.log(`  D ${path}`);
    } else {
      // 关键：内容取自该提交对象，而非工作区
      const buf = git(['cat-file', 'blob', newSha]);
      const blob = await api('POST', '/git/blobs', {
        content: buf.toString('base64'),
        encoding: 'base64',
      });
      entries.push({ path, mode: newMode, type: 'blob', sha: blob.sha });
      console.log(`  ${status} ${path} -> ${blob.sha.slice(0, 8)}`);
    }
  }

  if (!entries.length) { console.log(`  (空提交，跳过 ${c.slice(0, 8)})`); continue; }
  if (DRY) { console.log(`  [dry-run] 将提交: ${subject.split('\n')[0]}`); continue; }

  const tree = await api('POST', '/git/trees', { base_tree: baseTree, tree: entries });
  const commit = await api('POST', '/git/commits', {
    message: subject,
    tree: tree.sha,
    parents: [parentSha],
  });
  console.log(`  ✅ ${c.slice(0, 8)} -> ${commit.sha.slice(0, 8)}  ${subject.split('\n')[0].slice(0, 60)}`);

  // 完整性：重放后的 tree 必须与本地该提交的 tree 完全一致
  const localTree = gitStr(['rev-parse', `${c}^{tree}`]);
  if (tree.sha !== localTree) {
    throw new Error(`tree 不一致！本地 ${localTree} != 远端 ${tree.sha}（提交 ${c.slice(0, 8)}）`);
  }

  parentSha = commit.sha;
  baseTree = tree.sha;
}

if (DRY) { console.log('dry-run 结束'); process.exit(0); }

// ---------- 5. 更新分支引用 ----------
const upd = await api('PATCH', `/git/refs/heads/${BRANCH}`, { sha: parentSha, force: false });
console.log(`ref 已更新 -> ${upd.object.sha}`);

// ---------- 6. 收尾校验 ----------
const finalTree = gitStr(['rev-parse', 'HEAD^{tree}']);
const remoteCommit = await api('GET', `/git/commits/${upd.object.sha}`);
if (remoteCommit.tree.sha !== finalTree) {
  throw new Error(`最终 tree 不一致：本地 ${finalTree} != 远端 ${remoteCommit.tree.sha}`);
}
console.log(`✅ 校验通过：远端内容与本地 HEAD 完全一致 (tree ${finalTree.slice(0, 8)})`);

// 记录「远端 SHA -> 本地等价 SHA」映射，供下次运行识别基准
fs.writeFileSync(
  STATE_FILE,
  JSON.stringify({ remote: upd.object.sha, local: localSha, tree: finalTree, at: new Date().toISOString() }, null, 2)
);

// remote-tracking ref 指向**本地等价提交**（远端 SHA 本地不存在，写了会 fatal）。
// 内容等价，git status 因此显示同步，不会误导下一轮。
try { git(['update-ref', `refs/remotes/origin/${BRANCH}`, localSha]); } catch (e) {
  console.log(`  (remote-tracking ref 未更新: ${String(e.message).slice(0, 80)})`);
}
console.log('DONE');
