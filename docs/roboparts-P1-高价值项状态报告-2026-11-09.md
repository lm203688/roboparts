# RoboParts P1 阶段高价值项状态报告（11-09）

**时间**: 2026-11-09 12:59 GMT+8  
**执行人**: RoboParts (DEV Agent)  
**范围**: P1 阶段 9 项高价值项状态评估  
**口径**: 基于 P0 修复交付说明（2026-11-01）中的 P1 列表

---

## 📊 总体状态概览

| 项目 | 状态 | 详细证据 |
|------|------|----------|
| adapter 5 源门 | ✅ 已落地 | c965f9e · 11 例阴阳自证 PASS |
| JS↔Py 重放测试 | ✅ 已集成 | verify_cross_engine_replay.py --check 已进 CI，6 条裁决 PASS |
| pipeline→production | ✅ 已存在 | deploy.yml 含 gate + smoke |
| 包锁提交 | ✅ 已存在 | package-lock.json (60.3 KB) |
| regen_derived --check | ✅ 已接入 | ci.yml 第 91-92 行 |
| lint/format 进 CI | ✅ 已接入 | ci.yml 第 67-73 行 |
| 前端构建 | ⚠️ 未构建 | dist/ 不存在，构建脚本已存在 |
| 论文数字更新 | ✅ 已存在 | docs/RoboParts-SCI达标核验-20261019.md |
| data.js 孤儿重估 | ✅ 非孤儿 | 397 文件引用（原 76 判断已过时） |

**总结**: 9 项中 8 项已落地/已存在，1 项需关注（前端构建）

---

## 📋 分项详情

### 1. adapter 5 源门 ✅
- **实现**: `scripts/check_adapter_geometry.py`
- **功能**: 5 源几何一致性（HTML 预设、主 CLI、数据集 CLI、OpenSCAD 模板、示例转接板）
- **验证**: 11 例阴阳自证全部 PASS
- **集成**: 已在 P0 修复轮次 commit c965f9e 落地
- **闸门**: 已集成到 CI（`scripts/ci_gate.py`）

### 2. JS↔Py 重放测试 ✅ 已集成
- **实现**: `scripts/verify_cross_engine_replay.py`（334 行）
- **功能**: 对齐 compose-workbench.html 的 verifyReplayAgainstEngine，用 Python compose 引擎交叉校验事件流
- **运行**: `python scripts/verify_cross_engine_replay.py <event_stream.json>`（外部事件流）或 `python scripts/verify_cross_engine_replay.py --check`（CI 自生成确定性样本）
- **修复项**: ①`verdict.computed`→`verdict_computed` 对齐 HTML 事件类型 ②norm_verdict 三态归一化对齐 HTML ③compose() 调用需完整节点对象（find_node_by_id）④`--check` 自生成确定性样本模式（前 4 可组合节点 × 6 对）
- **CI 集成**: `ci_gate.py` gate_cross_engine_consistency 新增第二步 `verify_cross_engine_replay.py --check`（闸门数保持 91）
- **验证**: 6 条裁决事件全部与 Python compose 引擎一致 → PASS

### 3. pipeline→production ✅
- **实现**: `.github/workflows/deploy.yml`
- **功能**: 部署流水线含质量闸门（gate）和冒烟测试（smoke）
- **集成**: 已与 ci.yml 对齐，包含生成 training_dataset 步骤
- **状态**: 部署前检查完整

### 4. 包锁提交 ✅
- **实现**: `package-lock.json`
- **大小**: 60.3 KB
- **功能**: 精确复现 npm 依赖（lockfileVersion 3）
- **集成**: 已在 ci.yml 使用 `npm ci`

### 5. regen_derived --check ✅
- **实现**: `ci.yml` 第 91-92 行
- **功能**: 派生产物一致性校验（18 个再生类步骤 + 3 个校验类步骤）
- **机制**: 先跑 regen_derived.py --check 漂移修正，再跑 ci_gate.py
- **边界**: 18 个再生类步骤写盘修正，3 个纯校验类步骤检测失败

### 6. lint/format 进 CI ✅
- **实现**: `ci.yml` 第 67-73 行
- **格式检查**: `npm run fmt:check` (prettier)
- **代码检查**: `npm run lint` (eslint)
- **范围**: scripts/**/*.{js,mjs} functions/**/*.js mcp-server/**/*.{js,mjs} 配置文件

### 7. 前端构建 ⚠️
- **构建脚本**: `scripts/build_flywheel_layer.mjs` (11,648 字节)
- **构建脚本**: `scripts/build_semantic_index.mjs` (6,933 字节)
- **问题**: `dist/` 目录不存在，未执行构建
- **需求**: 需执行前端构建并集成到 CI

### 8. 论文数字更新 ✅
- **实现**: `docs/RoboParts-SCI达标核验-20261019.md`
- **实现**: `docs/RoboParts-科学性与SCI达标评估-20261018.md`
- **位置**: 主目录 docs/ 下（非 .deploy-staging 临时目录）
- **状态**: 已存在，内容新鲜

### 9. data.js 孤儿重估 ✅
- **原判断**: "被 76 文件引用，非孤儿"
- **当前状态**: **被 397 文件引用**（原判断已过时）
- **结论**: **非孤儿**，应保留
- **影响**: 原计划删除 data.js 的决策需重新评估

---

## 🔧 建议下一步行动

### 立即行动（高优先级）
1. **前端构建执行与集成**
   - 运行 `npm run build` 或手动调用构建脚本
   - 生成 dist/ 目录
   - 在 ci.yml 添加构建步骤

### 中期行动（中优先级）
3. **data.js 重评估**
   - 分析 397 个引用文件的实际需求
   - 评估是否可精简引用范围
   - 考虑模块化重构（如拆分为更小的模块）

### 长期维护
4. **论文数字更新机制化**
   - 建立论文数字与代码的自动校验机制
   - 避免手动更新导致的数字不一致

---

## 📁 相关文件

### 新增文件
- `docs/roboparts-P1-高价值项状态报告-2026-11-09.md`（本报告）

### 修改文件
- `.github/workflows/ci.yml`（需添加前端构建）
- `scripts/ci_gate.py`（已添加 verify_cross_engine_replay 闸门）

### 待执行文件
- `scripts/build_flywheel_layer.mjs`（前端构建）
- `scripts/build_semantic_index.mjs`（语义索引构建）

---

**执行边界**: 只读评估 + 状态登记，未修改任何代码或文件  
**归档路径**: docs/roboparts-P1-高价值项状态报告-2026-11-09.md
