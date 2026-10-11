// ESLint flat config（ESLint 9+）。
//
// 范围（诚实说明）：只覆盖 `scripts/*.mjs|js`、`functions/**/*.js`、
// `mcp-server/**/*.js`。Python 脚本走 `scripts/ci_gate.py` + ruff（暂未引入），
// HTML 由 Prettier 格式化。目标是**渐进启用**——先跑通现有代码，再逐条加规则，
// 避免一次性炸出一堆历史告警把 CI 变成噪音。

import js from '@eslint/js';

export default [
  // 全局忽略：与 .prettierignore 对齐
  {
    ignores: [
      'node_modules/**',
      '.deploy-staging/**',
      '.wrangler/**',
      '.tools/**',
      '.workbuddy/**',
      'ops/**',
      '.chk/**',
      '.tmp_scan/**',
      'mcp-server/node_modules/**',
      'roboparts-dataset-github/**',
    ],
  },

  // JS/ESM 基础规则
  js.configs.recommended,

  {
    files: ['scripts/**/*.{js,mjs}', 'functions/**/*.js', 'mcp-server/**/*.js'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: {
        // Node 22 全局
        process: 'readonly',
        console: 'readonly',
        fetch: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        Buffer: 'readonly',
        TextEncoder: 'readonly',
        TextDecoder: 'readonly',
        AbortController: 'readonly',
        structuredClone: 'readonly',
        crypto: 'readonly',
        // Cloudflare Pages / Workers
        addEventListener: 'readonly',
        serve: 'readonly',
        cloudflare: 'readonly',
        caches: 'readonly',
      },
    },
    rules: {
      // 只启用无争议的硬错误
      'no-undef': 'error',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-dupe-keys': 'error',
      'no-unreachable': 'error',
      'no-fallthrough': 'warn',
      'prefer-const': 'warn',
      'no-console': 'off',
    },
  },

  // Cloudflare Pages Functions 有全局 Request/Response 等
  {
    files: ['functions/**/*.js'],
    languageOptions: {
      globals: {
        Request: 'readonly',
        Response: 'readonly',
        Headers: 'readonly',
        FormData: 'readonly',
        Blob: 'readonly',
        File: 'readonly',
        WebSocket: 'readonly',
        Event: 'readonly',
        EventTarget: 'readonly',
      },
    },
  },
];
