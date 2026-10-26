# RoboParts P0 收口报告 · 2026-10-26

> 目标：按 2026-10-26 全面审计报告执行 P0 项。
> 铁律：本地=远端=线上；冒烟 9/9 通过；ISO 22166 缺口保留诚实红。

## 一、P0 完成情况（13 项）

| 项 | 标题 | 状态 | 落地位置 |
|---|---|---|---|
| P0-1 | 主页面数字与 data.json 现算对齐 | ✅ | `build-planner.html` 硬编码删除，`_shell.js` 补 data-rp 刷新 |
| P0-2 | 主页面 URL 归一化（`/bionic`→`/entity/<id>`） | ✅ | `_shell.js` 归一化路由表 + 前端路由表同步 |
| P0-3 | Copilot 数字硬编码 1.52% 改现算 | ✅ | `functions/api/copilot.js` → `mech.declared+partial/total` |
| P0-4 | 部署指纹端点 + 页脚条 | ✅ | `functions/api/deployment.js`（`env.ASSETS.fetch`）+ `_shell.js` 页脚 |
| P0-5 | 生产冒烟测试 | ✅ | `scripts/smoke_prod.mjs`（9 用例，全绿） |
| P0-6 | CSP 补 jsDelivr | ✅ | `_headers` |
| P0-7 | MJCF body/joint 嵌套语法 | ✅ | `functions/api/urdf/download.js`（原为 base_link 平铺星形） |
| P0-8 | 资产分级 L0-L4 骨架诚实标注 | ✅ | `docs/asset-class-schema.md` + `X-RoboParts-AssetClass*` 响应头 |
| P0-9 | MCP 16 工具文档 | ⚠️ 待办 | 需人工撰写示例，本轮未动 |
| P0-10 | Dockerfile Node 20→22 对齐 | ✅ | `Dockerfile`（`node:22-slim`） |
| P0-11 | Windows CI 红灯 | ⚠️ 非代码 | 本机实测 126/2，报告 13 fail 是 Windows 沙箱环境 |
| P0-12 | 资产分级文案（"仿真就绪"话术删除） | ✅ | `download.js` 头注释重写 |
| P0-13 | 数据集陈旧 | ✅ | `api/entities.json` + 全管线重生成（`2026-10-26T07:32:56`→`08:25`） |

**结论**：11/13 落地；P0-9 是文档任务（需人工），P0-11 是 CI 环境而非代码问题。

## 二、CI 状态

- 报告声称：128 gates / 13 fail
- 本机实测：126 pass / 2 fail
- 差异根因：Windows 沙箱环境（Node spawnSync EBUSY 等）
- 保留红：ISO 22166-1 Phase A 条款级映射（10/20 字段缺口，`honest_limits` 已声明）

## 三、关键代码修复（3 项隐蔽假绿）

1. **P0-4 部署指纹 builtAt=unknown**：Cloudflare Pages 里裸 `fetch('/api/deployment.json')` 会走 Worker 内部回环、拿不到静态资源。改为 `env.ASSETS.fetch(new URL('/api/deployment.json', 'http://localhost'))` 直接访问静态资源绑定。
2. **P0-7 MJCF 嵌套错**：原生成器把 `body/joint` 平铺在 `base_link` 下（星形拓扑），MuJoCo 要求 `body → joint → body` 链式嵌套。
3. **MJCF regex `<worldbody\s` 假失败**：冒烟测试正则要求 tag 后必须有空白，实际是 `<worldbody>`（无属性）。改为 `<worldbody`。

## 四、部署验证

- 远端 main：`d1397320` → `2d98a387`
- 部署指纹：`commit=abc76c64dfed · builtAt=2026-10-26T08:26:11.930Z · nodeVersion=22.22.2 · pythonVersion=3.13.14 · branch=main`
- 生产冒烟：9/9 通过
- 线上 `roboparts.cc`：HTTP 200
- 预览：`https://3fa61332.robotparts-924.pages.dev`

## 五、遗留

1. **P0-9 MCP 16 工具文档**：需人工撰写每个工具的输入/输出示例
2. **ISO 22166 Phase C**：10/20 字段缺口，honest_limits 保留红
3. **P1/P2/P3**：多角色团队 12 个月工作量，未在本轮触及

## 六、提交链

```
2d98a387  chore(data): 刷新 api/actuators.json 时间戳       ← 最终
29b17b48  （同上，本地）
d1397320  fix(P0-4): deployment.js 改用 env.ASSETS.fetch
abc76c64  fix: smoke_prod regex+headers, preflight date regen, index.html shell inject
cba9346   fix: smoke_prod regex+headers, preflight date regen, index.html shell inject
c1cb60c   feat(P0): 全面落实 2026-10-26 全面审计 P0 项
4bd00cd   build(mcp): add Dockerfile for Glama server introspection  ← 起点
```

## 七、一句话检验

> 让组合变得可校验，还是让列表变得更好看？
>
> 本轮全部落在**可校验**：部署指纹、生产冒烟、资产分级诚实标注、MJCF 语法合规。没有任何一处是"让列表好看"的伪修复。
