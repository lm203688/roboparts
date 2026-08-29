/**
 * 机械维度「侧别」行为对照 —— 证明引擎不再把「同侧一致」渲染成「可对接」。
 *
 * 为什么需要这支测试（20260811-03）
 * ---------------------------------
 * 库里 ACT-028（Robotiq 2F-85 夹爪）与 SENS-31（FT 300 力传感器）都声明了
 * ISO 9409-1-50-4-M6。线上 /api/compatibility 对这一对返回
 * `mechanical: compatible=true, notes="共享机械接口"`, `compatibility_score=100`。
 *
 * 但这两个取值描述的是**同一侧**：厂商官方手册 §5.5 明确
 * "couplings … provided with necessary hardware for fixation on the Robotiq device side /
 *  robot side screws and dowel pins are not provided"，
 * 即 50-4-M6 是**耦合件↔机器人法兰**那一对；传感器装到耦合件上用的是 **M4** 螺钉。
 * 所以"取值相同"只证明**能装在同一个法兰上（可互换）**，
 * 不证明**能彼此对接（可堆叠）**。
 *
 * 今天只有一对实体有身份键，且恰好真能堆叠，所以假绿还没显形；
 * 而补机械数据是既定路线（fill_pct 1.68% → 更高），届时每一对同法兰工具件
 * （两只夹爪 / 两个力传感器）都会输出 compatible:true —— 夹爪装不到夹爪上。
 * 这是**随数据覆盖率线性增长的假绿**，必须在补数据之前先拆开两种关系。
 *
 * 自证不空转：下方 legacyMechanical() 是**冻结的修复前实现**（照抄自
 * 20260811-03 之前的 compat_engine.js case 'mechanical' 分支），
 * 不是 `git show HEAD` —— 锚在会随提交移动的引用上，修好那一刻自证就蒸发
 * （run-71 已踩过一次，且会把后续每次发布卡死）。
 */
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')));
const enginePath = path.join(ROOT, 'functions', '_lib', 'compat_engine.js');
const { evalDimension } = await import(pathToFileURL(enginePath).href);

let fail = 0;
const ok = (cond, label) => {
  console.log((cond ? '  ✅ ' : '  ❌ ') + label);
  if (!cond) fail++;
};

const ent = (id, mi) => ({ id, name: id, mechanical_interface: mi });
const ISO50 = 'ISO 9409-1-50-4-M6';
const ISO31 = 'ISO 9409-1-31.5-4-M5';

// ── 冻结的修复前实现（只用于证明测试压在真缺陷上，不参与生产路径） ──────────
function legacyMechanical(a, b) {
  const keys = (x) => {
    const mi = x.mechanical_interface || {};
    const st = String(mi.status || '').toLowerCase();
    if (st === 'not_declared' || st === 'n_a') return [];
    return [...new Set(['standard', 'flange'].flatMap(k => {
      const v = mi[k];
      return (Array.isArray(v) ? v : [v]).filter(Boolean).map(s => String(s).trim().toLowerCase());
    }))];
  };
  const ea = keys(a), eb = keys(b);
  if (!ea.length || !eb.length) return { compatible: null, notes: '无法判定' };
  const shared = ea.filter(p => eb.includes(p));
  return {
    compatible: shared.length > 0,
    notes: shared.length ? '共享机械接口: ' + shared.join('/') : '机械接口无交集',
  };
}

console.log('=== 阳性 1：两只夹爪，安装侧同为 ISO 9409-1-50-4-M6（可互换，绝不可对接） ===');
{
  const a = ent('GRIP-A', { status: 'declared', standard: [ISO50] });
  const b = ent('GRIP-B', { status: 'declared', standard: [ISO50] });
  const r = evalDimension('mechanical', a, b);
  ok(r.compatible === true, '同侧一致仍判 true（这是真事实：能装同一法兰）');
  ok(r.relation === 'interchangeable', 'relation=interchangeable（关系类型必须透出）');
  ok(/安装侧接口一致/.test(r.notes), '措辞点明是「安装侧一致」');
  ok(/对接关系不判定/.test(r.notes), '措辞显式声明「对接关系不判定」');
  ok(!/可直接对接/.test(r.notes), '措辞不得出现「可直接对接」');

  // 自证：修复前的实现对同一输入给出无法区分关系类型的结论
  const legacy = legacyMechanical(a, b);
  ok(legacy.compatible === true && /共享机械接口/.test(legacy.notes) && legacy.relation === undefined,
     '修复前实现复现缺陷（同侧一致被渲染成「共享机械接口」且无关系类型）');
}

console.log('=== 阳性 2：传感器工具侧 == 夹爪安装侧（真·可对接） ===');
{
  const sensor = ent('SENS-X', { status: 'declared', standard: [ISO50], tool_side: [ISO50] });
  const grip = ent('GRIP-A', { status: 'declared', standard: [ISO50] });
  const r = evalDimension('mechanical', sensor, grip);
  ok(r.compatible === true, '可对接判 true');
  ok(r.relation === 'mateable', 'relation=mateable');
  ok(/可直接对接/.test(r.notes), '措辞点明可直接对接');
  ok(/工具侧/.test(r.notes), '措辞点明依据是工具侧');
}

console.log('=== 阳性 3：对接方向反过来同样成立（A.robot == B.tool） ===');
{
  const grip = ent('GRIP-A', { status: 'declared', standard: [ISO50] });
  const sensor = ent('SENS-X', { status: 'declared', standard: [ISO31], tool_side: [ISO50] });
  const r = evalDimension('mechanical', grip, sensor);
  ok(r.relation === 'mateable', '方向对称：B 的工具侧命中 A 的安装侧也算可对接');
}

console.log('=== 阴性 1：安装侧无交集且无工具侧证据 → false（真冲突，不许变 null） ===');
{
  const r = evalDimension('mechanical',
    ent('A', { status: 'declared', standard: [ISO50] }),
    ent('B', { status: 'declared', standard: [ISO31] }));
  ok(r.compatible === false, '无交集仍判 false');
  ok(r.relation === 'none', 'relation=none');
  ok(/安装侧/.test(r.notes), '说明里区分了侧别');
}

console.log('=== 阴性 2：一方未声明 → null（防假红的老不变式不许被本次改动破坏） ===');
{
  const r1 = evalDimension('mechanical',
    ent('A', { status: 'declared', standard: [ISO50] }),
    ent('B', { status: 'not_declared' }));
  ok(r1.compatible === null, 'not_declared 仍为 null（无数据 ≠ 不兼容）');

  const r2 = evalDimension('mechanical',
    ent('A', { status: 'declared', standard: [ISO50] }),
    ent('B', { status: 'partial', mount_type: 'direct_mount' }));
  ok(r2.compatible === null, '仅 mount_type 仍为 null（L1.x：安装方式不是身份键）');
}

console.log('=== 阴性 3：双方只声明工具侧 → 既不许判 true，也不许判 false（侧别不齐 = 判不了） ===');
{
  const r = evalDimension('mechanical',
    ent('A', { status: 'declared', tool_side: [ISO50] }),
    ent('B', { status: 'declared', tool_side: [ISO50] }));
  // 两个都只暴露工具侧（都是上游件）：对接需要对方的安装侧，没有；
  // 互换需要双方安装侧，也没有。判 false 就是假红 —— 把"没声明安装侧"
  // 说成"装不上"。三态里这一格只能是 null。
  ok(r.compatible === null, '侧别不齐判 null（不是 false，判 false 即假红）');
  ok(/仅声明工具侧接口/.test(r.notes), '说明点明「只给了工具侧、缺安装侧」而非笼统的「未声明」');
}

console.log('=== 覆盖面：真实库数据必须仍能走通已有的那一对 ===');
{
  const fs = await import('node:fs');
  const db = JSON.parse(fs.readFileSync(path.join(ROOT, 'api', 'entities.json'), 'utf-8'));
  const map = Object.fromEntries(db.entities.map(e => [e.id, e]));
  const a = map['ACT-028'], b = map['SENS-31'];
  ok(!!a && !!b, '库内 ACT-028 / SENS-31 仍存在');
  if (a && b) {
    const r = evalDimension('mechanical', a, b);
    ok(r.compatible === true && r.relation === 'interchangeable',
       '真实数据这一对判为 interchangeable（数据只声明了安装侧，结论就只能到互换为止）');
  }
}

console.log('=== 端到端：relation 必须活到对外响应里，不能只活在 notes 的那句话里 ===');
{
  // 首版只改了 evalDimension 就以为完事，线上实测 /api/compatibility 返回
  // notes 正确但 relation=undefined —— judgePair 按白名单拷字段，新字段被静默丢掉。
  // 人话给了 LLM，机读字段给了程序，两个消费方结论不一致 = 等于没修。
  const { judgePair } = await import(pathToFileURL(enginePath).href);
  const comp = (id, mi) => ({ ...ent(id, mi), entity_kind: 'component', category: 'actuators' });
  const j1 = judgePair(comp('A', { status: 'declared', standard: [ISO50] }),
                       comp('B', { status: 'declared', standard: [ISO50] }));
  const m1 = j1.dimensions.find(d => d.dimension === 'mechanical');
  ok(m1.relation === 'interchangeable', 'judgePair 输出携带 relation=interchangeable');

  const j2 = judgePair(comp('S', { status: 'declared', standard: [ISO50], tool_side: [ISO50] }),
                       comp('G', { status: 'declared', standard: [ISO50] }));
  ok(j2.dimensions.find(d => d.dimension === 'mechanical').relation === 'mateable',
     'judgePair 输出携带 relation=mateable');

  // 阴性：判不了的维度不许凭空冒出 relation（避免下游把 undefined 当成一种关系）
  const j3 = judgePair(comp('A', { status: 'declared', standard: [ISO50] }),
                       comp('B', { status: 'not_declared' }));
  ok(!('relation' in j3.dimensions.find(d => d.dimension === 'mechanical')),
     '不可判定的维度不输出 relation 字段（不制造第三种含义不明的取值）');
}

console.log(fail === 0 ? '\n✅ 机械侧别行为对照全部通过' : `\n❌ ${fail} 项未通过`);
process.exit(fail === 0 ? 0 : 1);
