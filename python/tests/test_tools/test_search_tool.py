"""
test_search_tool.py —— 搜索工具测试。

覆盖：无 API Key 时的 Demo 降级、web_search 正常路径、news_search 正常路径。
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.tools.search_tool import web_search, news_search, _demo_results, _demo_news


# ==================== Demo 降级测试（无 API Key） ====================

def test_demo_results_returns_list():
    """_demo_results 在无 API Key 时返回包含 demo 数据的列表。"""
    result = _demo_results("OpenAI")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "title" in result[0]
    assert "link" in result[0]
    assert "Demo" in result[0]["title"]


def test_demo_news_returns_list():
    """_demo_news 在无 API Key 时返回包含 demo 新闻的列表。"""
    result = _demo_news("OpenAI")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "title" in result[0]
    assert "source" in result[0]
    assert "Demo" in result[0]["source"]


# ==================== web_search 异步测试 ====================

@pytest.mark.asyncio
async def test_web_search_without_api_key():
    """无 API Key 时 web_search 回调 _demo_results。"""
    result = await web_search("test query", api_key="")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "Demo" in result[0]["title"]


@pytest.mark.asyncio
async def test_web_search_with_api_key(monkeypatch):
    """有 API Key 时 web_search 调用 SerpAPI 并解析 organic_results。"""
    mock_response = {
        "organic_results": [
            {"title": "Real Result", "link": "https://real.com", "snippet": "A real snippet."},
        ]
    }
    # Mock httpx.AsyncClient.get 的返回值（httpx Response.json() 是同步方法）
    async def mock_get(*args, **kwargs):
        class MockResp:
            def json(self):
                return mock_response
            def raise_for_status(self):
                pass
        return MockResp()

    with patch("httpx.AsyncClient.get", new=mock_get):
        result = await web_search("test", api_key="fake-key")
        assert len(result) == 1
        assert result[0]["title"] == "Real Result"


# ==================== news_search 异步测试 ====================

@pytest.mark.asyncio
async def test_news_search_without_api_key():
    """无 API Key 时 news_search 回调 _demo_news。"""
    result = await news_search("OpenAI", api_key="")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "Demo" in result[0]["source"]


@pytest.mark.asyncio
async def test_news_search_with_api_key(monkeypatch):
    """有 API Key 时 news_search 调用 SerpAPI 的 Google News 引擎。"""
    mock_response = {
        "news_results": [
            {
                "title": "Big Launch",
                "link": "https://news.com/1",
                "date": "2026-05-01",
                "source": {"name": "TechCrunch"},
            },
        ]
    }

    async def mock_get(*args, **kwargs):
        class MockResp:
            def json(self):
                return mock_response
            def raise_for_status(self):
                pass
        return MockResp()

    with patch("httpx.AsyncClient.get", new=mock_get):
        result = await news_search("test", api_key="fake-key")
        assert len(result) == 1
        assert result[0]["source"] == "TechCrunch"
