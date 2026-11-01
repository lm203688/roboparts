/**
 * Creem Webhook Handler
 * Receives payment events from Creem and credits user accounts
 *
 * Supported events:
 *   - checkout.completed  (one-time payment)
 *   - subscription.active   (new subscription)
 *   - subscription.paid     (recurring payment)
 *   - subscription.canceled (cancellation — revoke access)
 *
 * Signature verification:
 *   - Header: creem-signature (official Creem header name)
 *   - Also accepts: x-creem-signature (backward compatibility)
 *   - Algorithm: HMAC-SHA256 with CREEM_WEBHOOK_SECRET
 *   - FAIL-CLOSED (P0-2 修复, 2026-10-31):
 *       * CREEM_WEBHOOK_SECRET 未配置 => 直接 503，绝不静默跳过验签。
 *         （旧逻辑 `console.warn(...skipping...)` 是 fail-open：
 *          未配置密钥时任何人都能铸积分。）
 *       * 无签名头但密钥已配置 => 401 拒绝。
 *       * 有签名头但验签不符 => 401 拒绝。
 *
 * Security note: Cloudflare KV is encrypted at rest. The email_hash field
 * (SHA-256) is an additional application-layer security measure that allows
 * email-based lookups/comparisons without relying on the plaintext value.
 */

import { appendLedger } from '../../_lib/ledger.js';
import { runIdempotent } from '../../_lib/idempotency.js';

/**
 * Hash an email address with SHA-256 (lowercased + trimmed for consistency).
 * Uses the Web Crypto API available in Cloudflare Workers runtime.
 * @param {string} email
 * @returns {Promise<string>} hex-encoded SHA-256 digest
 */
async function hashEmail(email) {
  const encoder = new TextEncoder();
  const data = encoder.encode(email.toLowerCase().trim());
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

const corsHeaders = {
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, creem-signature, x-creem-signature',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    // === Signature verification (HMAC-SHA256) ===
    // Creem official header: creem-signature
    // Backward compat: x-creem-signature
    const signature = request.headers.get('creem-signature') ||
                       request.headers.get('x-creem-signature') || '';
    const rawBody = await request.text();

    // P0-2 修复（2026-10-31）：FAIL-CLOSED 验签。
    // 旧逻辑：`else if (!env.CREEM_WEBHOOK_SECRET) { console.warn('skipping') }`
    //   —— 密钥未配置时静默跳过验签，任何人可铸积分。这是 fail-open。
    // 现在：密钥未配置 => 503（不处理任何事件）；无签名头 => 401；验签不符 => 401。
    if (!env.CREEM_WEBHOOK_SECRET) {
      console.error('Creem webhook: CREEM_WEBHOOK_SECRET not configured, rejecting (fail-closed)');
      return new Response(JSON.stringify({
        error: 'Webhook verification unavailable',
        error_kind: 'secret_not_configured',
      }), { status: 503, headers: corsHeaders });
    }
    if (!signature) {
      console.error('Creem webhook: missing signature, rejecting (fail-closed)');
      return new Response(JSON.stringify({ error: 'Missing signature' }), {
        status: 401, headers: corsHeaders
      });
    }
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      'raw', encoder.encode(env.CREEM_WEBHOOK_SECRET),
      { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
    );
    const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(rawBody));
    const expected = Array.from(new Uint8Array(sig))
      .map(b => b.toString(16).padStart(2, '0')).join('');
    if (signature !== expected) {
      console.error('Creem webhook: signature mismatch');
      return new Response(JSON.stringify({ error: 'Invalid signature' }), {
        status: 401, headers: corsHeaders
      });
    }

    const body = JSON.parse(rawBody);

    // === Parse event (Creem official format) ===
    // Format: { eventType: "checkout.completed", object: { order, product, customer, subscription, metadata } }
    // Legacy format: { event: "payment.completed", data: { ... } }
    const eventType = body.eventType || body.event || '';
    console.log('Creem webhook:', eventType);

    // Normalize data extraction from both formats
    const obj = body.object || body.data || {};
    const order = obj.order || {};
    const product = obj.product || {};
    const customer = obj.customer || {};
    const subscription = obj.subscription || {};
    const metadata = obj.metadata || body.data?.metadata || {};

    // Extract useful fields
    const email = customer.email || order.customer_email || body.data?.customer?.email || '';
    const productId = product.id || order.product || body.data?.product?.id || '';
    const productName = product.name || '';
    const amount = order.amount || product.price || body.data?.amount || 0;
    // amount in Creem is in cents (e.g., 2900 = $29.00)
    const amountDollars = amount / 100;
    const metadataApiKey = metadata.api_key || metadata.referenceId || body.data?.metadata?.api_key || '';
    const subscriptionId = subscription.id || '';
    const subscriptionStatus = subscription.status || '';

    // === Handle payment events ===
    const isPaymentEvent = [
      'checkout.completed',
      'payment.completed',
      'subscription.active',
      'subscription.paid',
      'license.activated',
    ].includes(eventType);

    const isCancelEvent = [
      'subscription.canceled',
      'subscription.expired',
    ].includes(eventType);

    if (isPaymentEvent) {
      // Credit mapping based on amount (in dollars) — 1 credit = 1 API call, credits never expire
      let credits = 0;
      if (amountDollars >= 99) credits = 999999;     // Lifetime (unlimited)
      else if (amountDollars >= 49) credits = 990;     // Data pack
      else if (amountDollars >= 29) credits = 500;     // Pro
      else if (amountDollars >= 9) credits = 100;      // Starter
      else credits = 100; // Minimum

      if (env.USER_CREDITS) {
        // Idempotency key: payment_id + email + event type + amount
        const idempotencyKey = `creem_payment_${body.data?.payment_id || body.eventId || body.id || eventType}_${email}_${amount}_${productId}`;
        
        // Wrap credit granting in idempotent transaction.
        // skipReplay: true —— 加积分是**有副作用**的 fn，重复投递/重放时**绝不重跑 fn**
        // （否则二次入账 + deepEqual 对"余额已变"判 conflict，KV 被写坏）。
        // 首次结果即权威，回放只读、只回放首次结果。
        const idempotentResult = await runIdempotent(env, idempotencyKey, async () => {
          // Determine user key
          let userKey;
          if (metadataApiKey && metadataApiKey.startsWith('gtk_')) {
            userKey = metadataApiKey;
          } else {
            // Generate new key for unknown users
            userKey = 'gtk_' + Array.from(crypto.getRandomValues(new Uint8Array(24)))
              .map(b => b.toString(16).padStart(2, '0')).join('');
          }

          const existing = await env.USER_CREDITS.get(userKey);
          const now = new Date().toISOString();
          const user = existing ? JSON.parse(existing) : {
            email,
            credits: 0,
            plan: 'free',
            api_calls: 0,
            created: now,
          };

          // Add credits
          user.credits = (user.credits || 0) + credits;
          if (email) {
            // Compute SHA-256 hash of the email for application-layer lookups
            // Never store plaintext email — only the hash
            user.email_hash = await hashEmail(email);
          }
          user.plan = 'pro';
          user.updated = now;

          // Store subscription info if applicable
          if (subscriptionId) {
            user.creem_subscription_id = subscriptionId;
            user.creem_subscription_status = subscriptionStatus;
            user.creem_product_id = productId;
            user.creem_product_name = productName;
          }

          await env.USER_CREDITS.put(userKey, JSON.stringify(user));

          // Record credit history
          // 这是全站最要命的一处：钱**已经**进来了、余额**已经**加上了。
          // 旧写法 `if (env.USER_CREDIT_HISTORY) {...}` 在该 KV 从未绑定的生产环境里恒为 false，
          // 于是真实付款一条账本都没留，用户打开 /credits-history.html 看到的是
          // 「暂无消费记录 · 您的账户暂无积分变动记录」——他刚付过钱。
          // 现在走统一入口（回落到已绑定的 USER_CREDITS），并且**失败必须外露**：
          // 静默吞掉写账失败 = 制造一笔查无对证的收款。
          const ledgerWrite = await appendLedger(env, userKey, {
            type: 'creem_payment',
            amount: credits,
            balance: user.credits,
            description: `Creem ${productName || eventType}: $${amountDollars}`,
            event_type: eventType,
            product_id: productId,
            subscription_id: subscriptionId,
            timestamp: now,
          });
          if (!ledgerWrite.ok) {
            console.error('[creem-webhook] LEDGER WRITE FAILED — 已入账但无账本留痕', {
              api_key: userKey, credits, event: eventType,
              subscription_id: subscriptionId, reason: ledgerWrite.reason, backend: ledgerWrite.backend,
            });
          } else if (ledgerWrite.degraded) {
            console.error('[creem-webhook] ledger degraded', { api_key: userKey, degraded: ledgerWrite.degraded });
          }

          return {
            userKey,
            creditsAdded: credits,
            totalCredits: user.credits,
            ledgerRecorded: ledgerWrite.ok,
            ledgerError: ledgerWrite.ok ? undefined : ledgerWrite.reason,
            ledgerDegraded: ledgerWrite.degraded,
          };
        }, { skipReplay: true });

        if (idempotentResult.status === 'replayed') {
          console.log(`Creem webhook: replayed idempotent payment for ${idempotentResult.result.userKey} (${email})`);
          return new Response(JSON.stringify({
            success: true,
            api_key: idempotentResult.result.userKey,
            credits_added: idempotentResult.result.creditsAdded,
            total_credits: idempotentResult.result.totalCredits,
            event: eventType,
            ledger_recorded: idempotentResult.result.ledgerRecorded,
            ledger_error: idempotentResult.result.ledgerError,
            ledger_degraded: idempotentResult.result.ledgerDegraded,
            idempotency_status: 'replayed',
          }), { headers: corsHeaders });
        } else if (idempotentResult.status === 'created') {
          console.log(`Creem webhook: credited ${idempotentResult.result.creditsAdded} to ${idempotentResult.result.userKey} (${email}) for ${eventType}`);
          return new Response(JSON.stringify({
            success: true,
            api_key: idempotentResult.result.userKey,
            credits_added: idempotentResult.result.creditsAdded,
            total_credits: idempotentResult.result.totalCredits,
            event: eventType,
            ledger_recorded: idempotentResult.result.ledgerRecorded,
            ledger_error: idempotentResult.result.ledgerError,
            ledger_degraded: idempotentResult.result.ledgerDegraded,
            idempotency_status: 'created',
          }), { headers: corsHeaders });
        } else {
          console.error('[creem-webhook] idempotency failure', idempotentResult);
          return new Response(JSON.stringify({
            success: false,
            error: idempotentResult.reason,
            idempotency_status: idempotentResult.status,
            event: eventType,
          }), { status: 409, headers: corsHeaders });
        }
      }
    }

    if (isCancelEvent) {
      // Revoke pro access on cancellation
      if (env.USER_CREDITS && metadataApiKey && metadataApiKey.startsWith('gtk_')) {
        const existing = await env.USER_CREDITS.get(metadataApiKey);
        if (existing) {
          const user = JSON.parse(existing);
          user.plan = 'free';
          user.creem_subscription_status = 'canceled';
          user.creem_canceled_at = new Date().toISOString();
          await env.USER_CREDITS.put(metadataApiKey, JSON.stringify(user));
          console.log(`Creem webhook: revoked pro for ${metadataApiKey} (${eventType})`);
        }
      }

      return new Response(JSON.stringify({
        success: true,
        action: 'subscription_canceled',
        event: eventType,
      }), { headers: corsHeaders });
    }

    // Unknown/ignored event
    return new Response(JSON.stringify({
      success: true,
      ignored: true,
      event: eventType,
    }), { headers: corsHeaders });

  } catch(e) {
    console.error('Creem webhook error:', e);
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: corsHeaders
    });
  }
}
