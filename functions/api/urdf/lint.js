/**
 * RoboParts URDF Linter API
 * POST /api/urdf/lint          - 对 URDF XML 做兼容性静态检查
 *
 * 请求：
 *   Content-Type: application/json
 *   {
 *     "urdf_xml": "<?xml version=\"1.0\"?><robot name=\"...\">...</robot>",
 *     "check_level": "all" | "errors_only" | "warnings_and_errors"
 *   }
 *
 * 响应：
 *   {
 *     "severity": "error" | "warning" | "info",
 *     "robot_name": "string",
 *     "issues": [...],
 *     "summary": "string",
 *     "stats": {...}
 *   }
 *
 * 错误响应：
 *   400 - 请求体格式错误
 *   413 - URDF XML 超过 512KB
 *   500 - 服务端错误
 */

import { lintUrdf } from '../../_urdf_lint.js';

const MAX_SIZE = 524288; // 512KB

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  // CORS
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  // 只接受 POST
  if (request.method !== 'POST') {
    return jsonResponse({
      error: 'method_not_allowed',
      message: 'Only POST is supported. Send URDF XML as JSON: {"urdf_xml": "..."}',
    }, 405);
  }

  // 检查 Content-Type
  const contentType = request.headers.get('Content-Type') || '';
  if (!contentType.includes('application/json')) {
    return jsonResponse({
      error: 'invalid_content_type',
      message: `Expected Content-Type: application/json, got: ${contentType}`,
      hint: 'Send JSON body: {"urdf_xml": "<xml content>"}',
    }, 400);
  }

  try {
    const body = await request.json();
    const xml = body.urdf_xml;

    if (!xml || typeof xml !== 'string') {
      return jsonResponse({
        error: 'missing_urdf_xml',
        message: 'Missing required field: urdf_xml (string containing URDF XML)',
      }, 400);
    }

    if (xml.length > MAX_SIZE) {
      return jsonResponse({
        error: 'payload_too_large',
        message: `URDF XML exceeds ${MAX_SIZE} bytes (512KB). Got: ${xml.length} bytes.`,
        max_size: MAX_SIZE,
        actual_size: xml.length,
      }, 413);
    }

    // 运行 linter
    const result = lintUrdf(xml, {
      checkLevel: body.check_level || 'all',
    });

    return jsonResponse(result, 200, {
      'Cache-Control': 'no-cache',
    });
  } catch (e) {
    if (e instanceof SyntaxError) {
      return jsonResponse({
        error: 'invalid_json',
        message: 'Request body must be valid JSON',
      }, 400);
    }
    console.error('[urdf/lint] Error:', e);
    return jsonResponse({
      error: 'internal_error',
      message: 'Internal server error during URDF linting',
    }, 500);
  }
}

function jsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      ...extraHeaders,
    },
  });
}
