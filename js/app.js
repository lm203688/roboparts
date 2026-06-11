// ==========================================
// RoboLink - 机器人零件对接平台
// 应用逻辑 v2: 后端集成 + 佣金追踪
// ==========================================

document.addEventListener('DOMContentLoaded', async () => {
  initNavbar();
  await RoboLinkAuth.init();  // 先初始化认证
  initPartsGrid();
  initCompatChecker();
  initCommunity();
  initStlGrid();
  initMonitor();
  animateStats();
});

// ========== 导航栏 ==========
function initNavbar() {
  const navbar = document.getElementById('navbar');
  const toggle = document.getElementById('navToggle');
  const links = document.querySelector('.nav-links');

  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 10);
  });

  if (toggle) {
    toggle.addEventListener('click', () => {
      links.style.display = links.style.display === 'flex' ? 'none' : 'flex';
    });
  }

  // 点击外部关闭用户下拉
  document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('userDropdown');
    const userMenu = document.getElementById('navUserMenu');
    if (dropdown && userMenu && !userMenu.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });
}

// ========== 数字动画 ==========
function animateStats() {
  document.querySelectorAll('.stat-num').forEach(el => {
    const target = parseInt(el.textContent);
    let current = 0;
    const step = Math.ceil(target / 30);
    const interval = setInterval(() => {
      current += step;
      if (current >= target) { current = target; clearInterval(interval); }
      el.textContent = current;
    }, 40);
  });
}

// ========== 零件选型引擎 ==========
let currentCategory = 'all';
let currentBrand = 'all';
let partsPage = 0;

function initPartsGrid() {
  document.getElementById('categoryFilter').addEventListener('click', (e) => {
    if (!e.target.classList.contains('tag')) return;
    e.currentTarget.querySelectorAll('.tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    currentCategory = e.target.dataset.value;
    partsPage = 0;
    renderParts();
  });

  document.getElementById('brandFilter').addEventListener('click', (e) => {
    if (!e.target.classList.contains('tag')) return;
    e.currentTarget.querySelectorAll('.tag').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    currentBrand = e.target.dataset.value;
    partsPage = 0;
    renderParts();
  });

  document.getElementById('partSearch').addEventListener('input', debounce(() => {
    partsPage = 0;
    renderParts();
  }, 200));

  document.getElementById('loadMoreParts').addEventListener('click', () => {
    partsPage++;
    renderParts(true);
  });

  renderParts();
}

function renderParts(append = false) {
  const grid = document.getElementById('partsGrid');
  const search = document.getElementById('partSearch').value.toLowerCase();
  const pageSize = 8;

  let filtered = END_EFFECTORS.filter(p => {
    if (currentCategory !== 'all' && p.category !== currentCategory) return false;
    if (currentBrand !== 'all') {
      const brandKey = p.brand.toLowerCase().replace(/\s+/g, '');
      const filterKey = currentBrand.toLowerCase();
      if (!brandKey.includes(filterKey) && !p.brand.includes(currentBrand)) return false;
    }
    if (search) {
      const searchStr = `${p.brand} ${p.model} ${p.type} ${p.category}`.toLowerCase();
      if (!searchStr.includes(search)) return false;
    }
    return true;
  });

  const paginated = filtered.slice(0, (partsPage + 1) * pageSize);

  if (!append) grid.innerHTML = '';

  const start = partsPage * pageSize;
  const items = paginated.slice(start);

  items.forEach(p => {
    const card = document.createElement('div');
    card.className = 'part-card';

    // 导购按钮（如果有配置品牌链接）
    const buyLink = getProductLink(p);
    const buyBtn = buyLink ? `<a href="${buyLink}" target="_blank" rel="noopener" class="btn btn-secondary" style="font-size:12px;padding:6px 14px;" onclick="trackProductClick('${p.id}','${p.brand}','${p.model}')">去购买</a>` : '';

    card.innerHTML = `
      <div class="part-card-header">
        <span class="part-brand">${p.brand}</span>
        <span class="part-type">${p.type}</span>
      </div>
      <h3>${p.model}</h3>
      <div class="part-params">
        <div class="part-param"><strong>夹持力</strong> ${p.force}</div>
        <div class="part-param"><strong>行程</strong> ${p.stroke}</div>
        <div class="part-param"><strong>协议</strong> ${p.protocol}</div>
        <div class="part-param"><strong>重量</strong> ${p.weight}</div>
        <div class="part-param"><strong>法兰</strong> ${p.flange}</div>
        <div class="part-param"><strong>价格</strong> ${p.price >= 1000 ? '¥' + p.price.toLocaleString() : '¥' + p.price}</div>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;">
        <a href="#compat" class="btn btn-primary" style="font-size:12px;padding:6px 14px;flex:1;" onclick="prefillCompat('${p.id}')">检查兼容</a>
        ${buyBtn}
      </div>
    `;
    grid.appendChild(card);
  });

  const btn = document.getElementById('loadMoreParts');
  btn.style.display = paginated.length < filtered.length ? 'inline-flex' : 'none';
}

// 预填充兼容性检查
function prefillCompat(gripperId) {
  const select = document.getElementById('endEffector');
  if (select) {
    select.value = gripperId;
    document.getElementById('compat').scrollIntoView({ behavior: 'smooth' });
  }
}

// 获取零件导购链接
function getProductLink(product) {
  if (typeof AFFILIATE_CONFIG === 'undefined' || !AFFILIATE_CONFIG.enabled) return null;
  const brandNames = Object.keys(AFFILIATE_CONFIG.brandLinks);
  for (const bn of brandNames) {
    if (product.brand.includes(bn)) {
      const baseUrl = AFFILIATE_CONFIG.brandLinks[bn];
      // 搜索 "品牌 + 型号" 更精准
      const keyword = encodeURIComponent(`${product.brand} ${product.model}`);
      return `${baseUrl}${encodeURIComponent(product.model)}`;
    }
  }
  return null;
}

// 追踪零件点击
async function trackProductClick(productId, brand, model) {
  const client = RoboLinkAuth.getClient();
  if (client) {
    await client.from('product_clicks').insert({
      user_id: RoboLinkAuth.getUser()?.id || null,
      product_id: productId,
      product_name: model,
      brand: brand,
      ref_code: generateRefCode(),
    });
  }
}

// ========== 兼容性检查 ==========
function initCompatChecker() {
  const armSelect = document.getElementById('robotArm');
  const gripperSelect = document.getElementById('endEffector');

  const armGroups = {};
  ROBOT_ARMS.forEach(a => {
    if (!armGroups[a.brand]) armGroups[a.brand] = [];
    armGroups[a.brand].push(a);
  });
  Object.entries(armGroups).forEach(([brand, arms]) => {
    const optgroup = document.createElement('optgroup');
    optgroup.label = brand;
    arms.forEach(a => {
      const opt = document.createElement('option');
      opt.value = a.id;
      opt.textContent = `${a.model} (${a.flange})`;
      optgroup.appendChild(opt);
    });
    armSelect.appendChild(optgroup);
  });

  const gripperGroups = {};
  END_EFFECTORS.forEach(g => {
    if (!gripperGroups[g.brand]) gripperGroups[g.brand] = [];
    gripperGroups[g.brand].push(g);
  });
  Object.entries(gripperGroups).forEach(([brand, grippers]) => {
    const optgroup = document.createElement('optgroup');
    optgroup.label = brand;
    grippers.forEach(g => {
      const opt = document.createElement('option');
      opt.value = g.id;
      opt.textContent = `${g.model} - ${g.type} (${g.flange})`;
      optgroup.appendChild(opt);
    });
    gripperSelect.appendChild(optgroup);
  });

  document.getElementById('checkCompat').addEventListener('click', checkCompatibility);
}

function checkCompatibility() {
  const armId = document.getElementById('robotArm').value;
  const gripperId = document.getElementById('endEffector').value;
  const resultDiv = document.getElementById('compatResult');

  if (!armId || !gripperId) {
    showToast('请先选择机械臂和夹爪');
    return;
  }

  const arm = ROBOT_ARMS.find(a => a.id === armId);
  const gripper = END_EFFECTORS.find(g => g.id === gripperId);

  let armFlangeGroup = null;
  let gripperFlangeGroup = null;

  Object.entries(FLANGE_GROUPS).forEach(([key, group]) => {
    if (group.arms.includes(armId)) armFlangeGroup = key;
    if (group.grippers.includes(gripperId)) gripperFlangeGroup = key;
  });

  const armProtocols = arm.protocol.split('/');
  const gripperProtocols = gripper.protocol.split('/');
  const protocolMatch = armProtocols.some(ap =>
    gripperProtocols.some(gp => ap.toLowerCase().includes(gp.toLowerCase()) || gp.toLowerCase().includes(ap.toLowerCase()))
  );

  let status, statusText, statusDesc, statusClass, adapterNeeded = false, adapterInfo = '';

  if (armFlangeGroup === gripperFlangeGroup) {
    status = '&#10003;';
    statusText = '直接兼容';
    statusDesc = `${arm.brand} ${arm.model} 与 ${gripper.brand} ${gripper.model} 法兰直接匹配`;
    statusClass = 'success';
  } else {
    const adapterKey = `${armFlangeGroup}_to_${gripperFlangeGroup}`;
    const reverseKey = `${gripperFlangeGroup}_to_${armFlangeGroup}`;
    const adapter = ADAPTER_PAIRS[adapterKey] || ADAPTER_PAIRS[reverseKey];

    if (adapter) {
      status = '&#9888;';
      statusText = '需要转接件';
      statusDesc = `${arm.brand} ${arm.model} 与 ${gripper.brand} ${gripper.model} 法兰不直接匹配，需要转接件`;
      statusClass = 'warning';
      adapterNeeded = true;
      adapterInfo = adapter.name;
    } else {
      status = '&#10007;';
      statusText = '暂不兼容';
      statusDesc = `${arm.brand} ${arm.model} 与 ${gripper.brand} ${gripper.model} 目前没有已知转接方案`;
      statusClass = 'error';
    }
  }

  const protocolStatus = protocolMatch ? '兼容' : '需要适配';
  const protocolColor = protocolMatch ? 'var(--green-400)' : 'var(--amber-400)';

  resultDiv.style.display = 'block';
  resultDiv.className = `compat-result ${statusClass}`;
  resultDiv.innerHTML = `
    <div class="compat-status">
      <div class="compat-status-icon" style="background:${statusClass === 'success' ? 'var(--green-50)' : statusClass === 'warning' ? 'var(--amber-50)' : 'var(--coral-50)'}; color:${statusClass === 'success' ? 'var(--green-400)' : statusClass === 'warning' ? 'var(--amber-400)' : 'var(--coral-400)'}">${status}</div>
      <div class="compat-status-text">
        <h4>${statusText}</h4>
        <p>${statusDesc}</p>
      </div>
    </div>
    <div class="compat-details">
      <div class="compat-detail">
        <div class="compat-detail-label">机械臂法兰</div>
        <div class="compat-detail-value">${arm.flange}</div>
      </div>
      <div class="compat-detail">
        <div class="compat-detail-label">夹爪法兰</div>
        <div class="compat-detail-value">${gripper.flange}</div>
      </div>
      <div class="compat-detail">
        <div class="compat-detail-label">通讯协议</div>
        <div class="compat-detail-value" style="color:${protocolColor}">${protocolStatus}${!protocolMatch ? ' (' + arm.protocol + ' / ' + gripper.protocol + ')' : ''}</div>
      </div>
      <div class="compat-detail">
        <div class="compat-detail-label">机械臂电压</div>
        <div class="compat-detail-value">${arm.voltage}</div>
      </div>
      <div class="compat-detail">
        <div class="compat-detail-label">夹爪电压</div>
        <div class="compat-detail-value">${gripper.voltage}</div>
      </div>
      <div class="compat-detail">
        <div class="compat-detail-label">夹持力</div>
        <div class="compat-detail-value">${gripper.force}</div>
      </div>
    </div>
    ${adapterNeeded ? `
      <div class="compat-action">
        <p style="font-size:13px;color:var(--gray-600);margin-bottom:12px;">推荐转接件: <strong>${adapterInfo}</strong></p>
        <a href="#stl" class="btn btn-primary">查看转接件设计</a>
      </div>
    ` : ''}
  `;

  resultDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ========== 社区（支持 Supabase 持久化）==========
let allPostsCache = null;

function initCommunity() {
  document.querySelectorAll('.community-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.community-tabs .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderCommunity(tab.dataset.tab);
    });
  });

  loadCommunityPosts();
  renderCommunity('latest');
}

// 加载帖子（优先 Supabase，降级 localStorage）
async function loadCommunityPosts() {
  const client = RoboLinkAuth.getClient();

  if (client) {
    try {
      // 从 Supabase 加载帖子 + 关联的用户信息
      const { data: posts, error } = await client
        .from('posts')
        .select('*, profiles(username, display_name, avatar_initial)')
        .order('likes_count', { ascending: false });

      if (!error && posts) {
        allPostsCache = posts.map(p => ({
          id: p.id,
          author: p.profiles?.display_name || p.profiles?.username || '未知用户',
          avatar: p.profiles?.avatar_initial || 'U',
          time: formatRelativeTime(p.created_at),
          tab: p.tab,
          tag: p.tag,
          tagText: p.tag_text,
          title: p.title,
          content: p.content,
          likes: p.likes_count,
          comments: p.comments_count,
          _fromDb: true,
          _user_id: p.user_id,
        }));

        // 加载当前用户是否已点赞
        const user = RoboLinkAuth.getUser();
        if (user) {
          const { data: myLikes } = await client
            .from('likes')
            .select('post_id')
            .eq('user_id', user.id);
          if (myLikes) {
            const likedIds = new Set(myLikes.map(l => l.post_id));
            allPostsCache.forEach(p => { p._likedByMe = likedIds.has(p.id); });
          }
        }
        return;
      }
    } catch (e) {
      console.warn('Supabase posts load failed:', e);
    }
  }

  // 降级到 localStorage
  const saved = getSavedPosts();
  if (saved.length > 0) {
    COMMUNITY_POSTS = saved;
  }
  allPostsCache = null;
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return '未知';
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}天前`;
  return date.toLocaleDateString('zh-CN');
}

function getAllPosts() {
  if (allPostsCache) return allPostsCache;
  return [...COMMUNITY_POSTS];
}

function renderCommunity(tab) {
  const feed = document.getElementById('communityFeed');
  let posts = getAllPosts();

  if (tab === 'popular') posts = [...posts].sort((a, b) => b.likes - a.likes);
  else if (tab === 'combo') posts = posts.filter(p => p.tab === 'combo');
  else if (tab === 'tutorial') posts = posts.filter(p => p.tab === 'tutorial');
  else if (tab === 'qa') posts = posts.filter(p => p.tab === 'qa');
  else if (tab === 'review') posts = posts.filter(p => p.tab === 'review');
  else posts = [...posts].sort((a, b) => (b.likes * 3 + b.comments) - (a.likes * 3 + a.comments));

  feed.innerHTML = posts.map(p => `
    <div class="post-card">
      <div class="post-meta">
        <div class="post-avatar">${p.avatar}</div>
        <span class="post-author">${p.author}</span>
        <span class="post-time">${p.time}</span>
      </div>
      <span class="post-tag ${p.tag}">${p.tagText}</span>
      <h3>${p.title}</h3>
      <p class="post-content-text">${p.content}</p>
      <div class="post-footer">
        <span class="post-action${p._likedByMe ? ' liked' : ''}" onclick="likePost('${p.id}')" style="cursor:pointer">&#9650; ${p.likes}</span>
        <span class="post-action" onclick="toggleComments('${p.id}')" style="cursor:pointer">&#9993; ${p.comments}</span>
        <span class="post-action" onclick="bookmarkPost('${p.id}')" style="cursor:pointer">收藏</span>
        <span class="post-action" onclick="sharePost('${p.id}')" style="cursor:pointer">分享</span>
      </div>
      <div class="post-comments" id="comments-${p.id}" style="display:none;">
        <div id="comment-list-${p.id}"></div>
        <div class="comment-input">
          <input type="text" id="comment-input-${p.id}" placeholder="写下你的评论..." ${!RoboLinkAuth.isLoggedIn() ? 'disabled' : ''}>
          <button class="btn btn-primary btn-sm" onclick="addComment('${p.id}')" ${!RoboLinkAuth.isLoggedIn() ? 'disabled' : ''}>发送</button>
        </div>
      </div>
    </div>
  `).join('');
}

async function likePost(id) {
  const client = RoboLinkAuth.getClient();
  const user = RoboLinkAuth.getUser();

  if (client && user && !user.isGuest) {
    try {
      // 检查是否已点赞
      const { data: existing } = await client
        .from('likes')
        .select('id')
        .eq('post_id', id)
        .eq('user_id', user.id)
        .maybeSingle();

      if (existing) {
        // 取消点赞
        await client.from('likes').delete().eq('id', existing.id);
      } else {
        // 点赞
        await client.from('likes').insert({ post_id: id, user_id: user.id });
      }
      await loadCommunityPosts(); // 重新加载（自动更新计数）
      renderCommunity(document.querySelector('.community-tabs .tab.active')?.dataset?.tab || 'latest');
      return;
    } catch (e) {
      console.warn('Supabase like failed:', e);
    }
  }

  // 降级 localStorage
  const posts = getAllPosts();
  const post = posts.find(p => p.id === id);
  if (post) {
    if (!post._likedByMe) {
      post.likes++;
      post._likedByMe = true;
    } else {
      post.likes--;
      post._likedByMe = false;
    }
    if (!allPostsCache) savePosts(posts);
    renderCommunity(document.querySelector('.community-tabs .tab.active')?.dataset?.tab || 'latest');
  }
}

function toggleComments(id) {
  const el = document.getElementById(`comments-${id}`);
  if (el) {
    const isOpen = el.style.display !== 'none';
    el.style.display = isOpen ? 'none' : 'block';
    if (!isOpen) loadComments(id);
  }
}

async function loadComments(postId) {
  const client = RoboLinkAuth.getClient();
  const listEl = document.getElementById(`comment-list-${postId}`);

  if (client && listEl) {
    try {
      const { data: comments } = await client
        .from('comments')
        .select('*, profiles(username, display_name, avatar_initial)')
        .eq('post_id', postId)
        .order('created_at', { ascending: true });

      if (comments) {
        listEl.innerHTML = comments.map(c => `
          <div style="padding:8px 0;border-bottom:1px solid var(--gray-100);display:flex;gap:8px;align-items:flex-start;">
            <div class="post-avatar" style="width:24px;height:24px;font-size:11px;">${c.profiles?.avatar_initial || 'U'}</div>
            <div>
              <span style="font-size:12px;font-weight:500;">${c.profiles?.display_name || c.profiles?.username}</span>
              <span style="font-size:11px;color:var(--gray-400);margin-left:8px;">${formatRelativeTime(c.created_at)}</span>
              <p style="font-size:13px;color:var(--gray-600);margin-top:2px;">${c.content}</p>
            </div>
          </div>
        `).join('');
        return;
      }
    } catch (e) {
      console.warn('Load comments failed:', e);
    }
  }

  // 降级：从 localStorage 帖子的 userComments 加载
  const posts = getAllPosts();
  const post = posts.find(p => p.id === postId);
  if (post?.userComments?.length && listEl) {
    listEl.innerHTML = post.userComments.map(c => `
      <div style="padding:8px 0;border-bottom:1px solid var(--gray-100);">
        <span style="font-size:12px;font-weight:500;">${c.author}</span>
        <span style="font-size:11px;color:var(--gray-400);margin-left:8px;">${c.time}</span>
        <p style="font-size:13px;color:var(--gray-600);margin-top:2px;">${c.text}</p>
      </div>
    `).join('');
  }
}

async function addComment(postId) {
  const input = document.getElementById(`comment-input-${postId}`);
  if (!input || !input.value.trim()) return;

  if (!RoboLinkAuth.isLoggedIn()) {
    showAuthModal('register');
    return;
  }

  const text = input.value.trim();
  input.value = '';

  const user = RoboLinkAuth.getUser();
  const client = RoboLinkAuth.getClient();

  if (client && !user.isGuest) {
    try {
      await client.from('comments').insert({
        post_id: postId,
        user_id: user.id,
        content: text,
      });
      await loadCommunityPosts();
      renderCommunity(document.querySelector('.community-tabs .tab.active')?.dataset?.tab || 'latest');
      setTimeout(() => {
        const el = document.getElementById(`comments-${postId}`);
        if (el) el.style.display = 'block';
        loadComments(postId);
      }, 50);
      return;
    } catch (e) {
      console.warn('Supabase comment failed:', e);
    }
  }

  // 降级 localStorage
  const posts = getAllPosts();
  const post = posts.find(p => p.id === postId);
  if (post) {
    if (!post.userComments) post.userComments = [];
    post.userComments.push({ author: user.displayName || '我', text, time: '刚刚' });
    post.comments++;
    if (!allPostsCache) savePosts(posts);
    renderCommunity(document.querySelector('.community-tabs .tab.active')?.dataset?.tab || 'latest');
    setTimeout(() => {
      const el = document.getElementById(`comments-${postId}`);
      if (el) el.style.display = 'block';
    }, 50);
  }
}

async function bookmarkPost(id) {
  const user = RoboLinkAuth.getUser();
  const client = RoboLinkAuth.getClient();

  if (client && user && !user.isGuest) {
    try {
      const { data: existing } = await client
        .from('bookmarks')
        .select('id')
        .eq('post_id', id)
        .eq('user_id', user.id)
        .maybeSingle();

      if (existing) {
        await client.from('bookmarks').delete().eq('id', existing.id);
        showToast('已取消收藏');
      } else {
        await client.from('bookmarks').insert({ post_id: id, user_id: user.id });
        showToast('已收藏到我的收藏');
      }
      return;
    } catch (e) {
      console.warn('Bookmark failed:', e);
    }
  }

  showToast('登录后可使用收藏功能');
  showAuthModal('login');
}

function sharePost(id) {
  const base = (typeof SITE_CONFIG !== 'undefined') ? SITE_CONFIG.siteUrl : window.location.origin;
  const url = base + '/#community';
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url);
    showToast('链接已复制，分享给朋友吧');
  }
}

async function submitPost() {
  if (!RoboLinkAuth.isLoggedIn()) {
    showAuthModal('register');
    showToast('请先登录或注册');
    return;
  }

  const user = RoboLinkAuth.getUser();
  if (user.isGuest) {
    showAuthModal('register');
    showToast('游客模式不能发帖，请注册账号');
    return;
  }

  const titleEl = document.getElementById('newPostTitle');
  const contentEl = document.getElementById('newPostContent');
  const tabEl = document.getElementById('newPostTab');
  if (!titleEl || !contentEl) return;

  const title = titleEl.value.trim();
  const content = contentEl.value.trim();
  const tab = tabEl?.value || 'combo';

  if (!title || !content) {
    showToast('标题和内容不能为空');
    return;
  }

  const tagMap = {
    combo: { tag: 'combo', tagText: '搭配方案' },
    review: { tag: 'review', tagText: '评测' },
    qa: { tag: 'question', tagText: '求助' },
    tutorial: { tag: 'tutorial', tagText: '教程' },
  };
  const tagInfo = tagMap[tab] || tagMap.combo;

  const client = RoboLinkAuth.getClient();

  if (client) {
    try {
      await client.from('posts').insert({
        user_id: user.id,
        title,
        content,
        tab,
        tag: tagInfo.tag,
        tag_text: tagInfo.tagText,
      });
      titleEl.value = '';
      contentEl.value = '';
      document.getElementById('newPostForm').style.display = 'none';
      await loadCommunityPosts();
      document.querySelectorAll('.community-tabs .tab').forEach(t => t.classList.remove('active'));
      document.querySelector('.community-tabs .tab[data-tab="latest"]')?.classList.add('active');
      renderCommunity('latest');
      showToast('发布成功！');
      return;
    } catch (e) {
      console.warn('Supabase post failed:', e);
      showToast('发布失败，请稍后重试');
      return;
    }
  }

  // 降级 localStorage
  const newPost = {
    id: 'p' + Date.now(),
    author: user.displayName || '我',
    avatar: user.avatarInitial || 'M',
    time: '刚刚',
    tab,
    ...tagInfo,
    title,
    content,
    likes: 0,
    comments: 0,
    userComments: []
  };
  const posts = getAllPosts();
  posts.unshift(newPost);
  savePosts(posts);
  COMMUNITY_POSTS = posts;
  titleEl.value = '';
  contentEl.value = '';
  document.querySelectorAll('.community-tabs .tab').forEach(t => t.classList.remove('active'));
  document.querySelector('.community-tabs .tab[data-tab="latest"]')?.classList.add('active');
  renderCommunity('latest');
  showToast('发布成功！');
}

function togglePostForm() {
  if (!RoboLinkAuth.isLoggedIn()) {
    showAuthModal('register');
    return;
  }
  const form = document.getElementById('newPostForm');
  if (form) {
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
  }
}

// localStorage 降级
function getSavedPosts() {
  try {
    return JSON.parse(localStorage.getItem('robolink_posts') || '[]');
  } catch { return []; }
}
function savePosts(posts) {
  localStorage.setItem('robolink_posts', JSON.stringify(posts));
}

// ========== STL下载（含追踪）==========
function initStlGrid() {
  const grid = document.getElementById('stlGrid');
  grid.innerHTML = STL_DESIGNS.map(s => `
    <div class="stl-card${s.isNew ? ' stl-new' : ''}">
      <div class="stl-preview">
        <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
          <rect x="15" y="30" width="50" height="30" rx="4" stroke="#B4B2A9" stroke-width="1.5"/>
          <circle cx="28" cy="45" r="4" stroke="#378ADD" stroke-width="1.5"/>
          <circle cx="40" cy="45" r="4" stroke="#378ADD" stroke-width="1.5"/>
          <circle cx="52" cy="45" r="4" stroke="#378ADD" stroke-width="1.5"/>
          <rect x="25" y="15" width="30" height="20" rx="3" stroke="#D85A30" stroke-width="1.5" stroke-dasharray="4,2"/>
        </svg>
        <span class="stl-badge free">免费下载</span>
        ${s.isNew ? '<span class="stl-badge new">NEW</span>' : ''}
      </div>
      <div class="stl-info">
        <h4>${s.name}</h4>
        <p>${s.desc}</p>
        <div class="stl-compat">适用: ${s.compat}</div>
        <div class="stl-meta"><span>${s.size}</span> · <span>${s.downloads} 次下载</span></div>
        <div class="stl-actions">
          <button class="btn btn-primary" onclick="downloadStl('${s.id}')">下载STL</button>
          <button class="btn btn-outline" onclick="loadSTLModel('${s.id}')">3D预览</button>
          <button class="btn btn-secondary" onclick="orderPrint('${s.id}')">委托代打</button>
        </div>
      </div>
    </div>
  `).join('');
}

async function downloadStl(id) {
  const url = `stl/${id}.stl`;
  const design = STL_DESIGNS.find(s => s.id === id);

  fetch(url, { method: 'HEAD' })
    .then(res => {
      if (res.ok) {
        const a = document.createElement('a');
        a.href = url;
        a.download = `${id}.stl`;
        a.click();
        showToast('STL文件下载中，可用Cura/PrusaSlicer切片后打印');

        // 追踪下载（Supabase）
        const client = RoboLinkAuth.getClient();
        if (client && design) {
          client.from('product_clicks').insert({
            user_id: RoboLinkAuth.getUser()?.id || null,
            product_id: id,
            product_name: design.name,
            brand: 'STL下载',
            source_page: 'stl',
            ref_code: generateRefCode(),
          }).then(() => {
            // 更新本地计数
            design.downloads++;
          }).catch(() => {});
        }
      } else {
        showToast('该转接件设计正在制作中，敬请期待！');
      }
    })
    .catch(() => showToast('下载出错，请稍后重试'));
}

// 3D打印下单（含追踪）
async function orderPrint(id) {
  const design = STL_DESIGNS.find(s => s.id === id);
  if (!design) return;

  const refCode = generateRefCode();

  const msg = `准备为「${design.name}」下单3D打印。\n\n推荐材料：PLA（创客级，便宜耐用）\n预计费用：15-35元\n\n即将跳转到嘉立创3D打印平台（jlc-3dp.cn），请先下载STL文件再上传。\n追踪码: ${refCode}`;
  const confirmed = confirm(msg);

  if (confirmed) {
    // 记录订单追踪
    const client = RoboLinkAuth.getClient();
    if (client) {
      try {
        await client.from('print_orders').insert({
          user_id: RoboLinkAuth.getUser()?.id || null,
          stl_id: id,
          stl_name: design.name,
          target_url: 'https://www.jlc-3dp.cn/',
          ref_code: refCode,
          status: 'created',
        });
      } catch (e) {
        console.warn('Order tracking save failed:', e);
      }
    }

    // 先下载STL，再跳转（带追踪参数）
    const a = document.createElement('a');
    a.href = `stl/${id}.stl`;
    a.download = `${id}.stl`;
    a.click();
    setTimeout(() => {
      window.open(`https://www.jlc-3dp.cn/?ref=${refCode}`, '_blank');
    }, 500);
  }
}

// ========== 行业监控 ==========
let currentMonitorTab = 'brand';
let liveMonitorData = null;

function initMonitor() {
  document.querySelectorAll('.monitor-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.monitor-tabs .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentMonitorTab = tab.dataset.mtab;
      renderMonitor();
    });
  });

  fetch('data/monitor-feeds.json')
    .then(res => {
      if (!res.ok) throw new Error('Not found');
      return res.json();
    })
    .then(data => {
      liveMonitorData = data;
      renderMonitor();
    })
    .catch(() => {
      liveMonitorData = null;
      renderMonitor();
    });
}

function renderMonitor() {
  const feed = document.getElementById('monitorFeed');
  const impactLabels = { high: '高影响', medium: '中影响', low: '低影响' };

  const source = liveMonitorData || MONITOR_DATA;
  const data = source[currentMonitorTab] || [];

  if (data.length === 0) {
    feed.innerHTML = '<div style="text-align:center;padding:40px;color:var(--gray-400);">暂无监控数据</div>';
    return;
  }

  feed.innerHTML = data.map(item => `
    <div class="monitor-item">
      <div class="monitor-dot ${currentMonitorTab}"></div>
      <div class="monitor-content">
        <h4>${item.title} <span class="monitor-impact ${item.impact}">${impactLabels[item.impact]}</span></h4>
        <p>${item.content}</p>
        <div class="monitor-source">来源: ${item.source}</div>
      </div>
      <div class="monitor-date">${item.date}</div>
    </div>
  `).join('');

  const updateTime = liveMonitorData
    ? liveMonitorData.updatedAt
    : `${new Date().toLocaleDateString('zh-CN')} ${new Date().toLocaleTimeString('zh-CN', {hour:'2-digit', minute:'2-digit'})} (默认数据)`;
  document.getElementById('monitorUpdateTime').textContent = `数据更新于 ${updateTime}`;
}

// ========== 工具函数 ==========
function generateRefCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let code = 'RL';
  for (let i = 0; i < 8; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

function showToast(message) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

function debounce(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
