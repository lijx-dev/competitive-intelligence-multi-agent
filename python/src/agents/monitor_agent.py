"""Monitor Agent – 7x24 monitors competitor websites, pricing, and hiring."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..services.llm import LLMFactory
from ..models.schemas import (
    ChangeType,
    CompetitorChange,
    Severity,
)
from ..tools.web_scraper import (
    content_hash,
    extract_job_listings,
    extract_pricing,
    extract_text,
    fetch_page,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a Competitive Intelligence Monitor Agent.
Your job is to analyze web page content and detect meaningful changes for a given
competitor.  Given the OLD snapshot and NEW snapshot, identify:
  - Pricing changes
  - New product features or product launches
  - Hiring signals (new job postings, team expansion)
  - Important news or announcements

Return your findings as a JSON array of objects with keys:
  change_type (pricing | product | hiring | news),
  title, summary, severity (low | medium | high | critical), url.

If there are NO meaningful changes, return an empty array: []
"""


class MonitorAgent:
    """Stateless agent callable that fits into a LangGraph node."""

    def _get_llm(self):
        """统一 LLM 工厂 — 支持豆包/通义千问动态切换"""
        return LLMFactory.get_llm("monitor")

    async def detect_changes(
        self,
        competitor: str,
        urls: list[str],
        previous_hashes: Optional[dict[str, str]] = None,
    ) -> list[CompetitorChange]:
        """Fetch pages, diff against previous hashes, and ask the LLM to
        classify changes.
        """
        previous_hashes = previous_hashes or {}
        changes: list[CompetitorChange] = []

        for url in urls:
            try:
                html = await fetch_page(url)
                if html is None:
                    continue

                new_hash = content_hash(html)
                old_hash = previous_hashes.get(url)

                if old_hash and old_hash == new_hash:
                    logger.debug("No change detected for %s", url)
                    continue

                text = extract_text(html)[:6000]

                pricing = extract_pricing(html)
                jobs = extract_job_listings(html)

                user_msg = (
                    f"Competitor: {competitor}\nURL: {url}\n\n"
                    f"Page Content (truncated):\n{text}\n\n"
                    f"Extracted Pricing Info: {pricing}\n"
                    f"Extracted Job Listings: {jobs}\n\n"
                    "Analyze and return changes as JSON."
                )

                response = await self._get_llm().ainvoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_msg),
                ])

                parsed = self._parse_changes(response.content, competitor, url)
                changes.extend(parsed)

            except Exception:
                logger.exception("Error monitoring %s", url)

        return changes

    # ------------------------------------------------------------------
    # LangGraph node interface
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph node: reads ``competitor`` from state, returns detected
        changes."""
        competitor = state["competitor"]
        urls = state.get("monitor_urls", [])
        prev = state.get("previous_hashes", {})

        if not urls:
            urls = self._default_urls(competitor)

        changes = await self.detect_changes(competitor, urls, prev)
        return {
            "changes_detected": [c.model_dump() for c in changes],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_urls(competitor: str) -> list[str]:
        # 修复：中文名称转拼音/英文域名，避免无效域名
        competitor_map = {
            "字节跳动": "bytedance",
            "抖音": "douyin",
            "微信": "weixin.qq",
            "淘宝": "taobao",
            "openai": "openai",
            "stripe": "stripe",
        }
        # 优先用映射的英文域名，没有则转小写去空格
        slug = competitor_map.get(competitor.lower(), competitor.lower().replace(" ", ""))
        return [
            f"https://{slug}.com",
            f"https://{slug}.com/pricing",
            f"https://{slug}.com/careers",
            f"https://{slug}.com/blog",
        ]

    @staticmethod
    def _parse_changes(
        llm_output: str, competitor: str, url: str
    ) -> list[CompetitorChange]:
        import json as _json

        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            items = _json.loads(text)
        except (_json.JSONDecodeError, IndexError):
            logger.warning("Could not parse LLM output as JSON")
            return []

        results = []
        for item in items if isinstance(items, list) else [items]:
            results.append(
                CompetitorChange(
                    competitor=competitor,
                    change_type=item.get("change_type", "news"),
                    title=item.get("title", "Untitled change"),
                    summary=item.get("summary", ""),
                    url=item.get("url", url),
                    severity=item.get("severity", "medium"),
                    detected_at=datetime.utcnow(),
                )
            )
        return results
