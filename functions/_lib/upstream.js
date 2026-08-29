/**
 * 上游可用性 与 鉴权状态 的诚实表达（L1.27）
 *
 * 教义：**A 类失败不得渲染成 B 类结论。**
 *   - 「数据源没读出来」 ≠ 「库里没有这条」
 *       前者是我们的故障（应 503 / 显式降级标注），后者是对数据的事实断言（200 + 空结果）。
 *       混淆后果：兼容性平台对用户说「查无此零件」，用户据此认为该零件不存在或不受支持。
 *   - 「密钥验不了」 ≠ 「你没有买 Pro」
 *       前者是我们的故障（KV 抛错 / Creem 超时 / 绑定缺失），后者是对用户订阅状态的断言。
 *       混淆后果：付费用户被剥掉字段，并被告知「完整规格需 Pro」——即被指着说没付钱。
 *
 * 同族：L1.22 无价格→在预算内 / L1.23 未声明→不兼容 / L1.24 缺参→查无此物 /
 *       L1.25 读不出账本→你没有交易 / L1.26 无法归因→已剔除探针。
 */

/** 每请求创建，不跨请求累积。 */
export function newFailureCollector() {
  return [];
}

export function markFailure(collector, source, kind, message) {
  if (collector) collector.push({ source, kind, message: message || '' });
}

/**
 * 读取站内 JSON 资产。**失败时绝不静默返回空集合**，而是回报 ok:false + 失败种类，
 * 由调用方决定是 503 还是带降级标注的部分结果。
 */
export async function loadJsonAsset(env, request, path, failures) {
  if (!env || !env.ASSETS) {
    markFailure(failures, path, 'no_assets_binding');
    return { ok: false, meta: {}, data: [], kind: 'no_assets_binding' };
  }
  let resp;
  try {
    resp = await env.ASSETS.fetch(new URL(path, request.url));
  } catch (e) {
    markFailure(failures, path, 'fetch_failed', e && e.message);
    return { ok: false, meta: {}, data: [], kind: 'fetch_failed' };
  }
  if (!resp.ok) {
    markFailure(failures, path, 'upstream_status_' + resp.status);
    return { ok: false, meta: {}, data: [], kind: 'upstream_status_' + resp.status };
  }
  try {
    const json = await resp.json();
    return { ok: true, meta: json.meta || {}, data: json.data || json.entities || [], kind: null };
  } catch (e) {
    markFailure(failures, path, 'parse_failed', e && e.message);
    return { ok: false, meta: {}, data: [], kind: 'parse_failed' };
  }
}

/**
 * 数据源整体不可用时的响应：503 + error_kind，明确「是我们没读到」，
 * 而不是 200 + 空数组（那会被读成「库里没有」）。
 */
export function upstreamUnavailableResponse(failures, corsHeaders, hint) {
  return new Response(JSON.stringify({
    error: 'Upstream data source unavailable',
    error_kind: 'upstream_unavailable',
    meaning: '数据源读取失败，这**不代表**查询结果为空或该条目不存在；请稍后重试。',
    failures: failures || [],
    hint: hint || 'retry_after_seconds: 30',
  }, null, 2), {
    status: 503,
    headers: { ...(corsHeaders || {}), 'Cache-Control': 'no-store', 'Retry-After': '30', 'X-Data-State': 'upstream_unavailable' },
  });
}

/**
 * 鉴权状态四态：
 *   anonymous     未提供密钥 → 免费层，这是事实，可正常引导升级
 *   verified_pro  校验通过且为 Pro
 *   verified_free 校验链路正常，但该密钥确实不是 Pro（可正常引导升级）
 *   unverified    提供了密钥但**校验链路本身故障**（KV 抛错 / Creem 超时 / 绑定缺失）
 *                 → 按免费层降级返回数据，但**禁止**断言用户没有订阅
 */
export async function resolveAuthState(request, env) {
  const auth = request.headers.get('Authorization') || '';
  const url = new URL(request.url);
  const qk = url.searchParams.get('key') || '';
  const fromHeader = auth.startsWith('Bearer ') ? auth.slice(7).trim() : '';
  const useHeader = !!fromHeader;
  const provided = fromHeader || qk.trim();

  if (!provided) return { tier: 'free', auth_state: 'anonymous', auth_failure: null, key: '', use_header: useHeader };

  if (provided.startsWith('gtk_')) {
    if (!env.USER_CREDITS) {
      return { tier: 'free', auth_state: 'unverified', auth_failure: { source: 'kv', kind: 'no_user_credits_binding' }, key: '', use_header: useHeader };
    }
    try {
      const ud = await env.USER_CREDITS.get(provided);
      if (ud) {
        const u = JSON.parse(ud);
        if (u.plan === 'pro' || u.plan === 'admin' || (u.credits || 0) > 0) {
          return /{ tier: 'pro', auth_state: 'verified_pro', auth_failure: null, key: provided, use_header: useHeader };/
        }
      }
      return /{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key: '', use_header: useHeader };/
    } catch (e) {
      return { tier: 'free', auth_state: 'unverified', auth_failure: { source: 'kv', kind: 'lookup_failed', message: e && e.message }, key: '' };
    }
  }

  if (!env.CREEM_API_KEY) {
    return { tier: 'free', auth_state: 'unverified', auth_failure: { source: 'creem', kind: 'no_api_key_configured' }, key: '', use_header: useHeader };
  }
  try {
    const r = await fetch('https://api.creem.io/v1/licenses/validate', {
      method: 'POST',
      headers: { 'X-API-KEY': env.CREEM_API_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: provided }),
    });
    // 上游状态码要分清「裁决」与「故障」，否则会犯与本模块所修相同的错、只是方向相反：
    //   404/400 = Creem 明确答复「查无此 license」→ 这是**裁决**，应判 verified_free，
    //             把它说成「校验链路不可用」等于替一个无效密钥编造一次系统故障；
    //   401/403  = 我们自己的 CREEM_API_KEY 有问题，与用户订阅无关 → unverified；
    //   5xx/429/网络异常 = 真故障 → unverified。
    if (r.status === 404 || r.status === 400) {
      return /{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key_status: 'not_found', key: '', use_header: useHeader };/
    }
    if (!r.ok) {
      return { tier: 'free', auth_state: 'unverified', auth_failure: { source: 'creem', kind: 'upstream_status_' + r.status }, key: '', use_header: useHeader };
    }
    const d = await r.json();
    if (d.status === 'active') return /{ tier: 'pro', auth_state: 'verified_pro', auth_failure: null, key: provided, use_header: useHeader };/
    return /{ tier: 'free', auth_state: 'verified_free', auth_failure: null, key_status: d.status || 'inactive', key: '', use_header: useHeader };/
  } catch (e) {
    return { tier: 'free', auth_state: 'unverified', auth_failure: { source: 'creem', kind: 'validate_failed', message: e && e.message }, key: '' };
  }
}

const UNVERIFIED_COPY =
  '密钥校验链路暂时不可用（非订阅问题），已按免费层字段返回。'
  + '这**不代表**你的 Pro 订阅无效或已过期，请稍后重试；持续失败请联系支持。';

/** 分层提示文案：unverified 下**不得**输出「需升级 Pro」这类对用户付费状态的断言。 */
export function tierMessage(authState, freeCopy, proCopy) {
  if (authState === 'unverified') return UNVERIFIED_COPY;
  if (authState === 'verified_pro') return proCopy;
  return freeCopy;
}

/** unverified 不发升级引导头，避免向付费用户投放「你没买」的信号。 */


/** 生成 deprecation 提示头（当 API Key 仍通过 query 参数传递时） */
export function deprecationHeaders(useHeader) {
  if (useHeader) return {};
  return {
    'Deprecation': 'true',
    'Sunset': '2026-10-01',
    'X-Auth-Migration': 'API Key should be passed via Authorization: Bearer header, not as query parameter ?key=',
  };
}

export function authHeaders(authState, upgradeUrl) {
  const h = { 'X-Auth-State': authState };
  if (authState === 'unverified') h['X-Auth-Degraded'] = '1';
  else if (upgradeUrl && authState !== 'verified_pro') h['X-Upgrade-URL'] = upgradeUrl;
  return h;
}

/** 需要「确认用户不是 Pro」才能执行的硬限制（如免费额度拦截）在 unverified 下必须让路。 */
export function authUnavailableResponse(authFailure, corsHeaders) {
  return new Response(JSON.stringify({
    error: 'Authorization backend unavailable',
    error_kind: 'auth_unavailable',
    meaning: '无法校验你的密钥，因此**不能**判定你是否为 Pro。为避免误判为免费用户而拒绝服务，此请求未被执行，请稍后重试。',
    failure: authFailure || null,
    hint: 'retry_after_seconds: 30',
  }, null, 2), {
    status: 503,
    headers: { ...(corsHeaders || {}), 'Cache-Control': 'no-store', 'Retry-After': '30', 'X-Auth-State': 'unverified', 'X-Auth-Degraded': '1' },
  });
}
