/**
 * 部署快照：让「已上线但未入库」的代码**天然可恢复**。
 *
 * 真实事故（本模块的存在理由）：08-06 21:43、08-07 00:00、08-07 03:38 三轮
 * 各自完成实质工作并**部署上线**，却都没 commit —— 其中 03:38 那轮上线的是
 * 一处安全修复（供应商公开目录放行未审核记录）。仓库停在旧提交，**线上领先仓库**。
 *
 * deploy.mjs 的 ensureRunTrace() 已经把「这一小时动过什么」写进报告了，为何还不够？
 * 因为它留的是**描述**，不是**内容**：占位里只有一行 `M functions/.../list.js`。
 * 真正的修复内容此刻仅存在于工作区这一个副本里 —— 一次 `git checkout .`、
 * 一次误操作、一次换机器，线上跑着的那份代码就**再也拼不回来**了。
 * 已连续三轮踩在这个状态上，靠"下一轮记得去 commit"显然不成立。
 *
 * 做法：部署前把**当前工作区完整快照**写成一个 git commit 对象，挂在
 * refs/roboparts/deployed/<时间戳> 这个非分支 ref 上。
 * 关键是它**不碰 HEAD、不碰分支、不碰调用者的暂存区**（用临时 GIT_INDEX_FILE），
 * 对正常流程零副作用，也不会产生垃圾提交污染 main 的历史。
 * 但从此刻起，线上跑的那份代码永远躺在 git 对象库里，可用
 * `git diff HEAD <ref>` 随时取回。
 *
 * 定位：这是**兜底**，不是"可以不 commit 了"的许可。
 * 正常路径仍是运行本人 commit + push；快照只保证最坏情况下工作不灭失。
 *
 * ⚠️ 单独成模块而非内联在 deploy.mjs，是为了让 verify 脚本能 import **同一份实现**
 *    去真实建仓实跑。若把逻辑复制一份到测试里，测的就是副本 —— 副本永远是绿的。
 *
 * ⚠️ 所有 git 参数**不得含空格**（Windows + shell:true 会把含空格的单参数拆成两个，
 *    deploy.mjs 的 `--pretty=format:%h %s` 就栽在这里）。故提交信息不走 -m，
 *    改用 commit-tree 从 **stdin** 读取。
 */
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { spawnSync } from 'node:child_process';

export const SNAP_PREFIX = 'refs/roboparts/deployed/';
export const SNAP_KEEP = 40;

export function snapshotWorkingTree(root, log = console.log) {
  if (!fs.existsSync(path.join(root, '.git'))) return null;   // 非 git 仓库则不介入

  const run = (args, opts = {}) => spawnSync('git', args, {
    cwd: root, encoding: 'utf8', shell: true, ...opts,
  });
  const out = (args, opts) => (run(args, opts).stdout || '').trim();

  // 工作区干净就没有"未入库内容"可丢，无需快照（避免 ref 无意义堆积）
  const dirty = out(['status', '--porcelain']).split('\n').filter(Boolean);
  if (!dirty.length) return null;

  const now = new Date();
  const p2 = (n) => String(n).padStart(2, '0');
  const stamp = `${now.getFullYear()}${p2(now.getMonth() + 1)}${p2(now.getDate())}`
    + `-${p2(now.getHours())}${p2(now.getMinutes())}${p2(now.getSeconds())}`;

  // 临时索引：不污染调用者暂存区。先 read-tree HEAD 播种，
  // 这样「已追踪但被 .gitignore 忽略」的文件（如 mcp-server/*）不会从快照里消失。
  const tmpIndex = path.join(os.tmpdir(), `rp-snap-${process.pid}-${Date.now()}.idx`);
  const env = { ...process.env, GIT_INDEX_FILE: tmpIndex };
  try {
    if (run(['read-tree', 'HEAD'], { env }).status !== 0) return null;
    run(['add', '-A'], { env });                // 无 pathspec：已追踪文件照常更新
    const tree = out(['write-tree'], { env });
    if (!/^[0-9a-f]{40}$/.test(tree)) return null;

    const head = out(['rev-parse', 'HEAD']);
    const msg = [
      `deploy-snapshot ${stamp}`,
      '',
      '部署前自动快照：这份内容即将上线，但当时尚未 commit。',
      '由 scripts/lib/deploy_snapshot.mjs 生成，不属于 main 历史。',
      `未入库文件 ${dirty.length} 项：`,
      ...dirty.slice(0, 20).map((d) => '  ' + d),
    ].join('\n');
    const commit = (run(['commit-tree', tree, '-p', head], { env, input: msg }).stdout || '').trim();
    if (!/^[0-9a-f]{40}$/.test(commit)) return null;

    const ref = SNAP_PREFIX + stamp;
    if (run(['update-ref', ref, commit], { env }).status !== 0) return null;

    // 保留最近 SNAP_KEEP 个，避免无限堆积（ref 很便宜，但没必要留一年）
    const refs = out(['for-each-ref', '--format=%(refname)', SNAP_PREFIX])
      .split('\n').filter(Boolean).sort();
    for (const old of refs.slice(0, Math.max(0, refs.length - SNAP_KEEP))) {
      run(['update-ref', '-d', old], { env });
    }
    log(`   📦 已快照未入库内容 ${dirty.length} 项 -> ${ref} (${commit.slice(0, 7)})`);
    log('      取回: git diff HEAD ' + ref);
    return ref;
  } finally {
    try { if (fs.existsSync(tmpIndex)) fs.unlinkSync(tmpIndex); } catch { /* 忽略 */ }
  }
}
