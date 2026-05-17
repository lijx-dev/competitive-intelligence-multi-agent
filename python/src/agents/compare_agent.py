"""Compare Agent – multi-dimensional competitor comparison matrix."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatTongyi

from ..config import config
from ..models.schemas import ComparisonMatrix, DimensionScore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Competitive Intelligence Comparison Agent.
Given research insights about a competitor, produce a structured comparison
matrix that scores BOTH our product and the competitor across these dimensions
(each scored 0-10):
  1. Product Features
  2. Pricing & Value
  3. User Experience / UX
  4. Market Share & Momentum
  5. Customer Sentiment / Reviews
  6. Technology & Innovation
  7. Ecosystem & Integrations
  8. Support & Documentation

Return a JSON object with keys:
  dimensions: [{dimension, our_score, competitor_score, notes}],
  overall_assessment: <string>.
"""

DIMENSIONS = [
    "Product Features",
    "Pricing & Value",
    "User Experience",
    "Market Share & Momentum",
    "Customer Sentiment",
    "Technology & Innovation",
    "Ecosystem & Integrations",
    "Support & Documentation",
]


class CompareAgent:

    def _get_llm(self):
        """每次调用时从动态配置读取 LLM 参数，确保配置修改即时生效。"""
        cfg = get_effective_llm_config()
        return ChatTongyi(
            model=cfg.model,
            api_key=cfg.api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    async def compare(
        self,
        competitor: str,
        research_results: list[dict],
    ) -> ComparisonMatrix:
        research_text = json.dumps(research_results, ensure_ascii=False, indent=2)

        user_msg = (
            f"Competitor: {competitor}\n\n"
            # 修复：先model_dump()转成可序列化的字典
            f"Research Insights:\n{json.dumps([r.model_dump() if hasattr(r, 'model_dump') else r for r in research_results], ensure_ascii=False, indent=2)}\n\n"
            "Generate a comparison matrix as JSON."
        )

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])

        return self._parse_matrix(response.content, competitor)

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        competitor = state["competitor"]
        research = state.get("research_results", [])

        matrix = await self.compare(competitor, research)
        return {
            "comparison_matrix": matrix.model_dump(),
        }

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_matrix(llm_output: str, competitor: str) -> ComparisonMatrix:
        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Could not parse comparison matrix")
            return ComparisonMatrix(
                competitor=competitor,
                dimensions=[
                    DimensionScore(dimension=d, our_score=7.0, competitor_score=7.0)
                    for d in DIMENSIONS
                ],
                overall_assessment="Unable to parse detailed comparison.",
            )

        dims = []
        for d in data.get("dimensions", []):
            dims.append(
                DimensionScore(
                    dimension=d.get("dimension", "Unknown"),
                    our_score=float(d.get("our_score", 5.0)),
                    competitor_score=float(d.get("competitor_score", 5.0)),
                    notes=d.get("notes", ""),
                )
            )

        return ComparisonMatrix(
            competitor=competitor,
            dimensions=dims,
            overall_assessment=data.get("overall_assessment", ""),
        )
