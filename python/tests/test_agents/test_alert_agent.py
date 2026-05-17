"""
test_alert_agent.py —— Alert Agent 测试。

覆盖：HIGH/CRITICAL 阈值过滤逻辑、低严重度被忽略、
      broadcast_alert 调用、__call__ 节点接口。
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.agents.alert_agent import AlertAgent
from src.models.schemas import CompetitorChange, Severity, ChangeType
from datetime import datetime


def make_change(severity: Severity) -> CompetitorChange:
    """Helper: 创建指定严重度的 CompetitorChange。"""
    return CompetitorChange(
        competitor="TestCo",
        change_type=ChangeType.PRICING,
        title="Test Change",
        summary="Test",
        severity=severity,
        detected_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_only_high_and_critical_trigger_alerts():
    """仅 HIGH 和 CRITICAL 级别的变更触发告警，LOW/MEDIUM 被忽略。"""
    agent = AlertAgent()
    changes = [
        make_change(Severity.LOW),
        make_change(Severity.MEDIUM),
        make_change(Severity.HIGH),
        make_change(Severity.CRITICAL),
    ]

    with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": True, "dingtalk": False})):
        alerts = await agent.evaluate_and_alert(changes)
        assert len(alerts) == 2
        assert alerts[0].severity == Severity.HIGH
        assert alerts[1].severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_no_alerts_when_all_low():
    """所有变更均为 LOW 时 produce 0 条告警。"""
    agent = AlertAgent()
    changes = [make_change(Severity.LOW), make_change(Severity.MEDIUM)]

    with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": False, "dingtalk": False})):
        alerts = await agent.evaluate_and_alert(changes)
        assert len(alerts) == 0


@pytest.mark.asyncio
async def test_call_node(sample_changes):
    """AlertAgent.__call__ 从 state 中读取 changes_detected 并输出 alerts_sent。"""
    agent = AlertAgent()
    with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": True, "dingtalk": False})):
        result = await agent({"changes_detected": [make_change(Severity.CRITICAL)]})
        assert "alerts_sent" in result
        assert len(result["alerts_sent"]) == 1
        assert result["alerts_sent"][0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_call_node_empty_changes():
    """空变更列表时 alerts_sent 为空列表。"""
    agent = AlertAgent()
    result = await agent({"changes_detected": []})
    assert result["alerts_sent"] == []
