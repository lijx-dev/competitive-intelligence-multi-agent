"""URL Schema 白名单校验 — 防止 SSRF 攻击（file:///ftp:// 等危险协议拦截）"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ALLOWED_URL_SCHEMAS = {"http", "https"}


def validate_safe_http_url(url: str) -> bool:
    """校验 URL 是否为安全 HTTP/HTTPS 协议，且不超过 2048 字符。"""
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ALLOWED_URL_SCHEMAS
            and bool(parsed.netloc)
            and len(url) <= 2048
        )
    except Exception as e:
        logger.warning("URL校验失败: %s", e)
        return False
