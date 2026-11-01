/**
 * 积分套餐定义 —— 单一真相源
 *
 * 【20261031-P0-4】为什么抽出来：
 * 此前 payment/create.js、payment/notify.js、credits/balance.js 三处各自硬编码积分映射，
 * 且数值互相矛盾（如 balance.js 旧值 990/500/9999/4999 vs create.js 的 100/500/999999）。
 * 同一事实多处定义 = 后续某处腐烂，最终在无人察觉的情况下出现
 * 「用户付了 ¥29 到账积分与官方口径不一致」这类计费偏差。
 * 积分映射与 PREMIUM_FIELDS 同理：**同一事实只能有一处定义**。
 *
 * 口径（官方对外承诺）：
 * - starter : ¥9  / 100    积分
 * - pro     : ¥29 / 500    积分
 * - lifetime: ¥199/ 999999 积分（无限，占位用大数）
 */
export const PLANS = {
  starter: { price: 9, credits: 100, title: 'RoboParts Starter - 100积分' },
  pro: { price: 29, credits: 500, title: 'RoboParts Pro - 500积分' },
  lifetime: { price: 199, credits: 999999, title: 'RoboParts Lifetime - 无限积分' },
};
