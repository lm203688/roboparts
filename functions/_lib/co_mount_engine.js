/**
 * 共装（co-mount）查询的**共享纯逻辑**。
 *
 * 为什么必须抽出来共用（而不是在 MCP 与 REST 各写一份）：
 *   functions/api/compatibility.js 顶部已写死一条纪律 ——「不得在此重新实现判定，
 *   那会让 REST 与 MCP 对同一对零件给出不同答案」。共装层同理：
 *   check_co_mount（MCP）与 /api/co-mount（REST）必须调用**同一份** queryCoMount，
 *   否则两条通道会对「能不能同时装 A 和 B」给出不一致的裁决。
 *
 * 本模块**无副作用、不读盘、不联网**：只吃已解析的两份产物对象，返回结构化结论。
 * 数据来源：
 *   api/co_mount.json        （三段裁决：pair_verdicts / single_mount / summary）
 *   api/robot_tool_side.json （宿主工具侧取证：hosts[]）
 *
 * 口径：研究层三段 AND（mount_fit + port_budget + signal_complementary），
 * 与 check_compatibility 的四维（protocol/electrical/mechanical/software）**不可混用**。
 */

export const CO_MOUNT_CALIBER =
  'research_py_co_mount_engine/v1（三段共装：mount_fit + port_budget + signal_complementary）';

export const CO_MOUNT_WARNING =
  '本口径为研究层三段共装判据，与 check_compatibility 的四维'
  + '（protocol/electrical/mechanical/software）维度不同，两者结论不可混用或直接比较。';

/** 裁决态的中文释义（与 build_co_mount 的语义保持一致，不改写结论）。 */
export function coMountInterpret(verdict) {
  const m = {
    mountable:
      '可共装：机械同型 + 工具侧位数够 + 信号角色互补，三者均通过。',
    port_exhausted:
      '装不下：宿主工具侧位数被占满（**工程约束**，需转接件或换本体），与「不知道」严格区分。',
    type_error:
      '类型错误：不构成共装关系（典型是同角色对，如两个夹爪一起装无意义），属**确定的否定答案**，不是数据缺口。',
    unknown:
      '未知：数据不足（如宿主工具侧位数未取证），fail-closed 判未知，不判通过。',
  };
  return m[verdict] || `裁决态 ${verdict}（未登记释义）`;
}

/**
 * 共装裁决的证据链（判定层溯源）。
 *
 * 与数据层溯源（实体 → 厂商 datasheet）不同，这里回答「这条**判定**依据了哪几条取证」。
 * 只从 robot_tool_side / co_mount 的现算字段取，不新增断言。
 */
export function coMountEvidence(hostsById, cm, host, a, b) {
  const ev = [];
  const h = hostsById[host];
  if (h) {
    ev.push({
      kind: 'host_tool_side',
      ref: host,
      name: h.name,
      claim: `工具法兰 ${h.tool_flange}；工具 I/O 位数 ${
        h.tool_io_ports == null ? 'null（未取证）' : h.tool_io_ports
      }`,
      source_url: h.source_url || null,
      source: h.source || null,
      source_tier: h.source_tier || null,
      confidence: h.confidence != null ? h.confidence : null,
    });
  }
  for (const dev of [a, b]) {
    const sm = (cm.single_mount || {})[`${host}::${dev}`];
    if (sm) {
      ev.push({
        kind: 'device_mount',
        ref: dev,
        claim: sm.reason || `单件可装性 ${sm.verdict}`,
        verdict: sm.verdict,
        mount_fit: sm.mount_fit,
        port_budget: sm.port_budget,
      });
    }
  }
  ev.push({
    kind: 'caliber',
    ref: 'co_mount_engine/v1',
    claim:
      '三段 AND 判据（机械同型 + 位数预算 + 信号互补），任一 unknown 即判 unknown（fail-closed）。',
  });
  return ev;
}

/**
 * 共装查询主入口。三种问法：
 *   · host + a + b → 单对裁决（含 stage 分解 + 证据链）
 *   · host         → 该宿主的单件可装性 + 工具侧取证
 *   · 无参          → 全层摘要（关系语义 + 示例，向后兼容）
 *
 * @param {object} cm  api/co_mount.json 已解析对象
 * @param {object} ts  api/robot_tool_side.json 已解析对象（可为 null）
 * @param {{host?:string,a?:string,b?:string}} args
 */
export function queryCoMount(cm, ts, args = {}) {
  if (!cm) {
    return {
      caliber: CO_MOUNT_CALIBER,
      error: 'api/co_mount.json 不可用',
      error_kind: 'data_unavailable',
      note:
        '该产物由 scripts/build_co_mount.py 生成。未部署或构建失败时如实报错，不用其他口径的结论冒充。',
    };
  }

  const host = String(args.host || '').trim();
  const a = String(args.a || '').trim();
  const b = String(args.b || '').trim();
  const hostsById = {};
  if (ts && Array.isArray(ts.hosts)) for (const h of ts.hosts) hostsById[h.id] = h;

  const base = {
    caliber: CO_MOUNT_CALIBER,
    warning: CO_MOUNT_WARNING,
    question:
      '「A 和 B 能不能同时装在同一台机器人的工具侧」——这是三段共装关系，'
      + '不是点对点互插（后者见 check_compatibility）。',
  };

  // ── 情形 1：host + a + b → 单对裁决 + 证据链 ──────────────────────────────
  if (host && a && b) {
    const pv = (cm.pair_verdicts || []).find(
      (v) =>
        v.host === host &&
        ((v.a === a && v.b === b) || (v.a === b && v.b === a)),
    );
    if (!pv) {
      return {
        ...base,
        error_kind: 'not_evaluated',
        error: `未找到 ${host} 上 ${a} × ${b} 的共装裁决`,
        hint:
          '该对可能不在被裁决的配对集内。先用 check_co_mount({host}) 查该宿主的单件可装性，'
          + '或先用 search_components 确认实体 id。',
        known_hosts: Object.keys(hostsById),
      };
    }
    return {
      ...base,
      host,
      host_name: hostsById[host] ? hostsById[host].name : null,
      a,
      b,
      verdict: pv.verdict,
      stage_verdicts: pv.stage_verdicts,
      interpretation: coMountInterpret(pv.verdict),
      evidence: coMountEvidence(hostsById, cm, host, a, b),
    };
  }

  // ── 情形 2：仅 host → 单件可装性 + 工具侧取证 ─────────────────────────────
  if (host) {
    const h = hostsById[host];
    if (!h) {
      return {
        ...base,
        error_kind: 'unknown_host',
        error: `未知宿主 ${host}`,
        known_hosts: Object.keys(hostsById),
      };
    }
    const singles = Object.values(cm.single_mount || {}).filter(
      (s) => s.host === host,
    );
    return {
      ...base,
      host,
      host_name: h.name,
      tool_side: {
        tool_flange: h.tool_flange,
        tool_io_ports: h.tool_io_ports,
        tool_io_connector: h.tool_io_connector,
        tool_io_pins: h.tool_io_pins,
        tool_io_signals: h.tool_io_signals,
        mountable_tools: h.mountable_tools,
      },
      tool_side_evidence: {
        source_url: h.source_url || null,
        source: h.source || null,
        source_tier: h.source_tier || null,
        confidence: h.confidence != null ? h.confidence : null,
      },
      single_mount: singles,
      note:
        'single_mount 回答「这个器件单独能不能装上去」；要问「两个能不能同时装」，'
        + '请再传 a 与 b。tool_io_ports 为 null 表示**一手数据未公开**（刻意不填），据此判 unknown。',
    };
  }

  // ── 情形 3：无参 → 全层摘要（向后兼容） ───────────────────────────────────
  return {
    ...base,
    summary: cm.summary,
    relation_semantics: cm.relation_semantics,
    hosts:
      ts && Array.isArray(ts.hosts)
        ? ts.hosts.map((h) => ({
            id: h.id,
            name: h.name,
            tool_io_ports: h.tool_io_ports,
          }))
        : undefined,
    examples_mountable: cm.examples_mountable,
    examples_port_exhausted: cm.examples_port_exhausted,
    meta: cm.meta,
    how_to_query:
      '传 {host:"HUB-030"} 查该宿主；传 {host:"HUB-030",a:"ACT-028",b:"SENS-047"} 查单对。',
  };
}
