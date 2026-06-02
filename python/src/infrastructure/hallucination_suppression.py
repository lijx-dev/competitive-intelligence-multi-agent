"""三重幻觉抑制可演示系统 — 比赛技术深度核心项。

实现三大机制：
1. Self-Consistency 自一致性：关键问题调用 LLM 3 次，投票取占比≥2 的结论
2. Mandatory Citation 强制引用：所有非常识结论必须绑定≥1个 SourceSpan，系统自动拦截
3. Multi-Source Validation 多源交叉校验：同一数据点至少从 2 个不同 URL 抽取，偏差超 15% 自动标记
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ..models.schemas import SourceSpan, SourceSpanCollection

logger = logging.getLogger(__name__)

# ── 幻觉检测阈值 ──
HALLUCINATION_THRESHOLDS = {
    "max_numeric_deviation_pct": 15,   # 数值偏差超过 15% 标记异常
    "min_citation_per_claim": 1,       # 每个结论至少 1 个引用
    "self_consistency_quorum": 2,      # 3 次调用中有 2 次一致即通过
    "multi_source_min_urls": 2,        # 同一数据点至少 2 个不同来源
}


@dataclass
class HallucinationStats:
    """幻觉抑制实时统计"""
    total_claims_checked: int = 0
    hallucinations_detected: int = 0
    citations_enforced: int = 0
    citations_missing: int = 0
    multi_source_passed: int = 0
    multi_source_failed: int = 0
    self_consistency_passed: int = 0
    self_consistency_failed: int = 0

    @property
    def hallucination_rate(self) -> float:
        if self.total_claims_checked == 0:
            return 0.0
        return round(self.hallucinations_detected / self.total_claims_checked, 4)

    @property
    def citation_coverage(self) -> float:
        total = self.citations_enforced + self.citations_missing
        if total == 0:
            return 1.0
        return round(self.citations_enforced / total, 4)

    @property
    def multi_source_pass_rate(self) -> float:
        total = self.multi_source_passed + self.multi_source_failed
        if total == 0:
            return 1.0
        return round(self.multi_source_passed / total, 4)

    @property
    def self_consistency_pass_rate(self) -> float:
        total = self.self_consistency_passed + self.self_consistency_failed
        if total == 0:
            return 1.0
        return round(self.self_consistency_passed / total, 4)

    def to_dashboard_dict(self) -> dict:
        return {
            "hallucination_rate": self.hallucination_rate,
            "hallucination_rate_pct": f"{self.hallucination_rate * 100:.1f}%",
            "citation_coverage": self.citation_coverage,
            "citation_coverage_pct": f"{self.citation_coverage * 100:.1f}%",
            "multi_source_pass_rate": self.multi_source_pass_rate,
            "multi_source_pass_rate_pct": f"{self.multi_source_pass_rate * 100:.1f}%",
            "claims_checked": self.total_claims_checked,
            "hallucinations_detected": self.hallucinations_detected,
            "citations_enforced": self.citations_enforced,
            "multi_source_passed": self.multi_source_passed,
            "self_consistency_passed": self.self_consistency_passed,
        }


# ── 全局单例 ──
_stats = HallucinationStats()


def get_hallucination_stats() -> HallucinationStats:
    return _stats


def reset_hallucination_stats() -> None:
    global _stats
    _stats = HallucinationStats()


# ========================================================================
# 1. Self-Consistency 自一致性模块
# ========================================================================

async def self_consistency_check(
    llm_client,
    prompt: str,
    n_samples: int = 3,
) -> dict[str, Any]:
    """对同一 prompt 调用 LLM n 次，投票决定最终结论。

    Returns:
        {
            "consensus": <多数结论文本>,
            "agreement_ratio": <一致比例>,
            "passed": bool,
            "samples": [<n个原始返回>],
        }
    """
    if n_samples < 2:
        n_samples = 3

    try:
        # 并行调用 LLM n 次
        tasks = [_safe_llm_call(llm_client, prompt) for _ in range(n_samples)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤异常
        valid_results = [r for r in results if not isinstance(r, Exception) and r]
        if len(valid_results) < 2:
            _stats.self_consistency_failed += 1
            _stats.total_claims_checked += 1
            return {
                "consensus": "",
                "agreement_ratio": 0.0,
                "passed": False,
                "samples": valid_results,
                "error": "有效样本不足（<2）",
            }

        # 对结果进行哈希聚类投票
        clusters: dict[str, list[str]] = {}
        for r in valid_results:
            # 归一化后哈希
            normalized = _normalize_for_comparison(r)
            key = hashlib.md5(normalized.encode()).hexdigest()[:8]
            clusters.setdefault(key, []).append(r)

        # 找到最大的聚类
        best_cluster = max(clusters.values(), key=len)
        consensus = best_cluster[0]
        agreement_ratio = len(best_cluster) / len(valid_results)
        passed = agreement_ratio >= (HALLUCINATION_THRESHOLDS["self_consistency_quorum"] / n_samples)

        _stats.total_claims_checked += 1
        if passed:
            _stats.self_consistency_passed += 1
        else:
            _stats.self_consistency_failed += 1
            _stats.hallucinations_detected += 1

        return {
            "consensus": consensus,
            "agreement_ratio": round(agreement_ratio, 2),
            "passed": passed,
            "samples": valid_results,
        }
    except Exception as e:
        logger.warning("Self-consistency check failed: %s", e)
        return {"consensus": "", "agreement_ratio": 0.0, "passed": False, "samples": [], "error": str(e)}


async def _safe_llm_call(llm_client, prompt: str) -> str:
    """安全的 LLM 调用包装，支持同步/异步客户端。"""
    try:
        if hasattr(llm_client, "ainvoke"):
            resp = await llm_client.ainvoke(prompt)
        elif hasattr(llm_client, "invoke"):
            resp = await asyncio.to_thread(llm_client.invoke, prompt)
        elif hasattr(llm_client, "generate"):
            resp = await llm_client.generate(prompt)
        else:
            resp = str(llm_client(prompt))

        if hasattr(resp, "content"):
            return resp.content
        return str(resp)
    except Exception as e:
        logger.warning("LLM call in self-consistency failed: %s", e)
        return ""


def _normalize_for_comparison(text: str) -> str:
    """归一化文本用于比较：去空格、小写、去标点。"""
    import re
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text


# ========================================================================
# 2. Mandatory Citation 强制引用检查
# ========================================================================

class MandatoryCitationChecker:
    """强制引用检查器：每条非常识结论必须绑定 ≥1 个 SourceSpan。

    系统自动拦截不含引用的结论，标记为"待补充来源"。
    """

    # 常识性断言关键词（无需引用）
    COMMON_KNOWLEDGE_PATTERNS = [
        r"电商.*是.*重要.*渠道",
        r"用户.*体验.*关键",
        r"竞争.*日益.*激烈",
        r"技术.*不断.*发展",
        r"市场.*规模.*增长",
    ]

    def __init__(self):
        self._common_knowledge_re = [
            re.compile(p, re.IGNORECASE) for p in self.COMMON_KNOWLEDGE_PATTERNS
        ]

    def is_common_knowledge(self, claim: str) -> bool:
        """判断是否为常识性陈述（无需引用）。"""
        for pattern in self._common_knowledge_re:
            if pattern.search(claim):
                return True
        return False

    def check_claim(self, claim: str, source_spans: list[SourceSpan]) -> dict[str, Any]:
        """检查单条结论的引用完整度。

        Returns:
            {"passed": bool, "missing": bool, "spans_found": int}
        """
        if not claim or len(claim.strip()) < 20:
            return {"passed": True, "missing": False, "spans_found": 0, "skipped": "too_short"}

        if self.is_common_knowledge(claim):
            return {"passed": True, "missing": False, "spans_found": 0, "skipped": "common_knowledge"}

        # 检查是否有 SourceSpan 覆盖该 claim
        matches = []
        claim_lower = claim.lower()
        for span in source_spans:
            if span.analysis_text_snippet.lower() in claim_lower or claim_lower[:50] in span.analysis_text_snippet.lower():
                matches.append(span.span_id)

        passed = len(matches) >= HALLUCINATION_THRESHOLDS["min_citation_per_claim"]
        if passed:
            _stats.citations_enforced += 1
        else:
            _stats.citations_missing += 1
            _stats.hallucinations_detected += 1

        return {
            "passed": passed,
            "missing": not passed,
            "spans_found": len(matches),
            "matched_span_ids": matches,
        }

    def check_battlecard(self, battlecard: dict, source_spans: list[SourceSpan]) -> dict[str, Any]:
        """对整个 Battlecard 的所有结论进行强制引用检查。

        Returns:
            {"passed": bool, "violations": [{claim, reason}], "coverage_pct": float}
        """
        violations: list[dict] = []
        claims_checked = 0
        claims_passed = 0

        claim_fields = [
            ("elevator_pitch", battlecard.get("elevator_pitch", "")),
            ("our_strengths", battlecard.get("our_strengths", [])),
            ("competitor_strengths", battlecard.get("competitor_strengths", [])),
            ("key_differentiators", battlecard.get("key_differentiators", [])),
        ]

        for field_name, value in claim_fields:
            if isinstance(value, str) and len(value) > 20:
                claims_checked += 1
                result = self.check_claim(value, source_spans)
                if result["passed"]:
                    claims_passed += 1
                else:
                    violations.append({
                        "field": field_name,
                        "claim": value[:200],
                        "reason": "缺少引用来源",
                    })
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and len(item) > 20:
                        claims_checked += 1
                        result = self.check_claim(item, source_spans)
                        if result["passed"]:
                            claims_passed += 1
                        else:
                            violations.append({
                                "field": field_name,
                                "claim": item[:200],
                                "reason": "缺少引用来源",
                            })

        coverage = claims_passed / max(claims_checked, 1)

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "claims_checked": claims_checked,
            "claims_passed": claims_passed,
            "coverage_pct": round(coverage * 100, 1),
        }


# ── 全局单例 ──
citation_checker = MandatoryCitationChecker()


# ========================================================================
# 3. Multi-Source Validation 多源交叉校验
# ========================================================================

class MultiSourceValidator:
    """多源交叉校验器：同一数据点至少从 2 个不同 URL 抽取，偏差超过 15% 自动标记。

    从 comparison_matrix 维度提取数值型数据，检查不同来源之间的一致性。
    """

    def __init__(self, max_deviation_pct: float = 15.0):
        self.max_deviation_pct = max_deviation_pct

    def extract_numeric_claims(self, research_results: list[dict]) -> list[dict]:
        """从 research_results 中提取所有数值型声明和其来源。"""
        claims: list[dict] = []
        numeric_pattern = re.compile(
            r'(?:营收|收入|revenue|用户|user|GMV|DAU|MAU|增长率|growth|份额|share|评分|score)'
            r'\D{0,20}?(\d+(?:\.\d+)?)\s*(?:亿|万|百万|%|元|美元|人民币)?'
        )

        for r in research_results:
            if not isinstance(r, dict):
                continue
            summary = str(r.get("summary", ""))
            topic = str(r.get("topic", ""))
            sources = r.get("sources", [])

            for match in numeric_pattern.finditer(summary + " " + topic):
                value_str = match.group(1)
                try:
                    value = float(value_str)
                except ValueError:
                    continue

                claims.append({
                    "claim_text": match.group(0),
                    "numeric_value": value,
                    "sources": sources if isinstance(sources, list) else [str(sources)],
                    "topic": topic[:50],
                })

        return claims

    def validate(self, research_results: list[dict]) -> dict[str, Any]:
        """执行多源交叉校验。

        Returns:
            {
                "passed": bool,
                "total_claims": int,
                "validated_claims": int,
                "conflicts": [{claim, values, sources, deviation_pct}],
                "pass_rate": float,
            }
        """
        claims = self.extract_numeric_claims(research_results)
        if not claims:
            return {
                "passed": True, "total_claims": 0, "validated_claims": 0,
                "conflicts": [], "pass_rate": 1.0,
            }

        # 按 topic 聚类
        from collections import defaultdict
        by_topic: dict[str, list[dict]] = defaultdict(list)
        for c in claims:
            by_topic[c["topic"]].append(c)

        validated = 0
        conflicts: list[dict] = []

        for topic, topic_claims in by_topic.items():
            if len(topic_claims) < 2:
                # 只有 1 个来源，无法交叉验证
                continue

            # 获取去重后的来源 URL
            all_sources = set()
            for tc in topic_claims:
                for s in tc["sources"]:
                    if isinstance(s, str) and s.startswith("http"):
                        all_sources.add(s)

            if len(all_sources) < HALLUCINATION_THRESHOLDS["multi_source_min_urls"]:
                _stats.multi_source_failed += 1
                conflicts.append({
                    "topic": topic,
                    "reason": f"仅 {len(all_sources)} 个独立来源（需 ≥{HALLUCINATION_THRESHOLDS['multi_source_min_urls']}）",
                    "claims": topic_claims,
                    "sources": list(all_sources),
                })
                continue

            # 检查数值偏差
            values = [tc["numeric_value"] for tc in topic_claims]
            if len(values) >= 2:
                min_v, max_v = min(values), max(values)
                if min_v > 0:
                    deviation = abs(max_v - min_v) / min_v * 100
                    if deviation > self.max_deviation_pct:
                        _stats.multi_source_failed += 1
                        _stats.hallucinations_detected += 1
                        conflicts.append({
                            "topic": topic,
                            "reason": f"数值偏差 {deviation:.1f}%（超过阈值 {self.max_deviation_pct}%）",
                            "values": values,
                            "deviation_pct": round(deviation, 1),
                            "sources": list(all_sources),
                        })
                        continue

            validated += 1
            _stats.multi_source_passed += 1

        return {
            "passed": len(conflicts) == 0,
            "total_claims": len(claims),
            "validated_claims": validated,
            "conflicts": conflicts,
            "pass_rate": round(validated / max(len(claims), 1), 3),
        }


# ── 全局单例 ──
multi_source_validator = MultiSourceValidator()


# ========================================================================
# 4. 完整幻觉抑制 Pipeline（供 Reviewer / Citation 节点调用）
# ========================================================================

async def run_hallucination_suppression_pipeline(
    battlecard: dict,
    research_results: list[dict],
    comparison_matrix: dict,
    source_spans: list[SourceSpan],
    llm_client=None,
) -> dict[str, Any]:
    """运行完整的三重幻觉抑制 Pipeline。

    非阻塞：任一模块失败不影响主流程。

    Returns:
        {
            "self_consistency": {...},
            "mandatory_citation": {...},
            "multi_source_validation": {...},
            "overall_passed": bool,
            "stats": <HallucinationStats dashboard dict>,
        }
    """
    results: dict[str, Any] = {
        "self_consistency": {"passed": True, "skipped": True, "reason": "no_llm_client"},
        "mandatory_citation": {"passed": True, "violations": []},
        "multi_source_validation": {"passed": True, "conflicts": []},
    }

    # 1. Self-Consistency（需 LLM 客户端）
    if llm_client:
        try:
            # 对整体评估做自一致性检查
            overall_text = comparison_matrix.get("overall_assessment", "") if isinstance(comparison_matrix, dict) else str(comparison_matrix)
            if overall_text and len(overall_text) > 50:
                sc_result = await self_consistency_check(
                    llm_client,
                    f"请对以下竞品分析结论进行一致性评估，判断其是否基于充分数据支撑：\n\n{overall_text[:1000]}",
                    n_samples=3,
                )
                results["self_consistency"] = sc_result
        except Exception as e:
            logger.warning("Self-consistency check skipped: %s", e)

    # 2. Mandatory Citation
    try:
        mc_result = citation_checker.check_battlecard(battlecard, source_spans)
        results["mandatory_citation"] = mc_result
    except Exception as e:
        logger.warning("Mandatory citation check skipped: %s", e)

    # 3. Multi-Source Validation
    try:
        mv_result = multi_source_validator.validate(research_results)
        results["multi_source_validation"] = mv_result
    except Exception as e:
        logger.warning("Multi-source validation skipped: %s", e)

    # 整体通过判断
    results["overall_passed"] = (
        results["self_consistency"].get("passed", True) and
        results["mandatory_citation"].get("passed", True) and
        results["multi_source_validation"].get("passed", True)
    )
    results["stats"] = _stats.to_dashboard_dict()

    return results
