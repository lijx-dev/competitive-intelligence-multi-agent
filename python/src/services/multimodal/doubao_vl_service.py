"""
豆包多模态分析服务 — 字节原生优先，复用LLMFactory。
海报分析、卖点提取、定价识别全部用豆包多模态完成。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30


async def analyze_competitor_poster(poster_path: str) -> dict:
    """分析竞品宣传海报，返回结构化JSON结果。

    优先豆包多模态，失败自动降级到通义VL。
    路径校验 + 大图压缩 + 超时保护。
    """
    from ..llm.llm_factory import LLMFactory
    from .path_security import validate_safe_path
    from .image_preprocess import compress_large_image

    # 路径安全校验
    safe_path = validate_safe_path(poster_path)
    if safe_path is None:
        return {"ok": False, "error": "路径安全校验失败", "path": poster_path}

    # 大图自动压缩
    compressed_path = safe_path
    try:
        fd, tmp = tempfile.mkstemp(suffix=".jpg", prefix="vl_compress_")
        os.close(fd)
        compressed_path = await compress_large_image(safe_path, tmp) or safe_path
    except Exception:
        compressed_path = safe_path

    vl_llm = LLMFactory.get_multimodal_llm("poster_analysis")
    prompt = """你是专业的竞品分析师，请仔细分析这张竞品宣传海报，严格以JSON格式返回以下字段：
{
    "product_name": "产品名称和版本号",
    "core_selling_points": ["数组形式的核心卖点列表"],
    "pricing_info": "从海报提取的定价信息，没有就填空字符串",
    "target_user_hint": "暗示的目标用户群体",
    "visual_style": {
        "main_colors": ["主色调列表"],
        "layout_style": "排版布局类型描述",
        "emotion_tone": "视觉情感调性描述"
    },
    "differentiation_notes": "与上一代版本的差异化信息备注"
}
只返回纯JSON，不要任何markdown、不要其他解释文字。"""
    try:
        result_text = await asyncio.wait_for(
            vl_llm.ainvoke_multimodal(compressed_path, prompt),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("海报分析超时 (%ds)", _TIMEOUT_SECONDS)
        return {"ok": False, "error": f"超时 {_TIMEOUT_SECONDS}s"}

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning("多模态返回非JSON: %s", result_text[:200])
        return {"raw_text": result_text, "parse_success": False}


async def analyze_product_screenshot(image_path: str, context: str = "") -> dict:
    """分析竞品产品截图，提取功能特征和UI设计要素。"""
    from ..llm.llm_factory import LLMFactory
    from .path_security import validate_safe_path

    safe_path = validate_safe_path(image_path)
    if safe_path is None:
        return {"ok": False, "error": "路径安全校验失败"}

    vl_llm = LLMFactory.get_multimodal_llm("screenshot_analysis")
    prompt = f"""你是专业的竞品UI分析师。请分析这张竞品产品截图，返回JSON：
{{
    "feature_detected": ["检测到的功能列表"],
    "ui_patterns": ["UI设计模式"],
    "data_display": "数据可视化方式描述",
    "user_flow_hint": "推测的用户操作流程",
    "differentiation": "与我方产品UI的显著差异"
}}
上下文: {context}
只返回纯JSON。"""
    try:
        result_text = await asyncio.wait_for(
            vl_llm.ainvoke_multimodal(safe_path, prompt),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("截图分析超时 (%ds)", _TIMEOUT_SECONDS)
        return {"ok": False, "error": f"超时 {_TIMEOUT_SECONDS}s"}

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning("多模态截图分析返回非JSON: %s", result_text[:200])
        return {"raw_text": result_text, "parse_success": False}
