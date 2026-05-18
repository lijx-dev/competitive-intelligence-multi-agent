"""Compare Agent – multi-dimensional competitor comparison matrix.

评分基于我方产品真实信息 + 竞品研究洞察，禁止凭空估计。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatTongyi

from ..config import get_effective_llm_config
from ..models.schemas import ComparisonMatrix, DimensionScore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Competitive Intelligence Comparison Agent.
Given OUR PRODUCT's real information and RESEARCH INSIGHTS about a competitor,
produce a structured comparison matrix scoring BOTH products across these
dimensions (each scored 0-10):

  1. Product Features
  2. Pricing & Value
  3. User Experience / UX
  4. Market Share & Momentum
  5. Customer Sentiment / Reviews
  6. Technology & Innovation
  7. Ecosystem & Integrations
  8. Support & Documentation

CRITICAL RULES:
- our_score MUST be based on the provided OUR PRODUCT INFO, not guessed.
- competitor_score MUST be based on the provided RESEARCH INSIGHTS.
- If a dimension lacks data, score 5.0 (neutral) and note in "notes" that data is insufficient.
- notes field should be specific, comparing our real data vs competitor data.

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


def _format_product_info(info: dict) -> str:
    """将我方产品 dict 格式化为 LLM 可读的结构化文本。"""
    if not info:
        return "⚠️ OUR PRODUCT INFO NOT CONFIGURED. Use neutral scores (5.0) for all our_score and note this clearly."

    name = info.get("name", "My Product")
    features = info.get("core_features", [])
    pricing = info.get("pricing_model", "N/A")
    tech = info.get("tech_stack", [])
    market = info.get("target_market", "N/A")
    advantages = info.get("competitive_advantages", [])
    weaknesses = info.get("weaknesses", [])

    parts = [f"Product Name: {name}"]

    if features:
        parts.append("Core Features:\n  - " + "\n  - ".join(features))
    else:
        parts.append("Core Features: (not specified)")

    parts.append(f"Pricing Model: {pricing}")

    if tech:
        parts.append("Tech Stack:\n  - " + "\n  - ".join(tech))
    else:
        parts.append("Tech Stack: (not specified)")

    parts.append(f"Target Market: {market if market else '(not specified)'}")

    if advantages:
        parts.append("Competitive Advantages:\n  - " + "\n  - ".join(advantages))
    else:
        parts.append("Competitive Advantages: (not specified)")

    if weaknesses:
        parts.append("Known Weaknesses:\n  - " + "\n  - ".join(weaknesses))
    else:
        parts.append("Known Weaknesses: (not specified)")

    return "\n".join(parts)


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
        our_product_info: dict | None = None,
        fact_check_result: dict | None = None,
    ) -> ComparisonMatrix:
        our_info_text = _format_product_info(our_product_info or {})
        research_text = json.dumps(
            [r.model_dump() if hasattr(r, 'model_dump') else r for r in research_results],
            ensure_ascii=False, indent=2,
        )

        # 注入交叉验证结果
        fc_note = ""
        if fact_check_result:
            inconsistencies = fact_check_result.get("inconsistencies", [])
            confidence = fact_check_result.get("confidence_adjustments", {})
            if inconsistencies:
                fc_note = (
                    "\n\n=== FACT CHECK WARNING ===\n"
                    "The following claims were flagged as inconsistent or unverified. "
                    "Reduce confidence in competitor_score for dimensions relying on these claims:\n"
                    f"{json.dumps(inconsistencies[:5], ensure_ascii=False)}\n"
                )
            if confidence.get("verification_rate", 1.0) < 0.5:
                fc_note += (
                    f"\nOverall verification rate is only {confidence.get('verification_rate', 0)*100:.0f}%. "
                    "Please clearly note this in the overall_assessment."
                )

        user_msg = (
            f"=== OUR PRODUCT INFO (use this for our_score) ===\n"
            f"{our_info_text}\n\n"
            f"=== COMPETITOR: {competitor} ===\n\n"
            f"=== RESEARCH INSIGHTS (use this for competitor_score) ===\n"
            f"{research_text}"
            f"{fc_note}\n\n"
            "Generate a comparison matrix as JSON. Base our_score on the OUR PRODUCT INFO above. "
            "Base competitor_score on the RESEARCH INSIGHTS above."
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
        our_info = state.get("our_product_info", {})
        fact_check = state.get("fact_check_result", {})

        matrix = await self.compare(competitor, research, our_info, fact_check)
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
