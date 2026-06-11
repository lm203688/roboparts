// ==========================================
// RoboLink - 虎皮椒支付系统（前端）
// 支持：微信支付 / 支付宝
// PC端显示QR码，移动端自动跳转
// ==========================================

const PaymentSystem = {
  isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),

  materials: [
    { id: 'PLA', name: 'PLA (推荐)', desc: '环保材料，适合展示件和原型', extra: 0 },
    { id: 'PETG', name: 'PETG', desc: '更耐用耐温，适合功能性零件', extra: 5 },
    { id: 'ABS', name: 'ABS', desc: '工业级强度，耐冲击', extra: 8 },
    { id: 'TPU', name: 'TPU (柔性)', desc: '橡胶弹性体，适合夹爪指尖', extra: 12 },
  ],

  shipping: [
    { id: 'standard', name: '标准快递', desc: '3-5天送达', extra: 0 },
    { id: 'express', name: '加急快递', desc: '顺丰1-2天送达', extra: 10 },
  ],

  state: {
    design: null,
    material: 'PLA',
    shippingType: 'standard',
    orderId: null,
    pollTimer: null,
    step: 'select', // select | paying | success | error
  },

  // === 入口 ===
  open(design) {
    this.state.design = design;
    this.state.material = 'PLA';
    this.state.shippingType = 'standard';
    this.state.step = 'select';
    this.state.orderId = null;
    this.render();
  },

  close() {
    if (this.state.pollTimer) {
      clearInterval(this.state.pollTimer);
      this.state.pollTimer = null;
    }
    const modal = document.getElementById('payModal');
    if (modal) {
      modal.style.opacity = '0';
      setTimeout(() => modal.remove(), 200);
    }
  },

  // === 价格计算 ===
  getBasePrice() {
    return this.state.design?.printPrice || 20;
  },
  getMaterialExtra() {
    return this.materials.find(m => m.id === this.state.material)?.extra || 0;
  },
  getShippingExtra() {
    return this.shipping.find(s => s.id === this.state.shippingType)?.extra || 0;
  },
  getTotal() {
    return this.getBasePrice() + this.getMaterialExtra() + this.getShippingExtra();
  },

  // === 渲染弹窗 ===
  render() {
    // 移除已有弹窗
    const existing = document.getElementById('payModal');
    if (existing) existing.remove();

    const s = this.state;
    const d = s.design || {};

    const modal = document.createElement('div');
    modal.id = 'payModal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.5);opacity:0;transition:opacity 0.2s;';
    modal.innerHTML = this.renderContent();

    modal.addEventListener('click', (e) => {
      if (e.target === modal) this.close();
    });

    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.style.opacity = '1');
  },

  renderContent() {
    const s = this.state;
    const d = s.design || {};

    if (s.step === 'success') return this.renderSuccess();
    if (s.step === 'error') return this.renderError();
    if (s.step === 'paying') return this.renderPaying();

    // 选择步骤
    return `
      <div class="pay-card">
        <button class="pay-close" onclick="PaymentSystem.close()">&times;</button>
        <div class="pay-header">
          <h3>3D打印代打</h3>
          <p class="pay-item-name">${d.name || ''}</p>
          <p class="pay-item-desc">${d.desc || ''}</p>
        </div>

        <div class="pay-section">
          <h4>选择材料</h4>
          <div class="pay-options">
            ${this.materials.map(m => `
              <label class="pay-option ${s.material === m.id ? 'active' : ''}" onclick="PaymentSystem.selectMaterial('${m.id}')">
                <input type="radio" name="material" value="${m.id}" ${s.material === m.id ? 'checked' : ''}>
                <span class="pay-option-name">${m.name}</span>
                <span class="pay-option-desc">${m.desc}</span>
                ${m.extra > 0 ? `<span class="pay-option-price">+¥${m.extra}</span>` : '<span class="pay-option-price">基础</span>'}
              </label>
            `).join('')}
          </div>
        </div>

        <div class="pay-section">
          <h4>配送方式</h4>
          <div class="pay-options">
            ${this.shipping.map(sh => `
              <label class="pay-option ${s.shippingType === sh.id ? 'active' : ''}" onclick="PaymentSystem.selectShipping('${sh.id}')">
                <input type="radio" name="shipping" value="${sh.id}" ${s.shippingType === sh.id ? 'checked' : ''}>
                <span class="pay-option-name">${sh.name}</span>
                <span class="pay-option-desc">${sh.desc}</span>
                ${sh.extra > 0 ? `<span class="pay-option-price">+¥${sh.extra}</span>` : '<span class="pay-option-price">免费</span>'}
              </label>
            `).join('')}
          </div>
        </div>

        <div class="pay-summary">
          <div class="pay-summary-row">
            <span>打印费</span><span>¥${this.getBasePrice()}</span>
          </div>
          ${this.getMaterialExtra() > 0 ? `<div class="pay-summary-row"><span>${this.materials.find(m=>m.id===s.material).name} 加价</span><span>+¥${this.getMaterialExtra()}</span></div>` : ''}
          ${this.getShippingExtra() > 0 ? `<div class="pay-summary-row"><span>${this.shipping.find(sh=>sh.id===s.shippingType).name}</span><span>+¥${this.getShippingExtra()}</span></div>` : ''}
          <div class="pay-summary-total">
            <span>合计</span><span>¥${this.getTotal()}</span>
          </div>
        </div>

        <div class="pay-buttons">
          <button class="pay-btn wechat" onclick="PaymentSystem.pay('wechat')">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm3.845 4.016c-3.693 0-6.689 2.462-6.689 5.496 0 3.034 2.996 5.496 6.689 5.496a8.9 8.9 0 0 0 2.27-.3.69.69 0 0 1 .573.078l1.52.89a.262.262 0 0 0 .133.043.234.234 0 0 0 .232-.236c0-.058-.023-.114-.038-.17l-.312-1.183a.47.47 0 0 1 .17-.531C21.827 18.58 23 16.842 23 15.503c0-3.034-2.996-5.496-6.557-5.496zm-2.893 3.37c.513 0 .93.424.93.944a.937.937 0 0 1-.93.943.937.937 0 0 1-.93-.943c0-.52.417-.944.93-.944zm5.254 0c.513 0 .93.424.93.944a.937.937 0 0 1-.93.943.937.937 0 0 1-.93-.943c0-.52.417-.944.93-.944z"/></svg>
            微信支付
          </button>
          <button class="pay-btn alipay" onclick="PaymentSystem.pay('alipay')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M21.422 13.477C21.422 13.477 17.286 11.397 14.89 10.274C15.464 9.09 15.927 7.76 16.147 6.373L18.293 6.373L18.293 5.142L12.721 5.142L12.721 3.746L10.735 3.746L10.735 5.142L5.142 5.142L5.142 6.373L13.624 6.373C13.453 7.449 13.099 8.459 12.562 9.368C11.139 8.789 9.734 8.4 8.813 8.4C5.709 8.4 3.578 10.191 3.578 12.371C3.578 14.551 5.709 16.342 8.813 16.342C11.396 16.342 13.395 14.927 14.383 12.799C16.709 13.881 21.422 16.066 21.422 16.066L21.422 13.477ZM8.813 14.927C6.874 14.927 5.564 13.815 5.564 12.371C5.564 10.927 6.874 9.815 8.813 9.815C9.775 9.815 11.017 10.153 12.28 10.702C11.449 12.348 10.28 13.542 8.813 14.927Z"/></svg>
            支付宝
          </button>
        </div>

        <p class="pay-footer">支付即表示同意《代打服务协议》· 下单后3天内发货</p>
      </div>
    `;
  },

  renderPaying() {
    const s = this.state;
    const qrImg = s.qrUrl
      ? `<img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(s.payUrl)}" alt="扫码支付" style="border-radius:8px;">`
      : '<div class="pay-spinner"></div>';

    return `
      <div class="pay-card">
        <button class="pay-close" onclick="PaymentSystem.close()">&times;</button>
        <div class="pay-header">
          <h3>正在支付</h3>
          <p class="pay-item-name">${s.design?.name || ''}</p>
          <p class="pay-amount">¥${this.getTotal()}</p>
        </div>
        ${this.isMobile ? `
          <div class="pay-mobile-redirect">
            <div class="pay-spinner"></div>
            <p>正在跳转到${s.paymentType === 'wechat' ? '微信' : '支付宝'}支付...</p>
            <a href="${s.payUrl}" target="_blank" class="btn btn-primary" style="margin-top:12px;font-size:14px;">手动打开支付页面</a>
          </div>
        ` : `
          <div class="pay-qr-area">
            <p>${s.paymentType === 'wechat' ? '请使用微信扫码支付' : '请使用支付宝扫码支付'}</p>
            ${qrImg}
          </div>
        `}
        <div class="pay-poll-status" id="payPollStatus">
          <div class="pay-spinner-sm"></div>
          <span>等待支付结果...</span>
        </div>
      </div>
    `;
  },

  renderSuccess() {
    return `
      <div class="pay-card pay-card-success">
        <button class="pay-close" onclick="PaymentSystem.close()">&times;</button>
        <div class="pay-header" style="text-align:center;">
          <div class="pay-success-icon">&#10003;</div>
          <h3>支付成功</h3>
          <p class="pay-item-name">${this.state.design?.name || ''}</p>
          <p style="color:var(--gray-500);font-size:13px;margin-top:8px;">订单号: ${this.state.orderId}</p>
        </div>
        <div class="pay-success-info">
          <div class="pay-summary-row"><span>材料</span><span>${this.materials.find(m=>m.id===this.state.material)?.name || 'PLA'}</span></div>
          <div class="pay-summary-row"><span>配送</span><span>${this.shipping.find(s=>s.id===this.state.shippingType)?.name || '标准快递'}</span></div>
          <div class="pay-summary-row"><span>金额</span><span>¥${this.getTotal()}</span></div>
        </div>
        <div style="padding:16px;">
          <button class="btn btn-primary" style="width:100%;" onclick="PaymentSystem.close(); showToast('订单已提交，我们会尽快安排打印发货')">完成</button>
        </div>
      </div>
    `;
  },

  renderError() {
    return `
      <div class="pay-card">
        <button class="pay-close" onclick="PaymentSystem.close()">&times;</button>
        <div class="pay-header" style="text-align:center;">
          <h3>${this.state.errorTitle || '支付遇到问题'}</h3>
          <p style="color:var(--gray-500);font-size:13px;margin-top:8px;">${this.state.errorMsg || '请稍后重试'}</p>
        </div>
        <div style="padding:16px;display:flex;gap:12px;">
          <button class="btn btn-outline" style="flex:1;" onclick="PaymentSystem.close()">取消</button>
          <button class="btn btn-primary" style="flex:1;" onclick="PaymentSystem.open(PaymentSystem.state.design)">重试</button>
        </div>
      </div>
    `;
  },

  // === 交互方法 ===
  selectMaterial(id) {
    this.state.material = id;
    this.render();
  },

  selectShipping(id) {
    this.state.shippingType = id;
    this.render();
  },

  // === 发起支付 ===
  async pay(paymentType) {
    this.state.paymentType = paymentType;
    this.state.step = 'paying';
    this.render();

    try {
      const payload = {
        stl_id: this.state.design.id,
        stl_name: this.state.design.name,
        amount: this.getTotal(),
        payment_type: paymentType,
        material: this.state.material,
        shipping: this.state.shippingType,
      };

      // 获取用户ID
      if (typeof RoboLinkAuth !== 'undefined' && RoboLinkAuth.getUser()) {
        payload.user_id = RoboLinkAuth.getUser().id;
      }

      const res = await fetch('/api/create-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (data.errcode !== 0 || !data.url) {
        throw new Error(data.error || '创建支付订单失败');
      }

      this.state.orderId = data.order_id;
      this.state.payUrl = data.url;
      this.state.qrUrl = data.url_qrcode;
      this.state.step = 'paying';
      this.render();

      // 移动端自动跳转
      if (this.isMobile && data.url) {
        setTimeout(() => {
          window.location.href = data.url;
        }, 500);
      }

      // 开始轮询支付状态
      this.startPolling(data.order_id);

    } catch (err) {
      console.error('Payment error:', err);
      this.state.step = 'error';
      this.state.errorTitle = '支付创建失败';
      this.state.errorMsg = err.message;
      this.render();
    }
  },

  // === 轮询订单状态 ===
  startPolling(orderId) {
    if (this.state.pollTimer) clearInterval(this.state.pollTimer);

    let attempts = 0;
    const maxAttempts = 100; // 5分钟 (3秒*100)

    this.state.pollTimer = setInterval(async () => {
      attempts++;

      if (attempts > maxAttempts) {
        clearInterval(this.state.pollTimer);
        this.state.pollTimer = null;
        const statusEl = document.getElementById('payPollStatus');
        if (statusEl) {
          statusEl.innerHTML = '<span style="color:var(--coral-400);">支付超时，请重新下单</span>';
        }
        return;
      }

      try {
        const sbUrl = (typeof SITE_CONFIG !== 'undefined') ? SITE_CONFIG.supabaseUrl : 'https://pendpzoycfngylrrbwon.supabase.co';
        const sbKey = (typeof SUPABASE_CONFIG !== 'undefined') ? SUPABASE_CONFIG.anonKey : 'sb_publishable_Cm0je2pGSzSctnoNJh7wig_qsw-YxDo';

        const res = await fetch(
          `${sbUrl}/rest/v1/payment_orders?trade_order_id=eq.${orderId}&select=status`,
          { headers: { 'apikey': sbKey } }
        );
        const data = await res.json();

        if (data.length > 0 && data[0].status === 'paid') {
          clearInterval(this.state.pollTimer);
          this.state.pollTimer = null;
          this.state.step = 'success';
          this.render();
          showToast('支付成功！我们会尽快安排打印发货');
        }
      } catch (e) {
        // 轮询失败静默忽略
      }
    }, 3000);
  },

  // === 从URL参数恢复订单状态（用户支付后回跳） ===
  checkReturnOrder() {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('order');
    const status = params.get('status');

    if (orderId && status === 'success') {
      // 清理URL
      window.history.replaceState({}, '', window.location.pathname);

      // 查询订单状态
      setTimeout(() => {
        const sbUrl = (typeof SITE_CONFIG !== 'undefined') ? SITE_CONFIG.supabaseUrl : 'https://pendpzoycfngylrrbwon.supabase.co';
        const sbKey = (typeof SUPABASE_CONFIG !== 'undefined') ? SUPABASE_CONFIG.anonKey : 'sb_publishable_Cm0je2pGSzSctnoNJh7wig_qsw-YxDo';

        fetch(`${sbUrl}/rest/v1/payment_orders?trade_order_id=eq.${orderId}&select=status,stl_name,amount,material,shipping`,
          { headers: { 'apikey': sbKey } }
        )
        .then(res => res.json())
        .then(data => {
          if (data.length > 0 && data[0].status === 'paid') {
            this.state.orderId = orderId;
            this.state.design = { name: data[0].stl_name };
            this.state.material = data[0].material || 'PLA';
            this.state.shippingType = data[0].shipping || 'standard';
            this.state.step = 'success';
            this.render();
            showToast('支付成功！我们会尽快安排打印发货');
          } else if (data.length > 0 && data[0].status === 'pending') {
            // 还在支付中，开始轮询
            this.state.orderId = orderId;
            this.state.design = { name: data[0].stl_name, id: data[0].stl_id };
            this.state.material = data[0].material || 'PLA';
            this.state.shippingType = data[0].shipping || 'standard';
            this.state.step = 'paying';
            this.state.paymentType = 'wechat';
            this.render();
            this.startPolling(orderId);
          }
        })
        .catch(() => {});
      }, 500);
    }
  },
};

// 页面加载后检查URL回跳参数
document.addEventListener('DOMContentLoaded', () => {
  PaymentSystem.checkReturnOrder();
});
