/**
 * 部署指纹端点 — GET /api/deployment
 *
 * P0-4（docs/RoboParts-全面提升与前沿演进报告-20261026.md）：
 *   建立部署指纹：commit、数据版本、构建时间、功能清单。
 *   验收：页脚/API 可查询；线上与预期 commit 一致。
 *
 * 用途：
 *   1. 页脚展示当前线上的 commit 短哈希 + 构建时间，用户一眼看到"我看到的
 *      是哪一个版本"——这是把「部署新鲜度」从 CI 内部指标暴露给用户。
 *   2. MCP / Agent 客户端在会话开始时打一次 GET，把 fingerprint 带进上下文，
 *      避免 Agent 引用了"三小时前已经被回滚"的实体数据。
 *   3. 灾备演练：`scripts/deploy.mjs` 部署后调用 /api/deployment 与本地
 *      api/deployment.json 对比，确认 Cloudflare Pages 已把新文件分发完毕
 *      再宣布"上线"。
 *
 * 数据来源（优先级从高到低）：
 *   1. Cloudflare Pages 环境注入的 CF_PAGES_COMMIT_SHA / CF_PAGES_BRANCH
 *      （仅当通过 GitHub Actions + Pages 部署）
 *   2. 静态文件 api/deployment.json，由 scripts/deploy.mjs 在部署前写入，
 *      内含 git HEAD + 构建时间 + Node/Python 版本 + 功能清单
 *   3. 硬编码 fallback "unknown"，让端点从不 500（观测性优先于失败）
 *
 * 契约：响应 JSON schema 见 api/deployment.json 头部注释与 CI 闸门
 *      scripts/ci_gate.py::gate_deployment_fingerprint。
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

/**
 * 从 Cloudflare Pages 运行环境抽取 commit / branch / deploymentId。
 * 只有走 GitHub Actions → Pages 部署时 CF_PAGES_COMMIT_SHA 才会存在；
 * 手工 `wrangler pages deploy` 走本地路径时全部 undefined。
 */
function envFingerprint(env) {
  const cf = env && env.CF_PAGES ? env.CF_PAGES : {};
  // Cloudflare Pages 用 CLOUDFLARE_COMMIT_MESSAGE / CLOUDFLARE_COMMIT_SHA 命名（历史遗留）
  // 部分新模板用 CF_PAGES_COMMIT_SHA
  const commit = env.CF_PAGES_COMMIT_SHA || cf.commit || env.CLOUDFLARE_COMMIT_SHA || null;
  const branch = env.CF_PAGES_BRANCH || cf.branch || null;
  const deployId = env.CF_PAGES_ID || cf.id || null;
  return { commit, branch, deployId };
}

export async function onRequestGet(context) {
  const { env } = context;

  // 1. 尝试读静态 fingerprint 文件（scripts/deploy.mjs 每次部署写入）
  // 必须用 env.ASSETS.fetch 而不是裸 fetch——Cloudflare Pages 里裸 fetch 相对路径
  // 会在 Worker 内部回环、拿不到静态资源，是本次 builtAt=unknown 的根因（2026-10-26 审计 P0-4）。
  let file = null;
  try {
    const r = await env.ASSETS.fetch(new URL('/api/deployment.json', 'http://localhost'));
    if (r.ok) file = await r.json();
  } catch { /* 文件可能不存在（老版本部署），继续走 env 路径 */ }

  // 2. 合并：静态文件为主，env 提供 Cloudflare 侧真实 commit
  const envfp = envFingerprint(env);

  const fingerprint = {
    kind: 'roboparts.deployment-fingerprint',
    schemaVersion: 1,
    // Cloudflare 侧真实 commit（若有）优先
    commit: envfp.commit || (file && file.commit) || 'unknown',
    commitShort: (envfp.commit || (file && file.commit) || 'unknown').slice(0, 12),
    branch: envfp.branch || (file && file.branch) || 'unknown',
    deploymentId: envfp.deployId || (file && file.deploymentId) || 'unknown',
    // 构建时间：静态文件里是本地 git HEAD 时间，比 Cloudflare 分发时间更贴合"这一版是谁写的"
    builtAt: (file && file.builtAt) || 'unknown',
    gitHead: (file && file.gitHead) || null,
    nodeVersion: (file && file.nodeVersion) || 'unknown',
    pythonVersion: (file && file.pythonVersion) || 'unknown',
    ciGatePassed: (file && typeof file.ciGatePassed === 'boolean') ? file.ciGatePassed : null,
    ciGateSummary: (file && file.ciGateSummary) || null,
    features: (file && file.features) || [],
    // 数据新鲜度：data.json 里 meta.generated_at
    dataFingerprint: null,
    serverTime: new Date().toISOString(),
  };

  // 3. 顺手取一次数据版本，让 Agent 一次拿到"代码版本 + 数据版本"
  try {
    const d = await fetch('/api/data.json', { cache: 'no-store' });
    if (d.ok) {
      const j = await d.json();
      fingerprint.dataFingerprint = {
        generatedAt: j.meta && j.meta.generated_at,
        totalEntities: j.meta && j.meta.total_entities,
        schemaVersion: j.meta && j.meta.schema_version,
      };
    }
  } catch { /* 数据端点故障不影响 fingerprint 本身 */ }

  return new Response(JSON.stringify(fingerprint, null, 2), {
    status: 200,
    headers: {
      ...corsHeaders,
      // 极短缓存：让线上指纹几乎实时反映部署，但避免每次刷新都回源
      'Cache-Control': 'public, max-age=30, stale-while-revalidate=300',
      'X-Data-Version': 'deployment-fingerprint/v1',
      // 供 _shell.js 页脚脚本读 commit 短哈希
      'X-RoboParts-Commit': fingerprint.commitShort,
      'X-RoboParts-Built-At': fingerprint.builtAt,
    },
  });
}
