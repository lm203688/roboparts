#!/usr/bin/env node
/**
 * demand_signal_rules.mjs —— 需求信号判别层（共享规则，唯一真相源）。
 *
 * 被 scripts/demand_scan.mjs（抓取时判别）与 scripts/reflow_demand_signal.mjs
 * （回流对外端点时重判）共同引用。两端共用同一份规则，避免口径漂移。
 *
 * 【20260920 事故 · 为什么必须存在这个文件】
 * ----------------------------------------
 * 旧版 demand_scan.mjs 的 sources[] 里：
 *   - `real_signal: true` 是**写死常量**，不是判定结果；
 *   - `relevance` 写死为「中（需判别是否跨品牌兼容痛点）」，即「待人工判别」，
 *     而人工从未判过；
 *   - 检索词 `robot OR humanoid` + `compatible|replacement|interchange` 无领域
 *     锚定，GitHub 搜索命中 ROCm 的 `MXFP4 GEMM1 replacement`、godot 的
 *     `generators compatible with trimming`、rust 的 `mutually ABI-compatible`、
 *     opencodex 的 `OpenAI-compatible providers` —— 全是软件仓库的 PR。
 *
 * 结果：10 条零机器人语义的软件 PR 以 `real_signal=true` 计入
 * `real_query_count`，并经 deploy 链灌进公开端点 /api/demand-signal，verdict 写成
 * 「已捕获 10 条真实兼容性提问信号」。这是对外的**假陈述**，且每次部署都会
 * 静默重写它。判别层不可判定就默认判真 = fail-open，与本项目「不可判定 → 未知，
 * 绝不默认绿灯」的纪律相反。
 *
 * 本模块确立两条纪律：
 *   1. **fail-closed 三态**：confirmed / unclassified / noise。不可判定 →
 *      unclassified，**绝不默认 true**。unclassified 与 noise 均不计入
 *      real_query_count。
 *   2. **机器人领域锚定**：通用源（GitHub 搜索）的标题必须命中物理硬件锚词
 *      才算 confirmed —— 因为通用源的 "compatible" 在 2026-08 实测里 10/10
 *      指软件语义。领域专属源（机器人论坛）可用「源可信」作加分，退判为
 *      unclassified 而非直接 confirmed：机器人论坛里也有大量非兼容话题。
 *
 * 设计取舍（刻意不做的事）：
 *   - **不用 URL 路径反推仓库性质**。真实机器人讨论的标题里几乎总有
 *     robot/servo/flange 等词；标题无锚词时靠 URL 猜会产生假阳性，方向更差。
 *   - **不做模糊匹配/相似度打分**。锚词白名单可解释、可逐条复核；打分器会让
 *     「为什么判 noise」不可追溯，违反本项目的出处纪律。
 *
 * 用法：
 *   node scripts/lib/demand_signal_rules.mjs --self-test   # 阴阳对照，不联网
 *
 * 闸门：ci_gate.py 第 22 项跑本自测。自测含 2026-08-28 快照真实抓到的 10 条
 * 历史噪声作为**阴性 fixture**，防止将来有人放宽词表把软件 PR 重新算成真信号。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---------------------------------------------------------------- 词表
// 注意：只有需要 .match() 提取全部命中的人才用 g 标志。test() 的正则必须是
// 非全局的 —— 全局正则的 test() 会累积 lastIndex，同一字符串多次 test 结果
// 会交替反转（经典 JS 状态 bug）。

/** 物理机器人/硬件实体锚词：命中即认为标题在谈论实物部件而非软件语义。
 * 保守取高信号词，避免易误伤项（如 `ros` 单独写会命中 "pros"，故用 \bros\b）。 */
const ROBOTIC_ANCHOR_RE = new RegExp([
  // 构型
  'humanoid', 'quadruped', 'bipedal', 'hexapod', 'robot\\b', 'robotic', 'robotics',
  '人形', '四足', '仿生', '机器狗', '机器人',
  // 机械接口
  'end[.\\s-]?effector', 'flange', '\\bpcd\\b', 'iso[.\\s-]?9409', '法兰', '安装孔',
  'joint[.\\s-]?ball', 'shoulder[.\\s-]?joint', 'hip[.\\s-]?joint', 'knee[.\\s-]?joint',
  // 执行器
  'servo', 'actuat', 'harmonic', 'planetary', 'reducer', 'gearbox', '舵机', '减速',
  'stepper', 'steering', 'bl[dm]', '\\bvfd\\b', 'linear[.\\s-]?actuator', '丝杠',
  // 传感/驱动
  'torque[.\\s-]?sensor', 'force[.\\s-]?torque', '\\bfts\\b', 'encod', '\\bimu\\b',
  '\\blidar\\b', 'gripper', '夹爪', 'gimbal',
  // 结构/线缆
  'chassis', 'extrusion', 'aluminum', 'harness', '\\bstl\\b', '\\bdxf\\b', '3d[.\\s-]?print',
  // 协议/生态
  'urdf', 'ros2', '\\bros\\b', 'feetech', 'sts3215', 'sts3210', 'dynamixel', 'so-?arm',
  // 采购
  '\\bmpn\\b', 'bill of materials', '\\bbom\\b',
].join('|'), 'gi');

/** AI/LLM 语境：命中即判 noise —— 这类仓库的 "compatible" 几乎从不指硬件。 */
const AI_CTX_RE = new RegExp([
  'openai', 'chatgpt', 'gpt[-.\\s]?\\d', '\\bclaude\\b', '\\bgemini\\b', '\\bllm\\b',
  'responses\\s+api', 'websocket[.\\s-]?transport', '\\bgemm\\b', '\\bkernel\\b',
  '\\bgpu\\b', '\\bcuda\\b', '[\\(\\[]hip[\\)\\]]', '\\btriton\\b', '\\bvllm\\b',
  '\\binference\\b', '\\bmxfp\\b', '\\bfp16\\b', '\\bfp8\\b', 'completion',
].join('|'), 'i');

/** 软件工程语境：兼容指代码/ABI/依赖/构建，非物理硬件。 */
const SW_CTX_RE = new RegExp([
  '\\bab[io]\\b', 'abi[.\\s-]?compat', 'dotnet', 'godot', 'kibana', '\\bfleet\\b',
  '\\bdocker\\b', '\\bbump\\b', '\\bdependency\\b', 'trimming', 'generators',
  'policy[.\\s-]?icon', 'browser', 'rest[.\\s-]?api', 'upstream',
].join('|'), 'i');

/** 兼容性/替换语义：本层关心的信号类型。 */
const COMPAT_SEM_RE = new RegExp([
  'compat', 'interchang', 'replacement', '\\breplace\\b', '\\bmounting\\b',
  '互[换操]', '兼容', '适配', '替换', '互装', '\\bpcd\\b', 'iso[.\\s-]?9409',
].join('|'), 'i');

/** 跨品牌/混用语义（与旧字段 cross_brand_compat_engine_users 同口径）。
 * 单独定义一次并作为「强兼容语义」并入 COMPAT_SEM 判定 —— 跨品牌混用本身就是
 * 兼容性诉求，不该漏。注意：不能带 g 标志，全局正则的 test() 会累积 lastIndex，
 * 同一字符串多次 test 结果交替反转。
 * 「mixing two brands」这类口语形态中间隔着不定长度文字，故用 {0,15} 窗口。 */
const CROSS_BRAND_RE = /cross[.\s-]{0,3}brand|interoperab|互操作|不同[^\n]{0,6}品牌|different[^\n]{0,15}brand|mix(?:ing|ed|es|t)?[^\n]{0,15}brand/i;

/** 机器人领域专属源：标题可信度更高，无锚词时退判 unclassified 而非 noise。 */
const DOMAIN_SOURCES = new Set(['ros_discourse', 'stack_exchange', 'reddit']);

// ---------------------------------------------------------------- 判别

/** 判别单条信号。纯函数，无副作用，无网络。
 * @param {{title?:string, source?:string, url?:string}} it
 * @returns {{state:'confirmed'|'unclassified'|'noise', basis:string[]}}
 *   state='confirmed' 才计入 real_query_count；其余两种都是 fail-closed 结果。
 */
export function classifySignal(it = {}) {
  const t = String(it.title || '');
  const src = String(it.source || '');
  const basis = [];

  if (!t.trim()) {
    return { state: 'noise', basis: ['标题为空，无法判别'] };
  }

  // 语境排除优先于锚词：软件/AI 仓库标题里偶尔也会出现 "robot"（如
  // "make robot tests compatible"），但语境已足以定性，不该被判成硬件信号。
  if (AI_CTX_RE.test(t)) {
    return { state: 'noise', basis: ['AI/LLM 语境：兼容指 API/推理栈，非物理硬件'] };
  }
  if (SW_CTX_RE.test(t)) {
    return { state: 'noise', basis: ['软件工程语境：兼容指代码/ABI/依赖/构建，非物理硬件'] };
  }

  const anchors = t.match(ROBOTIC_ANCHOR_RE);
  const anchorList = anchors
    ? [...new Set(anchors.map((a) => a.toLowerCase()))].slice(0, 4)
    : [];
  if (anchorList.length) basis.push('硬件锚词命中: ' + anchorList.join(' / '));

  const domainSrc = DOMAIN_SOURCES.has(src);
  if (domainSrc) basis.push('机器人领域专属源');

  // 无兼容性/替换语义 → 不是本层关心的信号类型，不是「未判」。
  // 「跨品牌混用」单独算强兼容语义（见 CROSS_BRAND_RE 注释），避免漏判。
  const compatSem = COMPAT_SEM_RE.test(t) || CROSS_BRAND_RE.test(t);
  if (!compatSem) {
    return { state: 'noise', basis: [...basis, '标题无兼容性/替换语义'] };
  }

  // 有兼容性语义 + 硬件锚词 → 确认
  if (anchorList.length) {
    return { state: 'confirmed', basis };
  }

  // 有兼容性语义但无锚词
  if (domainSrc) {
    return { state: 'unclassified', basis: [...basis, '领域专属源但标题缺硬件锚词，需人工确认'] };
  }
  return { state: 'noise', basis: [...basis, '通用源且无硬件锚词：兼容语义极可能指软件'] };
}

/** 批量判别并聚合计数。 */
export function classifyBatch(items = []) {
  const byState = { confirmed: 0, unclassified: 0, noise: 0 };
  const out = items.map((it) => {
    const { state, basis } = classifySignal(it);
    byState[state] += 1;
    return { ...it, signal_state: state, basis };
  });
  return { byState, out };
}

export const SIGNAL_TYPE_BY_STATE = {
  confirmed: '社区兼容性提问（已锚定机器人硬件语境）',
  unclassified: '兼容性相关（未判：标题缺硬件锚词，需人工确认）',
  noise: '非机器人信号（已按领域锚定过滤）',
};

/** 把判别结果映射为对外 sources[] 结构。
 * 保留旧字段 real_signal（语义 = state==='confirmed'）与 evidence/signal_type，
 * 以免既有消费方静默失效；新增 signal_state 表达三态。 */
export function toPublicSources(classified = []) {
  return classified.map((c) => {
    const title = String(c.title || '');
    return {
      name: c.source || c.name,
      url: c.url || null,
      signal_type: SIGNAL_TYPE_BY_STATE[c.signal_state] || '未判别',
      signal_state: c.signal_state,
      real_signal: c.signal_state === 'confirmed',
      evidence: title,
      relevance: c.basis && c.basis.length ? c.basis.join('；') : '未判别',
      cross_brand: CROSS_BRAND_RE.test(title),
    };
  });
}

/** 生成诚实的对外 verdict。纯函数：confirmed=0 时绝不宣称「真实兼容性提问」。
 * @param {{confirmed:number,unclassified:number,noise:number,aliveSources:number,
 *          totalHits:number,declRatePct:string,selfTest?:boolean}} p
 */
export function buildVerdict(p) {
  const { confirmed, unclassified, noise, aliveSources, totalHits, declRatePct } = p;
  // 契约：declRatePct 应为裸数字串（如 '5.75'）。这里再剥一次 % 作为防御——
  // reflow 曾传已带 % 的串，导致对外 verdict 出现「5.75%%」。
  // 自测当时只传裸串，所以从未暴露：契约不一致的假绿。
  const pctStr = String(declRatePct).replace(/%+$/, '');
  if (aliveSources === 0) {
    return '通道全不可达（UNKNOWN）：本轮监听无法取得真实数据，不推断需求为零。需排查出网或更换数据源。';
  }
  const head = `本轮监听 ${aliveSources} 个可达源、${totalHits} 条命中，经机器人硬件锚定判别：确认兼容性提问 ${confirmed} 条`;
  const tail = `、未判 ${unclassified} 条、判为非机器人信号 ${noise} 条`;
  if (confirmed === 0) {
    return head + tail +
      '。自动抓取通道当前零确认信号——这不等于需求不存在，而是检索词未锚定机器人领域：' +
      '历史版本（2026-08-16/28 快照）曾把 AI/LLM 仓库的 "OpenAI-compatible"、' +
      '"ABI-compatible"、"GEMM replacement" 类 PR 以 real_signal=true 计为真实信号，' +
      '公开端点因此对外宣称了并不存在的 10 条提问。判别层现为三态 fail-closed。' +
      '机械接口声明率 ' + pctStr + '%，即便有提问也多数答不出。';
  }
  return head + tail +
    '。机械接口声明率仅 ' + pctStr + '%，多数今天仍答不出——需求存在，供给（可计算兼容性）不足。';
}

/** 按声明率阈值给「能否答」的诚实估算（与 reflow 的 estimate 同口径）。 */
export function estimateAnswerability(declRate) {
  if (declRate < 0.05) {
    return '极低：跨品牌兼容类提问今天绝大多数答不出。抬声明率的合法通道是厂商 datasheet 补录、' +
      'ISO 9409-1 查表补 A{n} 标准号、以及用户提交带出处的声明——不是批量导入开源 BOM ' +
      '（写入 oss_components.json 不影响本指标的分母 entities.json）。';
  }
  return '部分可答：跨品牌兼容类提问多数仍答不出，仅少数有厂商 datasheet 出处的条目可判。';
}

/** 抬声明率的合法通道清单。单一真相源：demand_scan 与 reflow 共用，避免两处漂移。
 * 旧版曾写「导入真实开源人形 BOM 反喂 ingestion」——那是无效指令：
 * ingest_oss_bom.mjs 写的是 oss_components.json，而声明率的分母是 entities.json，
 * 两条链路不相通。把不可达的路径写成 action item，等于把假解法对外发布。 */
export function buildActionableFixes(declRate) {
  const fixes = [
    '抬机械接口声明率的合法通道：厂商 datasheet 补录、ISO 9409-1 查表补 A{n} 标准号、' +
      '用户提交带出处的声明（add_mechanical_interface.py 写 entities.json）。',
    '不要把开源 BOM 批量导入当成抬本指标的手段：ingest_oss_bom.mjs 写 oss_components.json，' +
      '而本指标的分母是 entities.json，两条链路不相通。',
    '检索侧：GitHub 源的检索词必须锚定机器人领域（限定 repo:、或标题补 flange/servo/PCD 类硬件锚词），' +
      '否则命中会被判别层判为 noise，永不进入 confirmed。',
  ];
  // 只有「当前确实零确认」才提这条：否则会变成对已确认需求的虚假建议。
  // 声明率是硬门槛而非建议值——「无出处不收」纪律（add_mechanical_interface.py 的
  // _curated() 只保留有 source_url 的声明）意味着 50% 不能靠堆量达成，只能靠出处。
  if (declRate !== undefined && declRate < 0.5) {
    fixes.push(
      '先证明需求再投数据采集：当前零确认信号，抬供给前应先证明有真实用户在问；' +
        '且本层「无出处不收」，可答率 50% 只能靠厂商 datasheet 出处逐条登记，不能靠堆量。'
    );
  }
  return fixes;
}

// ---------------------------------------------------------------- 自测

const HISTORICAL_NOISE = [
  ['github', 'feat(core): support live component replacement'],
  ['github', 'Add guided alias activation and replacement workflow'],
  ['github', '[HIP] [FlyDSL] [Kernel] Extend MXFP4 GEMM1 replacement to A4W4'],
  ['github', 'Feature request: opt-in upstream Responses WebSocket transport for OpenAI-compatible providers'],
  ['github', 'feat: stream compatible Chat completions'],
  ['github', 'dotnet: Make GodotSharp and generators compatible with trimming'],
  ['github', '[9.5] fix(fleet): hide version-specific policy icon for compatible agents (#287504)'],
  ['github', '[9.4] fix(fleet): hide version-specific policy icon for compatible agents (#287504)'],
  ['github', 'build(deps): bump astral-sh/uv from 0.12.2 to 0.12.5 in /src/api in the docker-compatible group'],
  ['github', 'declare C and C-unwind as mutually ABI-compatible'],
];

const CONFIRMED_CASES = [
  ['github', 'humanoid robot shoulder joint flange not interchangeable across brands'],
  ['github', 'Can I use an STS3215 servo where the BOM specifies a different brand servo?'],
  ['github', 'ISO 9409-1 flange A50 mounting hole mismatch on arm adapter'],
  ['github', 'Need replacement harmonic drive reducer for quadruped hip joint'],
  ['github', 'force torque sensor replacement recommendation for gripper'],
  ['github', '舵机延长线不兼容，需要替代品'],
  ['reddit', 'flange adapter for mixing two brands of robot arms'],
];

const UNCLASSIFIED_CASES = [
  ['ros_discourse', 'Which versions are compatible with this release?'],
  ['stack_exchange', 'What adapters are compatible with each other?'],
  ['reddit', 'Is there a compatible replacement workflow for my setup?'],
];

function selfTest() {
  let passed = 0;
  const failures = [];
  function check(name, cond, detail = '') {
    if (cond) passed += 1;
    else failures.push(name + (detail ? ' — ' + detail : ''));
  }

  // 阴性对照：历史版本判为 real_signal=true 的 10 条软件 PR 必须全部判 noise
  for (const [src, title] of HISTORICAL_NOISE) {
    const r = classifySignal({ title, source: src });
    check('阴性·历史噪声判为 noise：' + title.slice(0, 46),
      r.state === 'noise', '实判 ' + r.state + '（' + r.basis.join('; ') + '）');
  }
  check('阴性·10 条历史噪声无一被误判为 confirmed',
    HISTORICAL_NOISE.every(([s, t]) => classifySignal({ title: t, source: s }).state !== 'confirmed'));

  // 阳性对照：真信号必须判 confirmed
  for (const [src, title] of CONFIRMED_CASES) {
    const r = classifySignal({ title, source: src });
    check('阳性·真信号判为 confirmed：' + title.slice(0, 46),
      r.state === 'confirmed', '实判 ' + r.state + '（' + r.basis.join('; ') + '）');
  }

  // 未判对照：领域专属源 + 无硬件锚词 → unclassified（不是 true、不是 noise）
  for (const [src, title] of UNCLASSIFIED_CASES) {
    const r = classifySignal({ title, source: src });
    check('未判·领域源无锚词 → unclassified：' + title.slice(0, 44),
      r.state === 'unclassified', '实判 ' + r.state + '（' + r.basis.join('; ') + '）');
  }

  // fail-closed 结构性断言：不存在默认判真的路径
  check('fail-closed·空标题不判 confirmed',
    classifySignal({ title: '', source: 'github' }).state !== 'confirmed');
  check('fail-closed·无兼容语义不判 confirmed',
    classifySignal({ title: 'How to build a robot arm', source: 'github' }).state !== 'confirmed');
  const allCases = [
    ...HISTORICAL_NOISE, ...CONFIRMED_CASES, ...UNCLASSIFIED_CASES,
    ['github', ''], ['github', 'How to build a robot arm'], ['github', 'Random title'],
  ];
  check('fail-closed·所有输入只落在三态内',
    allCases.every(([s, t]) => ['confirmed', 'unclassified', 'noise'].includes(classifySignal({ title: t, source: s }).state)));

  // 批量计数：real_query_count 只计 confirmed
  const mixed = [
    { title: 'humanoid robot shoulder joint flange not interchangeable', source: 'github' },
    { title: 'declare C and C-unwind as mutually ABI-compatible', source: 'github' },
    { title: 'Which versions are compatible with this release?', source: 'ros_discourse' },
  ];
  const { byState } = classifyBatch(mixed);
  check('计数·confirmed=1', byState.confirmed === 1, JSON.stringify(byState));
  check('计数·noise=1', byState.noise === 1, JSON.stringify(byState));
  check('计数·unclassified=1', byState.unclassified === 1, JSON.stringify(byState));
  check('计数·三态之和 = 输入数', byState.confirmed + byState.noise + byState.unclassified === mixed.length);

  // 对外字段：real_signal 与 signal_state 一致，旧字段不丢失
  const pub = toPublicSources(classifyBatch(mixed).out);
  check('字段·real_signal = (state===confirmed)',
    pub.every((p) => p.real_signal === (p.signal_state === 'confirmed')));
  check('字段·保留向后兼容字段 name/url/signal_type/evidence/relevance',
    pub.every((p) => 'name' in p && 'url' in p && 'signal_type' in p && 'evidence' in p && 'relevance' in p));
  check('字段·relevance 不再是写死的「需判别」占位',
    pub.every((p) => !/需判别/.test(p.relevance)));

  // verdict：零确认时不得宣称真实提问
  const v0 = buildVerdict({ confirmed: 0, unclassified: 1, noise: 1, aliveSources: 3, totalHits: 3, declRatePct: '5.75' });
  check('verdict·confirmed=0 时不宣称「真实兼容性提问信号」', !/真实兼容性提问/.test(v0));
  check('verdict·confirmed=0 时明示零确认与历史误判成因',
    /零确认信号/.test(v0) && /real_signal=true/.test(v0));
  check('verdict·confirmed=0 时仍披露声明率', /5\.75%/.test(v0));
  const v1 = buildVerdict({ confirmed: 3, unclassified: 1, noise: 5, aliveSources: 3, totalHits: 9, declRatePct: '5.75' });
  check('verdict·confirmed>0 时保留「需求存在、供给不足」表述',
    /需求存在/.test(v1) && /供给/.test(v1));
  const vUnknown = buildVerdict({ confirmed: 0, unclassified: 0, noise: 0, aliveSources: 0, totalHits: 0, declRatePct: '5.75' });
  check('verdict·通道全不可达 → UNKNOWN 且不推断零需求',
    /UNKNOWN/.test(vUnknown) && /不推断需求为零/.test(vUnknown));

  // 声明率估算文案不得再指向无效的开源 BOM 反喂
  const est = estimateAnswerability(0.0078);
  check('estimate·不宣称开源 BOM 反喂能抬声明率', !/反喂 ingestion/.test(est));
  check('estimate·指出合法通道为 datasheet/ISO/用户提交',
    /datasheet/.test(est) && /ISO 9409-1/.test(est));
  check('estimate·高声明率走另一分支', /部分可答/.test(estimateAnswerability(0.0575)));

  // 防「自测入参格式与真实调用方不一致」造成的假绿：buildVerdict 内部加 %，
  // 调用方必须传纯数字字符串。若有人传已带 % 的串，会出现 %% 这种对外可见的瑕疵。
  check('verdict·无 %% 双百分号（declRatePct 须为纯数字串）',
    !/%%/.test(v0) && !/%%/.test(v1) && !/%%/.test(vUnknown));

  // 阳性对照：模拟 reflow 的真实事故（传入已带 % 的串），证明防御性剥离生效
  const vPctSuffix = buildVerdict({ confirmed: 0, unclassified: 1, noise: 1, aliveSources: 3, totalHits: 3, declRatePct: '5.75%' });
  check('verdict·调用方误传带 % 的串也不会出现 %%', !/%%/.test(vPctSuffix));
  check('verdict·误传带 % 时仍保留正确的百分号', /声明率 5\.75%/.test(vPctSuffix));

  const fixes = buildActionableFixes();
  check('fixes·不宣称开源 BOM 反喂 ingestion', !fixes.some((f) => /反喂 ingestion/.test(f)));
  check('fixes·指出合法通道 datasheet / ISO 9409-1 / 用户提交',
    /datasheet/.test(fixes.join('')) && /ISO 9409-1/.test(fixes.join(''))
      && /用户提交/.test(fixes.join('')));
  check('fixes·明示两条链路不相通', /oss_components\.json/.test(fixes.join('')));
  check('fixes·指出检索侧须锚定机器人领域', /锚定机器人领域/.test(fixes.join('')));

  // 条件项：只在「零确认 + 声明率<50%」时追加，避免对已有确认需求误发建议
  check('fixes·declRate 缺省不追加条件项', fixes.length === 3);
  const fixesLow = buildActionableFixes(0.0575);
  check('fixes·低声明率追加「先证明需求」条件项', fixesLow.length === 4);
  check('fixes·条件项指出「先证明需求再投数据采集」',
    /先证明需求/.test(fixesLow[3]) && /无出处不收/.test(fixesLow[3]));
  const fixesHigh = buildActionableFixes(0.6);
  check('fixes·高声明率不追加「先证明需求」（已可答，不该再说缺需求）',
    fixesHigh.length === 3);

  printResult('需求信号判别层（demand_signal_rules）', passed, failures);
}

function printResult(label, passed, failures) {
  console.log(`\n[${label}]`);
  if (failures.length) {
    console.log(`  ❌ ${failures.length} 项未通过（通过 ${passed} 项）`);
    for (const f of failures) console.log('     - ' + f);
    process.exit(1);
  }
  console.log(`  ✅ 全部通过（${passed} 项，含 ${HISTORICAL_NOISE.length} 条历史噪声阴性对照）`);
}

// ---------------------------------------------------------------- CLI

const argv = process.argv.slice(2);
const isMain = process.argv[1]
  && path.resolve(process.argv[1]) === __filename;

if (isMain) {
  if (argv.includes('--self-test')) {
    selfTest();
  } else if (argv.includes('--smoke')) {
    // 最小烟囱：确认模块可被 import 且判别可用
    const r = classifySignal({ title: HISTORICAL_NOISE[2][1], source: 'github' });
    console.log(JSON.stringify({ ok: true, sample_state: r.state, sample_basis: r.basis }));
  } else {
    console.log('用法：node scripts/lib/demand_signal_rules.mjs --self-test|--smoke');
    process.exit(2);
  }
}

export { HISTORICAL_NOISE, CONFIRMED_CASES, UNCLASSIFIED_CASES, CROSS_BRAND_RE, DOMAIN_SOURCES };
