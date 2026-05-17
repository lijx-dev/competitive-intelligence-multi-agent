"""
test_battlecard_agent.py —— Battlecard Agent 测试。

覆盖：_parse_battlecard 正确解析和兜底、__call__ 节点接口、
      战术卡必填字段完整性。
"""

import json
import pytest
from src.agents.battlecard_agent import BattlecardAgent
from src.models.schemas import Battlecard


def test_parse_battlecard_valid_json():
    """_parse_battlecard 正确解析 LLM 返回的战术卡 JSON。"""
    llm_output = json.dumps({
        "our_strengths": ["Better AI", "Faster support"],
        "our_weaknesses": ["Small brand"],
        "competitor_strengths": ["Market leader"],
        "competitor_weaknesses": ["Slow innovation"],
        "key_differentiators": ["AI-first approach"],
        "objection_handling": {"They are bigger": "We are more agile."},
        "elevator_pitch": "Choose us for AI-driven value.",
    })
    card = BattlecardAgent._parse_battlecard(llm_output, "TestCo")
    assert isinstance(card, Battlecard)
    assert card.competitor == "TestCo"
    assert len(card.our_strengths) == 2
    assert card.elevator_pitch == "Choose us for AI-driven value."
    assert "They are bigger" in card.objection_handling


def test_parse_battlecard_invalid_json():
    """LLM 返回非法 JSON 时 _parse_battlecard 兜底：把原始文本放入 elevator_pitch。"""
    card = BattlecardAgent._parse_battlecard("garbled text from LLM", "TestCo")
    assert isinstance(card, Battlecard)
    assert card.competitor == "TestCo"
    assert card.elevator_pitch == "garbled text from LLM"
    assert card.our_strengths == []
    assert card.our_weaknesses == []


@pytest.mark.asyncio
async def test_call_node(mock_chat_tongyi, sample_matrix, sample_insights):
    """BattlecardAgent.__call__ 接收矩阵和洞察，返回 battlecard。"""
    mock_chat_tongyi.ainvoke.return_value.content = json.dumps({
        "our_strengths": ["AI features"],
        "our_weaknesses": ["Price"],
        "competitor_strengths": ["Brand"],
        "competitor_weaknesses": ["Support"],
        "key_differentiators": ["AI"],
        "objection_handling": {},
        "elevator_pitch": "We are better.",
    })
    agent = BattlecardAgent()
    result = await agent({
        "competitor": "TestCo",
        "comparison_matrix": sample_matrix,
        "research_results": sample_insights,
    })
    assert "battlecard" in result
    card = result["battlecard"]
    assert card["competitor"] == "TestCo"
    assert "our_strengths" in card
    assert "objection_handling" in card
