# scripts/

RoboParts 的运维脚本目录。工程化分层：

## 层级

```
scripts/
├── ci_gate.py                    # 主闸门：所有断言（收口用）
├── regression.py                 # L1.1–L1.195 回归层（含反向注入）
├── build_research_progress.py    # 生成 api/research_progress.json
├── build_*.py                    # 各类数据构建产物
├── verify_*.py / verify_*.mjs    # 反向注入验证（mutation tests）
├── deploy.mjs                    # Cloudflare Pages 部署
├── push_*.py / push_*.mjs        # GitHub Contents API 推送
├── ingest_*.mjs / .py            # 外部数据入库
├── _pdf_text_probe.py            # 人工取证工具（一次性用法）
├── lib/                          # 可复用库
├── pipeline/                     # 数据流水线
├── tests/                        # ← 见 ../tests/
└── _archive/                     # 一次性脚本归档（不参与 CI）
```

## 三类"验证"脚本的边界（重要）

| 类型 | 文件命名 | 目的 | 何时跑 |
|---|---|---|---|
| **主闸门** | `ci_gate.py` | 收口验收：所有断言聚合 | 提交前必跑 |
| **回归层** | `regression.py` | 按层 L1.1–L1.195 逐条检查数据产物 | 主闸门内部调用 |
| **反向注入** | `verify_*_injections.py/.mjs` | **故意改坏数据 → 断言闸门变红**（证明闸门不是恒绿摆设） | 新增/修改断言时必跑 |

### 反向注入的必要性

本仓历史上栽过 3 次「恒绿假绿」（括号深度判顶层、裸子串比数字、两个子串各自都在）。**任何新增断言必须证明它能红**，否则等于没写。`verify_l130/132/134-l144/oss_tristate_injections` 就是这些断言的自证。

## `_archive/` 边界

`scripts/_archive/` 存放**一次性历史脚本**（fix_*、curate_*_YYYYMMDD、upgrade_*_mi_*、push/deploy workaround 等）。规则：

- 不参与 `ci_gate.py` / `regression.py`
- 通过 `git mv` 归档（保留历史路径，可 `git log -p` 追溯）
- 归档不代表删除——如某段逻辑仍需参考，直接读文件即可

详见 [`_archive/README.md`](_archive/README.md)。

## 与 `tests/` 的分工

- `scripts/` 里的 `verify_*_injections.py` 是**断言的自证**（mutation tests），跑在 CI 里
- `tests/` 是**集成测试**（跑通端到端业务流程），独立目录、独立入口

## 常见误区

- **不要**把归档脚本"捡回来"到主目录 —— 一次性脚本重新引入会污染 CI 信号
- **不要**在 `scripts/` 主目录新增一次性脚本 —— 要么走 `build_*.py`（长期产物）要么直接落 `_archive/`
- **`_pdf_text_probe.py`** 是人工取证工具，不进 CI，只在你手动核对厂商手册原文时用
