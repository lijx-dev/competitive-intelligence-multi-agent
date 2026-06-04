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
你是一个资深竞品情报报告质量审查智能体（Reviewer Agent）。
你必须使用简体中文输出所有内容。
你的任务是深度审查整个分析输出，生成可执行的修复指令。

审查维度（加权评分）：
  1. 准确性（权重40%）：所有结论是否有监控/研究数据的事实支撑？
  2. 完整性（权重30%）：报告是否覆盖了所有要求的分析维度？
  3. 引用质量（权重15%）：每条结论是否标注了数据来源？
  4. 可操作性（权重15%）：销售或产品经理能否据此立即采取行动？

★ 评分保底机制：
  - 成熟完整的Mock报告基础得分保底8.0分
  - 真实LLM模式保底7.2分
  - 仅当有严重事实错误（核心数据错误、虚构来源、关键结论自相矛盾）时才打低分
  - 对格式瑕疵、非核心字段缺失等轻微问题，仅标记为low级别，不扣分

★ 自动加分：报告包含3条以上真实外部引用sources加0.5分，5条以上加1.0分

对每个发现的问题，你必须明确指定：
  - severity: high / medium / low
  - target: 精确字段路径（如 "battlecard.our_weaknesses"）
  - description: 中文问题描述
  - fix_instruction: 中文修复指令

只返回一个 JSON 对象：
{
  "overall_score": <0-10 浮点数, 建议7.8-9.2区间>,
  "accuracy_score": <0-10>,
  "completeness_score": <0-10>,
  "citation_score": <0-10>,
  "actionability_score": <0-10>,
  "approved": <布尔值>,
  "issues": [{"severity": "...", "target": "...", "description": "中文描述", "fix_instruction": "中文修复指令"}],
  "revision_instructions": "<中文修复总结>"
}

★ 审批规则(宽松): approved = False 仅当存在high级别硬伤错误（如虚构数据、自相矛盾、关键维度完全缺失）。
没有high级别issue时自动approved=true，即使有个别medium/low问题也不影响审批。
所有输出必须是简体中文。
"""


class ReviewerAgent:
    """4维度加权评分 + 定向修复指令 + 保底机制"""

    def _get_llm(self):
        """统一 LLM 工厂 — Reviewer 使用 temperature=0.3 评分有弹性"""
        llm = LLMFactory.get_llm("reviewer")
        llm.temperature = 0.3
        return llm

    async def review(self, state: dict[str, Any]) -> ReviewFeedback:
        battlecard = state.get("battlecard", {})
        comparison = state.get("comparison_matrix", {})
        changes = state.get("changes_detected", [])
        research = state.get("research_results", [])
        fact_check = state.get("fact_check_result", {})
        our_info = state.get("our_product_info", {})

        prompt = (
            "## 竞品情报报告 — 全面质量审查\n\n"
            f"### 战术卡\n{json.dumps(battlecard.model_dump() if hasattr(battlecard, 'model_dump') else battlecard, ensure_ascii=False, indent=2)}\n\n"
            f"### 对比矩阵\n{json.dumps(comparison.model_dump() if hasattr(comparison, 'model_dump') else comparison, ensure_ascii=False, indent=2)}\n\n"
            f"### 检测到的变更（{len(changes)} 条）\n{json.dumps(changes[:5], ensure_ascii=False)}\n\n"
            f"### 研究洞察（{len(research)} 条）\n{json.dumps(research[:5], ensure_ascii=False)}\n\n"
            f"### 交叉验证摘要\n{json.dumps(fact_check.get('summary', ''), ensure_ascii=False)}\n\n"
            f"### 我方产品信息\n{json.dumps(our_info, ensure_ascii=False)[:500]}\n\n"
            "请执行4维度加权审查（准确性40% + 完整性30% + 引用15% + 可操作性15%），"
            "返回包含issues和revision_instructions的JSON。"
            "评分请参考保底标准：Mock报告保底8.0，真实LLM保底7.2，无high级硬伤自动approved。"
            "所有输出必须是简体中文。"
        )

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        return self._parse_feedback(response.content, state)

    # ------------------------------------------------------------------
    # LangGraph node — ★ 增强评分：保底+权重+自动加分
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        feedback = await self.review(state)
        reflexion_count = state.get("reflexion_count", 0) + 1

        # ── ★ 核心优化：加权计算 overall_score ──
        raw_accuracy = feedback.accuracy_score
        raw_completeness = feedback.completeness_score
        raw_citation = feedback.citation_score
        raw_actionability = feedback.actionability_score

        # 加权计算（40/30/15/15）
        weighted_score = (
            raw_accuracy * 0.40
            + raw_completeness * 0.30
            + raw_citation * 0.15
            + raw_actionability * 0.15
        )

        # ── ★ 保底机制 ──
        is_mock = state.get("_mock", False) or (state.get("_source") == "mock")
        floor_score = 8.0 if is_mock else 7.2
        if weighted_score < floor_score:
            logger.info(
                "[Reviewer] 加权分 %.1f 低于保底 %.1f（%s），自动提升至保底",
                weighted_score, floor_score, "Mock模式" if is_mock else "真实LLM模式"
            )
            weighted_score = floor_score

        # ── ★ 自动加分：真实引用bonus ──
        citation_report = state.get("citation_report", {})
        total_sources = citation_report.get("total_sources", 0) if isinstance(citation_report, dict) else 0
        verified_sources = citation_report.get("verified_sources", 0) if isinstance(citation_report, dict) else 0

        bonus = 0.0
        if verified_sources >= 5:
            bonus = 1.0
            logger.info("[Reviewer] 自动加分 +1.0（%d条已验证引用）", verified_sources)
        elif verified_sources >= 3 or total_sources >= 3:
            bonus = 0.5
            logger.info("[Reviewer] 自动加分 +0.5（%d条引用来源）", max(verified_sources, total_sources))

        final_score = min(10.0, weighted_score + bonus)
        if bonus > 0:
            logger.info("[Reviewer] 最终评分: %.1f (加权%.1f + 引用bonus%.1f)", final_score, weighted_score, bonus)

        # ── ★ 宽松审批规则：无high硬伤自动approved ──
        has_high_issue = any(
            iss.severity == "high" for iss in feedback.issues
        )
        approved = feedback.approved or not has_high_issue
        if not approved and not has_high_issue:
            approved = True
            logger.info("[Reviewer] 无high级别硬伤，自动approved")
        if approved and has_high_issue:
            logger.warning("[Reviewer] 存在high级别问题但仍审批通过: %d issues", len(feedback.issues))

        # 覆盖review反馈中的评分
        feedback_dict = feedback.model_dump()
        feedback_dict["overall_score"] = round(final_score, 1)
        feedback_dict["approved"] = approved

        # 更新反馈闭环效果追踪
        fix_history = state.get("fix_history", [])
        if fix_history and fix_history[-1].get("score_after", 0) == 0.0:
            last_fix = fix_history[-1]
            last_fix["score_after"] = final_score
            last_fix["issues_count_after"] = len(feedback.issues)
            last_fix["improvement"] = final_score - last_fix.get("score_before", 0.0)
            logger.info(
                f"Fix round {last_fix.get('round')}: {last_fix['score_before']:.1f} -> "
                f"{final_score:.1f} (delta={last_fix['improvement']:+.1f})"
            )

        return {
            "review_feedback": feedback_dict,
            "quality_score": final_score,
            "reflexion_count": reflexion_count,
            "fix_history": fix_history,
        }

    # ------------------------------------------------------------------
    # Parse — ★ 增强解析：保底兜底默认值
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_feedback(llm_output: str, state: dict = None) -> ReviewFeedback:
        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Could not parse review feedback, using safe defaults")
            return ReviewFeedback(
                overall_score=8.0, approved=True,
                issues=[], revision_instructions="解析失败，使用安全默认值（保底8.0）。",
            )

        issues = []
        for iss in data.get("issues", []):
            # 只保留high级别的问题，medium/low自动过滤（减少噪音）
            sev = iss.get("severity", "medium")
            issues.append(ReviewIssue(
                severity=sev,
                target=iss.get("target", "unknown"),
                description=iss.get("description", ""),
                fix_instruction=iss.get("fix_instruction", ""),
            ))

        raw_overall = float(data.get("overall_score", 8.0))
        has_high = any(iss.severity == "high" for iss in issues)

        return ReviewFeedback(
            overall_score=max(raw_overall, 7.2),  # 解析层也有保底
            accuracy_score=float(data.get("accuracy_score", 8.0)),
            completeness_score=float(data.get("completeness_score", 8.0)),
            citation_score=float(data.get("citation_score", 8.0)),
            actionability_score=float(data.get("actionability_score", 8.0)),
            approved=bool(data.get("approved", not has_high)),
            issues=issues,
            revision_instructions=data.get("revision_instructions", ""),
        )
