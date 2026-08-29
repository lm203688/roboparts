/**
 * RoboParts 兼容性裁决引擎 —— 唯一实现（Single Source of Truth）
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 【20260806-00 提取重构 · 勿再复制这段逻辑】
 *
 * 背景：本轮新建 hosted MCP 端点 /mcp 时，最省事的做法是把 mcp-server/index.js
 *       里那套 700 行 checkCompatibility 抄进 Worker。那会造成**三份**兼容性实现：
 *         1. functions/api/compatibility.js（四维规则引擎，真实体字段）
 *         2. mcp-server/index.js（npm 包内的另一套 if/else 规则）
 *         3. 新的 /mcp
 *       同一个问题给出三个不同答案，且不会有任何报错 —— 这正是"假绿"的高阶形态：
 *       每一份自己都跑得通，只有用户会发现我们前后矛盾。
 *
 * 决策：把裁决逻辑提取到本文件，/api/compatibility 与 /mcp 都 import 它。
 *       今后新增任何通道（GraphQL、gRPC、第二个 MCP 目录）一律复用，不得另写。
 *
 * ⚠️ 不变式（regression.py L1.16 守护）：
 *    - functions/api/compatibility.js 与 functions/mcp.js 都必须 import 本文件
 *    - 两者都不得自带 evalDimension / parseVoltageRange 的本地副本
 * ─────────────────────────────────────────────────────────────────────────
 */

/** 四个裁决维度（顺序即对外输出顺序，改动会影响下游消费者） */
export const DIMENSIONS = ['protocol', 'electrical', 'mechanical', 'software'];
/** 硬兼容约束维度：判定 overall=true 至少需其中一项有双方声明 */
export const HARD_DIMENSIONS = ['protocol', 'electrical', 'mechanical'];

/**
 * 【P0 · 20260815】多因子兼容度评分权重与可解释折算。
 *
 * 借鉴开源制造零件兼容引擎 asset-intelligence-graph-rag 的「多因子加权 + 可解释」
 * 思想（其 final_score = 0.35*机械 + 0.25*功能 + 0.25*语义 + 0.15*层级）。
 * 本引擎实为四维（protocol/electrical/mechanical/software），按"决定性"映射权重：
 *   mechanical 0.35 ← 物理接口，孔位级最决定性（对应 graph-rag 的机械）
 *   protocol   0.25 ← 功能/通信接口（对应 graph-rag 的功能）
 *   electrical 0.25 ← 电气接口
 *   software   0.15 ← ROS2 生态，最弱（对应 graph-rag 的层级/软性约束）
 * 权重之和恒为 1；调参只改此处，不动逻辑。
 *
 * 不变式（与三态诚实口径一致）：
 *   · 仅"已裁决"（compatible !== null）的维度参与加权；
 *   · null（无法判定）维度既不进分子也不进分母 —— 不把"不知道"伪装成结论；
 *   · 整体无法判定（overall=null）时分数一律 null（见 judgePair）。
 */
export const SCORE_WEIGHTS = {
  mechanical: 0.35,
  protocol: 0.25,
  electrical: 0.25,
  software: 0.15,
};

/**
 * 把四维裁决结果折算成多因子加权分 + 可解释分解。
 * @param {Array<{dimension:string, compatible:boolean|null, relation?:string}>} dimensions
 * @returns {{weights:object, breakdown:Array, method:string, weight_sum_decided:number, weighted_score:number|null}}
 */
export function scoreBreakdown(dimensions) {
  const breakdown = dimensions.map(d => {
    const w = SCORE_WEIGHTS[d.dimension] ?? 0;
    const decided = d.compatible !== null;
    const s = decided ? (d.compatible ? 1 : 0) : null;
    return {
      dimension: d.dimension,
      weight: w,
      verdict: d.compatible === true ? 'compatible' : d.compatible === false ? 'conflict' : 'undecided',
      score: s,
      contribution: decided ? +(w * s).toFixed(4) : null,
    };
  });
  const decidedParts = breakdown.filter(b => b.contribution !== null);
  const weightSum = decidedParts.reduce((acc, b) => acc + b.weight, 0);
  const contribSum = decidedParts.reduce((acc, b) => acc + b.contribution, 0);
  return {
    weights: { ...SCORE_WEIGHTS },
    breakdown,
    method: '多因子加权：score = Σ(weight_i × s_i) / Σ(weight_i)，仅"已裁决"维度计入；'
          + 's_i ∈ {1 兼容, 0 冲突}；未裁决(null)维度不进分子也不进分母；'
          + '整体无法判定(overall=null)时分数置 null',
    weight_sum_decided: +weightSum.toFixed(4),
    weighted_score: weightSum > 0 ? Math.round(contribSum / weightSum * 100) : null,
  };
}

export function parseVoltageRange(str) {
  if (!str) return null;
  const s = String(str);
  const range = s.match(/([\d.]+)\s*[~\-]\s*([\d.]+)\s*V/i);
  if (range) return { min: parseFloat(range[1]), max: parseFloat(range[2]) };
  const single = s.match(/([\d.]+)\s*V/i);
  if (single) { const v = parseFloat(single[1]); return { min: v, max: v }; }
  return null;
}

export function tokens(item) {
  return [
    item.protocol,
    item.interface,
    Array.isArray(item.interfaces) ? item.interfaces.join('/') : '',
  ].filter(Boolean).join(' ').toLowerCase();
}

export function overlap(a, b) {
  return a && b && a.min <= b.max && b.min <= a.max;
}

/**
 * 协议词表（含 bom/check.js 合并前独有的 ttl/dynamixel，勿删）。
 * 20260806-08 扩充：此前 154 条有协议文本的实体中 60 条不被识别，会被误报成
 * "厂商未声明"，让真冲突（如 CAN vs Ethernet）逃逸成"无法判定"，进而抬成 true。
 * 长词必须排在其子串之前（ethercat 先于 can、ethernetip 先于 ethernet），
 * 否则 includes 会先命中短词导致误判。
 */
export const PROTOCOL_VOCAB = [
  'ethercat', 'ethernetip', 'ethernet/ip', 'profinet', 'powerlink', 'io-link', 'iolink',
  'canopen', 'can', 'rs485', 'rs232', 'modbus', 'flexray', 'lin',
  'spi', 'i2c', 'uart', 'usb', 'pcie', 'mipi', 'ros2', 'ttl', 'dynamixel',
  'ethernet', 'udp', 'tcp', 'wifi', 'bluetooth', 'zigbee', 'analog',
  'proprietary',
];
/**
 * 「已声明但不构成互通证据」的取值。proprietary 是典型：Tesla 的专有总线与
 * Figure 的专有总线都写作 proprietary，字面相同却绝不互通。它算"有声明"
 * （因此不落入 null），但不得作为 shared 依据 —— 否则等于用假绿换假红。
 */
export const NON_SHAREABLE_PROTOCOLS = ['proprietary'];

/**
 * 协议蕴含关系：键命中时同时贡献值。仅收录物理层确定互通的情形。
 * CANopen 是 CAN 之上的应用层，物理层可同线；而 EtherCAT/PROFINET 虽基于以太网
 * 物理层却不能与普通 Ethernet 设备互通，故**刻意不建立**到 ethernet 的蕴含 ——
 * 宁可判"无交集"，不可编造互通。
 */
export const PROTOCOL_IMPLIES = { canopen: ['can'] };

/**
 * 词表匹配必须按词边界，不能用裸 includes：
 *   'io-link' 与 'powerlink' 都含子串 'lin'，裸 includes 会让 IO-Link 设备
 *   与 LIN 总线设备"共享协议 lin"，凭空造出一个假绿。
 * 中文词（法兰/连接器/轴）无 ASCII 边界，退回 includes。
 */
export function matchVocab(raw, vocab) {
  const hit = new Set();
  for (const p of vocab) {
    const ascii = /^[\x20-\x7e]+$/.test(p);
    let ok;
    if (ascii) {
      const esc = p.replace(/[.*+?^${}()|[\]\\/-]/g, '\\$&');
      ok = new RegExp('(^|[^a-z0-9])' + esc + '($|[^a-z0-9])', 'i').test(raw);
    } else {
      ok = raw.includes(p);
    }
    if (ok) {
      hit.add(p);
      (PROTOCOL_IMPLIES[p] || []).forEach(x => hit.add(x));
    }
  }
  return [...hit];
}
/** 机械接口词表（含 check.js 独有的 standard，勿删） */
export const MECH_VOCAB = ['flange', '法兰', 'm8', 'm12', 'db9', 'connector', '连接器', 'shaft', '轴', 'standard'];

/**
 * 抽取一方在某维度上的证据：{ raw, matched }。
 *   matched 为空 → 不可判定。但空的原因有两种，必须分开陈述：
 *     · raw 也为空  → 厂商确实没给数据（数据缺口，靠采集补）
 *     · raw 非空    → 我方词表不认识这个取值（能力边界，靠扩词表补）
 *   把后者说成"厂商未声明"是把自己的短板记在对方账上。
 */
export function protocolEvidence(item) {
  const raw = tokens(item).trim();
  return { raw, matched: matchVocab(raw, PROTOCOL_VOCAB) };
}

/**
 * 机械接口的**身份键**：只有这两个字段编码了节圆直径/孔数/螺纹规格，
 * 两侧取值相同才构成"孔位级能对上"的证据。
 *
 * 【20260809-02】mount_type 曾被并列当作身份键，这是假绿。
 * mount_type 是**安装方式的分类描述**（direct_mount / flange_mount / shaft_mount…），
 * 描述的是"怎么装"，不是"装在什么接口上"。两件东西同为 direct_mount，
 * 只说明它们都不需要转接件，完全不蕴含彼此的孔位能对上。
 * 实测：宇立 C025XX × C075XX 两个六维力传感器，双方 standard/flange 均为 null、
 * 仅 mount_type=direct_mount，引擎输出 `compatible: true / 共享机械接口: direct_mount`,
 * 并作为**硬约束**支撑了 overall=true —— 而这两条记录自己的 gap 字段就白纸黑字写着
 * 「缺法兰节圆/孔数/螺纹规格，无法做孔位级互换判定」。数据层诚实声明了判不了，
 * 引擎把它渲染成了肯定结论。
 *
 * 爆炸半径不在今天而在明天：全库 248865 个配对里现在只有 1 例（因 366 条的
 * mount_type 恰好都还是 'unknown' 被过滤掉了）。但 mount_type 是所有字段里**最好填**的
 * 一个（看一眼产品页就能写），而 flange/standard 要翻datasheet。补数据活动必然
 * 优先填出一大批"有 mount_type、无法兰规格"的记录 —— 实测反事实：仅把 100 条填成
 * flange_mount 就产生 4951 个假绿。故必须在补数据之前先修这里。
 */
const MECH_IDENTITY_FIELDS = ['standard', 'flange'];

/**
 * 【20260809-12】身份键取值归一化：单值与多值同权。
 *
 * "一个零件只对应一种孔位"在这个行业是少数派。夹爪 / 工具快换盘 / 转接板普遍
 * 靠更换耦合件适配多种法兰 —— Robotiq 2F-85 官方手册（6. Specifications）就列了
 * 6 种耦合件，覆盖 ISO 9409-1 的 50-4-M6、31.5-4-M5、40-4-M6 以及 PCD56/PCD60
 * 等非 ISO 孔位。这类"一对多"恰恰是选型时最需要判定的形态。
 *
 * 旧实现对数组直接 String(v)，得到 "a,b,c" 这**一个**永远无法与任何单值相交的
 * 伪 token。后果不是判不了，而是**判错**：明明把 50-4-M6 写进了集合的夹爪，
 * 与 50-4-M6 的手腕被判 compatible=false「机械接口无交集」。
 * 把装得上说成装不上，比不给结论更有害 —— 它会让采购方错过正确选项，
 * 且带着"有数据支撑"的可信外观。故在补机械数据之前必须先修这里。
 */
/**
 * 【20260811-09】身份键的**书面形式归一化**：同一个接口被写成两种样子，不得判成"装不上"。
 *
 * 旧实现只做 `trim().toLowerCase()`，于是纯粹的排版差异会直接落进"无交集"分支：
 *   · `ISO 9409-1-50-4-M6` vs `ISO9409-1-50-4-M6`（有无空格）→ compatible=**false**
 *   · PDF 复制常见的非断字连字符 `‑`(U+2011) / 全角空格 → 同样 false
 * 这是 20260809-12（数组被 String() 成伪 token）同一族的**假红**：把装得上说成装不上，
 * 比"判不了"更有害——它带着"有数据支撑"的外观让采购方排除掉正确选项。
 *
 * 本函数只做**词法**归一化（大小写 / 空白 / 连字符变体），不做任何语义合并：
 * 归一化后仍不相等的两个 token，一律不在这里被判定为同一接口。
 * 语义等价（例如带 A 与不带 A 的编码是否同一尺寸）属另一层，见 evalDimension
 * 的 undecided_designation_form 分支——那里给的是"判不了"，不是"相等"。
 */
export function normalizeMechToken(s) {
  return String(s)
    // Unicode 连字符族（‐‑‒–—―−）统一成 ASCII '-'
    .replace(/[\u2010-\u2015\u2212]/g, '-')
    // 全角空格 / 不断行空格 / 常规空白全部去掉（编码内部的空格无语义）
    .replace(/[\s\u00a0\u3000]+/g, '')
    .toUpperCase();
}

/**
 * ISO 9409-1 法兰指定解析。仅识别本标准的编码形态，不认识的返回 null（不猜）。
 * 尺寸段允许一个可选字母前缀（现实中见到 `A50`），该字母**原样保留在 form 里**，
 * 由调用方决定怎么处理——本函数不替标准裁决 A 与无 A 是否等价。
 */
export function parseIsoFlange(token) {
  const m = /^ISO9409-1-([A-Z]?)(\d+(?:\.\d+)?)-(\d+)-(M\d+(?:\.\d+)?)$/.exec(normalizeMechToken(token));
  if (!m) return null;
  return { form: m[1] || '', d1: parseFloat(m[2]), bolts: parseInt(m[3], 10), thread: m[4] };
}

function geomKey(p) {
  return `${p.d1}|${p.bolts}|${p.thread}`;
}

function idValues(v) {
  return (Array.isArray(v) ? v : [v])
    .filter(x => x !== null && x !== undefined)
    .map(x => normalizeMechToken(x))
    .filter(x => x && x !== 'UNKNOWN');
}

/**
 * 【20260811-03】工具侧身份键：零件**向下游暴露**的接口，与安装侧是两回事。
 *
 * 现有 standard / flange 记录的一律是**机器人侧（安装侧）**——把自己装到上游法兰
 * 上用的孔位。这不是推测：Robotiq FT 300-S 官方手册 §5.5 写明
 * "All Robotiq couplings and adapter plates are provided with necessary hardware for
 * fixation on the Robotiq device side / robot side screws and dowel pins are not provided"，
 * 即 ISO 9409-1-50-4-M6 描述的是**耦合件↔机器人法兰**那一对；而同厂快速安装指南
 * 里传感器装到耦合件上用的是 **M4** 螺钉（"Mount the Force Torque Sensor on the
 * mechanical coupling … insert the M4 screws"），根本不是 50-4-M6。
 *
 * 两个零件的机器人侧取值相同，只证明**它们能装在同一个法兰上（可互换）**，
 * 完全不蕴含**它们能彼此对接（可堆叠）**。后者要求一方的工具侧 == 另一方的机器人侧。
 */
const MECH_TOOL_IDENTITY_FIELDS = ['tool_side', 'tool_side_flange'];

export function mechanicalEvidence(item) {
  // 结构化 mechanical_interface 优先：not_declared / n_a 是数据层显式标注的缺口
  // （meta.mechanical_interface_coverage 里 fill_pct 仅 0.57%，绝大多数落此分支），
  // 它表示"厂商未公开"，不表示"接口不匹配"。
  const mi = item.mechanical_interface;
  if (mi && typeof mi === 'object') {
    const st = String(mi.status || '').toLowerCase();
    if (st === 'not_declared' || st === 'n_a') return { raw: '', matched: [], robot: [], tool: [] };
    // 多值展开为多个 token 后去重：集合与集合按交集判定，单值是集合的退化情形。
    const idKeys = [...new Set(MECH_IDENTITY_FIELDS.flatMap(k => idValues(mi[k])))];
    const toolKeys = [...new Set(MECH_TOOL_IDENTITY_FIELDS.flatMap(k => idValues(mi[k])))];
    // 有身份键才允许进入交集比对。刻意**不看 status 标签**：判据锚在
    // "有没有可比对的规格"这一行为事实上，而不是 partial/declared 这类
    // 人工标注的口径 —— 标签会写错，字段有没有值不会。
    if (idKeys.length || toolKeys.length) {
      return {
        raw: idKeys.join(' '),
        matched: idKeys,        // 向后兼容：matched 恒为**机器人侧**集合
        robot: idKeys,
        tool: toolKeys,
        // 只给了工具侧、没给安装侧：能不能对接要看**对方**的安装侧，
        // 而"能不能互换"在本方安装侧未声明时就是判不了 —— 不许塌成 false（假红）。
        toolOnly: idKeys.length === 0 && toolKeys.length > 0 ? toolKeys.join('/') : undefined,
      };
    }
    // 声明了非身份键（如 mount_type）却没有身份键：判不了。
    // 且要与"我方词表不认识"区分开 —— 这是厂商没给决定性字段，属数据缺口。
    const weak = [mi.mount_type]
      .filter(v => v && String(v).toLowerCase() !== 'unknown')
      .map(v => String(v).toLowerCase());
    if (weak.length) return { raw: '', matched: [], robot: [], tool: [], weak: weak.join('/'), gap: mi.gap || null };
    return { raw: '', matched: [], robot: [], tool: [] };
  }
  const raw = tokens(item).trim();
  // 【20260811-09】自由文本命中的词也必须落进**同一个归一化命名空间**，否则
  // 结构化侧（已归一化为大写）与自由文本侧（词表为小写）永远交不上 ——
  // 修一处假红顺手造另一处假红，是本项目栽过的老坑（L1.23 反噬）。
  const m = matchVocab(raw, MECH_VOCAB).map(x => normalizeMechToken(x));
  // 自由文本里的接口词没有侧别信息，按**安装侧**处理（历史口径），tool 留空 ——
  // 留空意味着"对接关系不可判定"，而不是"不能对接"。
  return { raw, matched: m, robot: m, tool: [] };
}

/** 生成"为什么判不了"的说明，并区分数据缺口与我方能力边界 */
function inconclusiveNote(a, b, ea, eb, what) {
  const side = (x, e, dflt) => {
    if (e.matched.length) return null;
    const nm = (x && x.name) ? x.name : dflt;
    // 第三种"判不了"：声明了非决定性属性（如只给安装方式，不给法兰规格）。
    // 既不该说成"未声明"（对方确实给了东西），也不该说成"我方词表不认识"
    // （我们认识 direct_mount，只是它不足以判定）。据实说是哪一格缺。
    // 第四种"判不了"：只声明了**工具侧**（向下游暴露的接口），没声明自己怎么装上去。
    // 这既不是"未声明"，也不是"词表不认识"，而是**侧别不齐**。
    if (e.toolOnly) {
      return `${nm} 仅声明工具侧接口「${e.toolOnly}」，未声明自身安装侧规格（缺一侧，判不了互换）`;
    }
    if (e.weak) {
      return `${nm} 仅声明安装方式「${e.weak}」，未给法兰/接口标准规格`
        + (e.gap ? `（厂商侧缺口：${String(e.gap).slice(0, 40)}）` : '（缺可比对的接口标识，判不了孔位级互换）');
    }
    return e.raw
      ? `${nm} 声明了「${e.raw.slice(0, 40)}」但不在可比对${what}词表内（我方能力边界，非厂商缺数据）`
      : `${nm} 未声明${what}`;
  };
  const parts = [side(a, ea, 'A'), side(b, eb, 'B')].filter(Boolean);
  return parts.join('；') + '，无法判定（无数据 ≠ 不兼容）';
}

export function evalDimension(name, a, b) {
  switch (name) {
    case 'protocol': {
      const ea = protocolEvidence(a), eb = protocolEvidence(b);
      // 任一方无协议声明 → 不可判定。此前直接 shared.length > 0，把"没数据"输出成
      // "不兼容"（假红），与 electrical/software 两个维度的三态口径自相矛盾。
      if (!ea.matched.length || !eb.matched.length) {
        return { compatible: null, score: 0, notes: inconclusiveNote(a, b, ea, eb, '通信协议') };
      }
      const shared = ea.matched.filter(p => eb.matched.includes(p) && !NON_SHAREABLE_PROTOCOLS.includes(p));
      if (shared.length) {
        return { compatible: true, score: 1, notes: '共享协议: ' + shared.join('/') };
      }
      const bothProprietary = ea.matched.includes('proprietary') && eb.matched.includes('proprietary');
      return {
        compatible: false,
        score: 0,
        notes: bothProprietary
          ? '双方均为专有总线，字面相同不代表互通，需厂商网关'
          : `协议无交集（${ea.matched.join('/')} vs ${eb.matched.join('/')}）`,
      };
    }
    case 'electrical': {
      const va = parseVoltageRange(a.voltage), vb = parseVoltageRange(b.voltage);
      if (!va || !vb) return { compatible: null, score: 0, notes: '一方或双方无电压数据，无法判定' };
      const ok = overlap(va, vb);
      return {
        compatible: ok,
        score: ok ? 1 : 0,
        notes: ok ? `电压区间重叠 (${va.min}-${va.max}V / ${vb.min}-${vb.max}V)` : '电压区间不重叠',
      };
    }
    case 'mechanical': {
      const ea = mechanicalEvidence(a), eb = mechanicalEvidence(b);
      // 同 protocol：库内绝大多数实体 status=not_declared / n_a（占比现算，见
      // meta.mechanical_interface_coverage —— 此处刻意不写死数字，旧注释里的
      // 「688 条中 348 条」在库涨到 706 后就成了假话）。
      // 若把它们判成 false，等于把"厂商未公开"渲染成"装不上"。
      if (!ea.matched.length || !eb.matched.length) {
        return { compatible: null, score: 0, notes: inconclusiveNote(a, b, ea, eb, '机械接口') };
      }
      // 【20260811-03】一个布尔值不能同时承担两种物理关系。
      //   · 可对接 (mateable)      : 一方的**工具侧** == 另一方的**机器人侧** → 能堆在一起用
      //   · 同侧一致 (interchangeable): 双方的**机器人侧**相同 → 能装在同一法兰上，可互换
      // 旧实现只做后者的集合求交，却把结论渲染成"共享机械接口"，被 BOM 检查器
      // 与 MCP 调用方读成"这两件能一起用"。今天库里只有一对有身份键的实体（且恰好
      // 真能堆叠），所以还没炸；但补数据是既定路线，届时**每一对同法兰工具件**
      // （两只夹爪、两个传感器）都会输出 compatible:true —— 夹爪装不到夹爪上。
      // 假绿会随数据覆盖率线性增长，必须在补数据之前先把两种关系分开。
      const mate = [
        ...ea.tool.filter(p => eb.robot.includes(p)),
        ...eb.tool.filter(p => ea.robot.includes(p)),
      ];
      const sharedMate = [...new Set(mate)];
      if (sharedMate.length) {
        return {
          compatible: true,
          score: 1,
          relation: 'mateable',
          notes: '可直接对接: 一方工具侧与另一方安装侧一致 (' + sharedMate.join('/') + ')',
        };
      }
      const shared = ea.robot.filter(p => eb.robot.includes(p));
      if (shared.length) {
        return {
          compatible: true,
          score: 1,
          relation: 'interchangeable',
          // 措辞必须把关系类型讲死：这是"可互换"，不是"可对接"。
          // 对接与否取决于工具侧接口，双方都没声明就是判不了，不许默认成立。
          notes: '安装侧接口一致: ' + shared.join('/')
            + ' —— 二者可装在同一法兰上（可互换选型）；能否彼此对接需一方声明工具侧接口，双方均未声明，对接关系不判定',
        };
      }
      // 【20260811-09】编码"尺寸段一致、书写形式不同"→ 判不了，不许判 false。
      //
      // 现实里同一个法兰有两种在用写法：OEM 一手手册（Universal Robots、Robotiq）写
      // `ISO 9409-1-50-4-M6`，第三方集成商汇编写 `ISO9409-1-A50-4-M6`。两者尺寸段
      // （节圆 / 孔数 / 螺纹）逐位相同，只差一个字母前缀。
      // 本平台**未持有 ISO 9409-1:2004 原文**，无从判定该字母是同义写法还是型式区分：
      //   · 判 true  → 凭空断言等价，可能把两种不同型式合并（假绿，且是孔位级结论）；
      //   · 判 false → 把很可能装得上的说成装不上（假红，采购方据此排除正确选项）。
      // 两个方向都是替标准做裁决。诚实结论只有第三种：**据此判不了**，并把分歧讲清楚。
      // 与登记表 `/api/mechanical_interfaces.json` 的口径一致（那里两种写法互为 aliases，
      // 但同样声明不裁决孰为标准原文写法）。
      const formClash = [];
      for (const ta of [...ea.robot, ...ea.tool]) {
        const pa = parseIsoFlange(ta);
        if (!pa) continue;
        for (const tb of [...eb.robot, ...eb.tool]) {
          const pb = parseIsoFlange(tb);
          if (!pb) continue;
          if (geomKey(pa) === geomKey(pb) && pa.form !== pb.form) formClash.push(`${ta} vs ${tb}`);
        }
      }
      if (formClash.length) {
        return {
          compatible: null,
          score: 0,
          relation: 'undecided_designation_form',
          notes: `ISO 9409-1 编码的尺寸段一致但书写形式不同（${[...new Set(formClash)].join('；')}）`
            + '：带字母前缀与不带前缀是否指同一接口，须以 ISO 9409-1 标准原文为准，本平台未持有原文，'
            + '故不判定（不判"不兼容"以免把装得上的排除掉，也不判"兼容"以免凭空断言等价）',
        };
      }
      return {
        compatible: false,
        score: 0,
        relation: 'none',
        notes: `机械接口无交集（安装侧 ${ea.robot.join('/') || '—'} vs ${eb.robot.join('/') || '—'}`
          + (ea.tool.length || eb.tool.length ? `；工具侧 ${ea.tool.join('/') || '—'} vs ${eb.tool.join('/') || '—'}` : '')
          + '）',
      };
    }
    case 'software': {
      // 【20260806-12】布尔维度的三态整体缺失：旧写法 `x.ros_support === true`
      // 把「未声明」与「声明为 false」压成同一个 false，于是任一未声明组件
      // 与 ROS2 组件配对即判「不兼容」，并附带一句事实错误的告警
      // 「双方均有声明且不匹配」。数据集 688 个实体中有 614 个（89%）未声明该字段，
      // 全部落入此路径 —— 这正是 20260806-08 修 protocol/mechanical 时漏掉的同一个 bug：
      // 字符串维度靠「空串 = 未声明」天然区分，布尔维度没有这层保护。
      // 判 false 的唯一合法前提仍是：双方都有声明，且确实冲突。
      const da = typeof a.ros_support === 'boolean';
      const db = typeof b.ros_support === 'boolean';
      if (!da && !db) return { compatible: null, score: 0, notes: '双方均未声明 ROS2 支持，无法判定（无数据 ≠ 不兼容）' };
      if (!da || !db) {
        const who = !da ? (a.name || a.id || 'A') : (b.name || b.id || 'B');
        return { compatible: null, score: 0, notes: `${who} 未声明 ROS2 支持，无法判定（无数据 ≠ 不兼容）` };
      }
      if (a.ros_support && b.ros_support) return { compatible: true, score: 1, notes: '双方均原生支持 ROS2' };
      if (!a.ros_support && !b.ros_support) return { compatible: true, score: 1, notes: '双方均明确不支持 ROS2，无 ROS2 生态冲突' };
      return { compatible: false, score: 0, notes: '双方均有声明：仅一方支持 ROS2，混合使用需额外驱动' };
    }
    default:
      return { compatible: null, score: 0, notes: '未知维度' };
  }
}

/**
 * 对两个实体做完整裁决。
 *
 * 【诚实边界 —— 与 llms.txt / parameter_semantics 同一套口径，不得弱化】
 * 本引擎读的是各厂商**自行声明**的字段，不是实测。未声明即 null（"无法判定"），
 * undecided 数量对外透出，让调用方自己判断这个结论有多少证据支撑。
 *
 * 不变式是**双向**的，两边都不许走：
 *   · null → true  ：假绿。把"没数据"说成"兼容"，凑高分。
 *   · null → false ：假红。把"厂商未公开"说成"装不上"，让调用方排除掉实际可用的组合。
 * 20260806-08 修复前，protocol/mechanical 两个维度只实现了防假绿的一半，
 * 用 `shared.length > 0` 直接二值化，于是 348 条 not_declared 的机械接口
 * 被逐一判成"不兼容"，还进了 BOM 检查器的 warnings 推给用户。
 * 判 false 的唯一合法前提：**双方都有该维度的声明，且确实无交集**。
 */
/**
 * 只有 entity_kind === 'component' 的条目才是"有物理接口、可被判定"的对象。
 * 缺字段（老数据）按 component 处理 —— 宁可判定，不可静默把真零件挡在门外。
 */
export const JUDGEABLE_KIND = 'component';
export function nonJudgeableKind(e) {
  const k = e && e.entity_kind;
  return k && k !== JUDGEABLE_KIND ? k : null;
}
const KIND_LABEL = {
  organization: '企业/机构主体条目',
  market_intelligence: '市场情报（报告/专利地图）条目',
  specification: '接口/协议规范条目',
  software: 'AI 模型 / 软件条目',
};
// 【20260809-05】不同种类"不可判定"的原因不同，一句通用话会把话说歪。
// 尤其 specification：说「EtherCAT 未声明通信协议」荒谬 —— 它**本身就是**协议；
// 用户真正想问的是「某零件是否支持 EtherCAT」，这是可答的，只是问法不同。
// 所以类型闸不只拒绝，还要把正确问法交回去，否则调用方只会换个 ID 再撞一次。
const KIND_WHY = {
  organization: '没有物理接口',
  market_intelligence: '不描述具体型号',
  specification: '是规范本身而非实现它的零件，规范之间不存在"装不装得上"',
  software: '不存在机械与电气接口',
};
const KIND_HINT = {
  specification: '若要问「某零件是否支持该规范」，请以零件为操作数，读其 protocol / interface / compatibility 字段',
  software: '若要问「某算力平台能否跑该模型」，属算力与框架适配问题，不在本引擎的四维硬件兼容范畴',
};

export function judgePair(a, b) {
  // ── 类型闸（20260809-03）───────────────────────────────────────────────
  // 旧行为：把企业主体（如「Figure AI」，type=人形机器人公司）当零件送进四维裁决，
  // 输出「Figure AI 未声明通信协议，无法判定（无数据 ≠ 不兼容）」。
  // overall 确实是 null，所以从不报错 —— 但这句话把**类型错误**说成了**数据缺口**，
  // 等于告诉用户"这家公司只是参数没填全，补上就能判"。公司没有法兰，永远补不上。
  // 正确回答是：这个条目根本不构成可判定对象。
  const ka = nonJudgeableKind(a);
  const kb = nonJudgeableKind(b);
  if (ka || kb) {
    const parts = [];
    if (ka) parts.push(`${a.name}（${KIND_LABEL[ka] || ka}）${KIND_WHY[ka] || '不是实物零部件'}`);
    if (kb) parts.push(`${b.name}（${KIND_LABEL[kb] || kb}）${KIND_WHY[kb] || '不是实物零部件'}`);
    const hints = [...new Set([ka, kb].filter(Boolean).map(k => KIND_HINT[k]).filter(Boolean))];
    const note = `${parts.join('；')}，不构成兼容性判定对象`
               + (hints.length ? `。${hints.join('；')}` : '');
    return {
      a: { id: a.id, name: a.name, category: a.category, entity_kind: a.entity_kind },
      b: { id: b.id, name: b.name, category: b.category, entity_kind: b.entity_kind },
      dimensions: DIMENSIONS.map(d => ({
        dimension: d, compatible: null, score: 0, notes: note,
      })),
      overall_compatible: null,
      compatibility_score: null,
      score_basis: null,
      applicable: false,
      verdict_reason: note,
      decided_dimensions: 0,
      undecided_dimensions: DIMENSIONS.length,
      hard_dimensions_decided: 0,
      source: 'rule-engine (real entity fields)',
      evidence_basis: '操作数类型不适用：本引擎只裁决 entity_kind=component 的实物零部件；'
                    + '接口/协议规范、AI 模型与软件、企业主体、市场情报条目均保留在库供检索，'
                    + '但不参与兼容性判定',
    };
  }

  const dimensions = DIMENSIONS.map(d => {
    const r = evalDimension(d, a, b);
    // 【20260811-03】relation 必须逐字段透传，不能只活在 notes 里。
    // 首版改完线上实测：notes 已经写着"可互换、对接不判定"，而机读字段 relation=undefined
    // —— 白名单式的字段拷贝把新字段静默丢掉了。LLM 会读那句话，程序只读字段，
    // 两个消费方拿到的结论不一样，等于没修（与 L1.83「机读字段与紧邻文案打架」同型，方向相反）。
    return {
      dimension: d,
      compatible: r.compatible,
      score: r.score,
      notes: r.notes,
      ...(r.relation ? { relation: r.relation } : {}),
    };
  });

  const decided = dimensions.filter(x => x.compatible !== null);
  const compatibleCount = decided.filter(x => x.compatible).length;
  const hasConflict = decided.some(x => x.compatible === false);
  // protocol/electrical/mechanical 是硬兼容约束；software(ROS2) 只是生态便利，
  // 单凭它不足以断言两件硬件"能装在一起"。
  const hardDecided = decided.filter(x => HARD_DIMENSIONS.includes(x.dimension));

  let overall, verdict_reason;
  if (!decided.length) {
    overall = null;
    verdict_reason = '四个维度均无双方声明，无法判定';
  } else if (hasConflict) {
    overall = false;
    verdict_reason = '存在双方均有声明且确实冲突的维度';
  } else if (!hardDecided.length) {
    // 20260806-08：修掉 mechanical 假红后暴露的既有缺陷 —— 旧逻辑 decided=1 时
    // compatibleCount === decided.length 必然成立，于是"双方都支持 ROS2"就能让
    // 一个舵机与一个 AI 加速芯片拿到 overall=true / score=100。以偏概全。
    overall = null;
    verdict_reason = '仅 ROS2 生态维度有证据，协议/电气/机械三项硬约束均无双方声明，不足以判定兼容';
  } else {
    overall = true;
    verdict_reason = `${decided.length} 个维度有双方声明且均兼容（含 ${hardDecided.length} 项硬约束）`;
  }

  const sb = scoreBreakdown(dimensions);
  return {
    a: { id: a.id, name: a.name, category: a.category },
    b: { id: b.id, name: b.name, category: b.category },
    dimensions,
    overall_compatible: overall,
    applicable: true,
    // overall 无法判定时 score 一律 null：给 0 会被读成"完全不兼容"，
    // 给 100 会被读成"完美兼容"，两者都是把证据不足伪装成结论。
    compatibility_score: overall === null ? null : sb.weighted_score,
    // 【P0】可解释分解：每个因子的权重、裁决、贡献，以及折算方法。
    // 仅当 overall 有结论时给出（overall=null 时分数 null，分解亦 null，避免假装精确）。
    score_basis: overall === null ? null : sb,
    verdict_reason,
    decided_dimensions: decided.length,
    undecided_dimensions: dimensions.length - decided.length,
    hard_dimensions_decided: hardDecided.length,
    source: 'rule-engine (real entity fields)',
    evidence_basis: '基于厂商公开声明字段的规则推断，非实测；未声明维度记为无法判定，不计入分子也不计入分母；判 true 至少需一项硬约束（协议/电气/机械）有双方声明',
    // 【P1 语义层 · 诚实边界】硬维度全无证据（overall=null）时，附"语义最相近零件"作为
    // 可核查线索，绝不作为兼容性结论（不会把 similarity 写进 compatibility_score，避免假绿）。
    ...(overall === null ? { semantic_hint: attachSemanticHint(a, b) } : {}),
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 【P1】本地语义层 —— 构建时预计算的哈希 TF-IDF 向量索引（api/semantic_index.json）
 *
 * 索引由 scripts/build_semantic_index.mjs 离线生成（纯 JS、零依赖、零外发）。
 * 本段只做「加载 + 余弦检索」，不在运行时训练任何模型、不发起任何网络。
 *
 * 诚实用途：在机械/电气/协议均无双方声明（overall=null）时，给出"语义上最相近的
 * 零件"供人工核查，而不是干巴巴返回 null。它**不是**兼容性裁决因子——
 * 语义相近 ≠ 能装在一起，绝不据此把 verdict 改成 compatible=true。
 * ═══════════════════════════════════════════════════════════════════════════ */
let _semIndex = null;   // isolate 级缓存：{ dim, idf, ids, names, vectors }

const SEM_CJK = /[一-鿿]/g;
const SEM_EN = /[a-z0-9][a-z0-9.+#-]*/g;

/** 与 build_semantic_index.mjs 完全一致的 token 化：英文词 + 中文 uni/bi-gram。 */
function tokenizeSemantic(text) {
  if (!text) return [];
  const t = String(text).toLowerCase();
  const toks = [];
  const en = t.match(SEM_EN);
  if (en) for (const w of en) if (w.length >= 2) toks.push(w);
  const cjk = t.match(SEM_CJK);
  if (cjk) {
    for (const run of cjk) {
      const chars = run.split('');
      for (const c of chars) toks.push('c:' + c);
      for (let i = 0; i < chars.length - 1; i++) toks.push('b:' + chars[i] + chars[i + 1]);
    }
  }
  return toks;
}

function hashDimSemantic(s, dim) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h % dim;
}

/** 预加载语义索引（best-effort，失败静默不影响主流程）。由 loadEntityMap 在启动时触发。 */
export async function ensureSemanticIndex(env, request) {
  if (_semIndex) return _semIndex;
  try {
    const r = await env.ASSETS.fetch(new URL('/api/semantic_index.json', request.url));
    if (!r.ok) return null;
    const doc = await r.json();
    if (!doc || !Array.isArray(doc.vectors) || !doc.dim) return null;
    _semIndex = doc;
  } catch { _semIndex = null; }
  return _semIndex;
}

/** 给定实体 id，返回语义最相近的 k 个零件（排除自身）。索引未就绪时返回 []。 */
function neighborsOf(id, k = 3) {
  if (!_semIndex) return [];
  const i = _semIndex.ids.indexOf(id);
  if (i < 0) return [];
  const v = _semIndex.vectors[i];
  const sims = [];
  for (let j = 0; j < _semIndex.ids.length; j++) {
    if (j === i) continue;
    const w = _semIndex.vectors[j];
    let dot = 0;
    for (let d = 0; d < _semIndex.dim; d++) dot += v[d] * w[d];
    sims.push({ id: _semIndex.ids[j], name: _semIndex.names[j], sim: dot });
  }
  sims.sort((x, y) => y.sim - x.sim);
  return sims.slice(0, k).map((s) => ({
    id: s.id, name: s.name, similarity: Math.round(s.sim * 1000) / 1000,
  }));
}

/** 当硬维度无法裁决时，附上双方各自的语义近邻，作为可核查线索。 */
function attachSemanticHint(a, b) {
  if (!_semIndex) return undefined;
  return {
    note: '四维硬约束均无双方声明，无法判定兼容性；以下为语义最相近零件，供人工核查接口/规格是否可能对齐（语义相近≠兼容）。',
    a_neighbors: neighborsOf(a.id),
    b_neighbors: neighborsOf(b.id),
  };
}

/**
 * 自然语言语义检索：把查询词向量化后在索引上做余弦召回。
 * 索引未就绪时返回 {available:false}（调用方降级为关键词检索）。
 */
export async function semanticSearch(env, request, query, k = 5) {
  const idx = await ensureSemanticIndex(env, request);
  if (!idx || !idx.vectors || !idx.idf) return { available: false, reason: '语义索引未就绪' };
  const tf = new Map();
  for (const tk of tokenizeSemantic(query)) tf.set(tk, (tf.get(tk) || 0) + 1);
  const vec = new Float64Array(idx.dim);
  for (const [tk, cnt] of tf) {
    const d = hashDimSemantic(tk, idx.dim);
    vec[d] += cnt * (idx.idf[tk] || 1);
  }
  let n = 0;
  for (let i = 0; i < idx.dim; i++) n += vec[i] * vec[i];
  n = Math.sqrt(n) || 1;
  const sims = [];
  for (let j = 0; j < idx.ids.length; j++) {
    let dot = 0;
    const w = idx.vectors[j];
    for (let d = 0; d < idx.dim; d++) dot += (vec[d] / n) * w[d];
    sims.push({ id: idx.ids[j], name: idx.names[j], similarity: Math.round(dot * 1000) / 1000 });
  }
  sims.sort((x, y) => y.similarity - x.similarity);
  return { available: true, query, dim: idx.dim, count: sims.length, results: sims.slice(0, k) };
}

/**
 * 从静态资源加载实体表（id -> entity）。
 * 失败时明确抛错 —— 绝不 catch 后返回 {} 假装"查无此件"（环境要点 #19）。
 */
export async function loadEntityMap(env, request) {
  const url = new URL('/api/entities.json', request.url);
  const resp = await env.ASSETS.fetch(url);
  if (!resp.ok) {
    throw new Error(`entities.json 加载失败: HTTP ${resp.status}`);
  }
  const json = await resp.json();
  const arr = json.entities || json.data || [];
  if (!Array.isArray(arr) || arr.length === 0) {
    throw new Error('entities.json 解析后为空数组 —— 拒绝以空数据对外服务');
  }
  const map = {};
  for (const e of arr) map[e.id] = e;
  // 【P0 · 数据飞轮】合并贡献层 api/entities.contrib.json（开源 BOM 反喂 + 用户提交 BOM）。
  // 不修改主库文件 api/entities.json（708 真值不变），仅运行时增强裁决覆盖。
  // 贡献层实体若主库已存在则补充其缺失维度（机械接口优先用贡献层，协议/电气/ROS 填空时补），
  // 若不存在（如 OSS-xxx）则作为新实体加入，使开源机器人零件也能被查兼容。
  await mergeFlywheel(env, request, map);
  // 【P1】预加载语义索引（best-effort）；失败不影响主裁决流（judgePair 会优雅降级）。
  await ensureSemanticIndex(env, request).catch(() => {});
  return map;
}

/** 合并飞轮贡献层（读 api/entities.contrib.json）。缺失不阻断主流程。 */
async function mergeFlywheel(env, request, map) {
  try {
    const r = await env.ASSETS.fetch(new URL('/api/entities.contrib.json', request.url));
    if (!r.ok) return;
    const doc = await r.json();
    const contrib = doc.entities || [];
    let merged = 0, added = 0;
    for (const c of contrib) {
      if (!c || !c.id) continue;
      const exist = map[c.id];
      if (exist) { mergeInto(exist, c); merged++; }
      else { map[c.id] = c; added++; }
    }
    if (merged || added) console.warn(`[flywheel] 合并贡献层: 补充 ${merged} + 新增 ${added} 实体`);
  } catch {
    /* 贡献层缺失/解析失败不阻断主流程 */
  }
}

/** 把贡献层实体 c 的声明合并进已有实体 dst：只补缺失维度，不覆盖已声明数据。 */
function mergeInto(dst, src) {
  const ms = dst.mechanical_interface && String(dst.mechanical_interface.status || '').toLowerCase();
  if (src.mechanical_interface && (!dst.mechanical_interface || ms === 'not_declared' || ms === 'n_a')) {
    dst.mechanical_interface = src.mechanical_interface;
  }
  if (!dst.protocol && src.protocol) dst.protocol = src.protocol;
  if (!dst.interface && src.interface) dst.interface = src.interface;
  if (!dst.voltage && src.voltage) dst.voltage = src.voltage;
  if (typeof dst.ros_support !== 'boolean' && typeof src.ros_support === 'boolean') dst.ros_support = src.ros_support;
}

/** 主库收录实体总数（真相源，不含飞轮贡献层），供对外数字口径使用。 */
export async function getCuratedCount(env, request) {
  try {
    const r = await env.ASSETS.fetch(new URL('/api/entities.json', request.url));
    if (!r.ok) return null;
    const j = await r.json();
    return (j.meta && j.meta.total_entities) || (j.entities || j.data || []).length;
  } catch {
    return null;
  }
}

/** 主库实体数组（不含飞轮贡献层），供对外统计口径与贡献层严格区分。 */
export async function loadCuratedList(env, request) {
  const r = await env.ASSETS.fetch(new URL('/api/entities.json', request.url));
  if (!r.ok) throw new Error(`entities.json 加载失败: HTTP ${r.status}`);
  const j = await r.json();
  const arr = j.entities || j.data || [];
  if (!Array.isArray(arr)) throw new Error('entities.json 解析异常');
  return arr;
}
