"""Research Agent – deep analysis of financials, patents, tech blogs, and OSS."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatTongyi

from ..config import get_effective_llm_config
from ..models.schemas import ResearchInsight
from ..tools.search_tool import news_search, web_search

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Competitive Intelligence Research Agent.
Given detected changes about a competitor, perform a deep-dive analysis covering:
  1. Financial signals (revenue, funding, earnings)
  2. Patent and IP activity
  3. Technical blog posts and engineering direction
  4. Open-source contributions and community activity
  5. Strategic moves (partnerships, acquisitions, leadership changes)

For each area, return a JSON array of objects with keys:
  topic, summary, key_findings (list[str]), sources (list[str]), confidence (0-1).

Be factual and cite sources where possible.
"""


class ResearchAgent:

    def _get_llm(self):
        """每次调用时从动态配置读取 LLM 参数，确保配置修改即时生效。"""
        cfg = get_effective_llm_config()
        return ChatTongyi(
            model=cfg.model,
            api_key=cfg.api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    async def analyze(
        self,
        competitor: str,
        changes: list[dict],
    ) -> list[ResearchInsight]:
        search_results = await self._gather_intelligence(competitor)

        changes_summary = "\n".join(
            f"- [{c.get('change_type', 'unknown')}] {c.get('title', '')}: {c.get('summary', '')}"
            for c in changes
        ) or "No specific changes detected – perform general research."

        user_msg = (
            f"Competitor: {competitor}\n\n"
            f"Detected Changes:\n{changes_summary}\n\n"
            # 修复：先model_dump()转成可序列化的字典
            f"Web Search Results:\n{json.dumps(search_results, ensure_ascii=False, indent=2)}\n\n"
            "Provide deep research insights as JSON."
        )

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])

        return self._parse_insights(response.content)

    # ------------------------------------------------------------------
    # LangGraph node interface
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        competitor = state["competitor"]
        changes = state.get("changes_detected", [])

        insights = await self.analyze(competitor, changes)
        return {
            "research_results": [i.model_dump() for i in insights],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _gather_intelligence(self, competitor: str) -> dict:
        queries = [
            f"{competitor} financial results revenue 2026",
            f"{competitor} patent filings technology",
            f"{competitor} engineering blog technical",
            f"{competitor} open source github contributions",
            f"{competitor} partnership acquisition news 2026",
        ]
        results: dict[str, list] = {}
        for q in queries:
            results[q] = await web_search(q)
        results["news"] = await news_search(competitor)
        return results

    @staticmethod
    def _parse_insights(llm_output: str) -> list[ResearchInsight]:
        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            items = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Could not parse research output as JSON")
            return [
                ResearchInsight(
                    topic="Raw Analysis",
                    summary=llm_output[:2000],
                    key_findings=[],
                    sources=[],
                    confidence=0.5,
                )
            ]

        insights = []
        for item in items if isinstance(items, list) else [items]:
            insights.append(
                ResearchInsight(
                    topic=item.get("topic", "General"),
                    summary=item.get("summary", ""),
                    key_findings=item.get("key_findings", []),
                    sources=item.get("sources", []),
                    confidence=item.get("confidence", 0.7),
                )
            )
        return insights
