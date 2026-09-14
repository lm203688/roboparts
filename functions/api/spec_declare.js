/**
 * /api/spec_declare — 规格书文本 → 机械接口（ISO 9409-1 法兰）结构化提取。
 *
 * 设计要点（借鉴 heyclicky「文档拖入即上下文」+ 本仓「AI 不编」纪律）：
 *   - 确定性正则提取，不调用任何 LLM 后端；因此即便 P2 copilot 后端（Agnes/ECS）
 *     维护中，本端点仍可用。零外部依赖、零密钥。
 *   - 仅解析 ISO 9409-1 圆形安装法兰的螺栓孔节圆（PCD）/ 孔数 / 螺纹三项几何。
 *   - **诚实边界**：AI 提取只能产 status:"partial"，绝不直接升 declared。
 *     升 declared 必须由人工以厂商官域 source_url 逐字核对孔位尺寸后完成
 *     （见 regression L1.78 出处白名单纪律）。
 *   - 返回可点击的「指给你看」引用（canonical 法兰梯级 / ISO 速查 / 转接件生成器），
 *     与 copilot.js 的 buildReferences 同源体验。
 *
 * 输入：POST { text: string }（规格书原文，支持中英文、ISO 标号与厂商 A 记号混排）
 * 输出：{ parsed, count, candidates[], proposed:{mechanical_interface}, references[] }
 */

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

const CANONICAL_FLANGE = [
  'A40=4×M6', 'A50=4×M6', 'A63=6×M6', 'A80=6×M8',
  'A100=6×M10', 'A160=8×M16', 'A250=8×M20',
];

// ---- 提取逻辑（确定性，单源真值在此） ----
function parseSpec(text) {
  const cands = [];
  const push = (c) => cands.push(c);

  // 1) 完整 ISO 9409-1 标号：ISO 9409-1-50-4-M6
  //    group1=PCD(mm) group2=孔数 group3=螺纹直径
  const isoRe = /ISO\s*9409[-\s]*1[-\s](\d{2,3})[-\s](\d{1,2})[-\s]M(\d{1,2})/gi;
  let m;
  while ((m = isoRe.exec(text))) {
    push({
      pcd: +m[1], holes: +m[2], thread: 'M' + m[3],
      iso_code: `ISO 9409-1-${m[1]}-${m[2]}-M${m[3]}`,
      confidence: 0.95, rules: ['iso_code'], raw: m[0].trim(),
    });
  }

  // 2) 厂商 A 记号：A50-4-M6 / A80-6-M8（仅在未命中完整 ISO 标号时使用）
  if (cands.length === 0) {
    const aRe = /(?:^|[\s,，、;；])(A\d{2,3})[-\s](\d{1,2})[-\s]M(\d{1,2})/gi;
    while ((m = aRe.exec(text))) {
      const pcd = +m[1].slice(1); // A50 → 50 即 PCD
      push({
        pcd, holes: +m[2], thread: 'M' + m[3],
        iso_code: `ISO 9409-1-${pcd}-${m[2]}-M${m[3]}`,
        confidence: 0.9, rules: ['a_notation'], raw: m[0].trim(),
      });
    }
  }

  // 3) 散落几何（中英文，含中文数字孔数）：PCD 80 四孔 M8 / 六孔 M8 /
  //    节圆直径 80mm 6孔 M8 / pitch circle diameter 80 mm, 6 holes M8
  if (cands.length === 0) {
    const pcdM = text.match(/(?:PCD|节圆直径|节圆|pitch\s*circle\s*diameter)[\s:：]*?(\d{2,3})\s*(?:mm)?/i);
    const holeM = text.match(/(\d{1,2}|[一二三四五六七八九十])\s*(?:孔|holes|bolts|mounting\s*holes)/i);
    const thrM = text.match(/M(\d{1,2})/i);
    const CN = { '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10 };
    if (pcdM && holeM && thrM) {
      const pcd = +pcdM[1];
      const holes = /^\d/.test(holeM[1]) ? +holeM[1] : (CN[holeM[1]] || 0);
      const thread = 'M' + thrM[1];
      push({
        pcd, holes, thread,
        iso_code: `ISO 9409-1-${pcd}-${holes}-${thread}`,
        confidence: 0.7, rules: ['scattered_geometry'],
        raw: `PCD ${pcd} / ${holes}孔 / ${thread}`,
      });
    }
  }

  // 去重（同一 PCD+孔数+螺纹视为同一候选）
  const seen = new Set();
  const uniq = [];
  for (const c of cands) {
    const k = `${c.pcd}|${c.holes}|${c.thread}`;
    if (seen.has(k)) continue;
    seen.add(k);
    uniq.push(c);
  }
  return uniq;
}

function buildReferences(cands) {
  const refs = [
    { label: 'ISO 9409-1 法兰速查', url: 'https://roboparts.cc/iso-9409-flange' },
    { label: 'canonical 法兰梯级', url: 'https://roboparts.cc/adapter-generator' },
  ];
  for (const c of cands) {
    const a = `A${c.pcd}`;
    const b = c.pcd <= 50 ? 'A50' : c.pcd <= 80 ? 'A80' : c.pcd <= 100 ? 'A100' : 'A160';
    if (a !== b) {
      refs.push({
        label: `生成 ${a}↔${b} 转接件`,
        url: `https://roboparts.cc/adapter-generator?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}&t=10`,
      });
    }
  }
  return refs;
}

function buildProposed(cands) {
  if (!cands.length) return null;
  const c = cands.slice().sort((x, y) => y.confidence - x.confidence)[0];
  const iso = c.iso_code || `ISO 9409-1-${c.pcd}-${c.holes}-${c.thread}`;
  return {
    mechanical_interface: {
      status: 'partial', // 纪律：AI 提取只能 partial，升 declared 需人工补官域 source_url
      mount_type: 'flange',
      standard: iso,
      flange: null,
      declared_note: `AI 从规格书文本提取（${c.rules.join('+')} 命中：${c.raw || iso}）。待人工以厂商官域 source_url 逐字核对孔位尺寸后，方可升 declared。`,
      source: '用户拖入规格书文本，AI 正则提取（/api/spec_declare，2026-09-14）',
      source_url: '', // 必须由人工从厂商官域填入（L1.78 白名单）
      confidence: c.confidence,
      registry_ref: '/api/mechanical_interfaces.json',
      gap: 'source_url 官域出处待补；升 declared 前须核对 PCD/孔数/螺纹与厂商 Drawing 一致',
    },
  };
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS });
}

export async function onRequestPost({ request }) {
  let body;
  try { body = await request.json(); } catch {
    return new Response(JSON.stringify({ error: 'invalid_json' }),
      { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }
  const text = (body && body.text) ? String(body.text).slice(0, 20000) : '';
  if (!text.trim()) {
    return new Response(JSON.stringify({ error: 'missing_text' }),
      { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }

  const cands = parseSpec(text);
  const proposed = buildProposed(cands);
  const references = buildReferences(cands);

  const out = {
    parsed: cands.length > 0,
    count: cands.length,
    candidates: cands,
    proposed,
    references,
    note: '确定性正则提取，不调用 LLM。产出 status="partial"，需人工补官域 source_url 后升 declared（遵守 AI 不编纪律）。',
  };
  return new Response(JSON.stringify(out),
    { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
}
