"""
test_monitor_agent.py —— Monitor Agent 测试。

覆盖：_default_urls 中文映射、_parse_changes JSON 解析、__call__ 节点接口、
      空 URL 时自动生成默认 URL、fetch_page 异常时跳过。
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.monitor_agent import MonitorAgent
from src.models.schemas import CompetitorChange, Severity, ChangeType


def test_default_urls_known_competitor():
    """中文竞品名映射为对应英文域名。"""
    urls = MonitorAgent._default_urls("字节跳动")
    assert any("bytedance.com" in u for u in urls)


def test_default_urls_unknown_competitor():
    """未映射的英文竞品名直接用作域名。"""
    urls = MonitorAgent._default_urls("stripe")
    assert any("stripe.com" in u for u in urls)


def test_default_urls_includes_pricing_and_blog():
    """默认 URL 包含 /pricing 和 /blog 子页面。"""
    urls = MonitorAgent._default_urls("openai")
    assert any("/pricing" in u for u in urls)
    assert any("/blog" in u for u in urls)
    assert any("/careers" in u for u in urls)


def test_parse_changes_valid_json():
    """_parse_changes 正确解析 LLM 返回的 JSON 变更列表。"""
    llm_output = json.dumps([
        {
            "change_type": "pricing",
            "title": "Price increase",
            "summary": "Pro plan +$10",
            "severity": "high",
            "url": "https://test.com/pricing",
        },
    ])
    changes = MonitorAgent._parse_changes(llm_output, "TestCo", "https://test.com")
    assert len(changes) == 1
    assert isinstance(changes[0], CompetitorChange)
    assert changes[0].change_type == ChangeType.PRICING
    assert changes[0].severity == Severity.HIGH
    assert changes[0].competitor == "TestCo"


def test_parse_changes_invalid_json():
    """LLM 返回非法 JSON 时 _parse_changes 返回空列表（不抛异常）。"""
    changes = MonitorAgent._parse_changes("not json at all", "TestCo", "https://test.com")
    assert changes == []


def test_parse_changes_code_block_wrapped():
    """LLM 返回被 markdown code block 包裹的 JSON 时也能正确解析。"""
    llm_output = '```json\n[{"change_type":"news","title":"New launch","summary":"X","severity":"low"}]\n```'
    changes = MonitorAgent._parse_changes(llm_output, "TestCo", "https://test.com")
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.NEWS


@pytest.mark.asyncio
async def test_call_node_with_empty_urls(mock_chat_tongyi):
    """URL 列表为空时 MonitorAgent.__call__ 自动生成默认 URL。"""
    mock_chat_tongyi.ainvoke.return_value.content = "[]"
    agent = MonitorAgent()

    with patch("src.agents.monitor_agent.fetch_page", new=AsyncMock(return_value="<html></html>")):
        result = await agent({"competitor": "openai", "monitor_urls": [], "previous_hashes": {}})
        assert "changes_detected" in result
        assert isinstance(result["changes_detected"], list)


@pytest.mark.asyncio
async def test_call_node_handles_fetch_failure(mock_chat_tongyi):
    """fetch_page 抛异常时 MonitorAgent 跳过该 URL 继续执行（不崩溃）。"""
    mock_chat_tongyi.ainvoke.return_value.content = "[]"
    agent = MonitorAgent()

    async def failing_fetch(url):
        raise ConnectionError("simulated failure")

    with patch("src.agents.monitor_agent.fetch_page", new=failing_fetch):
        result = await agent({"competitor": "TestCo", "monitor_urls": ["https://bad.url"], "previous_hashes": {}})
        assert "changes_detected" in result
        assert result["changes_detected"] == []
