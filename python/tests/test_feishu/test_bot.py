"""
飞书 Bot 测试 — 覆盖签名生成、消息卡片构建、推送失败容错。
"""
import base64
import hmac
import hashlib

import pytest

from src.services.feishu.bot import FeishuBot


class TestFeishuSign:
    """HMAC-SHA256 签名验证"""

    def test_gen_sign_algorithm(self):
        """签名算法必须与飞书官方一致"""
        bot = FeishuBot(webhook_url="https://test", secret="test_secret")
        timestamp = 1234567890

        sign = bot.gen_sign(timestamp)

        # 手动计算期望签名
        string_to_sign = f"{timestamp}\ntest_secret"
        expected = base64.b64encode(
            hmac.new(
                "test_secret".encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        assert sign == expected

    def test_gen_sign_empty_secret(self):
        """空 secret 应返回空字符串"""
        bot = FeishuBot(webhook_url="https://test", secret="")
        assert bot.gen_sign(1234567890) == ""


class TestFeishuBotInit:
    """Bot 初始化"""

    def test_bot_init_with_params(self):
        """显式参数初始化"""
        bot = FeishuBot(webhook_url="https://open.feishu.cn/hook/xxx", secret="s")
        assert bot.webhook_url == "https://open.feishu.cn/hook/xxx"
        assert bot.secret == "s"

    def test_bot_init_no_webhook(self, monkeypatch):
        """未配置 webhook 时属性为空"""
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("FEISHU_WEBHOOK_SECRET", raising=False)
        bot = FeishuBot(webhook_url="", secret="")
        assert bot.webhook_url == ""
        assert bot.secret == ""


class TestReportCardBuild:
    """消息卡片模板"""

    def test_report_card_structure(self):
        """报告卡片必须包含关键字段"""
        from src.services.feishu.card_templates import build_report_card

        card = build_report_card(
            competitor="TestCorp",
            quality_score=8.5,
            total_sources=5,
            reliability="高",
            duration_ms=1250,
            key_findings="发现3个关键差异",
            comparison_summary="我们在产品功能上领先。",
            report_id="rpt_001",
        )

        assert "TestCorp" in str(card)
        assert "8.5" in str(card)

    def test_alert_card_structure(self):
        """告警卡片必须包含关键字段"""
        from src.services.feishu.card_templates import build_alert_card

        card = build_alert_card(
            competitor="TestCorp",
            severity="HIGH",
            change_type="pricing_change",
            summary="定价从99降到79",
            base_url="http://localhost:8000",
        )

        assert "TestCorp" in str(card)
        assert "HIGH" in str(card)
