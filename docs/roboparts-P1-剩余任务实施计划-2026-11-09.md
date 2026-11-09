# P1 阶段剩余任务实施计划

**时间**: 2026-11-09 13:06 GMT+8  
**当前状态**: 前端构建已完成，JS↔Py 重放测试需集成  
**下一步**: 完成剩余 2 项 P1 高价值项

---

## 📋 剩余任务清单

### ✅ 已完成（7/9 项）
1. **adapter 5 源门** ✅
   - check_adapter_geometry.py 已实现
   - 11 例阴阳自证全部 PASS
   - 已集成到 CI（gate_adapter_geometry）

2. **pipeline→production** ✅
   - deploy.yml 含 gate + smoke 测试
   - 部署流水线完整

3. **包锁提交** ✅
   - package-lock.json 存在（60.3 KB）
   - 已在 ci.yml 使用 npm ci

4. **regen_derived --check** ✅
   - 已在 ci.yml 第 91-92 行集成
   - 派生产物一致性校验完整

5. **lint/format 进 CI** ✅
   - 已在 ci.yml 第 67-73 行集成
   - prettier + eslint 检查完整

6. **前端构建** ✅（刚完成）
   - build_flywheel_layer.mjs：OSS 反喂 325 条 → 贡献层 142 条
   - build_semantic_index.mjs：983 实体 × 256 维，0.70 MB
   - 产物：entities.contrib.json（98 KB） + semantic_index.json（717 KB）

7. **论文数字更新** ✅
   - docs/RoboParts-SCI达标核验-20261019.md 存在
   - 数字验证文档完整

### ⚠️ 待完成（2/9 项）

#### 1. JS↔Py 重放测试 CI 集成
- **当前状态**: verify_cross_engine_replay.py 已实现（8,335 字节）
- **问题**: gate_cross_engine_consistency 存在但调用 verify_cross_engine.py（旧版）
- **需求**: 
  - 生成事件流文件（从 compose-workbench.html 导出）
  - 更新 gate_cross_engine_consistency 调用 verify_cross_engine_replay.py
  - 集成到 ci.yml

#### 2. data.js 孤儿重估（决策项）
- **当前状态**: 被 397 文件引用（原 76 判断已过时）
- **决策**: 需评估是否可精简引用范围或模块化重构
- **影响**: 原计划删除 data.js 的决策需重新评估

---

## 🚀 实施步骤

### 步骤 1: JS↔Py 重放测试 CI 集成
1. **生成事件流文件**
   ```bash
   # 从 compose-workbench.html 导出事件流
   # 或创建测试用例事件流文件
   ```

2. **更新 ci_gate.py**
   ```python
   # 将 gate_cross_engine_consistency 中的
   # 'verify_cross_engine.py' 改为 'verify_cross_engine_replay.py'
   # 并添加事件流文件参数
   ```

3. **集成到 ci.yml**
   ```yaml
   - name: JS↔Py 重放测试
     run: python scripts/verify_cross_engine_replay.py tests/sample_event_stream.json
   ```

### 步骤 2: data.js 重评估
1. **分析 397 个引用文件**
   - 评估实际需求 vs 历史遗留
   - 识别可精简的范围

2. **提出重构方案**
   - 模块化拆分（如按功能拆分）
   - 或保持现状（确认非孤儿）

---

## 📊 项目状态总结

| P1 阶段项目 | 状态 | 完成度 | 备注 |
|-------------|------|--------|------|
| adapter 5 源门 | ✅ 已完成 | 100% | 11 例阴阳自证 PASS |
| JS↔Py 重放测试 | ⚠️ 需集成 | 80% | 脚本已实现，需 CI 集成 |
| pipeline→production | ✅ 已完成 | 100% | deploy.yml 完整 |
| 包锁提交 | ✅ 已完成 | 100% | package-lock.json 存在 |
| regen_derived --check | ✅ 已完成 | 100% | ci.yml 已集成 |
| lint/format 进 CI | ✅ 已完成 | 100% | ci.yml 已集成 |
| 前端构建 | ✅ 已完成 | 100% | 产物已生成 |
| 论文数字更新 | ✅ 已完成 | 100% | 文档存在 |
| data.js 孤儿重估 | ⚠️ 需决策 | 50% | 397 文件引用，需评估 |

**总体进度**: 7/9 项完成（78%），剩余 2 项需实施/决策

---

## 🎯 下一步行动

1. **立即执行**: JS↔Py 重放测试 CI 集成（预计 30 分钟）
2. **决策确认**: data.js 重评估方案（需用户确认）
3. **汇报**: 完成后向 Chief 汇报 P1 阶段最终状态

**执行边界**: 严格遵循只读+登记+归档原则，重大修改需用户授权