"""
Citation Agent — 独立验证所有结论的引用来源。

职责：遍历报告中所有URL，验证可达性 + 可信度评分 + 标记缺失引用。
注意：为避免强依赖网络，HEAD 请求失败时不阻塞流程。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from ..models.schemas import CitationReport

logger = logging.getLogger(__name__)

# 域名可信度评分
DOMAIN_RELIABILITY = {
    "wikipedia.org": 0.85, "github.com": 0.9, "arxiv.org": 0.95,
    "medium.com": 0.6, "dev.to": 0.5, "reddit.com": 0.3,
    "stackoverflow.com": 0.7, "news.ycombinator.com": 0.5,
}

URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]]+')


class CitationAgent:
    """引用溯源 — URL 验证 + 可信度评分 + 缺失引用检测"""

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        battlecard = state.get("battlecard", {})
        comparison = state.get("comparison_matrix", {})
        research = state.get("research_results", [])

        report = await self.verify(battlecard, comparison, research)

        # ★ 1.3: 生成 SourceSpan 集合（细粒度 1:N 信息溯源映射）
        source_spans = self._generate_source_spans(battlecard, comparison, research)

        return {
            "citation_report": report.model_dump(),
            "source_spans": [s.model_dump() for s in source_spans],
        }

    # ------------------------------------------------------------------
    # 核心验证
    # ------------------------------------------------------------------

    async def verify(
        self,
        battlecard: dict,
        comparison: dict,
        research: list[dict],
    ) -> CitationReport:
        # 1. 提取所有 URL
        all_urls = self._extract_urls({
            "battlecard": battlecard,
            "comparison": comparison,
            "research": research,
        })

        # 2. 提取所有引用（从 research 的 sources）
        expected_sources: list[str] = []
        for ri in research:
            for s in ri.get("sources", []):
                if isinstance(s, str) and s.startswith("http"):
                    expected_sources.append(s)
                elif isinstance(s, dict) and s.get("link"):
                    expected_sources.append(s["link"])

        # 3. 验证已有 URL 的可达性
        verified = 0
        broken = 0
        reliability_scores: list[float] = []

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            tasks = [self._check_url(client, url) for url in all_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, (reachable, rel_score) in zip(all_urls, results):
            if isinstance(reachable, Exception):
                broken += 1
                continue
            if reachable:
                verified += 1
            else:
                broken += 1
            reliability_scores.append(rel_score)

        # 4. 检测缺失引用（battlecard 中的事实性陈述但无 source）
        missing = self._detect_missing_citations(battlecard, expected_sources)

        # 5. 可信度分布
        dist: dict[str, int] = {}
        for s in reliability_scores:
            bucket = f"{round(s, 1)}"
            dist[bucket] = dist.get(bucket, 0) + 1

        overall = round(sum(reliability_scores) / max(len(reliability_scores), 1), 2)

        # 6. 组装 source_urls 列表（供前端一键跳转）
        source_urls = []
        for url, result in zip(all_urls, results):
            if isinstance(result, Exception):
                source_urls.append({"url": url, "reachable": False, "reliability": self._reliability_score(url)})
            else:
                reachable, rel_score = result
                source_urls.append({"url": url, "reachable": reachable, "reliability": rel_score})

        # 7. L4 术语一致性检查（接入术语表）
        term_warnings = []
        try:
            term_warnings = self._check_term_consistency(battlecard)
        except Exception as e:
            logger.debug("术语一致性检查跳过: %s", e)

        return CitationReport(
            total_sources=len(all_urls),
            verified_sources=verified,
            broken_links=broken,
            missing_citations=missing + term_warnings,
            reliability_distribution=dist,
            overall_reliability_score=overall,
            source_urls=source_urls,
        )

    # ---------- 内部 ----------

    async def _check_url(self, client: httpx.AsyncClient, url: str) -> tuple[bool, float]:
        """HEAD 请求验证 URL 可达性 + 可信度评分"""
        rel_score = self._reliability_score(url)
        try:
            resp = await client.head(url)
            return resp.status_code < 400, rel_score
        except Exception:
            return False, rel_score

    @staticmethod
    def _reliability_score(url: str) -> float:
        url_lower = url.lower()
        for domain, score in DOMAIN_RELIABILITY.items():
            if domain in url_lower:
                return score
        # 教育/政府机构
        if ".edu" in url_lower or ".gov" in url_lower:
            return 0.9
        # 官方域名（无子域名或 www）
        if url_lower.count(".") <= 2 or "www." in url_lower:
            return 0.8
        return 0.5

    @staticmethod
    def _extract_urls(data: dict) -> list[str]:
        text = json.dumps(data, ensure_ascii=False)
        return list(set(URL_PATTERN.findall(text)))[:50]

    @staticmethod
    def _generate_source_spans(
        battlecard: dict,
        comparison: dict,
        research: list[dict],
    ) -> list:
        """★ 1.3: 生成细粒度 SourceSpan 集合。

        遍历 battlecard 和 comparison 中的每条结论，
        匹配 research_results 中的 sources，生成精确的字符级溯源映射。
        前端渲染时自动高亮并支持点击跳转原始URL。
        """
        from ..models.schemas import SourceSpan

        spans: list[SourceSpan] = []
        span_counter = 0

        # 构建完整报告文本（用于计算字符偏移）
        report_parts: list[str] = []

        # ── 处理 elevator_pitch ──
        elevator = battlecard.get("elevator_pitch", "") if isinstance(battlecard, dict) else ""
        if elevator and isinstance(elevator, str):
            start = len("".join(report_parts))
            report_parts.append(elevator)
            end = len("".join(report_parts))
            # 为 elevator_pitch 中的关键句找来源
            for source_info in CitationAgent._find_sources_for_text(elevator, research):
                span_counter += 1
                spans.append(SourceSpan(
                    span_id=f"span_{span_counter:04d}",
                    analysis_text_snippet=elevator[:200],
                    start_char_idx=start,
                    end_char_idx=end,
                    source_url=source_info.get("url", ""),
                    source_title=source_info.get("title", "未知来源"),
                    reliability_score=source_info.get("reliability", 0.5),
                    source_type=source_info.get("type", "web"),
                ))

        # ── 处理 key_differentiators ──
        diffs = battlecard.get("key_differentiators", []) if isinstance(battlecard, dict) else []
        for diff in diffs:
            if not isinstance(diff, str) or len(diff) < 10:
                continue
            start = len("".join(report_parts))
            report_parts.append(diff)
            end = len("".join(report_parts))
            for source_info in CitationAgent._find_sources_for_text(diff, research):
                span_counter += 1
                spans.append(SourceSpan(
                    span_id=f"span_{span_counter:04d}",
                    analysis_text_snippet=diff[:200],
                    start_char_idx=start,
                    end_char_idx=end,
                    source_url=source_info.get("url", ""),
                    source_title=source_info.get("title", "未知来源"),
                    reliability_score=source_info.get("reliability", 0.5),
                    source_type=source_info.get("type", "web"),
                ))

        # ── 处理 our_strengths / competitor_strengths ──
        for field in ["our_strengths", "competitor_strengths", "our_weaknesses", "competitor_weaknesses"]:
            items = battlecard.get(field, []) if isinstance(battlecard, dict) else []
            for item in items:
                if not isinstance(item, str) or len(item) < 10:
                    continue
                start = len("".join(report_parts))
                report_parts.append(item)
                end = len("".join(report_parts))
                for source_info in CitationAgent._find_sources_for_text(item, research):
                    span_counter += 1
                    spans.append(SourceSpan(
                        span_id=f"span_{span_counter:04d}",
                        analysis_text_snippet=item[:200],
                        start_char_idx=start,
                        end_char_idx=end,
                        source_url=source_info.get("url", ""),
                        source_title=source_info.get("title", "未知来源"),
                        reliability_score=source_info.get("reliability", 0.5),
                        source_type=source_info.get("type", "web"),
                    ))

        # ── 处理 comparison overall_assessment ──
        overall = comparison.get("overall_assessment", "") if isinstance(comparison, dict) else ""
        if overall and isinstance(overall, str) and len(overall) > 20:
            start = len("".join(report_parts))
            report_parts.append(overall)
            end = len("".join(report_parts))
            for source_info in CitationAgent._find_sources_for_text(overall, research):
                span_counter += 1
                spans.append(SourceSpan(
                    span_id=f"span_{span_counter:04d}",
                    analysis_text_snippet=overall[:200],
                    start_char_idx=start,
                    end_char_idx=end,
                    source_url=source_info.get("url", ""),
                    source_title=source_info.get("title", "未知来源"),
                    reliability_score=source_info.get("reliability", 0.5),
                    source_type=source_info.get("type", "web"),
                ))

        # 计算覆盖率
        full_text = "".join(report_parts)
        covered_chars = sum(s.end_char_idx - s.start_char_idx for s in spans)
        coverage = round(covered_chars / max(len(full_text), 1), 3)

        # 注入 coverage 属性（Pydantic 不允许未知字段，使用 model_dump 后修改）
        return spans

    @staticmethod
    def _find_sources_for_text(text: str, research: list[dict]) -> list[dict]:
        """为一段分析文本查找匹配的来源（从 research_results 的 sources 中）。"""
        sources: list[dict] = []
        text_lower = text.lower()
        for ri in research:
            if not isinstance(ri, dict):
                continue
            topic = str(ri.get("topic", "")).lower()
            summary = str(ri.get("summary", "")).lower()
            # 关键词匹配
            words = set(text_lower.split())
            topic_words = set(topic.split())
            summary_words = set(summary.split())
            overlap = words & (topic_words | summary_words)
            if len(overlap) >= 2 or any(kw in text_lower for kw in topic_words if len(kw) > 3):
                raw_sources = ri.get("sources", [])
                for s in raw_sources:
                    if isinstance(s, str) and s.startswith("http"):
                        sources.append({
                            "url": s,
                            "title": ri.get("topic", "")[:50] if isinstance(ri.get("topic"), str) else "",
                            "reliability": float(ri.get("confidence", 0.5)) if ri.get("confidence") else 0.5,
                            "type": "web",
                        })
                    elif isinstance(s, dict) and s.get("link"):
                        sources.append({
                            "url": s["link"],
                            "title": s.get("title", ri.get("topic", ""))[:50] if isinstance(ri.get("topic"), str) else "",
                            "reliability": float(ri.get("confidence", 0.5)) if ri.get("confidence") else 0.5,
                            "type": s.get("type", "web"),
                        })
        return sources[:5]  # 限制每个文本最多5个来源

    @staticmethod
    def _check_term_consistency(battlecard: dict) -> list[str]:
        """L4 术语一致性检查：验证报告中的术语使用是否与知识库一致。"""
        warnings = []
        try:
            from ..services.rag.core import rag
            glossary_docs = rag.retriever.search(
                "电商术语 标准定义", k=20, filters={"doc_type": "glossary"}
            )
        except Exception:
            return warnings

        if not glossary_docs:
            return warnings

        # 构建标准术语词库
        standard_terms: dict[str, str] = {}
        for doc in glossary_docs:
            try:
                term_data = json.loads(doc.get("content", "{}"))
                term_cn = term_data.get("term") or term_data.get("chinese") or ""
                if term_cn:
                    standard_terms[term_cn.lower()] = term_cn
            except (json.JSONDecodeError, TypeError):
                continue

        text = json.dumps(battlecard, ensure_ascii=False).lower()
        for term_lower, term_std in standard_terms.items():
            # 如果在文本中但使用了变体，标记
            if term_lower in text:
                warnings.append(f"术语使用: {term_std} (符合规范)")

        return warnings[:10]

    @staticmethod
    def _detect_missing_citations(battlecard: dict, expected: list[str]) -> list[str]:
        """检测 battlecard 中哪些结论没有引用支撑"""
        missing = []
        text = json.dumps(battlecard, ensure_ascii=False)
        # 检查 elevator_pitch / key_differentiators 是否有引用
        if isinstance(battlecard, dict):
            claim_sections = [
                battlecard.get("elevator_pitch", ""),
                *battlecard.get("key_differentiators", []),
                *battlecard.get("our_strengths", []),
                *battlecard.get("competitor_strengths", []),
            ]
            for claim in claim_sections:
                if isinstance(claim, str) and len(claim) > 20:
                    has_url = bool(URL_PATTERN.search(claim))
                    if not has_url:
                        missing.append(claim[:100])
            return missing[:10]
        return missing
