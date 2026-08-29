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
