"""大图片自动压缩预处理 — 减少多模态LLM Token消耗量。"""

from __future__ import annotations

import logging
from PIL import Image

logger = logging.getLogger(__name__)


async def compress_large_image(
    input_path: str, output_path: str, max_width: int = 1920, quality: int = 85
) -> str | None:
    """超过 max_width 像素的大图片自动等比缩放到指定宽度，JPEG质量压缩。

    返回压缩后的路径；失败或已足够小时返回原路径。
    """
    try:
        img = Image.open(input_path)
        width, height = img.size
        if width <= max_width:
            return input_path

        new_height = int(height * (max_width / width))
        resized = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        resized.save(output_path, "JPEG", quality=quality, optimize=True)
        logger.info("大图片压缩完成: %dx%d -> %dx%d", width, height, max_width, new_height)
        return output_path
    except Exception as e:
        logger.warning("图片压缩失败，返回原路径继续: %s", e)
        return input_path
