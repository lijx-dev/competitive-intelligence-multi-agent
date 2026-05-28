#!/usr/bin/env python
"""
RAG 知识库初始化脚本。

用法:
    python -m src.services.rag.seed_kb [kb_path]

默认 kb_path: 项目根目录/产品经理汇报报告/.../ecommerce_kb/
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# 确保项目根在 sys.path
project_root = Path(__file__).resolve().parents[3]  # python/
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("seed_kb")


def main():
    from src.services.rag.core import CompetitorRAG

    # 默认 KB 路径：新公开RAG知识库目录
    default_kb = (
        project_root.parent  # 项目根
        / "knowledge-base-public"
    )
    kb_path = sys.argv[1] if len(sys.argv) > 1 else str(default_kb)

    if not Path(kb_path).exists():
        logger.error("知识库路径不存在: %s", kb_path)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("竞品知识库 RAG 索引初始化")
    logger.info("KB 路径: %s", kb_path)
    logger.info("=" * 60)

    # 初始化 RAG 引擎
    rag = CompetitorRAG()

    # 加载文档
    docs = rag.loader.ingest_directory(kb_path)
    logger.info("已加载 %d 个文档", len(docs))

    if not docs:
        logger.warning("未找到任何文档，请检查 KB 路径")
        sys.exit(1)

    # 索引
    chunk_count = rag.ingest_documents(docs)
    logger.info("已分块索引: %d chunks", chunk_count)

    # 持久化
    rag.retriever.save()
    logger.info("索引已持久化到: %s", rag.index_dir)

    # 统计
    stats = rag.get_stats()
    logger.info("索引统计: %s", stats)

    # 检索测试
    test_query = "直播电商市场规模和增长率"
    results = rag.query(test_query, k=3)
    logger.info("检索测试: '%s' → %d 结果", test_query, len(results))
    for i, r in enumerate(results, 1):
        logger.info("  #%d [%.2f] %s → %s",
                     i, r["confidence"],
                     r["metadata"].get("source", "?"),
                     r["content"][:80])

    logger.info("=" * 60)
    logger.info("RAG 初始化完成！")
    logger.info("=" * 60)


def _flatten_json_to_docs(data: dict, doc_type: str = "general", source: str = "", layer: str = "") -> list[dict]:
    """将嵌套 JSON 模板展平为文档列表，每个顶层 section 为一个独立文档。

    L3/L4 模板文件（SWOT、波特五力、评分锚定等）通常是一个大 JSON，
    此函数将其拆分为更细粒度的文档便于检索。
    """
    docs = []
    if isinstance(data, dict):
        for key, value in data.items():
            content = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            docs.append({
                "content": content[:2000],
                "metadata": {
                    "doc_type": doc_type,
                    "source": source,
                    "section": key,
                    **({"layer": layer} if layer else {}),
                }
            })
    elif isinstance(data, list):
        for i, item in enumerate(data):
            content = json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
            docs.append({
                "content": content[:2000],
                "metadata": {
                    "doc_type": doc_type,
                    "source": source,
                    "section": f"item_{i}",
                    **({"layer": layer} if layer else {}),
                }
            })
    return docs


if __name__ == "__main__":
    main()
