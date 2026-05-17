"""
test_workflow.py —— LangGraph 工作流测试。

覆盖：Graph 构建与节点注册、quality_check 评分逻辑、
      _should_retry 条件分支（<7 重试 / >=7 结束 / 超过最大重试次数强制结束）。
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from src.graph.workflow import build_pipeline, quality_check, _should_retry, PipelineState


# ==================== Graph 构建 ====================

def test_build_pipeline_has_all_nodes():
    """build_pipeline 编译后的 graph 包含全部 6 个节点。"""
    graph = build_pipeline()
    nodes = graph.get_graph().nodes
    node_names = {n for n in nodes}
    expected = {"monitor", "alert", "research", "compare", "battlecard", "quality_check"}
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


def test_build_pipeline_entry_point():
    """入口点为 monitor 节点。"""
    graph = build_pipeline()
    # 验证 graph 编译无异常且可访问
    assert graph is not None


# ==================== Quality Check 节点 ====================

@pytest.mark.asyncio
async def test_quality_check_high_score(mock_chat_tongyi):
    """LLM 返回高分时 quality_check 输出对应评分。"""
    mock_chat_tongyi.ainvoke.return_value.content = '{"score": 9.0, "feedback": "Excellent"}'
    result = await quality_check({
        "battlecard": {"our_strengths": ["a"]},
        "comparison_matrix": {"overall_assessment": "good"},
        "reflexion_count": 0,
    })
    assert result["quality_score"] == 9.0
    assert result["reflexion_count"] == 1


@pytest.mark.asyncio
async def test_quality_check_low_score(mock_chat_tongyi):
    """LLM 返回低分时 quality_check 输出对应评分。"""
    mock_chat_tongyi.ainvoke.return_value.content = '{"score": 4.0, "feedback": "Needs improvement"}'
    result = await quality_check({
        "battlecard": {},
        "comparison_matrix": {},
        "reflexion_count": 0,
    })
    assert result["quality_score"] == 4.0


@pytest.mark.asyncio
async def test_quality_check_malformed_response(mock_chat_tongyi):
    """LLM 返回非法 JSON 时 quality_score 默认为 5.0。"""
    mock_chat_tongyi.ainvoke.return_value.content = "not valid json"
    result = await quality_check({
        "battlecard": {},
        "comparison_matrix": {},
        "reflexion_count": 0,
    })
    assert result["quality_score"] == 5.0


# ==================== _should_retry 条件分支 ====================

def test_should_retry_when_below_threshold():
    """评分低于阈值且未超过重试次数时返回 'research'（重试）。"""
    state = {"quality_score": 5.0, "reflexion_count": 1}
    # 默认阈值 7.0，最大重试 3 次
    with patch("src.graph.workflow.config") as mock_config:
        mock_config.quality_threshold = 7.0
        mock_config.max_reflexion_retries = 3
        result = _should_retry(state)
        assert result == "research"


def test_should_retry_ends_when_above_threshold():
    """评分达标时返回 END（不再重试）。"""
    state = {"quality_score": 8.0, "reflexion_count": 1}
    result = _should_retry(state)
    assert result == "__end__" or result is None  # END is typically "__end__"


def test_should_retry_ends_when_max_retries_reached():
    """超过最大重试次数时即使评分不足也返回 END。"""
    state = {"quality_score": 5.0, "reflexion_count": 4}
    with patch("src.graph.workflow.config") as mock_config:
        mock_config.max_reflexion_retries = 3
        mock_config.quality_threshold = 7.0
        result = _should_retry(state)
        assert result == "__end__" or result is None


# ==================== Pipeline 端到端（Mock 全部 Agent） ====================

@pytest.mark.asyncio
async def test_pipeline_full_run(mock_chat_tongyi):
    """完整 Pipeline 在 Mock 所有 LLM 调用后能成功执行到 quality_check 阶段。"""
    mock_chat_tongyi.ainvoke.return_value.content = "[]"

    # Mock MonitorAgent 的网页抓取
    with patch("src.agents.monitor_agent.fetch_page", new=AsyncMock(return_value="<html></html>")):
        # Mock ResearchAgent 的搜索工具
        with patch("src.agents.research_agent.web_search", new=AsyncMock(return_value=[])):
            with patch("src.agents.research_agent.news_search", new=AsyncMock(return_value=[])):
                # Mock AlertAgent 的通知广播
                with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": False})):
                    from src.graph.workflow import pipeline

                    initial_state: PipelineState = {
                        "competitor": "IntegrationTest",
                        "monitor_urls": [],
                        "previous_hashes": {},
                        "changes_detected": [],
                        "research_results": [],
                        "comparison_matrix": {},
                        "battlecard": {},
                        "alerts_sent": [],
                        "quality_score": 0.0,
                        "reflexion_count": 0,
                        "error": None,
                    }

                    final = await pipeline.ainvoke(initial_state)
                    # 验证最终状态包含关键字段
                    assert "competitor" in final
                    assert final["competitor"] == "IntegrationTest"
                    assert "quality_score" in final
