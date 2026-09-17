#!/usr/bin/env python3
"""SwarmLabs 外部数据源客户端（跨项目独立性：只走 HTTPS 公开 API）。

约束（与 docs/swarmlabs-api-spec-v1-20260917.md 对齐）：
- 唯一鉴权方式：`x-api-key` 头（大小写不敏感）
- 空 body 一律视为错误（不能当作 "no results"）
- 单次调用超时 15s，失败重试 1 次（退避 3s）
- 幂等：GET 相同 URL 多次调用返回字节一致（sha256 恒定，Spec §6）
- 不持久化原始响应缓存到 git（避免派生物冻结快照病）
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_BASE = "https://swarmlabs.tools"
DEFAULT_TIMEOUT = 15
RETRY_DELAY_SEC = 3
USER_AGENT = "roboparts-external-signals/1.0 (+https://roboparts.cc)"


class SwarmLabsError(Exception):
    """任何 API 错误。带 `status`（HTTP）与 `code`（响应体 error 字段）。"""

    def __init__(self, message: str, status: Optional[int] = None, code: Optional[str] = None, request_id: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id


def _load_env() -> Dict[str, str]:
    """读 .env.local + 真实环境变量。仅用 os.path / os.environ，不引入第三方库。"""
    env: Dict[str, str] = {}
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(cwd, ".env.local")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if k in ("SWARMLABS_API_KEY", "SWARMLABS_BASE_URL"):
            env[k] = v
    return env


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _request(
    method: str,
    base_url: str,
    path: str,
    api_key: Optional[str],
    params: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """发一次 HTTP 请求，返回解析后的 JSON。所有异常统一抛 SwarmLabsError。"""
    url = base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})

    req = urllib.request.Request(url, method=method)
    if api_key:
        req.add_header("x-api-key", api_key)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", USER_AGENT)

    last_exc: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8")
                return __import__("json").loads(body)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                import json as _json
                parsed = _json.loads(err_body)
            except Exception:
                parsed = {"error": "parse_error", "raw": err_body[:200]}
            raise SwarmLabsError(
                message=f"{method} {path} -> HTTP {e.code}: {parsed.get('message', parsed.get('error', '?'))}",
                status=e.code,
                code=parsed.get("error"),
                request_id=parsed.get("request_id"),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_exc = e
            if attempt == 2:
                raise SwarmLabsError(f"{method} {path} -> network error: {e}") from e
            time.sleep(RETRY_DELAY_SEC)
    raise SwarmLabsError(f"unreachable: {method} {path}")


class SwarmLabsClient:
    """极简客户端，只用 stdlib。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT):
        env = _load_env()
        self.api_key = api_key or env.get("SWARMLABS_API_KEY")
        self.base_url = (base_url or env.get("SWARMLABS_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("SWARMLABS_API_KEY missing (set in .env.local or env)")

    def health(self) -> Dict[str, Any]:
        return _request("GET", self.base_url, "/api/health", self.api_key, timeout=self.timeout)

    def search(self, q: str, kind: Optional[str] = None, limit: int = 20, since: Optional[str] = None) -> Dict[str, Any]:
        if not q or len(q) < 1 or len(q) > 100:
            raise ValueError(f"q must be 1-100 chars, got {len(q) if q else 0}")
        return _request(
            "GET", self.base_url, "/api/entities/search", self.api_key,
            params={"q": q, "kind": kind, "limit": limit, "since": since},
            timeout=self.timeout,
        )

    def bridge(self, from_tag: str, to_tag: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        return _request(
            "GET", self.base_url, "/api/bridge", self.api_key,
            params={"from": from_tag, "to": to_tag, "limit": limit},
            timeout=self.timeout,
        )

    def gaps(self, domain: str, status: Optional[str] = "open", limit: int = 20) -> Dict[str, Any]:
        return _request(
            "GET", self.base_url, "/api/gaps", self.api_key,
            params={"domain": domain, "status": status, "limit": limit},
            timeout=self.timeout,
        )

    def trends(self, domain: str, since: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        return _request(
            "GET", self.base_url, "/api/trends", self.api_key,
            params={"domain": domain, "since": since, "limit": limit},
            timeout=self.timeout,
        )

    def paper(self, id_or_doi: str) -> Dict[str, Any]:
        return _request("GET", self.base_url, f"/api/papers/{urllib.parse.quote(id_or_doi, safe='/%.')}", self.api_key, timeout=self.timeout)


def verify_idempotency(client: SwarmLabsClient, path: str, n: int = 3) -> Dict[str, Any]:
    """测 Spec §6 幂等契约：同一 URL 连续调用 n 次，body sha256 必须恒定。"""
    hashes: list = []
    for _ in range(n):
        data = _request("GET", client.base_url, path, client.api_key, timeout=client.timeout)
        import json as _json
        hashes.append(sha256(_json.dumps(data, sort_keys=True, ensure_ascii=False)))
    ok = len(set(hashes)) == 1
    return {"ok": ok, "hashes": hashes, "unique": len(set(hashes))}


if __name__ == "__main__":
    # 手工 smoke：`python scripts/swarmlabs_client.py`
    client = SwarmLabsClient()
    print(f"[info] base={client.base_url}")
    h = client.health()
    print(f"[health] status={h.get('status')} key_ok={h.get('key_ok')} project={h.get('project')} entity_count={h.get('entity_count')}")
    print()
    print("[smoke] search?q=neural&limit=3")
    r = client.search(q="neural", limit=3)
    print(f"  total={r.get('total')} returned={r.get('returned')}")
    for hit in r.get("results", [])[:3]:
        print(f"  - [{hit.get('kind')}] {hit.get('title') or hit.get('name')}")
    print()
    print("[smoke] idempotency (3 identical calls /api/trends?domain=cs&limit=5)")
    v = verify_idempotency(client, "/api/trends?domain=cs&limit=5", n=3)
    print(f"  ok={v['ok']} unique_sha256={v['unique']}")
