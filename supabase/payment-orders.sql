-- =============================================
-- RoboLink 支付订单表（虎皮椒支付）
-- 在 Supabase Dashboard > SQL Editor 中执行
-- =============================================

-- 9. 支付订单表
CREATE TABLE IF NOT EXISTS public.payment_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_order_id TEXT UNIQUE NOT NULL,  -- 虎皮椒订单号
  stl_id TEXT NOT NULL,                  -- STL设计ID
  stl_name TEXT,                         -- STL名称
  amount DECIMAL(10,2),                  -- 订单金额
  payment_type TEXT,                     -- wechat / alipay
  material TEXT DEFAULT 'PLA',           -- 打印材料
  shipping TEXT DEFAULT 'standard',      -- 配送方式
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending','paid','refunded','refunding','refund_failed','expired')),
  transaction_id TEXT,                  -- 第三方交易号
  paid_amount DECIMAL(10,2),             -- 实际支付金额
  paid_at TIMESTAMPTZ,                   -- 支付时间
  nonce_str TEXT,                        -- 随机字符串
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE public.payment_orders ENABLE ROW LEVEL SECURITY;

-- 允许匿名插入（API创建订单）
CREATE POLICY "payment_orders_insert" ON public.payment_orders
  FOR INSERT WITH CHECK (true);

-- 允许匿名读取（前端查询订单状态）
CREATE POLICY "payment_orders_select" ON public.payment_orders
  FOR SELECT USING (true);

-- 允许匿名更新（支付回调更新状态）
CREATE POLICY "payment_orders_update" ON public.payment_orders
  FOR UPDATE USING (true);

-- 索引
CREATE INDEX idx_payment_orders_trade ON public.payment_orders(trade_order_id);
CREATE INDEX idx_payment_orders_status ON public.payment_orders(status);
CREATE INDEX idx_payment_orders_user ON public.payment_orders(user_id);
