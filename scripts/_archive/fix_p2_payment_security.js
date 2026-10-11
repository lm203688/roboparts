/**
 * P2 支付回调签名验证增强
 * 
 * 审计发现：notify.js 已有签名验证框架但缺少：
 * 1. 幂等性检查（重放保护）
 * 2. 签名缺失时的硬拒绝（当前静默通过）
 * 3. 时间戳校验（防止延迟重放）
 */

const fs = require('fs');
const path = require('path');

const notifyPath = path.join(__dirname, '..', 'functions', 'api', 'payment', 'notify.js');
if (!fs.existsSync(notifyPath)) {
  console.error('notify.js not found, skipping');
  process.exit(1);
}

let code = fs.readFileSync(notifyPath, 'utf8');

// === 修改 1：签名验证缺失时硬拒绝 ===
const oldSecretCheck = `    const secret = env.XUNHU_SECRET;
    if (!secret) {`;

const newSecretCheck = `    const secret = env.XUNHU_SECRET;
    if (!secret) {
      // 生产环境必须有密钥——否则无法验证签名
      console.error('[PAYMENT] XUNHU_SECRET not configured, rejecting callback');
      return new Response(JSON.stringify({
        error: 'Payment verification disabled',
        error_kind: 'no_secret_configured',
        message: 'Server configuration error: payment secret not set'
      }), { status: 503, headers: corsHeaders });`;

code = code.replace(oldSecretCheck, newSecretCheck);

// === 修改 2：签名缺失时硬拒绝 ===
const oldHashCheck = `    if (!hash) {`;
const newHashCheck = `    if (!hash) {
      console.error('[PAYMENT] No hash signature in callback, rejecting');
      return new Response(JSON.stringify({
        error: 'Missing signature',
        error_kind: 'no_hash',
        message: 'Payment callback must include hash signature'
      }), { status: 401, headers: corsHeaders });`;

code = code.replace(oldHashCheck, newHashCheck);

// === 修改 3：增加幂等性检查（trade_order_id 去重） ===
const idempotencyBlock = `
    // === 幂等性检查：防止重放攻击 ===
    const orderId = trade_order_id || open_order_id;
    if (orderId) {
      try {
        const existing = await env.PAYMENT_LEDGER.get('processed:' + orderId);
        if (existing) {
          console.log('[PAYMENT] Duplicate callback for order:', orderId, '- already processed');
          return new Response('success', { status: 200, headers: corsHeaders });
        }
      } catch (e) {
        console.error('[PAYMENT] Idempotency check failed:', e.message);
        // 继续处理，但记录错误
      }
    }`;

// 在 hash 验证之后、加积分之前插入
const insertionPoint = `      // 验证通过，处理支付
`;
if (code.includes(insertionPoint)) {
  code = code.replace(insertionPoint, idempotencyBlock + '\n' + insertionPoint);
}

// === 修改 4：时间戳校验（15 分钟窗口） ===
const timestampCheck = `
    // === 时间戳校验：防止延迟重放（窗口 15 分钟）===
    if (time) {
      const callbackTime = parseInt(time) * 1000; // 虎皮椒时间戳通常是秒
      const now = Date.now();
      const diff = Math.abs(now - callbackTime);
      if (diff > 15 * 60 * 1000) {
        console.error('[PAYMENT] Timestamp too old or in future:', diff / 1000, 'seconds');
        return new Response(JSON.stringify({
          error: 'Timestamp expired',
          error_kind: 'timestamp_out_of_window',
          window_seconds: 900
        }), { status: 401, headers: corsHeaders });
      }
    }`;

if (code.includes(insertionPoint) && !code.includes('Timestamp expired')) {
  code = code.replace(insertionPoint, timestampCheck + '\n' + insertionPoint);
}

// === 修改 5：记录已处理的订单 ID ===
const recordProcessed = `
    // === 记录已处理订单（幂等性锚点）===
    if (orderId) {
      try {
        await env.PAYMENT_LEDGER.put('processed:' + orderId, JSON.stringify({
          processed_at: new Date().toISOString(),
          status: status,
          total_fee: total_fee,
        }), { expirationTtl: 86400 * 30 }); // 保留 30 天
      } catch (e) {
        console.error('[PAYMENT] Failed to record processed order:', e.message);
      }
    }`;

// 在返回 success 之前插入
const successReturn = `return new Response('success', { status: 200, headers: corsHeaders });`;
if (code.includes(successReturn) && !code.includes('recordProcessed')) {
  code = code.replace(successReturn, recordProcessed + '\n    ' + successReturn);
}

fs.writeFileSync(notifyPath, code);
console.log('✅ notify.js 安全增强完成');
console.log('  1. 签名缺失时硬拒绝（401）');
console.log('  2. 密钥未配置时硬拒绝（503）');
console.log('  3. 幂等性检查（trade_order_id 去重）');
console.log('  4. 时间戳校验（15 分钟窗口）');
console.log('  5. 已处理订单记录（30 天 TTL）');
