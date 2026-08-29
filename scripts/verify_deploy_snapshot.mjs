/**
 * 部署快照的功能性验证：在**真实的临时 git 仓库**里实跑，不测副本、不测正则。
 *
 * 为什么必须建真仓库跑：这套逻辑的全部风险都在 git 的真实行为上
 * （临时 GIT_INDEX_FILE 会不会串到主索引、read-tree 播种能否保住
 * 「已追踪但被 ignore」的文件、commit-tree 从 stdin 读信息在 Windows
 * shell:true 下会不会被拆参数）。这些东西源码级断言一个都看不出来。
 *
 * 断言的核心不是"函数返回了一个 ref"，而是**那个 ref 里真的装着当时的工作区内容**
 * —— 否则就是一个看起来在备份、实际备份了个空的假保险。
 */
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { snapshotWorkingTree, SNAP_PREFIX } from './lib/deploy_snapshot.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
let fail = 0;
const check = (ok, msg) => {
  console.log(`  ${ok ? '✅' : '❌'} ${msg}`);
  if (!ok) fail++;
};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'rp-snaptest-'));
const g = (args, opts = {}) => spawnSync('git', args, {
  cwd: tmp, encoding: 'utf8', shell: true, ...opts,
});
const gout = (args, opts) => (g(args, opts).stdout || '').trim();

try {
  console.log('[部署快照] 临时仓库:', tmp, '\n');
  g(['init', '-q']);
  g(['config', 'user.email', 't@t.t']);
  g(['config', 'user.name', 'test']);
  g(['config', 'commit.gpgsign', 'false']);

  // 基线提交：一个普通文件 + 一个「已追踪但随后被 .gitignore 忽略」的文件
  // （对应真实仓库里的 mcp-server/*，read-tree 播种正是为它而设）
  fs.writeFileSync(path.join(tmp, 'app.js'), 'v1\n');
  fs.mkdirSync(path.join(tmp, 'ignored'), { recursive: true });
  fs.writeFileSync(path.join(tmp, 'ignored', 'keep.md'), 'tracked-but-ignored-v1\n');
  g(['add', '-A']);
  g(['commit', '-q', '-m', 'base']);
  fs.writeFileSync(path.join(tmp, '.gitignore'), 'ignored/\n');
  g(['add', '.gitignore']);
  g(['commit', '-q', '-m', 'addignore']);
  const headBefore = gout(['rev-parse', 'HEAD']);

  // ---- 场景 1：工作区干净 → 不应产生 ref（避免无意义堆积）----
  const cleanRef = snapshotWorkingTree(tmp, () => {});
  check(cleanRef === null, '工作区干净时不建快照（实得 ' + cleanRef + '）');

  // ---- 场景 2：制造「已部署但未入库」的真实状态 ----
  fs.writeFileSync(path.join(tmp, 'app.js'), 'v2-SECURITY-FIX\n');       // 改已追踪文件
  fs.writeFileSync(path.join(tmp, 'newgate.py'), 'brand-new\n');          // 新增未追踪文件
  fs.writeFileSync(path.join(tmp, 'ignored', 'keep.md'), 'tracked-but-ignored-v2\n');
  // 往主索引里放点东西，用来验证快照不会污染它
  g(['add', 'newgate.py']);
  const idxBefore = gout(['diff', '--cached', '--name-only']);

  const ref = snapshotWorkingTree(tmp, () => {});
  check(typeof ref === 'string' && ref.startsWith(SNAP_PREFIX),
    '脏工作区产生快照 ref（实得 ' + ref + '）');

  // 核心断言：ref 里装的必须是**当时工作区的真实内容**，不是 HEAD 的副本
  const shown = gout(['show', ref + ':app.js']);
  check(shown === 'v2-SECURITY-FIX',
    '快照含已追踪文件的**未提交新内容**（实得 ' + JSON.stringify(shown) + '）');

  const shownNew = gout(['show', ref + ':newgate.py']);
  check(shownNew === 'brand-new',
    '快照含新增的未追踪文件（实得 ' + JSON.stringify(shownNew) + '）');

  // 「已追踪但被 ignore」的文件必须还在，且是新内容。
  // 这条最容易悄悄失守：若去掉 read-tree 播种，它会从快照里整个消失，
  // 而其它断言全绿 —— 备份看着成功，实则漏掉了一整个目录。
  const shownIgn = gout(['show', ref + ':ignored/keep.md']);
  check(shownIgn === 'tracked-but-ignored-v2',
    '快照保住「已追踪但被 ignore」的文件及其新内容（实得 ' + JSON.stringify(shownIgn) + '）');

  // ---- 场景 3：零副作用 ----
  check(gout(['rev-parse', 'HEAD']) === headBefore, '快照不移动 HEAD');
  check(gout(['rev-parse', '--abbrev-ref', 'HEAD']) === 'master'
    || gout(['rev-parse', '--abbrev-ref', 'HEAD']) === 'main', '快照不切换分支');
  check(gout(['diff', '--cached', '--name-only']) === idxBefore,
    '快照不污染调用者暂存区（前 ' + JSON.stringify(idxBefore)
    + ' / 后 ' + JSON.stringify(gout(['diff', '--cached', '--name-only'])) + '）');
  check(fs.readFileSync(path.join(tmp, 'app.js'), 'utf8') === 'v2-SECURITY-FIX\n',
    '快照不改动工作区文件');

  // 快照必须挂在**非分支** ref 上，不能出现在 branch 列表里污染历史
  check(!gout(['branch', '--list']).includes('deployed'), '快照不产生分支');
  check(gout(['log', '--oneline']).split('\n').length === 2,
    'main 历史未被写入垃圾提交（仍 2 条）');

  // ---- 场景 4：可恢复性（这才是整件事的目的）----
  // 模拟最坏情况：工作区被 checkout 冲掉、未追踪文件被删，能否从 ref 取回
  g(['checkout', '--', 'app.js']);
  fs.unlinkSync(path.join(tmp, 'newgate.py'));
  // 读文件一律去 CR 再比：Windows 上 core.autocrlf 会把 checkout 出来的内容变成
  // 'v1\r\n'，首版直接比 'v1\n' 当场误红。这是测试自身的环境缺陷，不是产品缺陷 ——
  // 但若当时图省事把这条断言删掉，就会连带失去"工作区确实被冲掉了"这个前置保证，
  // 使下面那条"仍能取回"变成无意义的恒绿（工作区压根没坏，取回当然成功）。
  const rd = (f) => fs.readFileSync(path.join(tmp, f), 'utf8').replace(/\r/g, '');
  check(rd('app.js') === 'v1\n', '（前置）工作区已被冲掉（实得 ' + JSON.stringify(rd('app.js')) + '）');
  const restored = gout(['show', ref + ':app.js']);
  check(restored === 'v2-SECURITY-FIX',
    '工作区被冲掉后仍能从快照取回上线内容 ← 本机制的唯一目的');

  // ---- 反向注入：把兜底能力破坏掉，断言必须变红 ----
  // 子进程跑的是本文件自身，必须靠 RP_SNAP_NOINJECT 截断，否则无限递归自我 fork。
  if (process.env.RP_SNAP_NOINJECT !== '1') {
    console.log('\n[反向注入] 破坏快照能力，验证上面的断言不是摆设');
    const modPath = path.join(HERE, 'lib', 'deploy_snapshot.mjs');
    const orig = fs.readFileSync(modPath, 'utf8');
    const injections = [
      ['①去掉 read-tree 播种（已追踪但被 ignore 的文件会整个丢失）',
        "if (run(['read-tree', 'HEAD'], { env }).status !== 0) return null;", ''],
      ['②不 add 工作区改动（快照退化成 HEAD 副本，备份了个寂寞）',
        "run(['add', '-A'], { env });", ''],
    ];
    try {
      for (const [name, from, to] of injections) {
        if (!orig.includes(from)) {
          console.log(`  ⚠️ ${name} -> 注入锚点未命中，用例失效`); fail++; continue;
        }
        fs.writeFileSync(modPath, orig.replace(from, to));
        const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url)],
          { encoding: 'utf8', env: { ...process.env, RP_SNAP_NOINJECT: '1' } });
        const red = (r.stdout || '').includes('❌');
        console.log(`  ${red ? '✅' : '❌'} ${name} -> ${red ? '被拦下' : '未被拦下（断言是摆设）'}`);
        if (!red) fail++;
      }
    } finally {
      fs.writeFileSync(modPath, orig);                 // 无论如何都还原
      console.log('  已还原 lib/deploy_snapshot.mjs');
    }
  }
} finally {
  try { fs.rmSync(tmp, { recursive: true, force: true }); } catch { /* 忽略 */ }
}

console.log('\n' + (fail ? `❌ ${fail} 项未通过` : '✅ 部署快照全部通过'));
process.exit(fail ? 1 : 0);
