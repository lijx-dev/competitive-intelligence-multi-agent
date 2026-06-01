"""
安全防护体系测试 — 覆盖 URL 安全校验、日志脱敏、错误响应。
"""
import pytest

from src.utils.url_security import validate_safe_http_url
from src.utils.log_mask import mask_sensitive


class TestURLSecurity:
    """URL 协议白名单防护"""

    @pytest.mark.parametrize("url", [
        "https://example.com",
        "http://localhost:8000",
        "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
    ])
    def test_valid_http_urls(self, url):
        """http/https URL 应通过"""
        assert validate_safe_http_url(url) is True

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "ftp:// attacker.com/malware",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
    ])
    def test_dangerous_urls_blocked(self, url):
        """非 http/https 协议必须被拦截"""
        assert validate_safe_http_url(url) is False

    def test_empty_url_blocked(self):
        """空 URL 必须被拦截"""
        assert validate_safe_http_url("") is False

    def test_overlong_url_blocked(self):
        """超长 URL 必须被拦截（>2048）"""
        long_url = "https://example.com/" + "a" * 3000
        assert validate_safe_http_url(long_url) is False


class TestLogMask:
    """敏感信息日志脱敏"""

    def test_mask_api_key(self):
        """API Key 中间打星"""
        key = "sk-abcdef1234567890"
        masked = mask_sensitive(key)
        assert "***" in masked
        assert "sk-" in masked
        assert "7890" in masked
        assert "abcdef123456" not in masked

    def test_mask_short_value(self):
        """短值不处理"""
        assert mask_sensitive("abc") == "abc"

    def test_mask_empty(self):
        """空值不处理"""
        assert mask_sensitive("") == ""

    def test_mask_16_char(self):
        """16字符值打3星"""
        val = "1234567890abcdef"
        masked = mask_sensitive(val)
        assert masked == "123***def"

    def test_mask_long_value(self):
        """长值打6星"""
        val = "ark-abcdefghijklmnopqrstuvwxyz1234567890"
        masked = mask_sensitive(val)
        assert "******" in masked
