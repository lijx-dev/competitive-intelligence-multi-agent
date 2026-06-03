"""
飞书自定义机器人 — 消息推送 + 卡片交互 + 签名验证。

支持:
  - send_competitor_report(report_data)  → 竞品分析报告卡片（蓝色模板）
  - send_simple_message(text)            → 纯文本消息
  - send_alert_card(alert_data)          → 告警通知卡片（红色模板）
  - gen_sign(timestamp)                  → HMAC-SHA256 签名验证
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

import httpx

from .card_templates import build_report_card, build_alert_card

logger = logging.getLogger(__name__)


class FeishuBot:
    """飞书自定义机器人 — 消息推送客户端。

    使用示例:
        bot = FeishuBot(webhook_url="https://open.feishu.cn/...", secret="xxx")
        await bot.send_simple_message("分析完成！")

        await bot.send_competitor_report({
            "competitor": "Notion",
            "quality_score": 8.5,
            "comparison_summary": "...",
            ...
        })
    """

    def __init__(
        self,
        webhook_url: str = "",
        secret: str = "",
    ):
        import os
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
        self.secret = secret or os.getenv("FEISHU_WEBHOOK_SECRET", "")
        self.base_url = os.getenv("BASE_URL", "http://localhost:8000")

        if not self.webhook_url:
            logger.info("飞书 Webhook 未配置，推送功能将静默跳过")

    # ── 签名验证 ───────────────────────────────────────

    def gen_sign(self, timestamp: int) -> str:
        """HMAC-SHA256 签名生成（飞书机器人安全设置）"""
        if not self.secret:
            return ""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    # ── 发送消息（核心方法）──────────────────────────────

    async def _send(self, payload: dict) -> bool:
        """发送消息到飞书 Webhook，返回是否成功（兼容模式：无SECRET也能直接发）"""
        if not self.webhook_url:
            logger.info("飞书推送跳过（未配置 webhook）")
            return False

        full_url = self.webhook_url
        # 兼容模式：如果用户没有配置SECRET，完全不附加签名参数也能发消息（飞书自定义机器人安全设置关闭时的标准用法）
        if self.secret and len(self.secret.strip()) > 0:
            ts = int(time.time())
            sign = self.gen_sign(ts)
            separator = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{separator}timestamp={ts}&sign={sign}"
        else:
            logger.info("飞书兼容模式（无签名）直接推送")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(full_url, json=payload)
                # ★ 防御：飞书可能返回非JSON（HTML错误页等）
                try:
                    result = resp.json()
                except Exception:
                    text_preview = (resp.text or "")[:300]
                    logger.warning("飞书返回非JSON响应 (status=%d): %s", resp.status_code, text_preview)
                    return False
                if result.get("code") == 0 or result.get("StatusCode") == 0:
                    logger.info("飞书消息推送成功")
                    return True
                else:
                    logger.error("飞书推送失败: code=%s, msg=%s",
                                 result.get("code"), result.get("msg"))
                    return False
        except Exception as e:
            logger.error("飞书推送异常: %s", str(e))
            return False

    # ── 业务推送方法 ────────────────────────────────────

    async def send_competitor_report(self, report_data: dict) -> bool:
        """推送竞品分析报告卡片

        report_data keys:
            competitor, quality_score, total_sources, reliability,
            duration_ms, key_findings, comparison_summary, report_id
        """
        if not self.webhook_url:
            return False

        card = build_report_card(
            competitor=report_data.get("competitor", "Unknown"),
            quality_score=float(report_data.get("quality_score", 0)),
            total_sources=int(report_data.get("total_sources", 0)),
            reliability=report_data.get("reliability", "N/A"),
            duration_ms=int(report_data.get("duration_ms", 0)),
            key_findings=report_data.get("key_findings", "分析完成，详见完整报告"),
            comparison_summary=report_data.get("comparison_summary", "详见完整报告"),
            report_id=report_data.get("report_id", ""),
            base_url=self.base_url,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        return await self._send(card)

    async def send_simple_message(self, text: str) -> bool:
        """发送普通文本消息"""
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return await self._send(payload)

    async def send_alert_card(self, alert_data: dict) -> bool:
        """推送告警通知卡片（红色模板）

        alert_data keys:
            competitor, severity, change_type, summary, alert_id, detected_at
        """
        if not self.webhook_url:
            return False

        card = build_alert_card(
            competitor=alert_data.get("competitor", "Unknown"),
            severity=alert_data.get("severity", "INFO"),
            change_type=alert_data.get("change_type", "unknown"),
            summary=alert_data.get("summary", ""),
            base_url=self.base_url,
            alert_id=alert_data.get("alert_id", ""),
            detected_at=alert_data.get("detected_at", ""),
        )
        return await self._send(card)

    async def send_test_card(self) -> bool:
        """发送测试卡片，验证推送链路"""
        return await self.send_competitor_report({
            "competitor": "测试竞品",
            "quality_score": 9.5,
            "total_sources": 12,
            "reliability": "85%",
            "duration_ms": 8500,
            "key_findings": "🧪 这是一条测试消息 — 飞书机器人推送链路正常\n✅ 签名验证通过\n✅ 卡片渲染正常",
            "comparison_summary": "测试对比摘要：我方产品在功能完整度(8.5)和技术创新(8.0)上领先",
            "report_id": "test-000",
        })

    # ── ★ 新增: 飞书CLI全局总调度官 — 确认卡片 + 进度卡片 ──

    async def send_confirmation_card(
        self, competitor: str, mode: str = "mock", task_id: str = ""
    ) -> bool:
        """发送交互式确认卡片（用户发命令后立即回复）。

        Args:
            competitor: 解析出的竞品名称
            mode: 分析模式 (mock/real)
            task_id: 任务追踪ID
        """
        try:
            from .command_parser import build_confirmation_card
        except ImportError:
            logger.warning("command_parser 模块不可用，跳过确认卡片")
            return False
        card = build_confirmation_card(competitor, mode, task_id)
        return await self._send(card)

    async def send_progress_card(
        self,
        competitor: str,
        task_id: str,
        node_statuses: dict,
        mode: str = "mock",
    ) -> bool:
        """发送分析进度卡片（12节点图标逐一更新）。

        node_statuses: {node_name: "pending"|"running"|"completed"|"failed"}
        """
        try:
            from .command_parser import build_progress_card
        except ImportError:
            logger.warning("command_parser 模块不可用，跳过进度卡片")
            return False
        card = build_progress_card(competitor, task_id, node_statuses, mode)
        return await self._send(card)

    async def send_task_completion_card(
        self,
        competitor: str,
        task_id: str,
        quality_score: float,
        mode: str = "mock",
        doc_url: str = "",
        bitable_url: str = "",
    ) -> bool:
        """发送任务完成汇总卡片（所有节点完成后的最终结果卡片）。

        Args:
            competitor: 竞品名称
            task_id: 任务ID
            quality_score: 质量评分
            mode: 分析模式
            doc_url: 飞书云文档链接
            bitable_url: 飞书多维表格链接
        """
        import json as _json

        lines = [
            f"🎉 **竞品分析完成！**",
            f"",
            f"**目标竞品**: {competitor}",
            f"**质量评分**: ⭐ {quality_score:.1f}/10",
            f"**任务ID**: `{task_id}`",
            f"**分析模式**: {'🎭 Mock演示' if mode == 'mock' else '🤖 真实LLM'}",
        ]
        if doc_url:
            lines.append(f"**📄 云文档报告**: [点击查看]({doc_url})")
        if bitable_url:
            lines.append(f"**📊 多维表格**: [点击查看]({bitable_url})")

        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "green",
                    "title": {
                        "tag": "plain_text",
                        "content": f"✅ 分析完成：{competitor}",
                    },
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": "\n".join(lines)},
                    },
                ],
            },
        }
        return await self._send(card)
