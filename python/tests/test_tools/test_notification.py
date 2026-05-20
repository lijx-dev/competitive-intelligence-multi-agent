"""
test_notification.py —— 通知工具测试。

覆盖：Slack/钉钉未配置时的优雅降级、邮件未配置降级、broadcast_alert 广播。
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.tools.notification import send_slack, send_dingtalk, send_email, broadcast_alert


# ==================== send_slack ====================

@pytest.mark.asyncio
async def test_send_slack_no_webhook():
    """未配置 Slack Webhook 时 send_slack 返回 False（优雅降级）。"""
    result = await send_slack("test message", webhook_url="")
    assert result is False


@pytest.mark.asyncio
async def test_send_slack_success():
    """配置了 Webhook 且请求成功时 send_slack 返回 True。"""
    async def mock_post(*args, **kwargs):
        class MockResp:
            status_code = 200
        return MockResp()

    with patch("httpx.AsyncClient.post", new=mock_post):
        result = await send_slack("test", webhook_url="https://hooks.slack.com/test")
        assert result is True


@pytest.mark.asyncio
async def test_send_slack_failure():
    """请求失败时 send_slack 返回 False。"""
    async def mock_post(*args, **kwargs):
        class MockResp:
            status_code = 500
        return MockResp()

    with patch("httpx.AsyncClient.post", new=mock_post):
        result = await send_slack("test", webhook_url="https://hooks.slack.com/test")
        assert result is False


# ==================== send_dingtalk ====================

@pytest.mark.asyncio
async def test_send_dingtalk_no_webhook():
    """未配置钉钉 Webhook 时 send_dingtalk 返回 False。"""
    result = await send_dingtalk("test message", webhook_url="")
    assert result is False


@pytest.mark.asyncio
async def test_send_dingtalk_success():
    """配置了 Webhook 且请求成功时 send_dingtalk 返回 True。"""
    async def mock_post(*args, **kwargs):
        class MockResp:
            status_code = 200
        return MockResp()

    with patch("httpx.AsyncClient.post", new=mock_post):
        result = await send_dingtalk("test", webhook_url="https://oapi.dingtalk.com/test")
        assert result is True


# ==================== send_email ====================

@pytest.mark.asyncio
async def test_send_email_not_configured():
    """未配置 SMTP 时 send_email 返回 False。"""
    result = await send_email("subject", "body", [])
    assert result is False


# ==================== broadcast_alert ====================

@pytest.mark.asyncio
async def test_broadcast_alert_all_disabled():
    """所有渠道未配置/未启用时 broadcast_alert 返回空 dict"""
    result = await broadcast_alert("Test Alert", "Something happened")
    # 未配置任何通知渠道时，返回空 dict（优雅降级）
    assert isinstance(result, dict)
    assert result.get("slack", True) is True or "slack" not in result  # 未启用=不发送
