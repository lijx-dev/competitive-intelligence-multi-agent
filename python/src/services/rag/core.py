"""
RAG 核心引擎 — 统一的文档索引/检索入口。

封装 FAISS 向量存储 + bge-large-zh-v1.5 嵌入模型，
提供 ingest / query / batch_query 统一接口。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .ingestion import DocumentLoader
from .retriever import VectorRetriever

logger = logging.getLogger(__name__)

# 优先本地缓存，不可用时回退到轻量多语言模型
_LOCAL_CACHE = os.path.expanduser("~/.cache/huggingface/hub/")
_HAS_BGE = os.path.exists(_LOCAL_CACHE) and any("bge-large-zh" in d for d in os.listdir(_LOCAL_CACHE))
DEFAULT_EMBED_MODEL = "BAAI/bge-large-zh-v1.5" if _HAS_BGE else "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_INDEX_DIR = os.getenv("RAG_INDEX_PATH", str(Path(__file__).parent.parent.parent.parent / "data" / "rag_index"))


class CompetitorRAG:
    """竞品知识 RAG 引擎 — 单例"""

    _instance: Optional[CompetitorRAG] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        embed_model: str = DEFAULT_EMBED_MODEL,
        index_dir: str = DEFAULT_INDEX_DIR,
    ):
        if self._initialized:
            return
        self._initialized = True

        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.embed_model_name = embed_model

        self.loader = DocumentLoader()
        self.retriever = VectorRetriever(
            embed_model=embed_model,
            index_path=str(self.index_dir / "faiss.index"),
            meta_path=str(self.index_dir / "metadata.jsonl"),
        )
        self._doc_count = 0

        # 尝试加载已有索引
        try:
            self.retriever.load()
            self._doc_count = len(self.retriever.metadata)
            logger.info("RAG 索引已加载: %d 文档", self._doc_count)
        except Exception:
            logger.info("RAG 索引未找到，请运行 seed_kb 初始化")

    # ── 索引 ───────────────────────────────────────

    def ingest_documents(self, documents: list[dict]) -> int:
        """批量摄入文档（chunk → embed → FAISS）"""
        if not documents:
            return 0
        chunks = self.loader.chunk_documents(documents, chunk_size=500, chunk_overlap=50)
        embeddings = self.retriever.embed_documents([c["content"] for c in chunks])
        self.retriever.add(chunks, embeddings)
        self._doc_count = len(self.retriever.metadata)
        logger.info("已索引 %d 个文档 → %d chunks", len(documents), len(chunks))
        return len(chunks)

    # ── 检索 ───────────────────────────────────────

    def query(self, query: str, k: int = 5, filters: Optional[dict] = None) -> list[dict]:
        """单次检索：稠密向量 + 元数据过滤"""
        return self.retriever.search(query, k=k, filters=filters)

    def batch_query(self, queries: list[str], k: int = 5) -> list[list[dict]]:
        """批量检索"""
        return [self.retriever.search(q, k=k) for q in queries]

    def multi_recall(self, query: str, k_per_strategy: int = 3) -> list[dict]:
        """多路召回：稠密 + 关键词"""
        return self.retriever.multi_recall(query, k_per_strategy=k_per_strategy)

    # ── 统计 ───────────────────────────────────────

    @property
    def doc_count(self) -> int:
        return self._doc_count

    def get_stats(self) -> dict:
        return {
            "doc_count": self._doc_count,
            "index_path": str(self.index_dir),
            "embed_model": self.embed_model_name,
            "industries": list(set(
                m.get("metadata", {}).get("industry", "") for m in self.retriever.metadata
                if m.get("metadata", {}).get("industry"))),
        }


# 全局单例
rag = CompetitorRAG()
