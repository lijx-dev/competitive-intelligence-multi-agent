"""
Targeted Fix Agent — 根据 Reviewer 反馈定向修改，只修复问题部分，保留已验证内容。

核心创新：不重跑整个 Agent，而是精准定位 + 定向修复。
最多重试 3 次，超过则标记部分完成。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatTongyi

from ..config import get_effective_llm_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Targeted Fix Agent. Your ONLY job is to fix specific issues in a competitive
intelligence report based on reviewer feedback. DO NOT rewrite the entire report.

Rules:
  1. Only modify the EXACT fields specified in the issues list
  2. Keep ALL other content unchanged
  3. Follow each fix_instruction precisely
  4. Return the FULL modified document (not just the fixes)

Output format:
  Return a JSON object with the COMPLETE battlecard after applying fixes:
  {
    "battlecard": { ... full battlecard with fixes applied ... }
  }
"""


class TargetedFixAgent:
    """定向修复 — 精准修改 + 保留已验证内容"""

    def _get_llm(self):
        cfg = get_effective_llm_config()
        return ChatTongyi(
            model=cfg.model,
            api_key=cfg.api_key,
            temperature=0.2,
            max_tokens=cfg.max_tokens,
        )

    async def fix(
        self,
        battlecard: dict,
        comparison_matrix: dict,
        review_feedback: dict,
    ) -> dict:
        issues = review_feedback.get("issues", [])
        revision_instructions = review_feedback.get("revision_instructions", "")

        issues_text = "\n".join(
            f"- [{iss.get('severity', '?')}] {iss.get('target', '?')}: "
            f"{iss.get('description', '')}\n  Fix: {iss.get('fix_instruction', '')}"
            for iss in issues
        )

        user_msg = (
            "## Issues to Fix\n"
            f"{issues_text}\n\n"
            f"## Revision Instructions\n{revision_instructions}\n\n"
            "## Current Battlecard (fix the issues above, keep everything else)\n"
            f"{json.dumps(battlecard.model_dump() if hasattr(battlecard, 'model_dump') else battlecard, ensure_ascii=False, indent=2)}\n\n"
            "## Current Comparison Matrix (for reference)\n"
            f"{json.dumps(comparison_matrix.model_dump() if hasattr(comparison_matrix, 'model_dump') else comparison_matrix, ensure_ascii=False, indent=2)}\n\n"
            "Apply ONLY the fixes described above. Return the COMPLETE battlecard JSON."
        )

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])

        return self._parse_fixed(response.content, battlecard)

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        battlecard = state.get("battlecard", {})
        comparison = state.get("comparison_matrix", {})
        feedback = state.get("review_feedback", {})
        fix_count = state.get("targeted_fix_count", 0) + 1

        fixed = await self.fix(battlecard, comparison, feedback)
        logger.info(f"TargetedFix attempt {fix_count} completed")
        return {"battlecard": fixed, "targeted_fix_count": fix_count}

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_fixed(llm_output: str, original: dict) -> dict:
        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
            if "battlecard" in data:
                return data["battlecard"]
            return data
        except (json.JSONDecodeError, IndexError):
            logger.warning("TargetedFix parse failed, returning original")
            return original if isinstance(original, dict) else (
                original.model_dump() if hasattr(original, 'model_dump') else {}
            )
