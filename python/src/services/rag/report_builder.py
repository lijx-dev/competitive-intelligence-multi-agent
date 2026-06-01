"""
L4 报告生成层 — 模板约束 + 术语标准化 + 格式规范。

提供工具函数供 BattlecardAgent / CompareAgent / Export 模块使用。
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── 报告结构模板 ──────────────────────────────────────────

REPORT_TEMPLATE = {
    "sections": [
        {"id": "executive_summary", "title": "摘要", "required": True},
        {"id": "competitor_overview", "title": "竞品概览", "required": True},
        {"id": "comparison_matrix", "title": "对比矩阵", "required": True},
        {"id": "battlecard", "title": "销售战术卡", "required": True},
        {"id": "research_insights", "title": "研究洞察", "required": False},
        {"id": "monitor_changes", "title": "变更监控", "required": False},
        {"id": "citation_report", "title": "引用溯源", "required": False},
        {"id": "quality_review", "title": "质量审查", "required": False},
    ]
}


def format_report_section(
    section_id: str,
    data: dict | list | str,
    title: str = "",
    wrap_markdown: bool = False,
) -> str:
    """格式化报告单个章节。

    Args:
        section_id: 章节标识（如 "comparison_matrix"）
        data: 章节数据
        title: 自定义标题（为空则使用模板默认标题）
        wrap_markdown: 是否使用 Markdown 包装

    Returns:
        格式化后的章节文本
    """
    # 查找章节标题
    section_title = title
    if not section_title:
        for sec in REPORT_TEMPLATE["sections"]:
            if sec["id"] == section_id:
                section_title = sec["title"]
                break
    if not section_title:
        section_title = section_id

    parts = [f"## {section_title}"]

    if isinstance(data, str):
        parts.append(data)
    elif isinstance(data, dict):
        if section_id == "comparison_matrix" and "dimensions" in data:
            parts.append(_format_matrix_markdown(data))
        elif section_id == "battlecard":
            parts.append(_format_battlecard_markdown(data))
        else:
            parts.append(f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                parts.append(f"- {json.dumps(item, ensure_ascii=False)[:200]}")
            else:
                parts.append(f"- {str(item)[:200]}")
    else:
        parts.append(str(data)[:5000])

    return "\n\n".join(parts)


def _format_matrix_markdown(matrix: dict) -> str:
    """将对比矩阵格式化为 Markdown 表格"""
    lines = ["| 维度 | 我方评分 | 竞品评分 | 说明 |", "|------|---------|----------|------|"]
    for dim in matrix.get("dimensions", []):
        notes = dim.get("notes", "")[:80].replace("|", "/")
        lines.append(
            f"| {dim.get('dimension', '?')} "
            f"| {dim.get('our_score', '-')} "
            f"| {dim.get('competitor_score', '-')} "
            f"| {notes} |"
        )
    overall = matrix.get("overall_assessment", "")
    if overall:
        lines.append(f"\n**整体评估**：{overall}")
    return "\n".join(lines)


def _format_battlecard_markdown(card: dict) -> str:
    """将战术卡格式化为 Markdown"""
    parts = []
    for section in ["our_strengths", "our_weaknesses", "competitor_strengths", "competitor_weaknesses", "key_differentiators"]:
        items = card.get(section, [])
        if items:
            label = {
                "our_strengths": "✅ 我方优势", "our_weaknesses": "⚠️ 我方劣势",
                "competitor_strengths": "📈 竞品优势", "competitor_weaknesses": "❌ 竞品劣势",
                "key_differentiators": "🎯 核心差异化",
            }.get(section, section)
            parts.append(f"### {label}")
            for item in items:
                parts.append(f"- {item}")

    objections = card.get("objection_handling", {})
    if objections:
        parts.append("### 🗣️ 异议处理话术")
        for question, answer in objections.items():
            parts.append(f"**Q: {question}**\nA: {answer}")

    pitch = card.get("elevator_pitch", "")
    if pitch:
        parts.append(f"### 🎙️ 电梯Pitch\n{pitch}")

    return "\n\n".join(parts)


def normalize_report_terms(
    report_sections: dict[str, Any],
    glossary_docs: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """对整个报告的所有文本章节做术语标准化。

    Args:
        report_sections: {section_id: content} 格式的报告
        glossary_docs: 术语表检索结果

    Returns:
        标准化后的报告
    """
    from .rag_agent import RAGEnhancedAgent

    normalized = {}
    for key, value in report_sections.items():
        if isinstance(value, str):
            normalized[key] = RAGEnhancedAgent.normalize_terms(value, glossary_docs)
        elif isinstance(value, dict):
            # 对 dict 中的字符串值做标准化
            normalized_dict = {}
            for k, v in value.items():
                if isinstance(v, str):
                    normalized_dict[k] = RAGEnhancedAgent.normalize_terms(v, glossary_docs)
                else:
                    normalized_dict[k] = v
            normalized[key] = normalized_dict
        else:
            normalized[key] = value

    return normalized
