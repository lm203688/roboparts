/**
 * RoboParts SEO 分析 API
 * GET /api/analytics/seo
 *
 * 功能：
 * 1. CORS 支持（onRequestOptions，GET 方法）
 * 2. 检查 sitemap.xml 是否存在（通过 context.env.ASSETS.fetch('/sitemap.xml')）
 * 3. 统计本地 content/ 目录的文件数（通过 context.env.ASSETS.fetch('/content/')）
 * 4. 返回 SEO 状态报告：
 *    {
 *      sitemap_exists: true/false,
 *      content_count: 5,
 *      published_externally: 0,           // placeholder
 *      google_indexed: "未配置Analytics",  // placeholder
 *      bing_indexed: "未配置Analytics",    // placeholder
 *      last_updated: "2026-07-27"
 *    }
 *
 * 注意：本接口为只读分析接口，无需 API Key，不消耗积分。
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { env } = context;

  try {
    // 并行执行：检查 sitemap.xml 与统计 content/ 目录文件数
    const [sitemapResult, contentResult] = await Promise.allSettled([
      checkSitemap(env),
      countContentFiles(env),
    ]);

    const sitemapExists = sitemapResult.status === 'fulfilled' ? sitemapResult.value : false;
    const contentCount = contentResult.status === 'fulfilled' ? contentResult.value : 0;

    // 检测到的诊断信息（用于排查 ASSETS 不可用等场景）
    const diagnostics = [];
    if (sitemapResult.status === 'rejected') {
      diagnostics.push('sitemap 检测异常: ' + (sitemapResult.reason && sitemapResult.reason.message ? sitemapResult.reason.message : String(sitemapResult.reason)));
    }
    if (contentResult.status === 'rejected') {
      diagnostics.push('content 统计异常: ' + (contentResult.reason && contentResult.reason.message ? contentResult.reason.message : String(contentResult.reason)));
    }

    const report = {
      sitemap_exists: sitemapExists,
      content_count: contentCount,
      published_externally: 0, // placeholder，后续接入外部发布统计
      google_indexed: '未配置Analytics', // placeholder，后续接入 Google Search Indexing API
      bing_indexed: '未配置Analytics', // placeholder，后续接入 Bing Webmaster API
      last_updated: '2026-07-27',
    };

    const meta = {
      endpoint: '/api/analytics/seo',
      generated_at: new Date().toISOString(),
      assets_available: !!(env && env.ASSETS),
      diagnostics: diagnostics.length > 0 ? diagnostics : undefined,
    };

    return new Response(JSON.stringify({ meta, report }, null, 2), {
      status: 200,
      headers: {
        ...corsHeaders,
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (e) {
    return new Response(JSON.stringify({
      error: 'Internal error',
      message: e.message,
      stack: e.stack,
    }), { status: 500, headers: corsHeaders });
  }
}

/**
 * 检查 sitemap.xml 是否存在
 * 通过 Cloudflare Pages 的 ASSETS 绑定 fetch /sitemap.xml
 * 返回 boolean
 */
async function checkSitemap(env) {
  if (!env || !env.ASSETS) {
    // ASSETS 绑定不可用，无法检测，返回 false
    return false;
  }
  try {
    const res = await env.ASSETS.fetch(new Request('https://internal.local/sitemap.xml', {
      method: 'GET',
    }));
    // 2xx 视为存在；404/5xx 视为不存在
    if (res && res.status >= 200 && res.status < 300) {
      // 进一步校验返回内容非空且包含 xml 标识，避免误判
      try {
        const text = await res.text();
        if (text && text.length > 0 && /<\?xml|<urlset|<sitemap/i.test(text)) {
          return true;
        }
        // 内容为空或非 XML，视为不存在
        return false;
      } catch (_) {
        // 无法读取 body，但状态码正常，保守判定为存在
        return true;
      }
    }
    return false;
  } catch (e) {
    // fetch 异常，视为不存在
    return false;
  }
}

/**
 * 统计 content/ 目录下的文件数
 * 通过 Cloudflare Pages 的 ASSETS 绑定 fetch /content/ 获取目录列表
 * 解析返回的 HTML 目录列表，统计 .md / .html 等内容文件
 * 返回 number
 */
async function countContentFiles(env) {
  if (!env || !env.ASSETS) {
    // ASSETS 绑定不可用，无法统计，返回 0
    return 0;
  }
  try {
    const res = await env.ASSETS.fetch(new Request('https://internal.local/content/', {
      method: 'GET',
    }));

    if (!res || res.status < 200 || res.status >= 300) {
      // 目录列表不可访问（Cloudflare Pages 默认可能不开放目录浏览）
      // 回退：尝试探测已知内容文件名模式 article-NN-*.md
      return await probeContentFiles(env);
    }

    const text = await res.text();
    if (!text) return 0;

    // 解析 HTML 目录列表中的文件链接
    // 匹配 href="article-..." 或类似模式（兼容 Apache/nginx 自动索引格式）
    const fileMatches = text.match(/href="([^"]+\.(?:md|html|markdown))"/gi) || [];
    // 去重并过滤掉父目录链接
    const files = new Set();
    for (const match of fileMatches) {
      const m = match.match(/href="([^"]+)"/i);
      if (m && m[1] && !m[1].startsWith('?') && !m[1].startsWith('../') && !m[1].startsWith('/')) {
        files.add(m[1]);
      }
    }
    const count = files.size;
    return count > 0 ? count : await probeContentFiles(env);
  } catch (e) {
    // 异常时回退到探测模式
    return await probeContentFiles(env);
  }
}

/**
 * 回退探测：逐个请求已知的 content 文件名模式，统计存在的数量
 * 覆盖 article-01 ~ article-20 以及 ros-discourse-post.md
 */
async function probeContentFiles(env) {
  if (!env || !env.ASSETS) return 0;

  const candidates = [];
  // article-01 ~ article-20
  for (let i = 1; i <= 20; i++) {
    const num = String(i).padStart(2, '0');
    candidates.push('/content/article-' + num + '.md');
  }
  // 其他已知内容文件
  candidates.push('/content/ros-discourse-post.md');

  const results = await Promise.allSettled(
    candidates.map(async (path) => {
      const res = await env.ASSETS.fetch(new Request('https://internal.local' + path, { method: 'GET' }));
      return (res && res.status >= 200 && res.status < 300) ? 1 : 0;
    })
  );

  return results
    .filter(r => r.status === 'fulfilled' && r.value === 1)
    .length;
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
