#!/usr/bin/env node
/**
 * RoboParts 部署脚本（安全版）
 *
 * 重要背景：wrangler pages deploy 以「git 仓库根」为部署源（无论 cwd / 目录参数 /
 * pages_build_output_dir 如何设置），而仓库根包含 .workbuddy（本地记忆/用户档案）、
 * ops/（运营报告）等私有目录。仅靠 .gitignore 无法阻止其上传。
 * 因此安全由「边缘中间件 functions/_middleware.js」兜底：对任意请求，私有路径前缀
 * 直接返回 404，合法请求 next() 放行。本脚本负责部署 + 部署后校验，确保中间件生效。
 *
 * 用法：node scripts/deploy.mjs
 * 依赖：已登录 wrangler（OAuth 或 CLOUDFLARE_API_TOKEN）。
 */
import path from 'node:path';
import fs from 'node:fs';
import { spawnSync, execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { snapshotWorkingTree } from './lib/deploy_snapshot.mjs';

const ROOT = process.cwd();
const PROJECT = 'robotparts';
const BASE = 'https://roboparts.cc';

/**
 * 【20260806-17 新增】运行留痕：部署前确保「本小时」已有报告文件。
 *
 * 真实事故（本函数的存在理由）：08-06 15:46 与 16:10 两次运行各自完成了实质工作
 * —— 前者清除 OSS 189 条无依据的 ros_support 断言，后者修掉 MCP 遥测 flush 竞态 ——
 * 两次都 commit 了代码，却都没写小时报告 / 摘要 / _LATEST / 记忆。
 * 用户对这两件事**完全不知情**，而其中一件直接影响 8/7 要读的 MCP 需求判据。
 *
 * regression L1.21 的孤儿检测能发现，但它是**下一轮**的事后检测：
 * 工作已经逃逸，且只在"下一轮恰好运行且恰好跑回归"时才会暴露。
 *
 * 这里把留痕前移到部署路径上：没有本小时报告就先落一份**占位**（带 AUTO-STUB 标记），
 * 内含 git HEAD 与本轮改动文件清单。即便该轮运行随后中断、上下文耗尽或跳过收尾，
 * 用户仍能看到"这一小时动过什么"。
 *
 * 占位不是免罪符：regression L1.32 盯住「早于当前小时的报告仍是占位」，
 * 即"部署了却始终没人来填写"。所以占位只保证**痕迹不丢**，不能用来糊弄闸门。
 *
 * ⚠️ 标记必须是**结构性**的，不能是散文里的裸子串。首版用 `'AUTO-STUB' in 文本` 判定，
 * 结果 17:00 那份**如实描述本机制**的正常报告因为正文提到这个词就被判成占位，
 * 闸门自那一刻起永久变红 —— 而它诞生的目的恰恰是防止"用自动化糊住自己的监控"。
 * 一个恒红的误报会训练下一轮去放宽它，等于亲手制造它要防的假绿。
 * 故改为下面这条**独占一行**的 sentinel，用行锚定正则匹配：文件"是占位" ≠ 文件"提到占位"。
 */
const STUB_SENTINEL = '<!-- ROBOPARTS-RUN-TRACE:AUTO-STUB -->';
function ensureRunTrace() {
  const now = new Date();
  const p2 = (n) => String(n).padStart(2, '0');
  let day = `${now.getFullYear()}${p2(now.getMonth() + 1)}${p2(now.getDate())}`;
  let hh = p2(now.getHours());
  const resDir = path.join(ROOT, 'ops', 'results');
  if (!fs.existsSync(resDir)) return;          // 无 ops/results 则不介入

  // 【20260809-11 修：占位归属「运行轮次」而非「墙钟小时」】
  //
  // 原实现按 `now.getHours()` 决定占位落在哪一格，隐含前提是
  // **「部署时刻的小时 == 该轮报告的小时」**。这条前提对飞轮恰恰不成立：
  // 一轮运行 09:35 起跑、干完活 10:06 才部署，报告写在 09 格 —— 于是
  // 10 格被落了一份**永远不会有人来填**的占位（那一小时并不存在第二轮运行）。
  //
  // 后果不是噪声：L1.32(过期占位) + L1.21(_LATEST 同口径) + L1.63(日报声明时刻)
  // 三道闸门连锁转红，回归 EXIT=1 **禁止发布**。8/9 内已复发两次（06:43、10:06），
  // 上一轮把它判为「误报噪声」记了一笔就放过 —— 这一轮它把回归卡死了。
  // 教训同「口径 ≠ 事实」族：判一个红灯为噪声之前，先看它会不会阻断。
  //
  // 修法是**纠正归属**，不是放宽闸门：飞轮调用前设 ROBOPARTS_RUN_SLOT=YYYYMMDD-HH
  // （本轮报告 slot），占位即落回本轮那一格，随后被真报告覆盖，孤儿消失；
  // 若该轮真的挂了，占位仍留在本轮格，孤儿检测照抓，检测力度分毫未减。
  // 未设该变量时行为**完全不变**（主线/人工部署照旧按墙钟留痕，L1.40 纪律保持）。
  //
  // 防滥用：slot 只能向过去归属、且不得超过 6 小时 —— 否则可把占位丢到远古
  // 格子（甚至已收口的旧格）来规避检测，那就成了免检通道。越界一律忽略并告警。
  const slotRaw = (process.env.ROBOPARTS_RUN_SLOT || '').trim();
  const actorIsFlywheel = (process.env.ROBOPARTS_ACTOR || '').trim() === 'flywheel';
  let slotNote = '';
  if (slotRaw) {
    // 【20260809-13】原本只认 `YYYYMMDD-HH`，传 `13` 直接判非法 → **静默回退墙钟**。
    // L1.73 上线后的第一轮就栽在这：飞轮传了 `13`，警告淹没在部署长输出里，
    // 于是照样生出一个孤儿占位 —— 修复本身给下一个人埋了个格式陷阱。
    // 「要求调用方记住某种格式，记错就悄悄退化」是典型 footgun：
    // 宽进（裸 HH 按今天补全）+ 出错就炸（flywheel 传错直接中止），
    // 比"格式必须精确否则默默降级"稳得多。
    const bare = /^(\d{1,2})$/.exec(slotRaw);
    const normalized = bare
      ? `${now.getFullYear()}${p2(now.getMonth() + 1)}${p2(now.getDate())}-${p2(+bare[1])}`
      : slotRaw;
    if (bare) {
      console.warn(`   ℹ️ ROBOPARTS_RUN_SLOT 收到裸小时 ${slotRaw}，已按今天补全为 ${normalized}`);
    }
    const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})$/.exec(normalized);
    if (!m) {
      const msg = `ROBOPARTS_RUN_SLOT 格式非法（应为 YYYYMMDD-HH 或裸 HH）: ${slotRaw}`;
      // 飞轮是唯一被要求必须传 slot 的调用方；它传错却继续跑，结果必然是孤儿占位，
      // 而孤儿会在下一轮点燃 L1.32/L1.21/L1.63 直接禁止发布。宁可现在就停。
      if (actorIsFlywheel) throw new Error(`${msg} —— 发起方为 flywheel，中止（避免自造孤儿占位）`);
      console.warn(`   ⚠️ ${msg} —— 忽略，按墙钟小时归属`);
    } else {
      const slotAt = new Date(+m[1], +m[2] - 1, +m[3], +m[4], 0, 0);
      const curAt = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0, 0);
      const diffH = (curAt - slotAt) / 3600000;
      if (diffH < 0) {
        console.warn(`   ⚠️ ROBOPARTS_RUN_SLOT 指向未来（${slotRaw}）—— 忽略，按墙钟小时归属`);
      } else if (diffH > 6) {
        console.warn(`   ⚠️ ROBOPARTS_RUN_SLOT 距今 ${diffH}h 超出 6h 上限（${slotRaw}）—— 忽略，按墙钟小时归属`);
      } else if (diffH > 0) {
        day = `${m[1]}${m[2]}${m[3]}`;
        hh = m[4];
        slotNote = `本轮 ${slotRaw} 起跑，部署时刻 ${p2(now.getHours())}:${p2(now.getMinutes())} 已跨小时；占位按运行轮次归属，非墙钟小时。`;
      }
    }
  } else if (actorIsFlywheel) {
    console.warn('   ⚠️ 发起方为 flywheel 但未设 ROBOPARTS_RUN_SLOT —— 跨小时部署将自造孤儿占位（L1.73）');
  }

  const reportPath = path.join(resDir, `roboparts-${day}-${hh}.md`);
  if (fs.existsSync(reportPath)) return;       // 本轮已自行报告，正常路径

  // ⚠️ Windows + shell:true 下，**含空格的单个参数会被拆成两个**。
  // 首版写 `--pretty=format:%h %s` 正是栽在这里：git 实际收到两个参数、输出为空，
  // 占位里最关键的那项痕迹变成「(无法读取 git HEAD)」。
  // 源码级断言看不出来（写法"像是对的"），是实跑一次才暴露的 —— 故所有 git 参数保持零空格。
  const git = (args) => {
    const r = spawnSync('git', args, { cwd: ROOT, encoding: 'utf8', shell: true });
    return (r.stdout || '').trim();
  };
  const sha = git(['rev-parse', '--short', 'HEAD']);
  const subj = git(['log', '-1', '--pretty=%s']);
  const head = sha ? (subj ? sha + ' ' + subj : sha) : '(无法读取 git HEAD)';
  const changed = git(['status', '--short']).split('\n').filter(Boolean).slice(0, 12);
  // 归属被重定向时，标题时刻取 slot 起点（与文件名小时保持一致，不制造 "09:06" 这种
  // 既非部署时刻、又非 slot 起点的怪值）；真实部署时刻另起一行如实记录，不靠读者猜。
  const stamp = slotNote
    ? `${day.slice(0, 4)}-${day.slice(4, 6)}-${day.slice(6, 8)} ${hh}:00`
    : `${now.getFullYear()}-${p2(now.getMonth() + 1)}-${p2(now.getDate())} ${hh}:${p2(now.getMinutes())}`;

  // 【20260807-08 补】部署发起方。此前占位一律断言"本轮运行异常中断"，
  // 但 8/7 07:02 / 08:20 两次部署来自**总指挥主线任务**，那两个小时压根没有飞轮轮次 ——
  // 占位却言之凿凿说有一轮跑挂了，把后续补写者引向"为不存在的运行编一份报告"。
  // 故如实记录发起方；未标注时写"未标注"，绝不假定是飞轮。飞轮轮次应设
  // ROBOPARTS_ACTOR=flywheel 后再调用本脚本。
  const actor = (process.env.ROBOPARTS_ACTOR || '').trim() || '未标注（非飞轮轮次或未设置环境变量）';

  const body = [
    `# RoboParts 飞轮 · ${stamp}`,
    '',
    // ↓ 机器判据：必须独占一行、逐字不变（L1.32 用行锚定正则匹配）。补写报告时连同此行一并删除。
    STUB_SENTINEL,
    '<!-- 上一行表示：本文件由 deploy.mjs 自动占位，这一小时有部署活动但尚无人填写报告。',
    '     内容以下方 git 痕迹为准；发起方见「部署发起方」一行。',
    '     若发起方不是 flywheel，说明这一小时的部署来自主线/人工，不存在"该轮飞轮运行"，',
    '     后续轮次应以 RECONCILED 补写（见 regression L1.40），不得伪造第一人称运行报告。 -->',
    '',
    '## 修复',
    '',
    `- ⚠️ **本文件为自动占位，尚未有人填写**。已知痕迹：git HEAD = \`${head}\`。`,
    `- 部署发起方：${actor}`,
    ...(slotNote ? [`- 归属说明：${slotNote}`] : []),
    ...(changed.length ? ['- 部署时工作区未提交改动：', ...changed.map((c) => `  - \`${c}\``)] : []),
    '',
    '## 提升',
    '',
    '- （占位，待填写）',
    '',
    '## 仍需你操作',
    '',
    '- 无（占位）。若本占位停留在过去的小时，须由后续轮次填写（第一人称）或以 RECONCILED 补写。',
    '',
  ].join('\n');
  fs.writeFileSync(reportPath, body, 'utf8');

  // 摘要行同步落一条，保持 L1.21「报告 ↔ 摘要」配对不变式成立
  const sumPath = path.join(resDir, '_SUMMARY.md');
  if (fs.existsSync(sumPath)) {
    let cur = fs.readFileSync(sumPath, 'utf8');
    if (!cur.endsWith('\n')) cur += '\n';       // 不以换行结尾必粘连（L1.21 第 2 条不变式）
    cur += `- ${stamp} | 修复:⚠️自动占位(运行未填写报告,HEAD=${sha || '未知'}) | 提升:占位 | 待办:待该轮或下一轮补写\n`;
    fs.writeFileSync(sumPath, cur, 'utf8');
  }
  console.log(`   ⚠️ ${slotNote ? '本轮 slot' : '本小时'}无报告，已落自动占位: ops/results/roboparts-${day}-${hh}.md`);
}

// 0) 留痕先于部署：任何工作上线前，先保证这一小时在 ops/results/ 留下痕迹
console.log('[0/3] 运行留痕检查...');
ensureRunTrace();
// 0b) 内容快照先于部署：留痕保住「说明」，快照保住「内容」，缺一不可
snapshotWorkingTree(ROOT);

// 0b2) 训练数据集重导出（api/training_dataset.json）
// 20260810-13：这份 10MB 的对外产物是「派生物没挂流水线」的典型 —— 它由 entities.json
// 现算而来，却是手工跑一次就上线，随后 12:26 那轮把标准登记表 10→11，它仍在对外播 10 条，
// 而 data-hub 页面与 MCP resources 都在把它当权威数据集推给 agent。派生物一旦对外，
// 就必须和真相源同一时刻更新，否则它就是一份「看起来有出处」的过期快照。
// 与 0c/0d 同理：无条件跑一次，比"记得跑"可靠；硬校验交给回归 L1.80。
{
  const ex = spawnSync(process.execPath, [path.join(ROOT, 'scripts', 'export_training_dataset.mjs')], { cwd: ROOT, encoding: 'utf8' });
  if (ex.status === 0) console.log('   ✅ 训练数据集已随真相源重导出');
  else console.warn('   ⚠️ 训练数据集导出失败:', (ex.stderr || ex.stdout || '').trim().slice(0, 300));
}

// 0b3) 真实需求信号回流（api/demand-signal.json）
// 20260815-补强：demand_scan.mjs 现算的「真实社区兼容性提问」信号原本是一次性 ops 报告，
// scoreboard.html 里对应单元格是人工维护日志 —— 监听器产物没回流到站上可读端点（H4/L6 断点）。
// 这里把最新 ops/demand-signal-*.json 在部署前无条件复制到 api/，让 /api/demand-signal
// 端点与计分板自动读取，取代手填。部署本就不依赖出网，复制本地文件零风险。
{
  const opsDir = path.join(ROOT, 'ops');
  const sigFiles = fs.existsSync(opsDir)
    ? fs.readdirSync(opsDir).filter((f) => /^demand-signal-\d{4}-\d{2}-\d{2}\.json$/.test(f))
        .map((f) => ({ f, t: fs.statSync(path.join(opsDir, f)).mtimeMs }))
        .sort((a, b) => b.t - a.t)
    : [];
  const src = sigFiles[0] ? path.join(opsDir, sigFiles[0].f) : null;
  if (src) {
    fs.copyFileSync(src, path.join(ROOT, 'api', 'demand-signal.json'));
    console.log(`   ✅ 需求信号已回流: ${sigFiles[0].f} → api/demand-signal.json`);
  } else {
    console.warn('   ⚠️ 未发现 ops/demand-signal-*.json，跳过回流（端点将返回 404 直至首次扫描）');
  }
}

// 0c) 机读接入声明兜底注入（meta.access）
// 20260808-04：inject_api_access.py 的 docstring 自称「由 deploy 前置与各 build 脚本调用，
// 不依赖任何人记得手工执行」，但实测 deploy.mjs 里对它的引用是 **0 处** —— 文档写了 ≠ 挂上了，
// 又一例「口径 ≠ 事实」。结果是任何整份重写 api/*.json 的脚本都会静默抹掉领 key 入口，
// 直到回归 L1.14 判红才被发现。这里把那句话变成真的：部署前无条件跑一次（幂等）。
{
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const ij = spawnSync(py, [path.join(ROOT, 'scripts', 'inject_api_access.py')], { cwd: ROOT, encoding: 'utf8' });
  if (ij.status === 0) console.log('   ✅ meta.access 注入检查通过（对外 JSON 均带领 key 入口）');
  else console.warn('   ⚠️ meta.access 注入失败:', (ij.stderr || ij.stdout || '').trim().slice(0, 300));
}

// 0d) 接入区块兜底注入（RP-ONBOARDING，覆盖 index + 2 落地页 + 全部 articles/*.html）
// 20260808-07：与上面 0c 完全同源的病，只是换了个注入器 —— inject_onboarding.py 的
// targets() 与回归扫描的页面集合逐个相同，却从未挂在 deploy 上；于是每次实体数变化
// 都得靠人记得手工跑，06:45 那轮就漏掉了 14 篇文章页（页面还写 688，真值已 706）。
// 注入器幂等（先剥离旧块再写入），无条件跑一次比"记得跑"可靠。
{
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const ob = spawnSync(py, [path.join(ROOT, 'scripts', 'inject_onboarding.py')], { cwd: ROOT, encoding: 'utf8' });
  if (ob.status === 0) console.log('   ✅ 接入区块注入检查通过（页面数字与真值同源）');
  else console.warn('   ⚠️ 接入区块注入失败:', (ob.stderr || ob.stdout || '').trim().slice(0, 300));
}

// 【GOAI 对齐 · J8】git tag 回滚锚点：部署前打一个可回滚点（非阻塞）。
// 格式 deploy-YYYYMMDD-HHmm；保留最近 40 个，超出自动清理最老 tag。
{
  try {
    const now = new Date();
    const tag = `deploy-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
    execSync(`git tag -f ${tag}`, { cwd: ROOT, stdio: 'pipe' });
    console.log('   ✅ 部署回滚锚点:', tag);
    try {
      const tags = execSync('git tag -l "deploy-*" --sort=-creatordate', { cwd: ROOT, encoding: 'utf8', stdio: 'pipe' }).trim().split('\n').filter(Boolean);
      if (tags.length > 40) {
        const toDelete = tags.slice(40);
        for (const t of toDelete) execSync(`git tag -d ${t}`, { cwd: ROOT, stdio: 'ignore' });
        console.log(`   (清理 ${toDelete.length} 个过期 deploy tag)`);
      }
    } catch { /* 清理失败不影响主流程 */ }
  } catch (e) {
    console.log('   ⚠️ 部署回滚锚点创建失败（非阻塞，如不在 git 仓库会跳过）:', e.message.slice(0, 200));
  }
}

// 1) 部署（wrangler 以 git 根为源；私有目录靠 _middleware.js 在边缘 404 拦截）
console.log('[1/3] 部署到 Cloudflare Pages...');
// 修复（20260814）：npx 会拉取最新 wrangler（实测 4.123），其 pages deploy 在部分账号下
// 误报 "The Pages project 'robotparts' does not exist"（同账号 project list 却正常列出）。
// 优先用 WRANGLER_BIN 指定的可复现 wrangler（格式 "node.exe|wrangler.js"），否则回退 npx。
const WRANGLER_BIN = process.env.WRANGLER_BIN;
let wranglerCmd, wranglerArgs;
if (WRANGLER_BIN) {
  const [wbNode, wbWjs] = WRANGLER_BIN.split('|');
  wranglerCmd = wbNode;
  wranglerArgs = [wbWjs, 'pages', 'deploy', '.', '--project-name=' + PROJECT];
} else {
  wranglerCmd = 'npx';
  wranglerArgs = ['wrangler', 'pages', 'deploy', '.', '--project-name=' + PROJECT];
}
const dep = spawnSync(wranglerCmd, wranglerArgs, {
  stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', cwd: ROOT, shell: true,
});
const depOut = (dep.stdout || '') + '\n' + (dep.stderr || '');
process.stdout.write(depOut);
if (dep.status !== 0) {
  console.error('❌ 部署命令失败，退出码', dep.status);
  process.exit(dep.status ?? 1);
}
const hashMatch = depOut.match(/https:\/\/([0-9a-f]+)\.robotparts-924\.pages\.dev/);
const TARGET = hashMatch ? `https://${hashMatch[1]}.robotparts-924.pages.dev` : BASE;
console.log(`   部署预览: ${TARGET}`);

/**
 * 【20260805-18 防自污染】部署校验请求必须带自检隔离头。
 * 每次部署会发出约 15 次校验请求；边缘遥测上线后，这些请求会被记成真实流量
 * （tool 类 + 私有路径 404），把飞轮自己的运维动作读成"站点有访问量"。
 * 与 15:00 的 testorder_ 隔离、record() 的 selftest 分支同源教训。
 */
const SELFTEST_HEADERS = { 'X-RoboParts-Selftest': '1' };

/**
 * 【20260818-W2 收尾加固】verify 的 fetch 此前不设超时，Cloudflare 连接挂死会无限等待
 * （实测 08-18 夜那轮部署因此卡 18 分钟、进程被杀、快照 ref 未写入）。
 * 给每次校验请求加 AbortSignal 超时，连接不可达时快速失败而非悬停。
 */
const fetchT = (u, o = {}) => fetch(u, { ...o, signal: o.signal || AbortSignal.timeout(25000) });

// 2) 校验：私有路径必须 404 + 数据一致 + 页面可用（带重试，等别名传播）
console.log('[2/3] 线上校验（中间件拦截 / 实体数+内容指纹一致性 / 页面可用性）...');
async function verify() {
  const errs = [];
  const today = new Date().toISOString().slice(0, 10);
  for (const p of [`.workbuddy/memory/${today}.md`, 'ops/']) {
    try {
      const r = await fetchT(TARGET + '/' + p, { headers: SELFTEST_HEADERS });
      if (r.status !== 404) errs.push(`私有路径未拦截: /${p} 返回 ${r.status}（应为 404）`);
    } catch (e) { errs.push(`校验请求异常 /${p}: ${e.message}`); }
  }
  let localTotal = 0;
  try {
    const meta = JSON.parse((await import('node:fs')).readFileSync(path.join(ROOT, 'api/entities.json'), 'utf8')).meta;
    localTotal = meta.total_entities;
  } catch (e) { errs.push('读取本地 meta 失败: ' + e.message); }
  // 【N03 20260805 加固】原校验仅比 meta.total_entities，属"自洽即通过"的弱口径：
  // 当线上与本地同为旧快照时也会全绿，曾掩盖 api/data.json 漂移 3 天（493/65类）。
  // 现增加 ID+category 内容指纹交叉比对，覆盖"总数不变、内容变更"的漂移。
  try {
    const fs = await import('node:fs');
    const src = JSON.parse(fs.readFileSync(path.join(ROOT, 'api/entities.json'), 'utf8')).entities || [];
    const d = await (await fetchT(TARGET + '/api/data.json', { headers: SELFTEST_HEADERS })).json();
    const onlineArr = d?.data || d?.entities || [];
    const online = d?.meta?.total_entities;
    if (online !== localTotal) errs.push(`数据不一致: 线上 ${online} != 本地 ${localTotal}`);
    if (onlineArr.length !== src.length) errs.push(`实体数组长度不一致: 线上 ${onlineArr.length} != 本地 ${src.length}`);
    const fp = (a) => new Set(a.map((e) => `${e.id}|${e.category}`));
    const [fsrc, fon] = [fp(src), fp(onlineArr)];
    const missing = [...fsrc].filter((k) => !fon.has(k));
    const extra = [...fon].filter((k) => !fsrc.has(k));
    if (missing.length || extra.length) {
      errs.push(`内容指纹不一致: 线上缺 ${missing.length} 条 / 多 ${extra.length} 条（示例: ${(missing[0] || extra[0])}）`);
    }
    // 【N03 20260805-r2 加固】ID+category 指纹仍是弱口径：只覆盖"实体增删 / 类目变更"，
    // 对"实体集合与类目都不变、仅字段内容变化"的漂移完全失明。
    // 实证：08-05 08:45 部署后，N10 Schema 治理于 08:51 向真相源写入 quarantine /
    // data_quality / source_tier / confidence 等治理字段，线上 544 条全部缺失该字段，
    // 而 ID+category 指纹判定为"零差异"，一路绿灯 —— 与被误诊 12 天的 api/data.json
    // 事件属同一类盲区，只是下沉到了字段层。
    // 现改为全字段稳定序列化指纹，字段级漂移必须被拦下。
    const stable = (v) => {
      if (Array.isArray(v)) return v.map(stable);
      if (v && typeof v === 'object') {
        return Object.keys(v).sort().reduce((o, k) => { o[k] = stable(v[k]); return o; }, {});
      }
      return v;
    };
    const deepFp = (a) => new Map(a.map((e) => [e.id, JSON.stringify(stable(e))]));
    const [dsrc, don] = [deepFp(src), deepFp(onlineArr)];
    const fieldDrift = [...dsrc.keys()].filter((id) => don.has(id) && don.get(id) !== dsrc.get(id));
    if (fieldDrift.length) {
      errs.push(`字段级内容漂移: ${fieldDrift.length} 条实体线上与真相源字段不一致（示例: ${fieldDrift.slice(0, 3).join(', ')}）`);
    }
  } catch (e) { errs.push('读取线上 /api/data.json 失败: ' + e.message); }
  const pages = ['/', '/selection.html', '/designer.html', '/suppliers.html', '/pricing.html', '/bom-manager.html', '/urdf-library.html', '/data-hub.html', '/bom-checker.html', '/oss.html', '/adapter-generator', '/copilot', '/agent-architecture', '/build-planner', '/geo-dashboard', '/mcp-guide', '/skills/manifest.json', '/waitlist.html', '/scoreboard.html', '/embed/lookup.html'];
  // OSS 数据层一致性（CL1 飞轮产物）
  try {
    const localOss = JSON.parse((await import('node:fs')).readFileSync(path.join(ROOT, 'api/oss_components.json'), 'utf8')).meta.total_entities;
    const onlineOss = (await (await fetchT(TARGET + '/api/oss?stats=1', { headers: SELFTEST_HEADERS })).json()).total;
    if (onlineOss !== localOss) errs.push(`OSS 数据层不一致: 线上 ${onlineOss} != 本地 ${localOss}`);
  } catch (e) { errs.push('读取 OSS 数据层失败: ' + e.message); }
  for (const pg of pages) {
    try {
      const r = await fetchT(TARGET + pg, { headers: SELFTEST_HEADERS });
      if (r.status !== 200) errs.push(`页面异常 ${pg}: ${r.status}`);
    } catch (e) { errs.push(`页面请求异常 ${pg}: ${e.message}`); }
  }
  /**
   * 【20260807-16】对外公布的入口必须扛得住 HEAD 探活。
   * Pages Functions 按 onRequest<Method> 具名导出路由，没有 onRequestHead 就一律 404。
   * 实测部署前 `HEAD /mcp` = 404 而 `GET /mcp` = 200 —— 而目录站、链接检查器、
   * 可用性监控默认用 HEAD，/mcp 又恰是我们唯一进了官方 Registry / Glama / mcp.so
   * 的对外通道。等于一边买曝光，一边对来探活的人说"我不在"。
   * 校验只查"不是 404"（405/200 都算活着），避免把方法语义写死。
   */
  for (const ep of ['/mcp', '/api/register', '/api/validate', '/api/data.json', '/api/waitlist', '/api/badge', '/api/recommend', '/api/demand-signal']) {
    try {
      const r = await fetchT(TARGET + ep, { method: 'HEAD', headers: SELFTEST_HEADERS });
      // 【20260807-17 收紧】原先 HEAD 拿到 404 会回退 GET，只要 GET 通就算存活。
      // 那条回退正是假修复的温床：线上 HEAD 一直是 404（目录站眼里我们已下线），
      // 部署校验却因为 GET 能通而始终报绿，问题被掩盖了两轮。
      // 目录站发的就是 HEAD，就只认 HEAD 的结果 —— 校验方式必须和真实探活方式一致。
      if (r.status === 404) errs.push(`HEAD 探活 404（目录站会判定为下线）: ${ep}`);
    } catch (e) { errs.push(`探活异常 ${ep}: ${e.message}`); }
  }
  return errs;
}

// 【N10 20260805 加固】原为「3 次 × 12s = 36s」固定间隔，Cloudflare Pages 自定义域别名
// 传播常需 60~120s，导致部署实际成功却判定失败（本次 N02→N01 已出现一次假阴性，
// 30s 后手工复核全部一致）。改为 5 次退避重试，总窗口 ~107s，覆盖典型传播时延。
const BACKOFF_MS = [12000, 20000, 30000, 45000];
let errs = [];
for (let attempt = 1; attempt <= BACKOFF_MS.length + 1; attempt++) {
  errs = await verify();
  if (errs.length === 0) break;
  const wait = BACKOFF_MS[attempt - 1];
  if (wait) { console.log(`   第 ${attempt} 次校验未通过，${wait / 1000}s 后重试（等待 CDN 别名传播）...`); await new Promise((r) => setTimeout(r, wait)); }
}
if (errs.length) {
  console.error('❌ 校验未通过（已退避重试 5 次 / 约 107s）:');
  for (const e of errs) console.error('   - ' + e);
  process.exit(1);
}

// 3) 成功
console.log('[3/3] 校验全部通过 ✅（私有目录已 404 拦截，实体数与内容指纹一致，关键页面正常）');

// 4) 推广脉冲（部署成功后自动通知搜索引擎与目录，失败不影响部署）
console.log('[4/4] 触发推广脉冲（IndexNow / sitemap ping / 目录登记）...');
try {
  const promoteScript = fileURLToPath(new URL('./promote.mjs', import.meta.url));
  const root = fileURLToPath(new URL('..', import.meta.url));
  const pr = spawnSync(process.execPath, [promoteScript], { cwd: root, encoding: 'utf8', timeout: 60000 });
  if (pr.stdout) process.stdout.write(pr.stdout);
  if (pr.status !== 0) console.log('   ⚠️ 推广脉冲非零退出（不影响部署）');
} catch (e) { console.log('   ⚠️ 推广脉冲异常（不影响部署）: ' + e.message); }
