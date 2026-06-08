// ==========================================
// RoboLink - 认证模块
// 支持 Supabase Auth + localStorage 降级
// ==========================================

const RoboLinkAuth = (() => {
  let supabase = null;
  let currentUser = null;
  let isSupabaseReady = false;

  // 初始化
  async function init() {
    // 检查是否配置了 Supabase
    if (typeof SUPABASE_CONFIG !== 'undefined' &&
        SUPABASE_CONFIG.url !== 'YOUR_SUPABASE_URL_HERE' &&
        SUPABASE_CONFIG.anonKey !== 'YOUR_SUPABASE_ANON_KEY_HERE') {
      try {
        // 动态加载 Supabase SDK
        if (typeof window.supabase === 'undefined' && typeof createClient === 'undefined') {
          await loadSupabaseSDK();
        }
        if (typeof createClient !== 'undefined') {
          supabase = createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey);
          isSupabaseReady = true;

          // 监听认证状态变化
          supabase.auth.onAuthStateChange((event, session) => {
            if (event === 'SIGNED_IN' && session) {
              handleSupabaseUser(session.user);
            } else if (event === 'SIGNED_OUT') {
              currentUser = null;
              updateUI();
            }
          });

          // 获取当前会话
          const { data: { session } } = await supabase.auth.getSession();
          if (session) {
            await handleSupabaseUser(session.user);
          }
        }
      } catch (e) {
        console.warn('Supabase init failed, using localStorage fallback:', e);
        isSupabaseReady = false;
      }
    }

    // localStorage 降级：检查是否有本地用户
    if (!currentUser) {
      const localUser = getLocalUser();
      if (localUser) {
        currentUser = localUser;
      }
    }

    updateUI();
    return currentUser;
  }

  async function loadSupabaseSDK() {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async function handleSupabaseUser(user) {
    if (!supabase) return;
    const { data: profile } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single();

    currentUser = {
      id: user.id,
      email: user.email,
      username: profile?.username || user.email?.split('@')[0] || '用户',
      displayName: profile?.display_name || profile?.username || user.email?.split('@')[0],
      avatarInitial: profile?.avatar_initial || user.email?.[0]?.toUpperCase() || 'U',
      isGuest: false,
    };
    updateUI();
  }

  // 注册
  async function signUp(email, password, username) {
    if (isSupabaseReady && supabase) {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { username, display_name: username }
        }
      });
      if (error) throw new Error(error.message);
      return data;
    } else {
      // localStorage 降级
      const localUser = {
        id: 'local_' + Date.now(),
        email: email,
        username: username || email.split('@')[0],
        displayName: username || email.split('@')[0],
        avatarInitial: (username || email)[0].toUpperCase(),
        isGuest: true,
      };
      setLocalUser(localUser);
      currentUser = localUser;
      updateUI();
      return { user: localUser };
    }
  }

  // 登录
  async function signIn(email, password) {
    if (isSupabaseReady && supabase) {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message);
      return data;
    } else {
      // localStorage 降级：简单验证
      const stored = getLocalUser();
      if (stored && stored.email === email) {
        currentUser = stored;
        updateUI();
        return { user: stored };
      }
      throw new Error('用户不存在，请先注册');
    }
  }

  // 退出
  async function signOut() {
    if (isSupabaseReady && supabase) {
      await supabase.auth.signOut();
    }
    currentUser = null;
    removeLocalUser();
    updateUI();
    showToast('已退出登录');
  }

  // 游客模式
  function guestLogin() {
    const guestName = '游客' + Math.floor(Math.random() * 9000 + 1000);
    currentUser = {
      id: 'guest_' + Date.now(),
      email: '',
      username: guestName,
      displayName: guestName,
      avatarInitial: 'G',
      isGuest: true,
    };
    setLocalUser(currentUser);
    updateUI();
    showToast('已进入游客模式，发帖和评论需注册账号');
  }

  // 获取 Supabase 客户端
  function getClient() {
    return isSupabaseReady ? supabase : null;
  }

  function isLoggedIn() {
    return currentUser !== null;
  }

  function getUser() {
    return currentUser;
  }

  function isBackendReady() {
    return isSupabaseReady;
  }

  // localStorage 工具
  function getLocalUser() {
    try {
      return JSON.parse(localStorage.getItem('robolink_user'));
    } catch { return null; }
  }

  function setLocalUser(user) {
    localStorage.setItem('robolink_user', JSON.stringify(user));
  }

  function removeLocalUser() {
    localStorage.removeItem('robolink_user');
  }

  // 更新 UI
  function updateUI() {
    const authBtn = document.getElementById('navAuthBtn');
    const userMenu = document.getElementById('navUserMenu');
    const postFormNotice = document.getElementById('postFormNotice');

    if (authBtn && userMenu) {
      if (currentUser) {
        authBtn.style.display = 'none';
        userMenu.style.display = 'flex';
        userMenu.querySelector('.user-avatar-initial').textContent = currentUser.avatarInitial;
        userMenu.querySelector('.user-display-name').textContent = currentUser.displayName;
      } else {
        authBtn.style.display = 'inline-flex';
        userMenu.style.display = 'none';
      }
    }

    // 发帖表单提示
    if (postFormNotice) {
      if (!currentUser) {
        postFormNotice.style.display = 'block';
        postFormNotice.querySelector('a').onclick = (e) => {
          e.preventDefault();
          showAuthModal('register');
        };
      } else if (currentUser.isGuest) {
        postFormNotice.style.display = 'block';
        postFormNotice.querySelector('span').textContent = '游客模式，注册后可发帖';
      } else {
        postFormNotice.style.display = 'none';
      }
    }
  }

  return {
    init,
    signUp,
    signIn,
    signOut,
    guestLogin,
    getClient,
    isLoggedIn,
    getUser,
    isBackendReady,
  };
})();

// Auth Modal 操作
function showAuthModal(mode = 'login') {
  const modal = document.getElementById('authModal');
  if (!modal) return;
  modal.style.display = 'flex';

  const loginTab = modal.querySelector('[data-auth-tab="login"]');
  const registerTab = modal.querySelector('[data-auth-tab="register"]');
  const loginForm = document.getElementById('authLoginForm');
  const registerForm = document.getElementById('authRegisterForm');

  if (mode === 'register') {
    loginTab?.classList.remove('active');
    registerTab?.classList.add('active');
    if (loginForm) loginForm.style.display = 'none';
    if (registerForm) registerForm.style.display = 'block';
  } else {
    loginTab?.classList.add('active');
    registerTab?.classList.remove('active');
    if (loginForm) loginForm.style.display = 'block';
    if (registerForm) registerForm.style.display = 'none';
  }
}

function closeAuthModal() {
  const modal = document.getElementById('authModal');
  if (modal) modal.style.display = 'none';
}

async function handleLogin(e) {
  e?.preventDefault();
  const email = document.getElementById('loginEmail')?.value?.trim();
  const password = document.getElementById('loginPassword')?.value;

  if (!email || !password) {
    showToast('请输入邮箱和密码');
    return;
  }

  const btn = document.getElementById('loginSubmitBtn');
  if (btn) { btn.disabled = true; btn.textContent = '登录中...'; }

  try {
    await RoboLinkAuth.signIn(email, password);
    closeAuthModal();
    showToast('登录成功，欢迎回来！');
  } catch (err) {
    showToast(err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '登录'; }
  }
}

async function handleRegister(e) {
  e?.preventDefault();
  const email = document.getElementById('registerEmail')?.value?.trim();
  const password = document.getElementById('registerPassword')?.value;
  const username = document.getElementById('registerUsername')?.value?.trim();

  if (!email || !password || !username) {
    showToast('请填写所有字段');
    return;
  }
  if (password.length < 6) {
    showToast('密码至少6位');
    return;
  }

  const btn = document.getElementById('registerSubmitBtn');
  if (btn) { btn.disabled = true; btn.textContent = '注册中...'; }

  try {
    await RoboLinkAuth.signUp(email, password, username);
    closeAuthModal();
    showToast('注册成功！');
  } catch (err) {
    showToast(err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '注册'; }
  }
}

function handleGuestLogin() {
  RoboLinkAuth.guestLogin();
  closeAuthModal();
}

function handleSignOut() {
  RoboLinkAuth.signOut();
}

function toggleUserDropdown() {
  const dropdown = document.getElementById('userDropdown');
  if (dropdown) {
    dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
  }
}
