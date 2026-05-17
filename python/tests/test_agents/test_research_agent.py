"""
test_research_agent.py —— Research Agent 测试。

覆盖：_parse_insights JSON 解析和兜底、__call__ 节点接口、
      _gather_intelligence 搜索维度完整。
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.research_agent import ResearchAgent
from src.models.schemas import ResearchInsight


def test_parse_insights_valid_json():
    """_parse_insights 正确解析 LLM 返回的研究洞察 JSON。"""
    llm_output = json.dumps([
        {
            "topic": "Financial Analysis",
            "summary": "Strong revenue growth.",
            "key_findings": ["Revenue +40% YoY", "Profit margin 25%"],
            "sources": ["https://example.com/report"],
            "confidence": 0.85,
        },
    ])
    insights = ResearchAgent._parse_insights(llm_output)
    assert len(insights) == 1
    assert isinstance(insights[0], ResearchInsight)
    assert insights[0].topic == "Financial Analysis"
    assert insights[0].confidence == 0.85
    assert len(insights[0].key_findings) == 2


def test_parse_insights_invalid_json_returns_raw():
    """LLM 返回非法 JSON 时 _parse_insights 降级为原始文本的单个 Insight。"""
    insights = ResearchAgent._parse_insights("garbled output from LLM")
    assert len(insights) == 1
    assert insights[0].topic == "Raw Analysis"
    assert insights[0].summary == "garbled output from LLM"
    assert insights[0].confidence == 0.5


@pytest.mark.asyncio
async def test_call_node_basic(mock_chat_tongyi):
    """ResearchAgent.__call__ 在 Mock LLM 返回有效 JSON 时输出 research_results。"""
    mock_chat_tongyi.ainvoke.return_value.content = json.dumps([
        {"topic": "Test", "summary": "Test summary", "key_findings": ["A", "B"], "sources": [], "confidence": 0.9},
    ])
    agent = ResearchAgent()

    with patch("src.agents.research_agent.web_search", new=AsyncMock(return_value=[])):
        with patch("src.agents.research_agent.news_search", new=AsyncMock(return_value=[])):
            result = await agent({
                "competitor": "TestCo",
                "changes_detected": [],
            })
            assert "research_results" in result
            assert isinstance(result["research_results"], list)


@pytest.mark.asyncio
async def test_gather_intelligence_queries():
    """_gather_intelligence 执行 5 个维度 + 1 个新闻搜索。"""
    agent = ResearchAgent()
    with patch("src.agents.research_agent.web_search", new=AsyncMock(return_value=[])):
        with patch("src.agents.research_agent.news_search", new=AsyncMock(return_value=[])):
            result = await agent._gather_intelligence("OpenAI")
            # 5 个 web_search 维度 + 1 个 news_search = 6 个 key
            assert len(result) == 6
            assert "news" in result
