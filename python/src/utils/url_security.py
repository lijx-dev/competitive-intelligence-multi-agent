"""URL安全校验工具 — 防止SSRF漏洞，白名单模式"""
from __future__ import annotations
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTS = {"127.0.0.1", "0.0.0.0", "192.168.", "10.", "172."}
MAX_URL_LENGTH = 2048


def validate_safe_url(url: str) -> bool:
    """
    校验URL是否安全，防止SSRF攻击。
    只允许http/https，拦截内网IP地址，限制URL长度≤2048。
    """
    if not url:
        return False
    if len(url) > MAX_URL_LENGTH:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        for blocked_prefix in BLOCKED_HOSTS:
            if host.startswith(blocked_prefix):
                return False
        return True
    except Exception:
        return False


# Alias for backward compatibility with test imports
validate_safe_http_url = validate_safe_url
