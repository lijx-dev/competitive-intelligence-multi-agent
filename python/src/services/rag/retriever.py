"""
L2 向量索引层 — FAISS 向量存储 + 元数据过滤 + 多路召回。

封装 sentence-transformers 嵌入模型和 FAISS IndexFlatIP，
支持持久化保存/加载和增量添加。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class VectorRetriever:
    """向量检索引擎 — FAISS + bge-large-zh-v1.5"""

    def __init__(
        self,
        embed_model: str = "BAAI/bge-large-zh-v1.5",
        index_path: str = "",
        meta_path: str = "",
    ):
        self.embed_model_name = embed_model
        self.index_path = index_path
        self.meta_path = meta_path

        self._embedder = None  # 延迟加载
        self.index = None       # FAISS IndexFlatIP
        self.metadata: list[dict] = []

    # ── 嵌入模型（延迟加载）───────────────────────

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            logger.info("加载嵌入模型: %s", self.embed_model_name)
            self._embedder = SentenceTransformer(self.embed_model_name)
        return self._embedder

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """批量生成文本嵌入向量（已做 L2 归一化，适合内积检索）"""
        embeddings = self.embedder.encode(
            texts, normalize_embeddings=True, show_progress_bar=False,
        )
        return np.array(embeddings, dtype=np.float32)

    # ── FAISS 索引 ─────────────────────────────────

    def add(self, documents: list[dict], embeddings: np.ndarray):
        """增量添加文档到 FAISS 索引"""
        import faiss

        dim = embeddings.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatIP(dim)  # Inner Product (cosine if normalized)

        self.index.add(embeddings)
        self.metadata.extend(documents)
        logger.debug("FAISS 索引: +%d chunks, total=%d", len(documents), self.index.ntotal)

    def search(self, query: str, k: int = 5, filters: Optional[dict] = None) -> list[dict]:
        """向量检索 + 元数据过滤 + 结果格式化"""
        if self.index is None or self.index.ntotal == 0:
            return []

        q_embed = self.embed_documents([query])
        # 检索 2x 以便过滤后有足够结果
        search_k = k * 3 if filters else k
        scores, indices = self.index.search(q_embed, min(search_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            # 元数据过滤
            if filters and not self._match_filters(meta.get("metadata", {}), filters):
                continue
            results.append({
                "content": meta.get("content", "")[:500],
                "metadata": meta.get("metadata", {}),
                "score": float(score),
                "confidence": min(1.0, max(0.0, (float(score) + 1.0) / 2.0)),
            })
            if len(results) >= k:
                break
        return results

    def multi_recall(self, query: str, k_per_strategy: int = 3) -> list[dict]:
        """多路召回：稠密检索 + 关键词检索 → 合并去重"""
        dense = self.search(query, k=k_per_strategy * 2)
        keyword = self._keyword_search(query, k=k_per_strategy * 2)
        # 合并去重（按 content 前 50 字去重）
        seen = set()
        merged = []
        for r in dense + keyword:
            key = r["content"][:50]
            if key not in seen:
                seen.add(key)
                merged.append(r)
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:k_per_strategy * 2]

    def _keyword_search(self, query: str, k: int = 5) -> list[dict]:
        """简易 BM25 风格关键词检索"""
        keywords = set(query.lower().split())
        scored = []
        for doc in self.metadata:
            content = doc.get("content", "").lower()
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scored.append({
                    "content": doc.get("content", "")[:500],
                    "metadata": doc.get("metadata", {}),
                    "score": min(score / len(keywords), 0.9),
                    "confidence": 0.5 + min(score / len(keywords), 0.5) * 0.5,
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    # ── 持久化 ─────────────────────────────────────

    def save(self):
        """保存 FAISS 索引和元数据到磁盘"""
        import faiss
        if self.index is None:
            return
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            for doc in self.metadata:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        logger.info("索引已持久化: %d 文档 → %s", self.index.ntotal, self.index_path)

    def load(self):
        """从磁盘加载 FAISS 索引和元数据"""
        import faiss
        if not os.path.exists(self.index_path):
            raise FileNotFoundError(f"索引文件不存在: {self.index_path}")
        self.index = faiss.read_index(self.index_path)
        self.metadata = []
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.metadata.append(json.loads(line))
        logger.info("索引已加载: %d 文档", self.index.ntotal)

    # ── 内部 ─────────────────────────────────────

    @staticmethod
    def _match_filters(meta: dict, filters: dict) -> bool:
        for key, val in filters.items():
            if meta.get(key) != val:
                return False
        return True
