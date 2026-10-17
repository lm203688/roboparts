# 性能预算（Performance Budget）

> **Phase 3 承重结构 8**（审计 §4）。
>
> 之前项目无性能预算文件——首页/关键端点无明确上限，一次依赖更新或图片
> 替换就能让移动端首屏退化 3×。本文件把「上限」写成文档 + 机器可读锚点，
> 让 CI 与 code review 都能对齐一个数。

## 一、为什么需要（诚实的动机）

1. **审计 F 系列**：无性能基准 → 无回退告警 → 页面越堆越慢没人发现
2. **Cloudflare Pages 免费配额**：单请求 10s CPU / 128 MB memory——超限会
   被强杀，返回 5xx；用户看到的直接是白屏
3. **产品目标**：T1 开源构建者 / T2 集成商工程师——他们的耐心阈值是 3s
   首屏，超过就跳走

## 二、预算表（当前基线，机器可读）

| 指标 | 上限 | 单位 | 测量方法 | 现状 |
|---|---|---|---|---|
| 首页 HTML 大小 | 30 | KB | `wc -c index.html` | 待测 |
| 首页 CSS+JS 总计 | 200 | KB | `du -b` assets | 待测 |
| 关键端点响应时间 | 500 | ms | p95 via Cloudflare Analytics | 待测 |
| `/api/entities.json` 大小 | 8 | MB | `wc -c` | 待测 |
| `/api/compatibility` p50 | 300 | ms | Workers 冷启动 | 待测 |
| Workers 单次 CPU | 5 | s | Cloudflare 默认 10s | 待测 |
| Workers 单次内存 | 64 | MB | Cloudflare 默认 128 MB | 待测 |
| Bundle size（新增依赖累计） | +15 | KB gz | `npm ls` 后重测 | 待测 |

## 三、CI 检查点（可执行的三条）

```bash
# 1. 首页 HTML 大小
[ $(wc -c < index.html) -lt 30720 ] || echo "FAIL: index.html 超 30KB"

# 2. entities.json 大小
[ $(wc -c < api/entities.json) -lt 8388608 ] || echo "FAIL: entities.json 超 8MB"

# 3. 新增依赖总大小（相对 package-lock 基线）
# 见 scripts/check_perf_budget.py（待实现）
```

## 四、豁免机制

任何突破预算的改动必须在本文件下方登记一条豁免，附：

- 突破项 + 具体数值
- 业务理由（一句话，不允许空泛）
- 回退计划（何时恢复）
- 过期日期（最长 90 天）

登记格式：

```markdown
| 日期 | 突破项 | 实际值 | 上限 | 理由 | 过期日 |
|------|--------|--------|------|------|--------|
| 2026-10-17 | 首页 CSS+JS | 220 KB | 200 KB | 新增 3D 预览依赖，下版本拆 chunk | 2027-01-15 |
```

## 五、监控（待接入）

上线后接 Cloudflare Analytics：

- **p95 首页 LCP < 2.5s**（移动端）
- **p95 API 响应 < 500ms**（`/api/entities.json` 除外，走 CDN 缓存）
- **Workers 5xx < 0.1%**（1 分钟粒度）

数据落到 `api/performance_history.json`（每季度快照），与
`api/research_progress.json` 同格式（口径可追）。

---

**状态**：v0.1（2026-10-17 首次登记），本文件由 Phase 3 承重结构 8 落地。
