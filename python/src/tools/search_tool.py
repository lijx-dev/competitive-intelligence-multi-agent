"""Search tool wrappers for retrieving competitor intelligence from the web.
Supports: SerpAPI (premium) → DuckDuckGo (free fallback, no API key needed).
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import quote_plus

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Proxy配置（加速网络请求）
_HTTP_PROXY = os.getenv("HTTP_PROXY", os.getenv("HTTPS_PROXY", ""))
_PROXY_MOUNT = _HTTP_PROXY if _HTTP_PROXY else None


def _get_api_key() -> str:
    """获取SerpAPI密钥（多种环境变量名兼容）"""
    return os.getenv("SERPAPI_KEY", "") or os.getenv("SERP_API_KEY", "") or os.getenv("SEARCH_API_KEY", "")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
async def web_search(query: str, num_results: int = 10, api_key: str = "") -> list[dict]:
    """Search the web via SerpAPI or DuckDuckGo (free fallback, no API key needed).

    Returns a list of ``{"title": ..., "link": ..., "snippet": ...}`` dicts.
    """
    api_key = api_key or _get_api_key()

    if api_key:
        return await _serpapi_search(query, num_results, api_key)

    # ★ 无API Key时用DuckDuckGo免费搜索（真实数据）
    logger.info("[Search] 无SerpAPI key，使用DuckDuckGo免费搜索: %s", query[:50])
    return await _duckduckgo_search(query, num_results)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
async def news_search(query: str, num_results: int = 10, api_key: str = "") -> list[dict]:
    """Search recent news articles about a competitor."""
    api_key = api_key or _get_api_key()

    if api_key:
        return await _serpapi_news_search(query, num_results, api_key)

    # ★ 无API Key时用DuckDuckGo News搜索
    logger.info("[Search] 无SerpAPI key，使用DuckDuckGo News搜索: %s", query[:50])
    return await _duckduckgo_news_search(query, num_results)


async def job_search(company: str, api_key: str = "") -> list[dict]:
    """Search for recent job postings of a given company."""
    return await web_search(f"{company} careers hiring jobs 2026", api_key=api_key)


# ---------------------------------------------------------------------------
# SerpAPI (premium — requires SERPAPI_KEY)
# ---------------------------------------------------------------------------

async def _serpapi_search(query: str, num_results: int, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0, proxy=_PROXY_MOUNT) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": api_key, "engine": "google", "num": num_results},
        )
        resp.raise_for_status()
        data = resp.json()
    return [
        {"title": r.get("title", ""), "link": r.get("link", ""), "snippet": r.get("snippet", "")}
        for r in data.get("organic_results", [])
    ]


async def _serpapi_news_search(query: str, num_results: int, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0, proxy=_PROXY_MOUNT) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": api_key, "engine": "google_news", "num": num_results},
        )
        resp.raise_for_status()
        data = resp.json()
    return [
        {"title": r.get("title", ""), "link": r.get("link", ""), "date": r.get("date", ""), "source": r.get("source", {}).get("name", "")}
        for r in data.get("news_results", [])
    ]


# ---------------------------------------------------------------------------
# DuckDuckGo free search (no API key needed, uses HTML scraping via proxy)
# ---------------------------------------------------------------------------

async def _duckduckgo_search(query: str, num_results: int = 10) -> list[dict]:
    """DuckDuckGo HTML搜索 — 免费，无需API Key，走代理加速。"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0, proxy=_PROXY_MOUNT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        # 简易HTML解析提取搜索结果
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for item in soup.select(".result")[:num_results]:
            title_el = item.select_one(".result__title a")
            snippet_el = item.select_one(".result__snippet")
            link_el = item.select_one(".result__url")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "link": link_el.get_text(strip=True) if link_el else "",
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })
        if results:
            logger.info("[Search] DuckDuckGo返回 %d 条结果: %s", len(results), query[:40])
            return results
    except Exception as e:
        logger.warning("[Search] DuckDuckGo搜索失败: %s，回退demo数据", e)

    # 最终fallback
    return _demo_results(query)


async def _duckduckgo_news_search(query: str, num_results: int = 10) -> list[dict]:
    """DuckDuckGo News搜索 — 免费，走代理。"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query + ' news')}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0, proxy=_PROXY_MOUNT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for item in soup.select(".result")[:num_results]:
            title_el = item.select_one(".result__title a")
            snippet_el = item.select_one(".result__snippet")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "link": "",
                    "date": "",
                    "source": "DuckDuckGo News",
                })
        if results:
            logger.info("[Search] DuckDuckGo News返回 %d 条结果", len(results))
            return results
    except Exception as e:
        logger.warning("[Search] DuckDuckGo News搜索失败: %s", e)

    return _demo_news(query)


# ---------------------------------------------------------------------------
# Demo / fallback stubs (最后一个兜底)
# ---------------------------------------------------------------------------

def _demo_results(query: str) -> list[dict]:
    return [
        {
            "title": f"[Demo] {query} – Official Website",
            "link": "https://example.com",
            "snippet": f"Demo search result for: {query}. Configure SERPAPI_KEY for real results.",
        },
    ]


def _demo_news(query: str) -> list[dict]:
    return [
        {
            "title": f"[Demo] {query} Announces New Product",
            "link": "https://example.com/news",
            "date": "2026-04-01",
            "source": "Demo News",
        },
    ]
