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
        # ★ 自动检测ngrok公网URL（用于卡片按钮跳转）
        self.base_url = os.getenv("BASE_URL", "")
        if not self.base_url:
            self.base_url = self._detect_ngrok_url() or "http://localhost:8000"
        # 全局推送开关（可在.env中设置 FEISHU_AUTO_PUSH_ENABLED=false 一键关闭）
        self.auto_push_enabled = os.getenv("FEISHU_AUTO_PUSH_ENABLED", "true").lower() != "false"
        # 告警去重缓存: (competitor, change_type, summary_hash) → last_push_timestamp
        self._alert_dedup_cache: dict[tuple, float] = {}

    @staticmethod
    def _detect_ngrok_url() -> str | None:
        """自动从本地ngrok API获取公网URL"""
        try:
            import urllib.request, json
            resp = urllib.request.urlopen("http://localhost:4040/api/tunnels", timeout=2)
            data = json.loads(resp.read())
            for t in data.get("tunnels", []):
                url = t.get("public_url", "")
                if url.startswith("https://"):
                    logger.info("[FeishuBot] 自动检测到ngrok URL: %s", url)
                    return url
        except Exception:
            pass
        return None

        if not self.webhook_url:
            logger.info("[FeishuBot] 飞书 Webhook 未配置，推送功能将静默跳过")
        elif not self.auto_push_enabled:
            logger.info("[FeishuBot] FEISHU_AUTO_PUSH_ENABLED=false，所有自动推送已关闭")

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
    
    def _deep_sanitize_payload(self, obj: Any) -> Any:
        """递归全量清洗payload中所有字符串，彻底清除所有非法控制字符。"""
        import re
        if isinstance(obj, str):
            # 移除 0x00-0x1F 和 0x7F 范围内所有不可打印控制字符
            cleaned = re.sub(r'[\x00-\x1f\x7f]', '', obj)
            return cleaned.strip()
        elif isinstance(obj, dict):
            return {k: self._deep_sanitize_payload(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_sanitize_payload(i) for i in obj]
        else:
            return obj

    async def _send(self, payload: dict, *, fallback_text: str = "") -> bool:
        """发送消息到飞书 Webhook，返回是否成功。

        ★ 全局加固：交互式卡片推送失败时自动降级发送纯文本消息，
        保证至少用户能收到通知，不会完全静默失败。
        """
        if not self.webhook_url:
            logger.info("[FeishuBot] 推送跳过（未配置 webhook）")
            return False

        if not self.auto_push_enabled:
            logger.info("[FeishuBot] 推送跳过（FEISHU_AUTO_PUSH_ENABLED=false）")
            return False

        # ★ 核心修复：递归全量清洗整个payload，彻底清除所有非法控制字符
        payload = self._deep_sanitize_payload(payload)

        full_url = self.webhook_url
        # 兼容模式：如果用户没有配置SECRET，完全不附加签名参数也能发消息
        if self.secret and len(self.secret.strip()) > 0:
            ts = int(time.time())
            sign = self.gen_sign(ts)
            separator = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{separator}timestamp={ts}&sign={sign}"

        msg_type = payload.get("msg_type", "unknown")
        card_title = ""
        try:
            card_title = payload.get("card", {}).get("header", {}).get("title", {}).get("content", "")
        except Exception:
            pass

        # ★ 全局限流：确保两次推送间隔至少1.5秒，避免9499
        now_ts = time.time()
        if hasattr(self, '_last_send_ts') and (now_ts - self._last_send_ts) < 1.5:
            wait = 1.5 - (now_ts - self._last_send_ts)
            logger.info("[FeishuBot] 限流等待 %.1fs...", wait)
            import asyncio as _asyncio_sleep
            await _asyncio_sleep.sleep(wait)
        self._last_send_ts = time.time()

        logger.info("[FeishuBot] 准备推送 %s 到 webhook... title=%s", msg_type, card_title[:80] if card_title else "(text)")

        # 内部推送函数（带9499重试）
        async def _do_send(pld: dict, attempt: int = 1) -> tuple[bool, int, str]:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(full_url, json=pld)
                    try:
                        result = resp.json()
                    except Exception:
                        return False, resp.status_code, (resp.text or "")[:200]
                    code = result.get("code") or result.get("StatusCode") or 0
                    msg = result.get("msg", "")
                    return code == 0, code, msg
            except Exception as e:
                return False, -1, str(e)[:200]

        success, code, msg = await _do_send(payload)
        if success:
            logger.info("[FeishuBot] 推送成功 code=0 msg_type=%s", msg_type)
            return True

        # ★ 9499限流 → 等待30秒让限流窗口完全重置
        if code == 9499:
            logger.warning("[FeishuBot] 触发9499限流，等待30秒让限流窗口重置...")
            import asyncio as _asyncio_retry
            await _asyncio_retry.sleep(30.0)
            success2, code2, msg2 = await _do_send(payload)
            if success2:
                logger.warning("[FeishuBot] ★ 9499等待30秒后重试成功！")
                return True
            logger.warning("[FeishuBot] ★ 9499等待30秒后重试仍失败: code=%s msg=%s", code2, msg2)

        # ★ 降级：发送纯文本消息
        if fallback_text and code != 0:
            logger.info("[FeishuBot] 卡片推送失败(code=%s)，降级发送纯文本...", code)
            return await self._send_text_fallback(fallback_text)
        return False

    async def _send_text_fallback(self, text: str) -> bool:
        """纯文本降级兜底：9499限流时自动等待重试。"""
        try:
            payload = {
                "msg_type": "text",
                "content": {"text": f"[竞品分析系统]\n{text}"},
            }
            payload = self._deep_sanitize_payload(payload)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.webhook_url, json=payload)
                result = resp.json()
                code = result.get("code") or result.get("StatusCode") or 0
                if code == 0:
                    logger.info("[FeishuBot] 纯文本降级推送成功")
                    return True
                elif code == 9499:
                    # 等待30秒限流窗口重置后重试
                    import asyncio as _retry_asyncio
                    await _retry_asyncio.sleep(30.0)
                    async with httpx.AsyncClient(timeout=10.0) as client2:
                        resp2 = await client2.post(self.webhook_url, json=payload)
                        r2 = resp2.json()
                        if (r2.get("code") or r2.get("StatusCode") or 0) == 0:
                            logger.info("[FeishuBot] 纯文本9499重试成功")
                            return True
                logger.warning("[FeishuBot] 纯文本降级推送也失败: code=%s", code)
                return False
        except Exception as e:
            logger.warning("[FeishuBot] 纯文本降级推送异常: %s", e)
            return False

    def _check_alert_dedup(self, competitor: str, change_type: str, summary: str) -> bool:
        """告警去重：相同competitor+相同change_type+24小时内同摘要只推送一次。
        返回 True 表示应该跳过（重复告警）。
        """
        import hashlib as _hashlib
        now = time.time()
        key = (competitor.strip(), change_type.strip(), _hashlib.md5(summary[:200].encode()).hexdigest())
        last_ts = self._alert_dedup_cache.get(key, 0)
        if now - last_ts < 86400:  # 24小时
            logger.info("[FeishuBot] 告警去重跳过: competitor=%s type=%s", competitor, change_type)
            return True
        self._alert_dedup_cache[key] = now
        # 清理过期缓存（超过48小时的条目）
        expired = [(k, v) for k, v in self._alert_dedup_cache.items() if now - v > 172800]
        for k, _ in expired:
            del self._alert_dedup_cache[k]
        return False

    # ── 业务推送方法 ────────────────────────────────────

    async def send_competitor_report(self, report_data: dict) -> bool:
        """推送竞品分析报告卡片（蓝头），失败自动降级纯文本。

        report_data keys:
            competitor, quality_score, total_sources, reliability,
            duration_ms, key_findings, comparison_summary, report_id
        """
        if not self.webhook_url:
            return False
        if not self.auto_push_enabled:
            logger.info("[FeishuBot] 自动推送已关闭，跳过报告卡片")
            return False

        competitor = report_data.get("competitor", "Unknown")
        quality = float(report_data.get("quality_score", 0))
        # 构建降级纯文本内容
        fallback = (
            f"竞品分析报告: {competitor}\n"
            f"质量评分: {quality:.1f}/10\n"
            f"数据来源: {report_data.get('total_sources', 0)}个\n"
            f"可信度: {report_data.get('reliability', 'N/A')}\n"
            f"报告ID: {report_data.get('report_id', '')}"
        )

        logger.info("[FeishuBot] 准备推送报告卡片到webhook... competitor=%s score=%.1f",
                     competitor, quality)

        card = build_report_card(
            competitor=competitor,
            quality_score=quality,
            total_sources=int(report_data.get("total_sources", 0)),
            reliability=report_data.get("reliability", "N/A"),
            duration_ms=int(report_data.get("duration_ms", 0)),
            key_findings=report_data.get("key_findings", "分析完成，详见完整报告"),
            comparison_summary=report_data.get("comparison_summary", "详见完整报告"),
            report_id=report_data.get("report_id", ""),
            base_url=self.base_url,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        return await self._send(card, fallback_text=fallback)

    async def send_simple_message(self, text: str) -> bool:
        """发送普通文本消息"""
        if not self.webhook_url:
            return False
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return await self._send(payload)

    async def send_alert_card(self, alert_data: dict) -> bool:
        """推送告警通知卡片（红色模板），失败自动降级纯文本。

        alert_data keys:
            competitor, severity, change_type, summary, alert_id, detected_at
        """
        if not self.webhook_url:
            return False
        if not self.auto_push_enabled:
            logger.info("[FeishuBot] 自动推送已关闭，跳过告警卡片")
            return False

        competitor = alert_data.get("competitor", "Unknown")
        change_type = alert_data.get("change_type", "unknown")
        summary = alert_data.get("summary", "")
        severity = alert_data.get("severity", "INFO")

        # ★ 告警去重：同competitor+同change_type+24h内同摘要只推一次
        if self._check_alert_dedup(competitor, change_type, summary):
            return False

        logger.info("[FeishuBot] 准备推送告警卡片到webhook... competitor=%s severity=%s type=%s",
                     competitor, severity, change_type)

        # 构建降级纯文本内容
        fallback = (
            f"[{severity.upper()}] 竞品监控告警\n"
            f"竞品: {competitor}\n"
            f"变更类型: {change_type}\n"
            f"摘要: {summary[:200]}\n"
            f"时间: {alert_data.get('detected_at', 'N/A')}"
        )

        card = build_alert_card(
            competitor=competitor,
            severity=severity,
            change_type=change_type,
            summary=summary,
            base_url=self.base_url,
            alert_id=alert_data.get("alert_id", ""),
            detected_at=alert_data.get("detected_at", ""),
        )
        return await self._send(card, fallback_text=fallback)

    async def send_test_card(self) -> bool:
        """发送测试卡片，验证推送链路（纯文本无emoji，100%兼容飞书JSON）"""
        return await self.send_competitor_report({
            "competitor": "测试竞品",
            "quality_score": 9.5,
            "total_sources": 12,
            "reliability": "85%",
            "duration_ms": 8500,
            "key_findings": "[测试] 这是一条测试消息 - 飞书机器人推送链路正常 签名验证通过 卡片渲染正常",
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
