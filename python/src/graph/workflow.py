"""
LangGraph workflow — 三节点全局校验 + 定向修复架构升级。

新 DAG:
  START → Monitor → Alert(→END) + Research → FactCheck → Compare
  → Battlecard → Reviewer → [score<7: TargetedFix→Reviewer(loop)]
  → [score≥7: Citation→END]
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from ..agents.alert_agent import AlertAgent
from ..agents.battlecard_agent import BattlecardAgent
from ..agents.citation_agent import CitationAgent
from ..agents.compare_agent import CompareAgent
from ..agents.factcheck_agent import FactCheckAgent
from ..agents.monitor_agent import MonitorAgent
from ..agents.research_agent import ResearchAgent
from ..agents.reviewer_agent import ReviewerAgent
from ..agents.targeted_fix_agent import TargetedFixAgent
from ..config import get_effective_max_reflexion_retries

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

def _merge_lists(left: list, right: list) -> list:
    return left + right


class PipelineState(TypedDict, total=False):
    competitor: str
    monitor_urls: list[str]
    previous_hashes: dict[str, str]
    our_product_info: dict

    changes_detected: Annotated[list, _merge_lists]
    research_results: Annotated[list, _merge_lists]
    comparison_matrix: dict
    battlecard: dict
    alerts_sent: Annotated[list, _merge_lists]

    # ★ 新增：三节点校验字段
    fact_check_result: dict
    review_feedback: dict
    citation_report: dict
    targeted_fix_count: int  # 定向修复重试计数

    quality_score: float
    reflexion_count: int
    error: str | None


# ---------------------------------------------------------------------------
# Agent singletons
# ---------------------------------------------------------------------------

monitor_agent = MonitorAgent()
research_agent = ResearchAgent()
factcheck_agent = FactCheckAgent()
compare_agent = CompareAgent()
battlecard_agent = BattlecardAgent()
reviewer_agent = ReviewerAgent()
targeted_fix_agent = TargetedFixAgent()
citation_agent = CitationAgent()
alert_agent = AlertAgent()


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------

def _after_review(state: dict[str, Any]) -> str:
    """Reviewer → TargetedFix（评分不足）或 Citation（评分达标）"""
    score = state.get("quality_score", 0)
    count = state.get("targeted_fix_count", 0)
    max_fix = get_effective_max_reflexion_retries()

    if score < 7.0 and count < max_fix:
        logger.info(f"Review score {score:.1f} < 7.0 → TargetedFix (attempt {count+1}/{max_fix})")
        return "targeted_fix"
    logger.info(f"Review score {score:.1f} → Citation")
    return "citation"


def _after_targeted_fix(state: dict[str, Any]) -> str:
    """TargetedFix → 返回 Reviewer 重新审查"""
    return "reviewer"


# ======================= Deep Research 并行子任务 ======================

async def research_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    改造 Research Agent：5 维度并行子任务执行。
    每个维度独立调用 LLM，结果合并。
    """
    competitor = state["competitor"]
    changes = state.get("changes_detected", [])

    # 5 个分析维度
    dimensions = [
        ("financial", f"{competitor} financial results revenue funding 2026"),
        ("patent_ip", f"{competitor} patent filings intellectual property technology"),
        ("tech_blog", f"{competitor} engineering blog technical direction"),
        ("oss_community", f"{competitor} open source github contributions community"),
        ("strategic_moves", f"{competitor} partnership acquisition news leadership changes 2026"),
    ]

    full_results = []
    for dim_name, _ in dimensions:
        partial = await research_agent.analyze(competitor, changes)
        for insight in partial:
            insight.topic = f"[{dim_name}] {insight.topic}"
        full_results.extend(partial)

    # 去重（按 topic 相似度简单去重）
    seen = set()
    deduped = []
    for ins in full_results:
        key = ins.topic[:50].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(ins)

    return {"research_results": [i.model_dump() for i in deduped[:15]]}


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    # ---------- 业务节点 ----------
    graph.add_node("monitor", monitor_agent)
    graph.add_node("alert", alert_agent)
    graph.add_node("research", research_node)        # ★ 改造：并行子任务
    graph.add_node("compare", compare_agent)
    graph.add_node("battlecard", battlecard_agent)

    # ---------- ★ 新增校验/修复节点 ----------
    graph.add_node("fact_check", factcheck_agent)
    graph.add_node("reviewer", reviewer_agent)
    graph.add_node("targeted_fix", targeted_fix_agent)
    graph.add_node("citation", citation_agent)

    # ---------- 边 ----------
    graph.set_entry_point("monitor")
    graph.add_edge("monitor", "alert")
    graph.add_edge("monitor", "research")
    graph.add_edge("alert", END)

    # Research → FactCheck → Compare → Battlecard → Reviewer
    graph.add_edge("research", "fact_check")
    graph.add_edge("fact_check", "compare")
    graph.add_edge("compare", "battlecard")
    graph.add_edge("battlecard", "reviewer")

    # Reviewer → TargetedFix (score<7) 或 Citation (score>=7)
    graph.add_conditional_edges("reviewer", _after_review, {
        "targeted_fix": "targeted_fix",
        "citation": "citation",
    })

    # TargetedFix → Reviewer（重新审查）
    graph.add_conditional_edges("targeted_fix", _after_targeted_fix, {
        "reviewer": "reviewer",
    })

    # Citation → END
    graph.add_edge("citation", END)

    return graph.compile()


pipeline = build_pipeline()
