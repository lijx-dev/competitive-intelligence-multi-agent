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

from ..services.llm import LLMFactory
from ..models.schemas import FixEffectiveness

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是一个定向修复智能体（Targeted Fix Agent）。
你必须使用简体中文输出所有内容。
你唯一的任务是：根据审查反馈，精准修复竞品情报报告中的指定问题。不要重写整个报告。

规则：
  1. 只修改 issues 列表中明确指定的字段
  2. 保持所有其他内容不变
  3. 严格遵循每个 fix_instruction 的修复指令
  4. 返回完整的修复后文档（不仅是修复内容）

输出格式：
  返回包含完整修复后 battlecard 的 JSON 对象：
  {
    "battlecard": { ... 修复后的完整战术卡 ... }
  }
所有输出必须是简体中文。
"""


class TargetedFixAgent:
    """定向修复 — 精准修改 + 保留已验证内容"""

    def _get_llm(self):
        """统一 LLM 工厂 — TargetedFix 使用低 temperature 确保精准修改"""
        llm = LLMFactory.get_llm("targeted_fix")
        llm.temperature = 0.2
        return llm

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
            "## 需要修复的问题\n"
            f"{issues_text}\n\n"
            f"## 修复指令\n{revision_instructions}\n\n"
            "## 当前战术卡（请只修复上述问题，保持其他内容不变）\n"
            f"{json.dumps(battlecard.model_dump() if hasattr(battlecard, 'model_dump') else battlecard, ensure_ascii=False, indent=2)}\n\n"
            "## 当前对比矩阵（仅供参考）\n"
            f"{json.dumps(comparison_matrix.model_dump() if hasattr(comparison_matrix, 'model_dump') else comparison_matrix, ensure_ascii=False, indent=2)}\n\n"
            "请只应用上述修复。返回完整的 battlecard JSON。所有输出必须是简体中文。"
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

        # 记录修复前状态（用于反馈闭环效果追踪）
        score_before = state.get("quality_score", 0.0)
        issues_before = len(feedback.get("issues", []))

        fixed = await self.fix(battlecard, comparison, feedback)
        logger.info(f"TargetedFix attempt {fix_count} completed (score_before={score_before:.1f}, issues={issues_before})")

        # 创建 FixEffectiveness 记录（score_after 由下一轮 Reviewer 填入）
        fix_record = FixEffectiveness(
            round=fix_count,
            score_before=score_before,
            score_after=0.0,  # 占位，由下一轮 Reviewer 更新
            issues_count_before=issues_before,
            issues_count_after=0,  # 占位
            improvement=0.0,  # 占位
            fixed_fields=[iss.get("target", "") for iss in feedback.get("issues", [])],
        )

        # 累积到 fix_history
        fix_history = state.get("fix_history", [])
        fix_history.append(fix_record.model_dump())

        return {
            "battlecard": fixed,
            "targeted_fix_count": fix_count,
            "fix_history": fix_history,
        }

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
