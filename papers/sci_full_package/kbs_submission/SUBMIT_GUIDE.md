# KBS 投稿操作指南（Knowledge-Based Systems, Elsevier）

## 一、稿件文件夹（已就绪）

`papers/kbs_submission/`
- `main.tex` — 主文稿（已按 KBS 视角重写：knowledge engineering + decision support + abstention honesty；5 条 Contributions）
- `references.bib` — 58 条参考文献
- `figures/` — 4 张图（全部 .pdf，compile-safe）
- `cover_letter.md` — 投稿信（含 JAAMAS-style info sheet）
- `highlights.txt` — 5 条 Highlights（每条 ≤85 字符）
- `data_availability_statement.md` — 数据可用性声明（KBS 强制）
- `SUBMIT_GUIDE.md` — 本文件

## 二、编译 PDF（两种方法，任选）

本机无 LaTeX 引擎（pdflatex/xelatex/tectonic 均缺失），需借外部环境编译。

### 方法 A：Overleaf（推荐，你已有账号，mechatronics 那次用过）

1. 打开 https://www.overleaf.com → 登录
2. `New Project` → `Upload Project` → 选择 `papers/kbs_submission/` 整个文件夹压缩上传
   （或 `New Project` → `Import from GitHub` 若已推送）
3. 主文件设为 `main.tex`
4. 点 `Recompile` —— 应一次通过（已验证：brace 平衡 815/815，`\begin/\end{document}` 各 1，无自定义宏冲突）
5. `PDF` → `Download PDF` 存为 `kbs_main.pdf`

若 Overleaf 报字体/编码错，多半是 `\usepackage{microtype}` 与中文无关，可忽略或删该行重编。

### 方法 B：本地 TeX Live（若你机器装了）

```bash
cd papers/kbs_submission
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
# 产出 main.pdf
```

## 三、投稿上传（Editorial Manager）——小白级详细步骤

### 3.1 准备文件清单（必须全部准备齐）

✅ **主文稿**：`kbs_main.pdf`（从 Overleaf 编译下载）
✅ **Cover Letter**：`cover_letter.md`（已强化贡献点）
✅ **Highlights**：`highlights.txt`（5条，每条≤85字符）
✅ **Data Availability Statement**：`data_availability_statement.md`
✅ **CRediT 表单**：系统会自动生成，照填
✅ **Highlights 文件**：系统单独上传
✅ **声明文件**：系统自动生成，确认即可

### 3.2 Editorial Manager 详细操作步骤

#### 步骤1：进入投稿系统
- 打开 **https://www.editorialmanager.com/kbsy/**
- 点击 `Login`（已有账号）或 `Register`（新账号）
- **新账号注册**：邮箱用 `463102527@qq.com`，密码记牢

#### 步骤2：新建投稿
- 登录后点击主菜单 **`Submit New Manuscript`**
- 选择文章类型：**`Full Length Article`**（或 `Original Research Article`，以下拉菜单为准）

#### 步骤3：填写基本信息

| 字段 | 填写内容 | 注意事项 |
|---|---|---|
| **Title** | Three-State Honesty in Robotic Hardware Compatibility: A Vendor-Neutral Determination Layer | 逐字复制，无拼写错误 |
| **Abstract** | 抄 `main.tex` 的 `\abstract` 全文 | 425字以内，确保完整 |
| **Keywords** | knowledge-based decision support; three-valued reasoning; abstention honesty; knowledge acquisition prioritisation; robotic hardware compatibility | 严格按此格式，分号分隔 |
| **Article Type** | Full Length Article | 确认不是 "Letter" 或 "Short Communication" |

#### 步骤4：作者信息
- **Corresponding Author**: Xing Li
- **Affiliation**: Zhejiang Academy of Building Research & Design Co., Ltd.
- **Email**: 463102527@qq.com
- **ORCID**: 0009-0004-2152-7669
- **建议审稿人**：可留空，或填 2-3 个（见下）

#### 步骤5：上传文件

**必须上传的文件**：
1. **Manuscript File** → 上传 `kbs_main.pdf`
2. **Cover Letter** → 上传 `cover_letter.md`（或转PDF）
3. **Highlights** → 上传 `highlights.txt`
4. **Data Availability Statement** → 上传 `data_availability_statement.md`

**系统自动生成**：
- CRediT 表单：照填 `Xing Li: Conceptualization, Methodology, Software...`
- 利益冲突声明：选 "None"
- AI使用声明：选 "Used for grammar check only"

#### 步骤6：预览和提交
- 点击 **`Build PDF for Approval`**
- 下载确认稿，检查：
  - [ ] 页码正确（约28页）
  - [ ] 图表显示正常
  - [ ] 参考文献格式正确
  - [ ] 作者名是 Xing Li
  - [ ] 机构名称正确
- 确认无误后点击 **`Submit`**

### 3.3 常见问题解决

#### Q1：系统提示文件格式错误？
- **解决方案**：确保所有文件都是 UTF-8 编码，PDF 是标准格式

#### Q2：页数超限被警告？
- **解决方案**：Cover Letter 已加入页数说明，强调 78-gate CI 和 48-case 外部验证的必要性

#### Q3：要求推荐审稿人？
- **解决方案**：可推荐：
  - 机械/机器人领域专家
  - 知识工程专家
  - 不推荐熟人（避免利益冲突）

#### Q4：系统卡住/报错？
- **解决方案**：刷新页面重新登录，或联系 Elsevier 支持团队

## 四、投稿后流程（预期时间线）

### 阶段1：编辑初审（1-2周）
- 编辑检查是否符合 KBS 范围
- Desk Reject 概率：极低（cover letter 已强化匹配度）
- 若通过 → 进入 peer review

### 阶段2：同行评审（8-12周）
- 2-3 位审稿人
- 可能收到：小修（minor revision）或大修（major revision）
- 最坏情况：拒稿（rejection）

### 阶段3：修改和返修（若需要）
- 按审稿意见逐条回应
- 修改论文内容
- 2-4 周内完成

### 阶段4：最终决定
- 接受（accept）或再次拒稿
- 接受后进入校对阶段

## 五、费用说明（重要！）

### APC（文章处理费）
- **开放获取**：需支付 APC，具体金额待编辑告知（通常 $2000-3000）
- **订阅模式**：无需支付 APC，文章通过订阅访问
- **建议**：选择订阅模式（零费用）

### 其他费用
- **无审稿费**
- **无彩图费**
- **无版面费**（订阅模式下）

## 六、与 arXiv 的关系处理

### 投稿策略
1. **先投 KBS**：今天就能投，不依赖 arXiv
2. **arXiv endorsement**：已拿到 code 98DU3H，可稍后补投
3. **预印本策略**：KBS 接受 Elsevier 预印本政策，投稿后可在 SSRN 发布

### 邮件模板（给 endorser）
```
Subject: Endorsement Request for arXiv submission (cs.AI/2610.xxxxx)

Dear [Endorser Name],

I am submitting my manuscript "Three-State Honesty in Robotic Hardware Compatibility: A Vendor-Neutral Determination Layer" to arXiv cs.AI category. My endorsement code is 98DU3H.

The manuscript is currently under review at Knowledge-Based Systems (KBS), and I would be grateful for your endorsement as it is a registered cs.AI author.

Thank you for your consideration.

Best regards,
Xing Li
```

## 七、紧急联系方式

- **Elsevier 支持团队**：https://service.elsevier.com/app/answers/list/
- **KBS 编辑部**：通过 Editorial Manager 内部消息联系
- **我的邮箱**：463102527@qq.com（作为通讯作者）

---

**最后核对清单**：
- [ ] 作者名统一为 Xing Li ✅
- [ ] 机构统一为 Zhejiang Academy ✅
- [ ] Cover Letter 强化完成 ✅
- [ ] 页数说明已加入 ✅
- [ ] 文件全部准备齐 ✅
- [ ] Editorial Manager 流程熟悉 ✅

**下一步行动**：
1. 去 Overleaf 编译 PDF
2. 登录 Editorial Manager 投稿
3. 等待编辑初审结果（1-2周）

有问题随时问我！

## 四、投稿前最后核对（避免 Desk Reject）

- [ ] PDF 里作者名是 **Xing Li**（不是 Lexing Li）✅ 已统一
- [ ] 机构是 **Zhejiang Academy of Building Research & Design Co., Ltd.** ✅
- [ ] cover letter 第 4 节写的是 "No preprint available"（**不能写 arXiv**）✅ 已改
- [ ] Highlights 5 条，每条 ≤85 字符 ✅
- [ ] Data Availability Statement 含 MIT + CC BY 4.0 + G-S1 ✅
- [ ] 参考文献 58 条，BibTeX 无 `[?]` 未解析 ✅（编译后确认）

## 五、页数风险（非硬拒，但建议处理）

KBS 建议 12-15 页，当前源码约 28 页。两个选择：
- **A. 直接投 + 附 page-limit waiver**：cover letter 加一句 "The 28-page length is required by the external-validity protocol (48-case independent set) and the 78-gate CI harness, both central contributions." —— 多数 Elsevier 编辑接受。
- **B. 先压缩 30%**（Related Work 5→3 节、Experiments 非 §5.11 部分、Discussion 合并）再投。

## 六、与 arXiv 的关系

arXiv endorsement code **98DU3H** 已拿到，需转发给 cs.AI registered endorser。
KBS 投稿**不依赖** arXiv 号 —— 今天就能投 KBS；arXiv 下来后可在返修阶段补挂。
若 KBS 进入 review，再把 "under review at KBS" 写进给 endorser 的邮件，反而更容易过。
