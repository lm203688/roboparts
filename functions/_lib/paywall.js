/**
 * 付费墙字段表 —— 单一真相源
 *
 * 【20260808-11】为什么要抽出来：
 * 本轮新增 `/api/entity/{id}` 时，需要与 `api/[[path]].js` 保持同一套"哪些字段属于
 * 付费层"的判定。若在新端点里再抄一份 PREMIUM_FIELDS，就会出现本仓反复踩过的那类
 * 缺陷 —— 两份清单起初一致，此后各自腐烂，最终某个端点在无人察觉的情况下把付费
 * 字段免费送出去。数字如此，字段清单同理：**同一事实只能有一处定义**。
 *
 * 这里只放"清单 + 投影函数"，不含鉴权逻辑。鉴权仍由各端点自行决定，
 * 因为不同端点的计费口径（是否扣积分、是否校验 license）并不相同。
 */

/** 免费层不返回的高价值字段（黑名单：新增的普通字段默认免费可见）。 */
export const PREMIUM_FIELDS = [
  'price_range',        // 价格区间（最有变现价值的字段）
  'compatibility',      // 兼容性结论
  'confidence',         // 数据置信度
  'source',             // 数据来源
  'source_url',         // 来源链接
  'standard_compliance',// 合规标签
  'standard',           // 合规标准
  'domestic_rate',      // 国产化率
  'import_dependency',  // 进口依赖度
  'last_verified',      // 最后核验时间
];

/**
 * 【P0-4 修复】开放数据集端点 —— 结构付费墙**明确豁免**。
 *
 * 为什么豁免：这些是**公开开放数据**（CC BY 4.0，见 DATA-LICENSE.md），站点文章与
 * 下载 CTA（"下载结构化数据 (JSON)"）公开承诺免费可获取；它们虽含 PREMIUM_FIELDS
 * 键，但按许可证与公开承诺必须保持免费。付费墙的真正商品是 `entities.json` 的
 * 深度字段视图与分析型产物的高级派生（见 PAYWALLED_DERIVED）。
 *
 * 此处作为单一事实源登记；`api/[[path]].js` 依此决定是否绕过付费墙。
 */
export const OPEN_DATASET_FILES = [
  'data.json',           // 公开数据集（文章/下载 CTA/CC BY 4.0）
  'oss_components.json', // 开源组件数据层（公开功能页，325 组件）
];

/**
 * 【P0-4 说明】判定类派生产物（co_mount/compose_semantics/standard-audit/
 * gap_classification/reachability_gap/parameter_semantics/demand-signal 等）**不在此
 * 屏蔽**：它们用 verdict/overall 词汇而非 PREMIUM_FIELDS 字面键，且 /mcp 端点与
 * /api/entity/{id} 已按公开接口暴露其判定结论 —— 保持免费是**与 /mcp 一致**的内部
 * 自洽（这正是本修复的备选口径之一："或明确标注为 free（与 /mcp 对齐）"）。
 * 真正需要屏蔽的是**字面携带 PREMIUM_FIELDS 键**的载荷，由 containsPremiumField
 * 结构判定捕获，配合下方 OPEN_DATASET_FILES 豁免开放数据集。
 */

/**
 * 返回剔除付费字段后的浅拷贝，并给出**这一条实体上实际被锁掉的字段名**。
 *
 * 注意返回的是 locked 的具体字段名而不是个数：调用方（以及 AI agent）需要知道
 * "缺的是什么"，只给一个数字等于让对方猜。字段不存在于该实体时不计入 —— 
 * 不把"我们本来就没这个数据"包装成"你没付费所以看不到"。
 */
export function maskPremium(entity) {
  const out = {};
  const locked = [];
  for (const [k, v] of Object.entries(entity || {})) {
    if (PREMIUM_FIELDS.includes(k)) locked.push(k);
    else out[k] = v;
  }
  return { entity: out, locked };
}

/**
 * 【P0-4 修复, 2026-10-31】深度判定：载荷里是否出现**任一** PREMIUM_FIELD 键。
 *
 * 为什么用"结构判定"而不是"文件名清单"：此前 `api/[[path]].js` 只对 entities.json
 * 套付费墙，其余承载付费字段的 JSON（compatibility_matrix/co_mount/compose_semantics/
 * standard-audit/training_dataset/gap_classification/reachability_gap…）全部裸奔。
 * 若改成"逐文件登记"，又会出现本仓反复踩的那类缺陷——新增一个文件忘登记，
 * 付费字段再次免费送出。**同一事实只能有一处定义**：以"字段是否出现"为准。
 */
export function containsPremiumField(node) {
  if (Array.isArray(node)) return node.some(containsPremiumField);
  if (node && typeof node === 'object') {
    for (const k of Object.keys(node)) {
      if (PREMIUM_FIELDS.includes(k)) return true;
      if (containsPremiumField(node[k])) return true;
    }
  }
  return false;
}

/**
 * 【P0-4 修复】深度屏蔽：递归**移除**所有 PREMIUM_FIELD 键（与实体级 maskPremium 同口径）。
 * 数组保持形状（元素逐个屏蔽）；对象剔除付费键；meta 亦照此处理。
 * 返回 { value, lockedCount } —— lockedCount 为被屏蔽键出现总次数（供 X-* 头/提示用）。
 */
export function maskPremiumDeep(node) {
  if (Array.isArray(node)) {
    let locked = 0;
    const arr = node.map(n => {
      const r = maskPremiumDeep(n);
      locked += r.lockedCount;
      return r.value;
    });
    return { value: arr, lockedCount: locked };
  }
  if (node && typeof node === 'object') {
    const out = {};
    let locked = 0;
    for (const [k, v] of Object.entries(node)) {
      if (PREMIUM_FIELDS.includes(k)) { locked += 1; continue; }
      const r = maskPremiumDeep(v);
      locked += r.lockedCount;
      out[k] = r.value;
    }
    return { value: out, lockedCount: locked };
  }
  return { value: node, lockedCount: 0 };
}
