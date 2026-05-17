"""LangGraph workflow – the core event-driven pipeline that orchestrates all
five agents.

Architecture
------------
                ┌──────────────┐
                │   START      │
                └──────┬───────┘
                       ▼
              ┌────────────────┐
              │ Monitor Agent  │  (detects changes)
              └────────┬───────┘
                       │
              ┌────────┴───────┐
              ▼                ▼
      ┌──────────────┐  ┌───────────────┐
      │ Alert Agent  │  │ Research Agent │  (parallel fan-out)
      └──────────────┘  └───────┬───────┘
                                ▼
                      ┌─────────────────┐
                      │ Compare Agent   │
                      └────────┬────────┘
                               ▼
                     ┌──────────────────┐
                     │ Battlecard Agent │
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │ Quality Check    │  (Reflexion gate)
                     └────────┬─────────┘
                       ┌──────┴──────┐
                 score < 7      score >= 7
                       │             │
                       ▼             ▼
               ┌──────────┐    ┌─────┐
               │ Research  │    │ END │
               └──────────┘    └─────┘
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from ..agents.alert_agent import AlertAgent
from ..agents.battlecard_agent import BattlecardAgent
from ..agents.compare_agent import CompareAgent
from ..agents.monitor_agent import MonitorAgent
from ..agents.research_agent import ResearchAgent
from ..config import get_effective_llm_config, get_effective_quality_threshold, get_effective_max_reflexion_retries

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

def _merge_lists(left: list, right: list) -> list:
    """Reducer that appends new items instead of replacing."""
    return left + right


class PipelineState(TypedDict, total=False):
    competitor: str
    monitor_urls: list[str]
    previous_hashes: dict[str, str]

    changes_detected: Annotated[list, _merge_lists]
    research_results: Annotated[list, _merge_lists]
    comparison_matrix: dict
    battlecard: dict
    alerts_sent: Annotated[list, _merge_lists]

    quality_score: float
    reflexion_count: int
    error: str | None


# ---------------------------------------------------------------------------
# Agent singletons
# ---------------------------------------------------------------------------

monitor_agent = MonitorAgent()
research_agent = ResearchAgent()
compare_agent = CompareAgent()
battlecard_agent = BattlecardAgent()
alert_agent = AlertAgent()


# ---------------------------------------------------------------------------
# Quality-check / Reflexion node
# ---------------------------------------------------------------------------

async def quality_check(state: dict[str, Any]) -> dict[str, Any]:
    """Score the generated battlecard and decide whether to loop back."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_community.chat_models import ChatTongyi

    llm_cfg = get_effective_llm_config()
    llm = ChatTongyi(
        model=llm_cfg.model,
        api_key=llm_cfg.api_key,
        temperature=0.0,  # quality_check 始终使用 temperature=0 确保评分稳定
    )

    battlecard = state.get("battlecard", {})
    comparison = state.get("comparison_matrix", {})

    prompt = (
        "You are a quality evaluator. Rate the following competitive intelligence "
        "battlecard on a scale of 1-10 based on:\n"
        "  - Completeness (are strengths/weaknesses/objections covered?)\n"
        "  - Accuracy (does it align with the comparison data?)\n"
        "  - Actionability (can a sales rep use this immediately?)\n\n"
        # 修复：先model_dump()转成可序列化的字典
        f"Battlecard:\n{json.dumps(battlecard.model_dump() if hasattr(battlecard, 'model_dump') else battlecard, ensure_ascii=False, indent=2)}\n\n"
        f"Comparison Matrix:\n{json.dumps(comparison.model_dump() if hasattr(comparison, 'model_dump') else comparison, ensure_ascii=False, indent=2)}\n\n"
        "Return ONLY a JSON object: {\"score\": <float>, \"feedback\": <string>}"
    )

    response = await llm.ainvoke([
        SystemMessage(content="You are a strict quality evaluator."),
        HumanMessage(content=prompt),
    ])

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        result = json.loads(text)
        score = float(result.get("score", 5.0))
    except Exception:
        score = 5.0

    reflexion_count = state.get("reflexion_count", 0) + 1

    return {
        "quality_score": score,
        "reflexion_count": reflexion_count,
    }


def _should_retry(state: dict[str, Any]) -> str:
    """Conditional edge: retry research if quality is below threshold."""
    score = state.get("quality_score", 0)
    count = state.get("reflexion_count", 0)
    max_retries = get_effective_max_reflexion_retries()
    threshold = get_effective_quality_threshold()

    if score < threshold and count < max_retries:
        logger.info(
            "Quality %.1f < %.1f (attempt %d/%d) → retrying research",
            score, threshold, count, max_retries,
        )
        return "research"
    return END


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_pipeline() -> StateGraph:
    """Construct and compile the CI pipeline graph."""
    graph = StateGraph(PipelineState)

    graph.add_node("monitor", monitor_agent)
    graph.add_node("alert", alert_agent)
    graph.add_node("research", research_agent)
    graph.add_node("compare", compare_agent)
    graph.add_node("battlecard", battlecard_agent)
    graph.add_node("quality_check", quality_check)

    graph.set_entry_point("monitor")

    graph.add_edge("monitor", "alert")
    graph.add_edge("monitor", "research")

    graph.add_edge("alert", END)
    graph.add_edge("research", "compare")
    graph.add_edge("compare", "battlecard")
    graph.add_edge("battlecard", "quality_check")

    graph.add_conditional_edges("quality_check", _should_retry)

    return graph.compile()


pipeline = build_pipeline()
