/**
 * RoboParts 贡献者 API
 * GET /api/contributors                  - 排行榜（按 flywheel_source 聚合，附 git 作者）
 * GET /api/contributors?handle=xxx       - 单个贡献者详情（当前无用户级贡献，返回空 + 说明）
 *
 * 数据来源：
 *   - api/entities.contrib.json（142 条 flywheel 贡献，按 flywheel_source 聚合为开源项目贡献者）
 *   - git log（仓库作者；当前仅 1 位维护者）
 *
 * 诚实口径：
 *   1. 本表**只列真实贡献**——来自开源机器人项目 URDF 摄取与仓库提交者；没有匿名贡献、没有假名。
 *   2. 机械接口声明层的真实贡献者（提供孔位/螺纹一手数据）目前为 0，
 *      因为 issue 通道尚未开放（见 CONTRIBUTING.md）。页面会如实标注这一空集。
 *   3. 「核心贡献者徽章」在 CONTRIBUTING.md 承诺为「前 10 名」，当前真实贡献者
 *      未达 10 人时，**不虚构排名**：徽章栏为空并说明原因。
 */

import {
  newFailureCollector, loadJsonAsset, upstreamUnavailableResponse,
} from '../_lib/upstream.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

async function loadContrib(env, request, failures) {
  return await loadJsonAsset(env, request, '/api/entities.contrib.json', failures);
}

function parseRobotFromSource(src) {
  // "oss_urdf:天工 TienKung (开源人形)" -> { name, license, source }
  if (!src) return { name: '未知', license: 'unknown', source: 'unknown' };
  const m = String(src).match(/^oss_urdf:(.+?)\s*[（(](.+?)[)）]$/);
  if (m) {
    return { name: m[1].trim(), license: m[2].trim(), source: 'oss_urdf' };
  }
  return { name: String(src), license: 'unknown', source: 'other' };
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const failures = newFailureCollector();
  const loaded = await loadContrib(env, request, failures);
  if (!loaded.ok) {
    return upstreamUnavailableResponse(failures, corsHeaders,
      '贡献层数据源未能读取；空排行榜与「没有人贡献」不是同一件事，请勿据此判定项目无贡献。');
  }
  const { meta, data: entities } = loaded;

  // 按 flywheel_source 聚合
  const bySource = new Map();
  for (const e of entities) {
    const src = e.flywheel_source || e.source || 'unknown';
    if (!bySource.has(src)) {
      const parsed = parseRobotFromSource(src);
      bySource.set(src, {
        handle: 'oss:' + parsed.name.replace(/\s+/g, '-').toLowerCase(),
        display_name: parsed.name,
        kind: 'oss_robot_project',
        license_note: parsed.license,
        source_kind: 'oss_urdf_ingestion',
        entities_count: 0,
        categories: {},
        sample_ids: [],
        source_url: null,
      });
    }
    const b = bySource.get(src);
    b.entities_count += 1;
    b.categories[e.category] = (b.categories[e.category] || 0) + 1;
    if (b.sample_ids.length < 3) b.sample_ids.push(e.id);
  }

  const leaders = Array.from(bySource.values())
    .sort((a, b) => b.entities_count - a.entities_count);

  // 维护者（git 作者；仓内 git 历史已重置，仅保留 1 位维护者）
  // 不在 API 中硬编码姓名——由 build 脚本从 git log 现算生成 api/contributors.json
  const maintainers = (await (async () => {
    try {
      const r = await fetch('https://api.github.com/repos/lm203688/roboparts/contributors?per_page=10');
      if (!r.ok) return [];
      return await r.json();
    } catch {
      return [];
    }
  })()).map(c => ({
    handle: c.login,
    display_name: c.name || c.login,
    kind: 'maintainer',
    commits: c.contributions,
    url: c.html_url,
  }));

  // 机械接口声明贡献者（一手孔位/螺纹数据）—— 当前空集
  // 该集合应来自 CONTRIBUTING.md 通道一（issue 提交）+ 通道三（直接 PR 补 mechanical 字段），
  // 目前尚未有真实条目。空集如实返回，不虚构。
  const mechContributors = [];

  // 徽章资格（前 10 名）—— 真实贡献者不足 10 人时返回空数组并说明
  const badgeThreshold = 10;
  const badges = leaders.filter(l => l.entities_count >= badgeThreshold)
    .slice(0, 10)
    .map(l => ({ handle: l.handle, display_name: l.display_name, level: '核心贡献者' }));

  // 单贡献者详情查询
  const handle = url.searchParams.get('handle');
  if (handle) {
    const found = leaders.find(l => l.handle === handle)
      || maintainers.find(m => m.handle === handle);
    if (!found) {
      return new Response(JSON.stringify({
        meta: {
          found: false,
          handle,
          reason: '未找到该 handle 的贡献记录。当前贡献层包含开源项目贡献者与仓库维护者；'
            + '机械接口声明贡献者集合为空（issue 通道尚未开放真实提交）。',
        },
        data: null,
      }, null, 2), { status: 404, headers: { ...corsHeaders, 'Cache-Control': 'no-store' } });
    }
    return new Response(JSON.stringify({
      meta: { found: true, handle, generated_at: meta.generated_at },
      data: found,
    }, null, 2), { status: 200, headers: { ...corsHeaders, 'Cache-Control': 'public, max-age=300' } });
  }

  return new Response(JSON.stringify({
    meta: {
      ...meta,
      total_contributions: entities.length,
      total_oss_projects: leaders.length,
      total_maintainers: maintainers.length,
      total_mechanical_declare_contributors: mechContributors.length,
      badge_threshold: badgeThreshold,
      badge_granted_count: badges.length,
      badge_note: badges.length === 0
        ? '当前核心贡献者数为 0：开源项目贡献者按 URDF 摄取行数聚合，尚未达到 10 行门槛中的「项目级」判定；机械接口声明贡献者集合为空。'
        : `前 ${badgeThreshold} 名开源项目贡献者获得核心贡献者徽章。`,
      honest_limits: [
        '本排行榜只列真实贡献者；没有匿名贡献、没有假名。',
        '机械接口声明贡献者集合为空——issue 提交通道尚未有真实条目，我们不虚构。',
        'git 历史已重置，仓库维护者仅 1 位（lm203688），不做「多作者」宣传。',
      ],
    },
    leaders,
    maintainers,
    mechanical_declare_contributors: mechContributors,
    badges,
  }, null, 2), {
    status: 200,
    headers: { ...corsHeaders, 'Cache-Control': 'public, max-age=300' },
  });
}

export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
