"""Battlecard Agent – auto-generates sales battlecards (us vs. competitor)."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..services.llm import LLMFactory
from ..models.schemas import Battlecard
from ..services.rag.rag_agent import RAGEnhancedAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是一个销售战术卡生成智能体（Battlecard Agent）。
你必须使用简体中文输出所有内容。
根据对比矩阵和研究洞察，生成销售人员可在竞争交易中使用的销售战术卡。

返回包含以下字段的 JSON 对象：
  our_strengths: [中文优势列表, 3-5项],
  our_weaknesses: [中文劣势列表, 3-5项],
  competitor_strengths: [竞品中文优势列表, 3-5项],
  competitor_weaknesses: [竞品中文劣势列表, 3-5项],
  key_differentiators: [中文关键差异化点列表, 3-5项],
  objection_handling: {客户异议: 应对话术, ...},
  elevator_pitch: 2-3句中文电梯演讲,
  next_actions: [
    {
      "action": "具体可执行动作（中文，不超过50字）",
      "owner": "责任部门（销售/产品/技术）",
      "expected_impact": "预期效果（中文，不超过30字）"
    },
    ... 至少3条，分别面向销售、产品、技术团队
  ]

语言简洁有说服力，具备可操作性。next_actions必须面向不同责任部门，明确预期效果。
所有输出必须是简体中文。
"""


class BattlecardAgent:

    def _get_llm(self):
        """统一 LLM 工厂 — 支持豆包/通义千问动态切换"""
        return LLMFactory.get_llm("battlecard")

    async def generate(
        self,
        competitor: str,
        comparison: dict,
        research: list[dict],
    ) -> Battlecard:
        # ★ RAG 检索：L2 行业知识 + L3 战术卡/SWOT/波特五力模板
        rag_docs = []
        try:
            from ..services.rag.core import rag
            # L2 行业知识
            l2_docs = rag.multi_recall(
                f"{competitor} 销售战术卡 异议处理 竞争优劣势", k_per_strategy=3
            )
            rag_docs.extend(l2_docs)
            # L3 方法论检索：SWOT + 波特五力 + 战术卡模板
            l3_docs = rag.retriever.search(
                f"SWOT 波特五力 战术卡 模板 {competitor}",
                k=2, filters={"doc_type": "methodology"},
            )
            if l3_docs:
                rag_docs.extend(l3_docs)
                logger.debug("L3 methodology docs for battlecard: %d", len(l3_docs))
        except Exception as e:
            logger.debug("RAG 检索跳过: %s", e)

        user_msg = (
            f"竞品名称: {competitor}\n\n"
            f"对比矩阵:\n{json.dumps(comparison.model_dump() if hasattr(comparison, 'model_dump') else comparison, ensure_ascii=False, indent=2)}\n\n"
            f"研究洞察:\n{json.dumps([r.model_dump() if hasattr(r, 'model_dump') else r for r in research], ensure_ascii=False, indent=2)}\n\n"
            "请以JSON格式生成销售战术卡。所有输出必须是简体中文。"
        )
        user_msg = RAGEnhancedAgent.augment_prompt(user_msg, rag_docs, max_docs=2)

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
            next_actions=data.get("next_actions", []),  # ★ 新增：下一步动作
        )
