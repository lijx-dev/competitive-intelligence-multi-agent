"""
PaddleOCR本地OCR服务 — 完全开源免费，无需API key。
中文识别准确率>95%，支持80+语言，断网也能运行。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)
_ocr_instance = None

_TIMEOUT_SECONDS = 20


def get_paddle_ocr(lang: str = "ch"):
    """获取PaddleOCR单例实例。首次调用自动初始化。"""
    global _ocr_instance
    if _ocr_instance is None:
        try:
            from paddleocr import PaddleOCR
            _ocr_instance = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            logger.info("PaddleOCR 初始化成功 (lang=%s)", lang)
        except ImportError:
            logger.warning("PaddleOCR未安装，返回None。安装: pip install paddleocr")
            return None
    return _ocr_instance


async def extract_text_from_image(image_path: str) -> dict:
    """从本地图片路径提取OCR文本+置信度。

    路径安全校验 + 超时保护。
    Returns:
        {"ok": bool, "text": str, "confidence": float, "lines": list[dict]}
    """
    from .path_security import validate_safe_path

    safe_path = validate_safe_path(image_path)
    if safe_path is None:
        return {"ok": False, "text": "", "confidence": 0.0, "lines": [],
                "error": "路径安全校验失败"}

    ocr = get_paddle_ocr()
    if ocr is None:
        return {"ok": False, "text": "", "confidence": 0.0, "lines": []}

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(ocr.ocr, safe_path, True),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("OCR超时 (%ds)", _TIMEOUT_SECONDS)
        return {"ok": False, "text": "", "confidence": 0.0, "lines": [],
                "error": f"超时 {_TIMEOUT_SECONDS}s"}

    lines: list[dict] = []
    total_conf = 0.0
    count = 0
    if result and result[0]:
        for line in result[0]:
            txt = line[1][0]
            conf = line[1][1]
            lines.append({"text": txt, "confidence": conf, "bbox": line[0]})
            total_conf += conf
            count += 1

    avg_conf = total_conf / count if count > 0 else 0.0
    full_text = "\n".join([line["text"] for line in lines])
    return {
        "ok": True,
        "text": full_text,
        "confidence": round(avg_conf, 4),
        "lines": lines,
    }
