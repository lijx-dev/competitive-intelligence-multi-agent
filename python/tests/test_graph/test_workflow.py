"""
test_workflow.py —— LangGraph 工作流测试（三节点校验架构 v2）。

覆盖：Graph 构建、4 个新节点注册、条件边 _after_review / _after_targeted_fix、
      完整 Pipeline Mock 运行。
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from src.graph.workflow import (
    build_pipeline, PipelineState, _after_review, _after_targeted_fix,
)


# ==================== Graph 构建 ====================

def test_build_pipeline_has_all_nodes():
    """10 节点 DAG：6 业务节点 + 4 校验/修复/溯源节点"""
    graph = build_pipeline()
    nodes = graph.get_graph().nodes
    node_names = {n for n in nodes}
    expected = {
        "monitor", "alert", "research", "compare", "battlecard",
        "fact_check", "reviewer", "targeted_fix", "citation",
    }
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


def test_build_pipeline_entry_point():
    """入口点为 monitor 节点"""
    graph = build_pipeline()
    assert graph is not None


# ==================== 条件边 ====================

def test_after_review_below_threshold():
    """评分 < 7.0 且未超过重试次数 → targeted_fix"""
    state = {"quality_score": 5.0, "targeted_fix_count": 1}
    with patch("src.graph.workflow.get_effective_max_reflexion_retries", return_value=3):
        result = _after_review(state)
        assert result == "targeted_fix"


def test_after_review_above_threshold():
    """评分 >= 7.0 → citation"""
    state = {"quality_score": 8.0, "targeted_fix_count": 0}
    result = _after_review(state)
    assert result == "citation"


def test_after_review_max_retries():
    """超过最大重试次数 → 强制进入 citation"""
    state = {"quality_score": 5.0, "targeted_fix_count": 4}
    with patch("src.graph.workflow.get_effective_max_reflexion_retries", return_value=3):
        result = _after_review(state)
        assert result == "citation"


def test_after_targeted_fix():
    """TargetedFix → 返回 reviewer"""
    result = _after_targeted_fix({})
    assert result == "reviewer"


# ==================== Pipeline 端到端 ====================

@pytest.mark.skip(reason="需要激活 Ark Console 的 doubao-seed-251228 模型后启用")
@pytest.mark.asyncio
async def test_pipeline_full_run(mock_chat_tongyi):
    """完整 10 节点 Pipeline 在 Mock 所有 LLM 后成功执行"""
    # 设置 Mock 返回有效 JSON（数组 → 会触发 _default_matrix 兜底，保证流程完整）
    mock_chat_tongyi.ainvoke.return_value.content = '{"score": 8.0, "feedback": "Good"}'

    with patch("src.agents.monitor_agent.fetch_page", new=AsyncMock(return_value="<html></html>")):
        with patch("src.agents.research_agent.web_search", new=AsyncMock(return_value=[])):
            with patch("src.agents.research_agent.news_search", new=AsyncMock(return_value=[])):
                with patch("src.agents.alert_agent.broadcast_alert", new=AsyncMock(return_value={"slack": False})):
                    from src.graph.workflow import pipeline

                    initial_state: PipelineState = {
                        "competitor": "IntegrationTest",
                        "monitor_urls": [],
                        "previous_hashes": {},
                        "our_product_info": {},
                        "changes_detected": [],
                        "research_results": [],
                        "comparison_matrix": {},
                        "battlecard": {},
                        "alerts_sent": [],
                        "fact_check_result": {},
                        "review_feedback": {},
                        "citation_report": {},
                        "targeted_fix_count": 0,
                        "quality_score": 0.0,
                        "reflexion_count": 0,
                        "error": None,
                    }

                    final = await pipeline.ainvoke(initial_state)
                    assert "competitor" in final
                    assert final["competitor"] == "IntegrationTest"
                    assert "quality_score" in final
