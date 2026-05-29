"""敏感信息掩码日志工具 — API Key / Secret 防泄漏"""

from __future__ import annotations


def mask_sensitive(value: str) -> str:
    """把 API Key 这类敏感字符串打中间 *** 掩码，防止泄露到日志。

    >>> mask_sensitive("ark-abcdef1234567890")
    'ark-ab******67890'
    """
    if not value or len(value) < 10:
        return value
    if len(value) <= 16:
        return value[:3] + "***" + value[-3:]
    return value[:6] + "******" + value[-6:]
