"""RAG 服务模块 — 四层架构 MVP (L1+L2)"""

from .core import CompetitorRAG
from .ingestion import DocumentLoader
from .retriever import VectorRetriever
from .rag_agent import RAGEnhancedAgent

__all__ = ["CompetitorRAG", "DocumentLoader", "VectorRetriever", "RAGEnhancedAgent"]
