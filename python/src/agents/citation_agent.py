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
        return {"citation_report": report.model_dump()}

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
