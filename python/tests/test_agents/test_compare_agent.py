"""
test_compare_agent.py —— Compare Agent 测试。

覆盖：_parse_matrix 正确解析、无效 JSON 兜底返回默认矩阵、
      8 个固定维度的完整性、__call__ 节点接口。
"""

import json
import pytest
from src.agents.compare_agent import CompareAgent, DIMENSIONS
from src.models.schemas import ComparisonMatrix, DimensionScore


def test_dimensions_list_complete():
    """DIMENSIONS 常量包含 8 个标准对比维度。"""
    assert len(DIMENSIONS) == 8
    assert "Product Features" in DIMENSIONS
    assert "Pricing & Value" in DIMENSIONS
    assert "User Experience" in DIMENSIONS
    assert "Technology & Innovation" in DIMENSIONS


def test_parse_matrix_valid_json():
    """_parse_matrix 正确解析 LLM 返回的对比矩阵 JSON。"""
    llm_output = json.dumps({
        "dimensions": [
            {"dimension": "Product Features", "our_score": 9.0, "competitor_score": 7.0, "notes": "Better AI"},
        ],
        "overall_assessment": "We lead in product.",
    })
    matrix = CompareAgent._parse_matrix(llm_output, "TestCo")
    assert isinstance(matrix, ComparisonMatrix)
    assert matrix.competitor == "TestCo"
    assert len(matrix.dimensions) == 1
    assert matrix.dimensions[0].our_score == 9.0
    assert matrix.overall_assessment == "We lead in product."


def test_parse_matrix_invalid_json():
    """LLM 返回非法 JSON 时 _parse_matrix 返回 8 维度默认 7.0 分矩阵。"""
    matrix = CompareAgent._parse_matrix("not json", "TestCo")
    assert isinstance(matrix, ComparisonMatrix)
    assert len(matrix.dimensions) == 8
    for d in matrix.dimensions:
        assert d.our_score == 7.0
        assert d.competitor_score == 7.0
    assert "Unable to parse" in matrix.overall_assessment


@pytest.mark.asyncio
async def test_call_node(mock_chat_tongyi, sample_insights):
    """CompareAgent.__call__ 接收洞察列表，返回 comparison_matrix。"""
    mock_chat_tongyi.ainvoke.return_value.content = json.dumps({
        "dimensions": [
            {"dimension": d, "our_score": 8.0, "competitor_score": 6.0, "notes": "test"}
            for d in DIMENSIONS
        ],
        "overall_assessment": "We are ahead.",
    })
    agent = CompareAgent()
    result = await agent({
        "competitor": "TestCo",
        "research_results": sample_insights,
    })
    assert "comparison_matrix" in result
    matrix = result["comparison_matrix"]
    assert matrix["competitor"] == "TestCo"
    assert len(matrix["dimensions"]) == 8
