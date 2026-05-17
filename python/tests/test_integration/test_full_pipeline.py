"""
test_full_pipeline.py —— 端到端集成测试。

覆盖：API → Agent → 数据库存储的完整链路（使用 Mock LLM + TestClient + 临时数据库）。
      三个核心场景：同步分析存库、流式分析、竞品创建后分析关联。
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def integration_client(monkeypatch, tmp_path):
    """
    集成测试专用 TestClient，同时隔离数据库路径。
    在测试模块内导入 server 以应用 monkeypatch。
    """
    import src.db.sqlite as db_module
    db_path = str(tmp_path / "integration_test.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()

    # Mock 所有 Agent 的 ChatTongyi
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = "[]"

    import src.agents.monitor_agent as ma
    import src.agents.research_agent as ra
    import src.agents.compare_agent as ca
    import src.agents.battlecard_agent as ba

    monkeypatch.setattr(ma, "ChatTongyi", lambda *a, **kw: mock_llm)
    monkeypatch.setattr(ra, "ChatTongyi", lambda *a, **kw: mock_llm)
    monkeypatch.setattr(ca, "ChatTongyi", lambda *a, **kw: mock_llm)
    monkeypatch.setattr(ba, "ChatTongyi", lambda *a, **kw: mock_llm)

    # workflow.py 的 quality_check 函数内延迟导入 ChatTongyi，
    # 需要 patch langchain_community 中的引用
    monkeypatch.setattr(
        "langchain_community.chat_models.ChatTongyi",
        lambda *a, **kw: mock_llm,
    )

    from src.api.server import app
    return TestClient(app), mock_llm, db_path


# ==================== 场景1：同步分析 → 数据库存储 ====================

def test_full_sync_analysis_flow(integration_client):
    """POST /analyze → 分析结果自动存入数据库 → 可通过历史接口查询。"""
    client, mock_llm, db_path = integration_client
    mock_llm.ainvoke.return_value.content = "[]"

    with patch("src.agents.monitor_agent.fetch_page", new=AsyncMock(return_value="<html></html>")):
        with patch("src.agents.research_agent.web_search", new=AsyncMock(return_value=[])):
            with patch("src.agents.research_agent.news_search", new=AsyncMock(return_value=[])):
                with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": False})):
                    # 1. 发起同步分析
                    resp = client.post("/analyze", json={"competitor": "IntegrationCo", "urls": ["https://test.com"]})
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["competitor"] == "IntegrationCo"

                    # 2. 验证分析结果已存入数据库
                    resp2 = client.get("/analysis/records")
                    assert resp2.status_code == 200
                    records = resp2.json()
                    assert len(records) >= 1
                    assert records[0]["competitor_name"] == "IntegrationCo"


# ==================== 场景2：流式分析 → SSE 事件流 ====================

def test_full_stream_analysis_flow(integration_client):
    """POST /analyze/stream → SSE 事件流包含完整节点事件。"""
    client, mock_llm, db_path = integration_client
    mock_llm.ainvoke.return_value.content = "[]"

    with patch("src.agents.monitor_agent.fetch_page", new=AsyncMock(return_value="<html></html>")):
        with patch("src.agents.research_agent.web_search", new=AsyncMock(return_value=[])):
            with patch("src.agents.research_agent.news_search", new=AsyncMock(return_value=[])):
                with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": False})):
                    resp = client.post(
                        "/analyze/stream",
                        json={"competitor": "StreamCo", "urls": []},
                        headers={"Accept": "text/event-stream"},
                    )
                    assert resp.status_code == 200
                    body = resp.text
                    # SSE 事件流应包含关键节点名
                    assert "monitor" in body
                    assert "quality_check" in body


# ==================== 场景3：竞品创建→分析→关联 ====================

def test_competitor_create_then_analyze_association(integration_client):
    """创建竞品 → 分析该竞品 → 历史记录 competitor_id 关联正确。"""
    client, mock_llm, db_path = integration_client
    mock_llm.ainvoke.return_value.content = "[]"

    with patch("src.agents.monitor_agent.fetch_page", new=AsyncMock(return_value="<html></html>")):
        with patch("src.agents.research_agent.web_search", new=AsyncMock(return_value=[])):
            with patch("src.agents.research_agent.news_search", new=AsyncMock(return_value=[])):
                with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": False})):
                    # 1. 创建竞品
                    resp = client.post("/competitors", json={"name": "LinkedComp", "urls": ["https://linked.com"]})
                    assert resp.status_code == 200
                    comp_id = resp.json()["id"]

                    # 2. 分析该竞品
                    resp2 = client.post("/analyze", json={"competitor": "LinkedComp", "urls": ["https://linked.com"]})
                    assert resp2.status_code == 200

                    # 3. 历史记录中 competitor_id 正确关联
                    resp3 = client.get("/analysis/records", params={"competitor_id": comp_id})
                    assert resp3.status_code == 200
                    records = resp3.json()
                    assert len(records) >= 1
                    assert records[0]["competitor_id"] == comp_id
                    assert records[0]["competitor_name"] == "LinkedComp"
