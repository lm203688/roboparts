/* RoboParts 统一 Project 状态模块 (P1-1)
 *
 * 报告：docs/RoboParts-五维全面调查与提升报告-20261022.md §2.2 & P1-1
 * 原状：五步流水线各用 localStorage / URLSearchParams / 内存 三套状态，互不相认
 * 目标：一个 project 对象贯穿 ① 选型 → ② 规划 → ③ 设计 → ④ BOM 校验 → ⑤ 转接件
 *
 * 存储策略：
 *   - localStorage key: `rp-project-v1`  存完整 project 对象
 *   - URL `?rp=<projectId>` 支持跨设备分享（只读快照）
 *   - localStorage key: `rp-projects-index-v1` 存历史项目列表（最近 10 条）
 *
 * API:
 *   RpProject.get(key, fallback)   取某字段
 *   RpProject.set(key, value)      改某字段并自动持久化 + 广播
 *   RpProject.setBatch(obj)        批量改
 *   RpProject.reset()              清空当前 project
 *   RpProject.create(name)         新建并切换到新 project
 *   RpProject.list()               列出历史项目（最近 10 条）
 *   RpProject.load(id)             加载历史项目到当前
 *   RpProject.onChange(fn)         订阅变更事件
 *   RpProject.fromUrl()            从 URL `?rp=xxx` 读取快照
 *   RpProject.step()               取当前流水线步序 0..4 或 -1
 *   RpProject.init()               页面 onmount 通用钩子
 */
(function () {
  'use strict';
  if (window.RpProject) return;

  var STORAGE_KEY = 'rp-project-v1';
  var INDEX_KEY = 'rp-projects-index-v1';
  var MAX_HISTORY = 10;
  var SCHEMA_VERSION = 1;

  function nowISO() { try { return new Date().toISOString(); } catch (e) { return ''; } }
  function shortId() { return 'rp_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8); }
  function safeParse(str) { if (!str) return null; try { return JSON.parse(str); } catch (e) { return null; } }
  function safeStringify(obj) { try { return JSON.stringify(obj); } catch (e) { return null; } }

  // P0-3：UTF-8 安全的 base64 编解码。
  // 浏览器原生 btoa/atob 只接受 latin1，中文字段（如项目名"我的机器人"）会被截断。
  function _encodeBase64(str) {
    try {
      var bytes = new TextEncoder().encode(str);
      var bin = '';
      for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
      return btoa(bin);
    } catch (e) { return ''; }
  }
  function _decodeBase64(b64) {
    try {
      var bin = atob(b64);
      var bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return new TextDecoder().decode(bytes);
    } catch (e) { return ''; }
  }

  function readStorage() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      var obj = safeParse(raw);
      return (obj && typeof obj === 'object') ? obj : null;
    } catch (e) { return null; }
  }

  function writeStorage(obj) {
    try { localStorage.setItem(STORAGE_KEY, safeStringify(obj)); } catch (e) {}
  }

  function readIndex() {
    try {
      var raw = localStorage.getItem(INDEX_KEY);
      if (!raw) return [];
      var arr = safeParse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }

  function writeIndex(arr) {
    try { localStorage.setItem(INDEX_KEY, safeStringify(arr)); } catch (e) {}
  }

  function touchHistory(p) {
    if (!p || !p.id) return;
    // 归档快照到独立 key，供 load/fromUrl 用
    try { localStorage.setItem('rp-project-' + p.id, safeStringify(p)); } catch (e) {}
    var idx = readIndex();
    var without = idx.filter(function (x) { return !x || x.id !== p.id; });
    without.unshift({
      id: p.id,
      name: p.name || '未命名项目',
      currentStep: p.currentStep,
      updatedAt: p.updatedAt || nowISO(),
      createdAt: p.createdAt || nowISO(),
    });
    if (without.length > MAX_HISTORY) without.length = MAX_HISTORY;
    writeIndex(without);
  }

  var _current = readStorage();
  if (!_current) _current = createEmpty();
  else _current = migrate(_current);

  function createEmpty() {
    return {
      _schema: SCHEMA_VERSION,
      id: shortId(),
      name: '新构建',
      createdAt: nowISO(),
      updatedAt: nowISO(),
      currentStep: 0,
      selection: {},
      planner: {},
      design: {},
      bom: {},
      adapter: {},
    };
  }

  function migrate(p) {
    if (p._schema === SCHEMA_VERSION) return p;
    var merged = Object.assign(createEmpty(), p || {});
    merged._schema = SCHEMA_VERSION;
    return merged;
  }

  var _subs = [];
  function notify(key, val) {
    _subs.forEach(function (fn) { try { fn(key, val, _current); } catch (e) {} });
    try { window.dispatchEvent(new CustomEvent('rp-project-change', { detail: { key: key, value: val } })); } catch (e) {}
  }

  var STEP_KEYS = ['selection', 'planner', 'design', 'bom', 'adapter'];

  function stepForPage(name) {
    if (name === 'selection.html') return 0;
    if (name === 'build-planner.html') return 1;
    if (name === 'designer.html') return 2;
    if (name === 'bom-checker.html') return 3;
    if (name === 'adapter-generator.html') return 4;
    return -1;
  }

  function currentPage() {
    try { return location.pathname.split('/').pop() || 'index.html'; }
    catch (e) { return ''; }
  }

  window.RpProject = {
    get: function (key, fallback) {
      var v = _current[key];
      return (v === undefined || v === null) ? fallback : v;
    },

    all: function () { return Object.assign({}, _current); },

    set: function (key, value) {
      _current[key] = value;
      _current.updatedAt = nowISO();
      writeStorage(_current);
      touchHistory(_current);
      notify(key, value);
      return _current[key];
    },

    setBatch: function (obj) {
      if (!obj || typeof obj !== 'object') return;
      Object.keys(obj).forEach(function (k) { _current[k] = obj[k]; });
      _current.updatedAt = nowISO();
      writeStorage(_current);
      touchHistory(_current);
      _subs.forEach(function (fn) { try { fn('*', obj, _current); } catch (e) {} });
    },

    touchStep: function (step) {
      _current.currentStep = step;
      _current.updatedAt = nowISO();
      writeStorage(_current);
      touchHistory(_current);
      notify('currentStep', step);
    },

    setForStep: function (step, data) {
      if (step < 0 || step >= STEP_KEYS.length) return;
      _current[STEP_KEYS[step]] = data || {};
      _current.currentStep = step;
      _current.updatedAt = nowISO();
      writeStorage(_current);
      touchHistory(_current);
      notify(STEP_KEYS[step], data);
    },

    getForStep: function (step) {
      if (step < 0 || step >= STEP_KEYS.length) return null;
      return _current[STEP_KEYS[step]] || null;
    },

    step: function () { return stepForPage(currentPage()); },

    reset: function () {
      _current = createEmpty();
      writeStorage(_current);
      touchHistory(_current);
      notify('reset', _current.id, _current);
      return _current;
    },

    create: function (name) {
      _current = Object.assign(createEmpty(), name ? { name: name } : {});
      writeStorage(_current);
      touchHistory(_current);
      notify('created', _current.id, _current);
      return _current;
    },

    list: function () { return readIndex().slice(); },

    load: function (id) {
      try {
        var raw = localStorage.getItem('rp-project-' + id);
        if (!raw) return false;
        var p = safeParse(raw);
        if (!p) return false;
        try { localStorage.setItem('rp-project-' + _current.id, safeStringify(_current)); } catch (e) {}
        _current = migrate(p);
        writeStorage(_current);
        touchHistory(_current);
        notify('loaded', p.id, _current);
        return true;
      } catch (e) { return false; }
    },

    onChange: function (fn) {
      _subs.push(fn);
      return function () {
        var i = _subs.indexOf(fn);
        if (i >= 0) _subs.splice(i, 1);
      };
    },

    fromUrl: function () {
      try {
        var sp = new URLSearchParams(location.search);
        // P0-3：优先读 ?share=<base64 JSON>（真正跨设备可用的自包含快照）；
        // 兼容旧的 ?rp=<id>（本机 localStorage 反查），保持老链接不失效。
        var inline = sp.get('share');
        if (inline) {
          try {
            var json = _decodeBase64(inline);
            var p = safeParse(json);
            if (p && typeof p === 'object' && p.id) return p;
          } catch (e) {}
        }
        var id = sp.get('rp');
        if (!id) return null;
        try {
          var raw = localStorage.getItem('rp-project-' + id);
          if (raw) {
            var p = safeParse(raw);
            if (p) return p;
          }
        } catch (e) {}
        return null;
      } catch (e) { return null; }
    },

    snapshot: function () {
      try { localStorage.setItem('rp-project-' + _current.id, safeStringify(_current)); } catch (e) {}
      return _current.id;
    },

    shareUrl: function () {
      // P0-3 修复（诚实化）：旧版本生成 /xxx.html?rp=rp_<random>，其中 id 是本机
      // localStorage 产生的随机 ID，接收方打开必然查不到 localStorage，fromUrl 静默
      // 返回 null——是「看起来能分享、实际永不跨设备」的经典假绿。
      //
      // 修法：把整个 project snapshot JSON 直接 base64 编码进 URL query，形成
      // **自包含**的分享链接，任何设备打开都能还原完整项目，无需后端/登录。
      // 代价：URL 较长（3–6KB base64 常见）；现代浏览器支持 32KB+ URL 无压力。
      // 诚实边界：超过 32KB 会 fail-fast 提示改用 backup() 导出文件，避免静默截断。
      var json = safeStringify(_current);
      if (!json) return null;
      var b64 = _encodeBase64(json);
      if (b64.length > 32000) {
        console.warn('[RpProject] snapshot ' + b64.length +
          ' chars 超过 32KB URL 分享安全上限，可能被浏览器截断。建议改用 RpProject.backup()。');
      }
      var base = location.origin + '/selection.html';
      return base + '?share=' + b64;
    },

    init: function () {
      var snapshot = this.fromUrl();
      if (snapshot && snapshot.id && snapshot.id !== _current.id) {
        _current = migrate(snapshot);
        try { localStorage.setItem('rp-project-' + snapshot.id, safeStringify(snapshot)); } catch (e) {}
        notify('loaded', snapshot.id, _current);
      }
      var step = this.step();
      if (step >= 0) {
        if (step !== _current.currentStep) {
          _current.currentStep = step;
        }
        _current.updatedAt = nowISO();
        writeStorage(_current);
        touchHistory(_current);
      }
      return _current;
    },
  };

  try { window.RpProject.init(); } catch (e) {}
})();
