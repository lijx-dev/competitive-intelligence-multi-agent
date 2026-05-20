"""
pytest 共享 fixtures —— 所有测试模块共用。

提供：内存数据库、FastAPI TestClient、Mock LLM 响应、示例数据。
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock

# 确保项目根在 sys.path 中，使 test 文件可直接 import src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===================== 数据库 fixtures =====================

@pytest.fixture
def test_db_path(tmp_path):
    """为每个测试生成临时数据库路径，避免污染真实 ci_system.db。"""
    db_file = tmp_path / "test_ci.db"
    return str(db_file)


# ===================== FastAPI TestClient fixture =====================

@pytest.fixture
def api_client(monkeypatch, tmp_path):
    """创建 FastAPI TestClient（同步版），每个测试使用独立的临时数据库。"""
    import src.db.sqlite as db_module
    db_path = str(tmp_path / "test_api.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()

    from src.api.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


# ===================== Mock LLM fixtures =====================

@pytest.fixture
def mock_llm_response():
    """返回一个可配置的 Mock，模拟 ChatTongyi.ainvoke 的返回值。"""
    mock = MagicMock()
    mock.content = "{}"
    return mock


@pytest.fixture
def mock_chat_tongyi(monkeypatch):
    """
    替换 LLM 调用为 AsyncMock，防止测试意外调用真实 API。
    同时 Mock 旧的 ChatTongyi 路径（回退兼容）和新的 LLMFactory 路径。
    子测试可通过设置 mock_instance.ainvoke.return_value 自定义返回内容。
    """
    mock_instance = AsyncMock()
    mock_instance.ainvoke.return_value.content = "{}"

    # Mock LLMFactory.get_llm — 所有 Agent 现在通过此路径获取 LLM
    import src.services.llm.llm_factory as lf
    FakeFactory = type("FakeFactory", (), {
        "get_llm": staticmethod(lambda agent_name="default": mock_instance),
        "get_provider_info": staticmethod(lambda: {"provider": "mock"}),
    })
    monkeypatch.setattr(lf, "LLMFactory", FakeFactory)

    # 同时 patch services.llm 包导出（覆盖 from ..services.llm import LLMFactory 路径）
    import src.services.llm as sl
    monkeypatch.setattr(sl, "LLMFactory", FakeFactory)

    # 覆盖每个 Agent 模块内部的 LLMFactory 引用（from ..services.llm import LLMFactory）
    for agent_mod_name in [
        "src.agents.monitor_agent",
        "src.agents.research_agent",
        "src.agents.compare_agent",
        "src.agents.battlecard_agent",
        "src.agents.reviewer_agent",
        "src.agents.targeted_fix_agent",
    ]:
        monkeypatch.setattr(f"{agent_mod_name}.LLMFactory", FakeFactory)

    # Mock DoubaoLLM.generate — 防止 API 测试穿透到真实 Ark 调用
    import src.services.llm.doubao_client as dc
    monkeypatch.setattr(dc.DoubaoLLM, "generate",
        AsyncMock(return_value={"content": "{}", "usage": {"input_tokens": 0, "output_tokens": 0}, "model": "mock"}))
    monkeypatch.setattr(dc.DoubaoLLM, "generate_stream",
        AsyncMock(return_value=None))

    # 保留旧 ChatTongyi 路径的 Mock（回退兼容）
    monkeypatch.setattr(
        "langchain_community.chat_models.ChatTongyi",
        lambda *a, **kw: mock_instance,
    )

    # Reviewer 和 TargetedFix 会设置 llm.temperature，需要支持属性赋值
    mock_instance.temperature = 0.7

    return mock_instance


# ===================== 示例数据 fixtures =====================

@pytest.fixture
def sample_competitor():
    """标准竞品数据。"""
    return {
        "name": "Acme Corp",
        "urls": ["https://acme.com", "https://acme.com/pricing"],
    }


@pytest.fixture
def sample_changes():
    """Monitor Agent 产出的标准变更列表（dict 格式）。"""
    return [
        {
            "competitor": "Acme Corp",
            "change_type": "pricing",
            "title": "Pro plan price increase",
            "summary": "Pro plan went from $49 to $59/mo",
            "url": "https://acme.com/pricing",
            "severity": "high",
        },
    ]


@pytest.fixture
def sample_insights():
    """Research Agent 产出的标准洞察列表（dict 格式）。"""
    return [
        {
            "topic": "Financial Analysis",
            "summary": "Acme Corp raised $200M Series D.",
            "key_findings": ["Valuation at $2B", "Revenue growth 40% YoY"],
            "sources": ["https://news.example.com/acme-series-d"],
            "confidence": 0.9,
        },
    ]


@pytest.fixture
def sample_matrix():
    """Compare Agent 产出的标准对比矩阵（dict 格式）。"""
    return {
        "competitor": "Acme Corp",
        "dimensions": [
            {
                "dimension": "Product Features",
                "our_score": 8.0,
                "competitor_score": 7.0,
                "notes": "We have AI features; they don't.",
            },
        ],
        "overall_assessment": "We lead on product features.",
    }


@pytest.fixture
def sample_battlecard():
    """Battlecard Agent 产出的标准战术卡（dict 格式）。"""
    return {
        "competitor": "Acme Corp",
        "our_strengths": ["Better AI features", "Lower pricing"],
        "our_weaknesses": ["Smaller market share"],
        "competitor_strengths": ["Brand recognition"],
        "competitor_weaknesses": ["Slower innovation"],
        "key_differentiators": ["AI-first approach"],
        "objection_handling": {"They are bigger": "We are more agile."},
        "elevator_pitch": "We deliver more value at a lower cost.",
    }
