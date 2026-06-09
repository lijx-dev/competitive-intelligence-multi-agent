"""Alert Agent – real-time critical-change notifications via Feishu / Slack / DingTalk."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..models.schemas import Alert, CompetitorChange, Severity
from ..tools.notification import broadcast_alert

logger = logging.getLogger(__name__)

SEVERITY_THRESHOLD = Severity.HIGH

# ★ 记录最近推送的告警摘要hash，用于内存级去重（跨agent调用共享）
_ALERT_SUMMARY_CACHE: set[str] = set()


class AlertAgent:
    """Runs independently: evaluates changes and pushes alerts for high/critical
    severity items. ★ 修复: HIGH/CRITICAL变更立即推送飞书红头卡片。"""

    async def evaluate_and_alert(
        self,
        changes: list[CompetitorChange],
    ) -> list[Alert]:
        alerts: list[Alert] = []

        critical_changes = [
            c for c in changes
            if c.severity in (Severity.HIGH, Severity.CRITICAL)
        ]

        for change in critical_changes:
            title = f"[{change.severity.value.upper()}] {change.competitor}: {change.title}"
            message = (
                f"Change Type: {change.change_type.value}\n"
                f"Summary: {change.summary}\n"
                f"URL: {change.url}\n"
                f"Detected: {change.detected_at.isoformat()}"
            )

            # ★ 智能推送：Pipeline内静默（报告卡片已汇总），独立监控时推送
            channels = []
            import os as _alert_os
            skip_feishu = _alert_os.getenv("FEISHU_SKIP_ALERT_PUSH", "false").lower() == "true"
            if not skip_feishu:
                try:
                    from ..services.feishu import FeishuBot
                    from ..config import get_effective_notification_config
                    cfg = get_effective_notification_config()
                    if cfg.feishu_webhook_url:
                        bot = FeishuBot(
                            webhook_url=cfg.feishu_webhook_url,
                            secret=cfg.feishu_webhook_secret,
                        )
                        import asyncio as _asyncio
                        _asyncio.create_task(
                            bot.send_alert_card({
                                "competitor": change.competitor,
                                "severity": change.severity.value.upper(),
                                "change_type": change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type),
                                "summary": change.summary,
                                "alert_id": f"alert_{change.competitor}_{change.severity.value}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                                "detected_at": change.detected_at.isoformat() if isinstance(change.detected_at, datetime) else str(change.detected_at),
                            })
                        )
                        channels.append("feishu")
                        logger.info("[AlertAgent] 飞书告警卡片已发送: %s", change.title[:50])
                except Exception as e:
                    logger.warning("[AlertAgent] 飞书告警推送失败: %s", e)
            else:
                logger.info("[AlertAgent] Pipeline模式，告警合入报告卡片: %s", change.title[:50])

            # 同时走原有broadcast渠道（slack/dingtalk等）
            try:
                delivery = await broadcast_alert(title, message)
                for ch, ok in delivery.items():
                    if ok and ch not in channels:
                        channels.append(ch)
            except Exception:
                pass

            channel_str = ", ".join(channels) if channels else "feishu"

            alert = Alert(
                competitor=change.competitor,
                title=title,
                message=message,
                severity=change.severity,
                channel=channel_str,
                sent_at=datetime.utcnow(),
            )
            alerts.append(alert)
            logger.info("[AlertAgent] 告警已发送: %s (channels: %s)", title, channel_str)

        return alerts

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_changes = state.get("changes_detected", [])
        changes = [
            CompetitorChange(**c) if isinstance(c, dict) else c
            for c in raw_changes
        ]

        alerts = await self.evaluate_and_alert(changes)
        return {
            "alerts_sent": [a.model_dump() for a in alerts],
        }
