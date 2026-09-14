# 规格书 → 机械接口声明（spec_declare）设计文档

> 日期：2026-09-14 · 借鉴自 heyclicky「文档拖入即上下文」+ 本仓「AI 不编」纪律
> 关联：`functions/api/spec_declare.js` · `spec-declare.html` · `scripts/spec_declare_cli.py`

## 1. 出发点

heyclicky/clicky 体验远超普通 Chatbot 的两点之一，是 **"把文档拖进来就当作上下文"**（clicky-windows 的文档拖放 + OCR 兜底）。
对 RoboParts 而言，这直接对上长期硬阻塞 **P0：真实 BOM 机械接口声明数据缺口**（applicable 435，declared 仅 15，partial 10）。

人工逐条补机械接口声明，瓶颈是"得有人把厂商规格书里的孔位尺寸读出来再敲进 `entities.json`"。
spec_declare 把这一步**自动化到 partial**：拖入/粘贴规格书 → AI 提取 ISO 9409-1 法兰几何 → 产出待人工核实的声明。

## 2. 核心设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 提取引擎 | **确定性正则**，不调用 LLM | P2 copilot 后端（Agnes/ECS）维护中，正则零依赖、零密钥、永远可用；结果可复现、可审计 |
| 产出状态 | **一律 `status: "partial"`** | 遵守「AI 不编」纪律：AI 不得凭空升 declared。升 declared 必须由人工补厂商官域 `source_url` 并逐字核对 |
| `source_url` | **留空**，页面显式提示补官域 | L1.78 出处白名单（robotiq/onrobot/schunk/ati-ia/universal-robots/iso.org/openstd.samr.gov.cn）纪律 |
| 是否自动写库 | **否**，只产出提案 JSON | 防 AI 误写；人工 review 后再合入 `entities.json` |

## 3. 提取能力（单源真值，JS 与 Python 同源）

三级匹配，命中即停（高置信优先）：

1. **完整 ISO 标号**：`ISO 9409-1-50-4-M6` → PCD=50, 孔数=4, 螺纹=M6，置信 0.95
2. **厂商 A 记号**：`A80-6-M8`（A{n} 中 n 即 PCD）→ 置信 0.90
3. **散落几何（中英文，含中文数字孔数）**：`PCD 100 六孔 M10` / `pitch circle diameter 100 mm, 6 holes M10` → 置信 0.70

去重：同一 (PCD, 孔数, 螺纹) 视为同一候选。
仅产出 `ISO 9409-1` 圆形安装法兰；非 ISO 法兰（如 DYNAMIXEL 专有 horn）不误判。

## 4. 交付物

- **`functions/api/spec_declare.js`**（Cloudflare Pages Function）：POST `{text}` →
  `{ parsed, count, candidates[], proposed:{mechanical_interface}, references[] }`。
  `references` 复用 copilot 的「指给你看」体验（ISO 速查 / canonical 梯级 / 转接件生成器）。
- **`spec-declare.html`**：粘贴或拖入 `.txt/.md` 规格书 → 渲染候选 + 可复制的 partial 声明 JSON + 「指给你看」引用。
- **`scripts/spec_declare_cli.py`**：本地批量——`scripts/spec_declare_cli.py specs/*.txt --out proposals/`
  每份写出 `*.patch.json` 提案（不自动入库）。

## 5. 诚实边界（务必保留）

- AI 提取产物**只能是 partial**；升 declared 的三步人工动作（填官域 source_url / 逐字核对孔位 / 改 status）写在页面与 CLI 输出里，不由 AI 代做。
- 正则仅覆盖 ISO 9409-1 三项几何；厂商若用非标准标注（如 KUKA 型 A100-4-M8）可能漏提或误提，需人工在 partial 阶段把关。
- 这不是"自动填满数据"的魔法——它是把**人工最枯燥的读尺寸**这一步机器化，把**判断与担责**留给人工。

## 6. 后续（未在本轮落地，需你拍板/资源）

- **SSE 流式**：长规格书逐段提取可视化（依赖 P2 后端，非必需）。
- **PDF/OCR 直读**：浏览器端 pdf.js 解析、或对扫描件走 OCR 兜底（clicky-windows 思路）。当前仅支持纯文本拖入。
- **合入工作流**：人工在 partial 核实后，可由 `scripts/upgrade_*.py` 风格的脚本一键升 declared（仍需人工填 source_url）。
- 真正补齐 P0 数据仍需**你提供厂商规格书语料**（越多越准）——本工具是管道，不是数据源。
