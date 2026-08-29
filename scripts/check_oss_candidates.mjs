#!/usr/bin/env node
/**
 * check_oss_candidates.mjs — 复核 ops/oss-flywheel/source-candidates.json 里
 * 被判 rejected/watch/blocked 的开源数据源候选，看它们是否已经变得「可摄取」。
 *
 * 存在的理由：开源项目会持续更新，一次判「无 BOM」不等于永远无 BOM；
 * 但每轮拿新闻重新捞一遍同样的项目也是纯浪费。台账 + 机读触发器解决这个来回。
 *
 * 关键纪律（L1.88 的直接后果）：
 *   拿不到仓库树（HTTP 非 200 / 空树 / truncated=true）时必须判 **UNKNOWN**，
 *   绝不能因为「没匹配到 BOM 文件」就输出 HOLD —— 那个结论在空输入下平凡成立，
 *   等于没检查。UNKNOWN 用 exit 2 与真正的 HOLD(exit 0) 区分开。
 *
 * ── 20260811-19 新增第二级「内容闸」（修一处 L1.89 同族缺陷）─────────────
 * 原实现只按**文件名**判 PROMOTE。20260811-19 实测 LeRobot Humanoid：
 * 文件名闸 PROMOTE（4 份 bom.*），但拉到 bom.csv 原文后 128 行里
 * ISO 9409 / 法兰 / EtherCAT / RJ45 / XT30 / JST 命中 **0**，
 * 唯一的 M5 是「M5 x 10 圆柱头螺钉」——**紧固件规格不是机械接口声明**。
 * 也就是「查得到 BOM 文件」≠「判得出 declared 接口」：
 * 沿用旧判据会把 declared 增量为 0 的源反复喊 PROMOTE，只虚增 OSS 计数。
 * 现在改成两级：文件名命中 → 拉原文 → 内容闸判 declared 接口是否真的存在。
 *   有 → PROMOTE（真可摄取）
 *   无 → HOLD_CONTENT_GATE（文件在但 declared 增量 0，不进管线）
 *   原文拿不到 → UNVERIFIED（**不许**退化成 PROMOTE 或 HOLD，同 L1.88）
 * 自测内置「鉴别力自证」：对同一份冻结样本，旧判据(仅文件名)与新判据(内容)
 * 必须给出**相反**结论，否则说明新闸空转（L1.90 纪律 #10）。
 *
 * 用法：
 *   node scripts/check_oss_candidates.mjs            # 复核全部
 *   node scripts/check_oss_candidates.mjs --selftest # 只跑阴阳对照，不联网
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const LEDGER =
  process.env.OSS_CANDIDATES_LEDGER ||
  path.join(ROOT, 'ops', 'oss-flywheel', 'source-candidates.json');
const UA = 'RoboPartsBot/1.0 (+https://roboparts.cc)';

function matchPaths(paths, pattern) {
  const re = new RegExp(pattern);
  return paths.filter((p) => re.test(p));
}

/* ─── 内容闸：BOM 原文里是否真的声明了「标准化接口」 ───────────────────
 * 机械侧只认三类：ISO 9409 / ISO 22166 明文、法兰编码形式（如 50-4-M6、A31.5-4-M5）、
 * 明确写「工具法兰 / tool flange」的行。
 *   —— 故意**不认**裸 flange（"flanged ball bearing" 是轴承型式，不是接口）
 *   —— 故意**不认**裸 M\d（"M5 x 10 cyl head" 是螺钉，不是 4-M5 螺纹分布）
 * 通信侧只认公开总线/连接器族；私有 CAN-FD 生态（如 RobStride）不算。
 */
const MECH_IFACE_RE =
  /(ISO\s*9409|ISO\s*22166|(?<![\w.])A?\d{2,3}(?:\.\d)?-\d-M\d(?![\w])|tool\s*flange|工具法兰|末端法兰|机械接口法兰)/i;
const COMM_IFACE_RE =
  /(EtherCAT|CANopen|PROFINET|EtherNet\/IP|Modbus|RS-?485|RS-?232|\bRJ-?45\b|\bD-?sub\b|\bDB-?9\b|\bXT-?(?:30|60|90)\b|\bJST\b|\bMolex\b|\bHirose\b|Amphenol|\bM(?:8|12)\b[^,\n]{0,24}(?:connector|接头|连接器|circular))/i;

/** 返回 {declared:boolean, hits:string[]} —— 逐行判，避免跨行拼接出假命中 */
function contentGate(text) {
  const hits = [];
  for (const line of String(text || '').split(/\r?\n/)) {
    if (!line.trim()) continue;
    const m1 = line.match(MECH_IFACE_RE);
    if (m1) hits.push(`mech:${m1[1]}`);
    const m2 = line.match(COMM_IFACE_RE);
    if (m2) hits.push(`comm:${m2[1]}`);
  }
  return { declared: hits.length > 0, hits: [...new Set(hits)].slice(0, 6) };
}

/** 冻结样本：20260811-19 实测的 LeRobot Humanoid bom.csv 真实片段 */
const FROZEN_LEROBOT_BOM = [
  'subassembly,category,name,specification,qty_subassembly,qty_robot',
  'torso,electronics_controller,Raspberry Pi 5,single-board computer,1,1',
  'torso,electronics_canfd_adapter,SAVVYCANFD 2CH CANFD adapter,"USB, dual CAN FD, 12 Mbps max",1,1',
  'torso,motor,RobStride O0,actuator,2,2',
  'torso,fastener_screw,M5 screw,M5 x 10 cyl head,5,5',
  'torso,stl_print,torso/torso_can_holder.stl,stl,1,1',
  'hipx,fastener_screw,M4 screw,M4 x 40 cyl head,6,12',
].join('\n');

/* raw.githubusercontent.com 对本机是**间歇可达**（20260811-19 同一分钟内实测：
 * node fetch 200/1.6s 而 curl 000/20s 超时；上一轮又恰好相反）。
 * 所以只重试**传输层**（抛错/超时），HTTP 非 200 属协议层，一次即定论——
 * 对着协议层错误重试会把「被挡在门外」熬成「看起来偶发」。
 * 两条通道都试，是因为它们的失败不同步，不是为了刷成功率。 */
async function fetchRaw(repo, filePath) {
  const url = `https://raw.githubusercontent.com/${repo}/HEAD/${filePath}`;
  const errs = [];
  for (let i = 0; i < 2; i++) {
    try {
      const res = await fetch(url, {
        headers: { 'User-Agent': UA },
        signal: AbortSignal.timeout(20000),
      });
      if (res.status !== 200) return { ok: false, why: `HTTP ${res.status}（协议层，不重试）` };
      const t = await res.text();
      if (!t.trim()) return { ok: false, why: '原文为空（空输入不得产生结论）' };
      return { ok: true, text: t, bytes: t.length, url, via: 'fetch' };
    } catch (e) {
      errs.push(`fetch#${i + 1} ${e.message}`);
    }
  }
  // 传输层连续失败 → 换 curl 通道（失败模式与 node 不同步）
  try {
    const { execFileSync } = await import('node:child_process');
    const out = execFileSync('curl', ['-s', '-m', '20', '-A', UA, url], {
      encoding: 'utf-8',
      maxBuffer: 8 * 1024 * 1024,
    });
    if (out && out.trim()) return { ok: true, text: out, bytes: out.length, url, via: 'curl' };
    errs.push('curl 空响应');
  } catch (e) {
    errs.push(`curl ${e.message.split('\n')[0]}`);
  }
  return { ok: false, why: `两条通道均失败（${errs.join(' / ')}）` };
}

/** 阴阳对照：判据本身必须能分辨「有 BOM」与「只有结构件」 */
function selftest() {
  const pattern =
    '(?i)(^|/)(bom|bill[-_ ]?of[-_ ]?materials|parts?[-_ ]?list)[^/]*\\.(csv|md|tsv|json|ods|xlsx)$';
  // Node 的 RegExp 不支持内联 (?i)，统一剥离后用 i flag —— 这一步本身也要被测到
  const norm = pattern.replace(/^\(\?i\)/, '');
  const re = new RegExp(norm, 'i');
  const cases = [
    // 阳性：这些必须命中，否则判据形同虚设
    ['BOM.csv', true],
    ['hardware/bill-of-materials.md', true],
    ['docs/Parts_List.xlsx', true],
    ['electronics/bom_v2.json', true],
    // 阴性：这些不得命中，否则会把 CAD 结构件误当成部件清单
    ['Robot/Arms/Bicep Left.step', false],
    ['src/model/Arm.urdf', false],
    ['README.md', false],
    ['defaults/left_arm_default_calibration.json', false],
    ['bomber/notes.txt', false], // 词根误伤：bom 出现在别的词里且扩展名不符
  ];
  let bad = 0;
  for (const [p, want] of cases) {
    const got = re.test(p);
    if (got !== want) {
      console.log(`  ❌ 自测失配: ${p} 期望=${want} 实得=${got}`);
      bad++;
    }
  }
  // 空输入不得产生「通过」的错觉
  if (matchPaths([], norm).length !== 0) {
    console.log('  ❌ 空输入应当零命中');
    bad++;
  }
  // ── 内容闸阴阳对照 ──
  const gateCases = [
    // 阳性：真的声明了标准化接口
    ['arm,mech_interface,Tool flange,ISO 9409-1-50-4-M6,1,1', true],
    ['wrist,adapter,Quick changer plate,A31.5-4-M5,1,1', true],
    ['torso,electronics,Fieldbus slave board,EtherCAT,1,1', true],
    ['hand,cable,Sensor lead,M12 connector 4-pin shielded,1,1', true],
    // 阴性：本轮真实缺陷 —— 紧固件/结构件/私有总线都不得算 declared 接口
    ['torso,fastener_screw,M5 screw,M5 x 10 cyl head,5,5', false],
    ['torso,fastener_screw,M12 screw,M12 x 40 cyl head,2,2', false],
    ['torso,stl_print,torso/torso_can_holder.stl,stl,1,1', false],
    ['torso,electronics_canfd_adapter,SAVVYCANFD 2CH CANFD adapter,"USB, dual CAN FD",1,1', false],
    ['leg,bearing,Flanged ball bearing 6800,flange bearing,1,1', false],
  ];
  for (const [line, want] of gateCases) {
    const got = contentGate(line).declared;
    if (got !== want) {
      console.log(`  ❌ 内容闸失配: ${line.slice(0, 60)} 期望=${want} 实得=${got}`);
      bad++;
    }
  }
  // 空输入不得平凡成立（L1.88）
  if (contentGate('').declared || contentGate(null).declared) {
    console.log('  ❌ 空输入下内容闸不得判 declared');
    bad++;
  }
  // 鉴别力自证（L1.90 #10）：同一份冻结样本，旧判据 vs 新判据结论必须相反
  const oldVerdict = /bom/i.test('hardware/bom/bom.csv') ? 'PROMOTE' : 'HOLD';
  const newVerdict = contentGate(FROZEN_LEROBOT_BOM).declared
    ? 'PROMOTE'
    : 'HOLD_CONTENT_GATE';
  if (oldVerdict === 'PROMOTE' && newVerdict === 'HOLD_CONTENT_GATE') {
    console.log('  ✅ 鉴别力自证：冻结 LeRobot BOM 上 旧判据=PROMOTE / 新判据=HOLD_CONTENT_GATE（结论相反，非空转）');
  } else {
    console.log(`  ❌ 鉴别力自证失败：旧=${oldVerdict} 新=${newVerdict}（两版结论未相反 ⇒ 新闸可能空转）`);
    bad++;
  }
  console.log(
    bad === 0
      ? `  ✅ 阴阳对照通过（路径 阳4/阴5 + 内容闸 阳4/阴5 + 空输入 3 + 鉴别力 1）`
      : `  ❌ 阴阳对照失败 ${bad} 项`
  );
  return bad === 0;
}

async function fetchTree(repo) {
  const url = `https://api.github.com/repos/${repo}/git/trees/HEAD?recursive=1`;
  const headers = { 'User-Agent': UA, Accept: 'application/vnd.github+json' };
  const tok = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (tok) headers.Authorization = `Bearer ${tok}`;
  let res;
  try {
    res = await fetch(url, { headers, signal: AbortSignal.timeout(25000) });
  } catch (e) {
    return { ok: false, why: `请求失败 ${e.message}` };
  }
  if (res.status !== 200) return { ok: false, why: `HTTP ${res.status}` };
  let j;
  try {
    j = await res.json();
  } catch (e) {
    return { ok: false, why: `响应非 JSON` };
  }
  const tree = Array.isArray(j.tree) ? j.tree : null;
  if (!tree) return { ok: false, why: '响应无 tree 字段' };
  if (tree.length === 0) return { ok: false, why: '空树（拿到的不是一张表）' };
  if (j.truncated) return { ok: false, why: 'truncated=true（只拿到部分文件，不足以断言无 BOM）' };
  return { ok: true, paths: tree.map((x) => x.path) };
}

async function main() {
  console.log('=== OSS 数据源候选复核 ===');
  const selfOk = selftest();
  if (!selfOk) {
    console.log('判据自测未通过，拒绝据此下结论。');
    process.exit(3);
  }
  if (process.argv.includes('--selftest')) return;

  const ledger = JSON.parse(fs.readFileSync(LEDGER, 'utf-8'));
  let promote = 0;
  let unknown = 0;
  let hold = 0;
  let unverified = 0;

  for (const c of ledger.candidates) {
    if (c.verdict === 'ingested') continue;
    const rc = c.recheck;
    if (!rc || rc.type !== 'github_tree_match') {
      console.log(`\n[${c.id}] ⚠️  无机读触发器，跳过（应补 recheck）`);
      unknown++;
      continue;
    }
    console.log(`\n[${c.id}] ${c.name}  当前裁决=${c.verdict}`);
    for (const repo of rc.repos) {
      const r = await fetchTree(repo);
      if (!r.ok) {
        console.log(`  ❔ UNKNOWN ${repo} —— ${r.why}（不判 HOLD，因该结论在空输入下平凡成立）`);
        unknown++;
        continue;
      }
      const hits = matchPaths(r.paths, rc.pattern.replace(/^\(\?i\)/, ''));
      const re = new RegExp(rc.pattern.replace(/^\(\?i\)/, ''), 'i');
      const real = r.paths.filter((p) => re.test(p));
      if (real.length) {
        // 第一级过了只说明「有 BOM 文件」；第二级才判「有 declared 接口」
        console.log(`  📄 ${repo} 出现部件清单 ${real.length} 份：${real.slice(0, 5).join(', ')}`);
        let gated = null;
        let why = '';
        for (const f of real.slice(0, 3)) {
          const raw = await fetchRaw(repo, f);
          if (!raw.ok) {
            why = `${f}: ${raw.why}`;
            // 同一个 host 的通道死了就是死了，不必对剩下的文件重复熬 20s×N
            if (/两条通道均失败/.test(raw.why)) {
              why += '（同 host 通道已判死，跳过其余 BOM 文件）';
              break;
            }
            continue;
          }
          const g = contentGate(raw.text);
          why = `${f} (${raw.bytes}B)`;
          if (g.declared) {
            gated = g;
            break;
          }
          gated = gated || g;
        }
        if (gated === null) {
          console.log(`  ❔ UNVERIFIED ${repo} —— BOM 原文拿不到（${why}），不判 PROMOTE 也不判 HOLD`);
          unverified++;
        } else if (gated.declared) {
          console.log(`  🔔 PROMOTE ${repo} 内容闸命中 declared 接口：${gated.hits.join(', ')} ← ${why}`);
          promote++;
        } else {
          console.log(
            `  ⏸️  HOLD_CONTENT_GATE ${repo} —— BOM 原文已读(${why})但无标准化接口声明（螺钉/STL/私有总线不算），declared 增量 0，不进管线`
          );
          hold++;
        }
      } else {
        console.log(`  ⏸️  HOLD ${repo}（${r.paths.length} 个文件，仍无部件清单）`);
        hold++;
      }
      void hits;
    }
  }

  console.log(
    `\n小结：PROMOTE ${promote} ｜ HOLD ${hold} ｜ UNKNOWN ${unknown} ｜ UNVERIFIED ${unverified}`
  );
  if (unknown > 0 || unverified > 0) {
    console.log('存在 UNKNOWN/UNVERIFIED：本轮不得声称「候选源都已复核过」。');
    process.exit(2);
  }
  process.exit(0);
}

main().catch((e) => {
  console.error('复核异常：', e);
  process.exit(3);
});
