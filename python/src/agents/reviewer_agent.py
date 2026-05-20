"""
Reviewer Agent — 4维度深度质量审查（替代原简单 Quality Check）。

产出可执行的定向修改指令，精确到字段路径，供 TargetedFix Agent 使用。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..services.llm import LLMFactory
from ..models.schemas import ReviewFeedback, ReviewIssue

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Senior Quality Reviewer for competitive intelligence reports.
Your job is to deeply review the entire analysis output and produce actionable fix instructions.

Review Dimensions:
  1. Accuracy (0-10): Are all claims factually supported by Monitor/Research data?
  2. Completeness (0-10): Does the report cover all required analysis dimensions?
  3. Citation (0-10): Is every claim attributed to a source?
  4. Actionability (0-10): Can a sales rep or product manager act on this immediately?

For each issue found, you MUST specify:
  - severity: high / medium / low
  - target: exact field path (e.g., "battlecard.our_weaknesses", "comparison_matrix.dimensions[2].notes")
  - description: what is wrong and why
  - fix_instruction: specific steps to fix it

Return ONLY a JSON object:
{
  "overall_score": <float 0-10>,
  "accuracy_score": <float 0-10>,
  "completeness_score": <float 0-10>,
  "citation_score": <float 0-10>,
  "actionability_score": <float 0-10>,
  "approved": <bool>,
  "issues": [
    {"severity": "high/medium/low", "target": "field.path", "description": "...", "fix_instruction": "..."}
  ],
  "revision_instructions": "<string summarizing all fixes needed>"
}

Approval: approved = True only if overall_score >= 7.0 AND no high-severity issues.
"""


class ReviewerAgent:
    """4维度评分 + 定向修复指令"""

    def _get_llm(self):
        """统一 LLM 工厂 — Reviewer 使用 temperature=0 确保评分稳定"""
        llm = LLMFactory.get_llm("reviewer")
        llm.temperature = 0.0
        return llm

    async def review(self, state: dict[str, Any]) -> ReviewFeedback:
        battlecard = state.get("battlecard", {})
        comparison = state.get("comparison_matrix", {})
        changes = state.get("changes_detected", [])
        research = state.get("research_results", [])
        fact_check = state.get("fact_check_result", {})
        our_info = state.get("our_product_info", {})

        prompt = (
            "## Competitive Intelligence Report — Full Review\n\n"
            f"### Battlecard\n{json.dumps(battlecard.model_dump() if hasattr(battlecard, 'model_dump') else battlecard, ensure_ascii=False, indent=2)}\n\n"
            f"### Comparison Matrix\n{json.dumps(comparison.model_dump() if hasattr(comparison, 'model_dump') else comparison, ensure_ascii=False, indent=2)}\n\n"
            f"### Detected Changes ({len(changes)} items)\n{json.dumps(changes[:5], ensure_ascii=False)}\n\n"
            f"### Research Insights ({len(research)} items)\n{json.dumps(research[:5], ensure_ascii=False)}\n\n"
            f"### FactCheck Summary\n{json.dumps(fact_check.get('summary', ''), ensure_ascii=False)}\n\n"
            f"### Our Product Info\n{json.dumps(our_info, ensure_ascii=False)[:500]}\n\n"
            "Perform a 4-dimension review and return JSON with issues (target=exact field path) and fix_instructions."
        )

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        return self._parse_feedback(response.content)

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        feedback = await self.review(state)
        reflexion_count = state.get("reflexion_count", 0) + 1
        return {
            "review_feedback": feedback.model_dump(),
            "quality_score": feedback.overall_score,
            "reflexion_count": reflexion_count,
        }

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_feedback(llm_output: str) -> ReviewFeedback:
        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Could not parse review feedback")
            return ReviewFeedback(
                overall_score=7.0, approved=True,
                issues=[], revision_instructions="Parse failed, defaulting to approve.",
            )

        issues = []
        for iss in data.get("issues", []):
            issues.append(ReviewIssue(
                severity=iss.get("severity", "medium"),
                target=iss.get("target", "unknown"),
                description=iss.get("description", ""),
                fix_instruction=iss.get("fix_instruction", ""),
            ))

        return ReviewFeedback(
            overall_score=float(data.get("overall_score", 5.0)),
            accuracy_score=float(data.get("accuracy_score", 5.0)),
            completeness_score=float(data.get("completeness_score", 5.0)),
            citation_score=float(data.get("citation_score", 5.0)),
            actionability_score=float(data.get("actionability_score", 5.0)),
            approved=bool(data.get("approved", False)),
            issues=issues,
            revision_instructions=data.get("revision_instructions", ""),
        )
