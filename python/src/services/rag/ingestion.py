"""
L1 文档摄取层 — 竞品数据加载、清洗、分块。

支持:
  - 读取 ecommerce_kb/ 下全部 JSON 文件
  - 抓取竞品网页（复用 web_scraper）
  - 将我方产品信息纳入知识库
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HTML_TAG_RE = re.compile(r"<[^>]+>")


class DocumentLoader:
    """文档加载/清洗/分块"""

    # ── 从知识库目录加载 ────────────────────────

    def ingest_directory(self, kb_path: str) -> list[dict]:
        """递归读取 kb_path 下所有 JSON 文件，转为结构化文档列表。

        每个文档: {"content": "...", "metadata": {"source": "...", "industry": "...", "type": "..."}}
        """
        kb_root = Path(kb_path)
        if not kb_root.exists():
            logger.warning("知识库路径不存在: %s", kb_path)
            return []

        documents = []
        for json_file in sorted(kb_root.rglob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                docs = self._parse_kb_file(data, json_file, kb_root)
                documents.extend(docs)
                logger.debug("Loaded %d docs from %s", len(docs), json_file.name)
            except Exception as e:
                logger.warning("Failed to load %s: %s", json_file.name, e)

        logger.info("知识库加载完成: %d 文档 from %d 文件", len(documents),
                     len(set(f.parent.name for f in kb_root.rglob("*.json"))))
        return documents

    def _parse_kb_file(self, data: dict, file_path: Path, kb_root: Path) -> list[dict]:
        """解析单个 KB JSON 文件为文档列表"""
        rel = file_path.relative_to(kb_root)
        category = rel.parts[0] if len(rel.parts) > 1 else "root"
        source = str(rel)

        documents = []

        # 提取行业名
        industry = data.get("industry_name") or data.get("name") or ""

        if category == "industries":
            # 行业文件：market_overview + key_metrics + 竞品列表 各成一个文档
            if "market_overview" in data:
                documents.append(self._make_doc(
                    json.dumps(data["market_overview"], ensure_ascii=False),
                    source=source, industry=industry, doc_type="market_overview",
                ))
            if "key_metrics" in data:
                documents.append(self._make_doc(
                    json.dumps(data["key_metrics"], ensure_ascii=False),
                    source=source, industry=industry, doc_type="key_metrics",
                ))
            if "key_players" in data:
                for player in data.get("key_players", []):
                    documents.append(self._make_doc(
                        json.dumps(player, ensure_ascii=False),
                        source=source, industry=industry, doc_type="competitor_profile",
                    ))
        elif category == "rubrics":
            # 评分锚定标准 → L3 方法论层
            for dim in data.get("dimensions", []):
                documents.append(self._make_doc(
                    json.dumps(dim, ensure_ascii=False),
                    source=source, industry=industry, doc_type="methodology", layer="L3",
                ))
        elif category == "terms":
            # 术语表 → L4 报告生成层（兼容 "terms" 和 "glossary" 两种 key）
            term_list = data.get("terms") or data.get("glossary") or []
            for term in term_list:
                documents.append(self._make_doc(
                    json.dumps(term, ensure_ascii=False),
                    source=source, industry="电商通用", doc_type="glossary", layer="L4",
                ))
        elif category in ("tactics", "templates", "schemas"):
            # 战术卡/SWOT/波特五力/对比维度 → L3 方法论层
            documents.append(self._make_doc(
                json.dumps(data, ensure_ascii=False),
                source=source, industry=industry or "电商通用", doc_type="methodology", layer="L3",
            ))
        elif category == "demo":
            documents.append(self._make_doc(
                json.dumps(data, ensure_ascii=False),
                source=source, industry=industry or "电商通用", doc_type=category,
            ))
        else:
            documents.append(self._make_doc(
                json.dumps(data, ensure_ascii=False)[:8000],
                source=source, industry=industry or "电商通用", doc_type=category,
            ))

        return documents

    # ── 竞品数据摄入 ─────────────────────────────

    async def ingest_competitor_data(self, competitor: str, urls: list[str]) -> list[dict]:
        """抓取竞品网页 → 清洗 → 分块"""
        from ...tools.web_scraper import fetch_page, extract_text

        documents = []
        for url in urls:
            try:
                html = await fetch_page(url)
                if not html:
                    continue
                text = extract_text(html)
                text = self._clean_text(text)
                documents.append(self._make_doc(
                    text[:8000], source=url, industry="web_scraped",
                    doc_type="competitor_page", competitor=competitor,
                ))
            except Exception as e:
                logger.warning("Failed to scrape %s: %s", url, e)
        return documents

    def ingest_our_product(self, product_info: dict) -> list[dict]:
        """将我方产品信息纳入 RAG（用于对比分析参照）"""
        doc = self._make_doc(
            json.dumps(product_info, ensure_ascii=False),
            source="our_product_db", industry="internal", doc_type="our_product",
        )
        return [doc]

    # ── 分块 ─────────────────────────────────────

    def chunk_documents(self, documents: list[dict], chunk_size: int = 500, chunk_overlap: int = 50) -> list[dict]:
        """按字符数滑动窗口分块，同时保留 metadata"""
        chunks = []
        for doc in documents:
            content = doc.get("content", "")
            meta = doc.get("metadata", {})
            if len(content) <= chunk_size:
                chunks.append(doc)
            else:
                for i in range(0, len(content), chunk_size - chunk_overlap):
                    chunk_text = content[i:i + chunk_size]
                    if len(chunk_text) < 100:
                        continue
                    chunks.append({
                        "content": chunk_text,
                        "metadata": {**meta, "chunk_start": i},
                    })
        return chunks

    # ── 内部 ─────────────────────────────────────

    @staticmethod
    def _make_doc(content: str, source: str = "", industry: str = "",
                  doc_type: str = "general", competitor: str = "",
                  layer: str = "") -> dict:
        meta: dict[str, str] = {
            "source": source,
            "industry": industry,
            "type": doc_type,
            "competitor": competitor,
        }
        if layer:
            meta["layer"] = layer
        return {
            "content": content[:10000],
            "metadata": meta,
        }

    @staticmethod
    def _clean_text(text: str) -> str:
        text = HTML_TAG_RE.sub("", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
