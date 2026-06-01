"""
RAGEnhancedAgent — RAG 增强的 Agent 基类。

提供 augment_prompt() 和 citations_from_docs() 两个核心方法，
所有需要 RAG 能力的 Agent 继承此类。
"""

from __future__ import annotations

import json
from typing import Any


class RAGEnhancedAgent:
    """RAG 增强的 Agent 基类

    使用方式:
        class MyAgent(RAGEnhancedAgent):
            async def analyze(self, ...):
                docs = rag.query("竞品查询")
                prompt = self.augment_prompt(original_prompt, docs)
                response = await llm.ainvoke([SystemMessage(content=prompt), ...])
    """

    @staticmethod
    def augment_prompt(original_prompt: str, context_docs: list[dict], max_docs: int = 5) -> str:
        """将检索到的知识注入到 Agent 的 Prompt 中。

        Args:
            original_prompt: 原始任务 prompt
            context_docs: RAG 检索返回的文档列表 [{"content": ..., "metadata": ..., "confidence": ...}]
            max_docs: 最多注入文档数

        Returns:
            增强后的 prompt 字符串
        """
        if not context_docs:
            return original_prompt

        context_parts = ["## 参考竞品知识（从知识库检索）"]
        for i, doc in enumerate(context_docs[:max_docs], 1):
            meta = doc.get("metadata", {})
            source = meta.get("source", "unknown")
            confidence = doc.get("confidence", 0)
            content = doc.get("content", "")[:800]
            context_parts.append(
                f"### 文档 {i} [来源: {source}] [置信度: {confidence:.0%}]\n{content}"
            )

        context_block = "\n\n".join(context_parts)
        return f"{context_block}\n\n---\n\n## 原始分析任务\n{original_prompt}"

    @staticmethod
    def citations_from_docs(docs: list[dict]) -> list[dict]:
        """从检索文档生成引用信息（供 Citation Agent 使用）。"""
        citations = []
        for doc in docs:
            meta = doc.get("metadata", {})
            citations.append({
                "source": meta.get("source", "unknown"),
                "content_preview": doc.get("content", "")[:200],
                "confidence": doc.get("confidence", 0),
                "industry": meta.get("industry", ""),
                "type": meta.get("type", ""),
            })
        return citations

    @staticmethod
    def normalize_terms(text: str, glossary_docs: Optional[list[dict]] = None) -> str:
        """术语标准化：将文本中的非标准术语替换为知识库定义的规范术语。

        从 RAG 检索术语表（doc_type="glossary"），对输入文本做术语替换。
        不修改已符合规范的术语。

        Args:
            text: 需要标准化的原始文本
            glossary_docs: 术语表检索结果（为空则自动从 RAG 检索）

        Returns:
            标准化后的文本
        """
        if not text:
            return text

        if glossary_docs is None:
            try:
                from .core import rag
                glossary_docs = rag.retriever.search(
                    "电商术语 标准定义", k=20, filters={"doc_type": "glossary"}
                )
            except Exception:
                glossary_docs = []

        if not glossary_docs:
            return text

        result = text
        for doc in glossary_docs:
            meta = doc.get("metadata", {})
            try:
                term_data = json.loads(doc.get("content", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue

            term_cn = term_data.get("term_cn") or term_data.get("term") or term_data.get("chinese") or ""
            term_en = term_data.get("term_en") or term_data.get("english") or term_data.get("abbreviation") or ""
            if not term_cn:
                continue

            # 替换常见非标准表述（仅当不冲突时）
            aliases = term_data.get("aliases", [])
            if isinstance(aliases, list):
                for alias in aliases:
                    if alias and alias != term_cn and alias in result:
                        result = result.replace(alias, term_cn)
            # 英文缩写加注中文术语
            if term_en and term_en in result and term_cn not in result:
                result = result.replace(
                    term_en, f"{term_cn}（{term_en}）"
                )

        return result
