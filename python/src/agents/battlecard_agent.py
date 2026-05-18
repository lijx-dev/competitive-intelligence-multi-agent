"""Battlecard Agent – auto-generates sales battlecards (us vs. competitor)."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatTongyi

from ..config import get_effective_llm_config
from ..models.schemas import Battlecard

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Sales Battlecard Generator Agent.
Given a comparison matrix and research insights, create a sales battlecard that
a sales rep can use in competitive deals.

Return a JSON object with keys:
  our_strengths: [str],
  our_weaknesses: [str],
  competitor_strengths: [str],
  competitor_weaknesses: [str],
  key_differentiators: [str],
  objection_handling: {objection: response, ...},
  elevator_pitch: str.

Keep language concise, persuasive, and actionable. Each list should have 3-5
items. The elevator_pitch should be 2-3 sentences.
"""


class BattlecardAgent:

    def _get_llm(self):
        """每次调用时从动态配置读取 LLM 参数，确保配置修改即时生效。"""
        cfg = get_effective_llm_config()
        return ChatTongyi(
            model=cfg.model,
            api_key=cfg.api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    async def generate(
        self,
        competitor: str,
        comparison: dict,
        research: list[dict],
    ) -> Battlecard:
        user_msg = (
            f"Competitor: {competitor}\n\n"
            # 修复：先model_dump()转成可序列化的字典
            f"Comparison Matrix:\n{json.dumps(comparison.model_dump() if hasattr(comparison, 'model_dump') else comparison, ensure_ascii=False, indent=2)}\n\n"
            f"Research Insights:\n{json.dumps([r.model_dump() if hasattr(r, 'model_dump') else r for r in research], ensure_ascii=False, indent=2)}\n\n"
            "Generate a battlecard as JSON."
        )

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])

        return self._parse_battlecard(response.content, competitor)

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        competitor = state["competitor"]
        comparison = state.get("comparison_matrix", {})
        research = state.get("research_results", [])

        card = await self.generate(competitor, comparison, research)
        return {
            "battlecard": card.model_dump(),
        }

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_battlecard(llm_output: str, competitor: str) -> Battlecard:
        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Could not parse battlecard JSON")
            return Battlecard(competitor=competitor, elevator_pitch=llm_output[:500])

        return Battlecard(
            competitor=competitor,
            our_strengths=data.get("our_strengths", []),
            our_weaknesses=data.get("our_weaknesses", []),
            competitor_strengths=data.get("competitor_strengths", []),
            competitor_weaknesses=data.get("competitor_weaknesses", []),
            key_differentiators=data.get("key_differentiators", []),
            objection_handling=data.get("objection_handling", {}),
            elevator_pitch=data.get("elevator_pitch", ""),
        )
