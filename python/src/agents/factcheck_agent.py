"""
FactCheck Agent — 交叉验证 Monitor 和 Research 输出的一致性。

职责：独立审查两个上游Agent的结论，标记验证状态，解决"数据打架"问题。
对未验证的变更自动降级严重程度，对无证据的研究洞察降低置信度。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..models.schemas import (
    FactCheckItem,
    FactCheckResult,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class FactCheckAgent:
    """交叉验证 Monitor vs Research 一致性，不调用 LLM（纯规则引擎）。"""

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        competitor = state.get("competitor", "Unknown")
        changes = state.get("changes_detected", [])
        research = state.get("research_results", [])

        result = self.verify(competitor, changes, research)
        return {"fact_check_result": result.model_dump()}

    # ------------------------------------------------------------------
    # 核心校验
    # ------------------------------------------------------------------

    def verify(
        self,
        competitor: str,
        changes: list[dict],
        research: list[dict],
    ) -> FactCheckResult:
        items: list[FactCheckItem] = []
        inconsistencies: list[dict] = []

        # 从 changes 中提取关键词索引
        change_keywords = self._extract_keywords(changes)
        research_keywords = self._extract_keywords(research)

        # 1. 验证每条 Change 是否有 Research 支撑
        for ch in changes:
            ch_title = ch.get("title", "")
            ch_type = ch.get("change_type", "")
            ch_severity = ch.get("severity", "medium")

            support = self._find_support(ch_title, ch_type, research)
            item = FactCheckItem(
                source_agent="monitor",
                claim=ch_title[:200],
                status=VerificationStatus.VERIFIED if support else VerificationStatus.UNVERIFIED,
                supporting_evidence=[s.get("topic", "") for s in support],
                adjusted_severity=ch_severity if support else "low",
            )
            items.append(item)

            # 未验证的变更 → 标记为不一致
            if not support and ch_severity in ("high", "critical"):
                inconsistencies.append({
                    "type": "unverified_change",
                    "monitor_claim": ch_title,
                    "original_severity": ch_severity,
                    "action": "severity_downgraded_to_low",
                })

        # 2. 验证每条 Research Insight 是否有 Monitor 或外部搜索支撑
        for ri in research:
            ri_topic = ri.get("topic", "")
            ri_summary = ri.get("summary", "")
            ri_sources = ri.get("sources", [])

            has_monitor_support = self._find_support(ri_topic, "research", changes)
            has_sources = len(ri_sources) > 0

            if not has_monitor_support and not has_sources:
                items.append(FactCheckItem(
                    source_agent="research",
                    claim=ri_topic[:200],
                    status=VerificationStatus.UNVERIFIED,
                    supporting_evidence=[],
                ))
                inconsistencies.append({
                    "type": "low_confidence_insight",
                    "research_topic": ri_topic,
                    "summary": ri_summary[:150],
                    "action": "confidence_marked_low",
                })
            elif has_monitor_support and has_sources:
                items.append(FactCheckItem(
                    source_agent="research",
                    claim=ri_topic[:200],
                    status=VerificationStatus.VERIFIED,
                    supporting_evidence=ri_sources,
                ))
            else:
                items.append(FactCheckItem(
                    source_agent="research",
                    claim=ri_topic[:200],
                    status=VerificationStatus.PARTIALLY_VERIFIED,
                    supporting_evidence=ri_sources if has_sources else ["monitor_correlated"],
                ))

        # 3. 汇总
        total = len(items)
        verified = sum(1 for i in items if i.status == VerificationStatus.VERIFIED)
        partially = sum(1 for i in items if i.status == VerificationStatus.PARTIALLY_VERIFIED)

        return FactCheckResult(
            competitor=competitor,
            cross_verified=items,
            inconsistencies=inconsistencies,
            confidence_adjustments={
                "total_claims": total,
                "verified": verified,
                "partially_verified": partially,
                "unverified": total - verified - partially,
                "verification_rate": round(verified / max(total, 1), 2),
            },
            summary=(
                f"交叉验证完成：{total} 条断言中，{verified} 条已验证、"
                f"{partially} 条部分验证、{total - verified - partially} 条未验证。"
                f"发现 {len(inconsistencies)} 处不一致。"
            ),
        )

    # ---------- 内部 ----------

    @staticmethod
    def _extract_keywords(items: list[dict]) -> set:
        """从 JSON 中提取关键词用于模糊匹配"""
        kw = set()
        for item in items:
            text = json.dumps(item, ensure_ascii=False).lower()
            for word in text.split():
                clean = word.strip('",:[]{}')
                if len(clean) > 2:
                    kw.add(clean)
        return kw

    @staticmethod
    def _find_support(claim: str, claim_type: str, candidates: list[dict]) -> list[dict]:
        """在候选中搜索支撑证据"""
        claim_lower = claim.lower()
        matched = []
        for c in candidates:
            c_text = json.dumps(c, ensure_ascii=False).lower()
            # 简单词重叠度匹配
            overlap = sum(1 for w in claim_lower.split() if w.strip('",:[]{}') in c_text)
            if overlap >= 1:
                matched.append(c)
        return matched
