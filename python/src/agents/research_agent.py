"""Research Agent – deep analysis of financials, patents, tech blogs, and OSS."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..services.llm import LLMFactory
from ..models.schemas import ResearchInsight
from ..tools.search_tool import news_search, web_search
from ..services.rag.rag_agent import RAGEnhancedAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是一个竞品情报深度研究智能体（Research Agent）。
你必须使用简体中文输出所有内容。
给定检测到的竞品变更，对以下维度进行深度分析：
  1. 财务信号（营收、融资、盈利数据）
  2. 专利和知识产权活动
  3. 技术博客和工程方向
  4. 开源贡献和社区活跃度
  5. 战略动向（合作、收购、高管变动）
  6. 竞争策略洞察（从公开信息提炼竞品未来动作预判和我方应对策略）

★ 竞争策略洞察维度要求：从20+条公开信息中提炼3-5条竞品未来动作预判，每条包含：
  - 竞品最可能的下一个战略动作（基于当前公开信息推理）
  - 这个动作对我方的威胁级别（高/中/低）
  - 我方可采取的应对策略建议

对每个维度，返回包含以下字段的 JSON 数组：
  topic（主题，中文，以[financial]/[patent_ip]/[tech_blog]/[oss]/[strategic_moves]/[competitive_strategy]开头）,
  summary（摘要，中文）,
  key_findings（关键发现列表，中文，竞争策略维度至少包含3条预判+应对）,
  sources（来源URL列表）,
  confidence（置信度 0-1）。

请基于事实分析，尽可能引用具体来源。所有输出必须是简体中文。
"""


class ResearchAgent:

    def _get_llm(self):
        """统一 LLM 工厂 — 支持豆包/通义千问动态切换"""
        return LLMFactory.get_llm("research")

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

        # ★ RAG 检索：注入行业知识和评分标准
        rag_docs = []
        try:
            from ..services.rag.core import rag
            rag_query = f"{competitor} {' '.join(c.get('title','') for c in changes[:3])}"
            rag_docs = rag.multi_recall(rag_query, k_per_strategy=3)
        except Exception as e:
            logger.debug("RAG 检索跳过: %s", e)

        user_msg = (
            f"竞品名称: {competitor}\n\n"
            f"检测到的变更:\n{changes_summary}\n\n"
            f"网络搜索结果:\n{json.dumps(search_results, ensure_ascii=False, indent=2)}\n\n"
            "请以JSON格式提供深度研究洞察。所有输出必须是简体中文。"
        )
        # 注入 RAG 上下文
        user_msg = RAGEnhancedAgent.augment_prompt(user_msg, rag_docs, max_docs=3)

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])

        insights = self._parse_insights(response.content)
        # 附加引用来源
        for ins in insights:
            if not ins.sources:
                ins.sources = [c["source"] for c in RAGEnhancedAgent.citations_from_docs(rag_docs)[:3]]
        return insights

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
