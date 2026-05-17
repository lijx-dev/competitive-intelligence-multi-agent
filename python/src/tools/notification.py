"""Notification dispatcher – Slack, DingTalk, and Email.

所有通知渠道配置从动态配置系统读取，支持运行时修改即时生效。
"""

from __future__ import annotations

import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional

import httpx

from ..config import get_effective_notification_config

logger = logging.getLogger(__name__)


async def send_slack(message: str, webhook_url: Optional[str] = None) -> bool:
    url = webhook_url or get_effective_notification_config().slack_webhook
    if not url:
        logger.info("Slack webhook not configured – skipping")
        return False
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={"text": message}, timeout=10)
        return resp.status_code == 200


async def send_dingtalk(message: str, webhook_url: Optional[str] = None) -> bool:
    url = webhook_url or get_effective_notification_config().dingtalk_webhook
    if not url:
        logger.info("DingTalk webhook not configured – skipping")
        return False
    payload = {
        "msgtype": "text",
        "text": {"content": message},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=10)
        return resp.status_code == 200


async def send_email(
    subject: str,
    body: str,
    to_addrs: Optional[list[str]] = None,
) -> bool:
    cfg = get_effective_notification_config()
    if to_addrs is None:
        to_addrs = [cfg.email_to] if cfg.email_to else []
    if not cfg.email_smtp_host or not to_addrs:
        logger.info("Email not configured – skipping")
        return False
    try:
        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg.email_from
        msg["To"] = ", ".join(to_addrs)
        with smtplib.SMTP(cfg.email_smtp_host, cfg.email_smtp_port) as server:
            server.starttls()
            server.login(cfg.email_from, cfg.email_password)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email")
        return False


async def broadcast_alert(title: str, message: str) -> dict[str, bool]:
    """Send an alert to all configured channels and return delivery status."""
    full_message = f"🚨 *{title}*\n{message}"
    cfg = get_effective_notification_config()
    result = {}
    if cfg.slack_enabled or cfg.slack_webhook:
        result["slack"] = await send_slack(full_message)
    if cfg.dingtalk_enabled or cfg.dingtalk_webhook:
        result["dingtalk"] = await send_dingtalk(full_message)
    return result
