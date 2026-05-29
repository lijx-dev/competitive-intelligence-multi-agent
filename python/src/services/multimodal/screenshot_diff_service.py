"""
截图像素级差异检测服务 — diffimg/pixelmatch开源实现。
对比竞品网站UI改版，检测Banner变更、定价页更新。
"""

from __future__ import annotations

import asyncio
import logging
from PIL import Image

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15


async def compare_two_screenshots(old_path: str, new_path: str, output_diff_path: str) -> dict:
    """对比两张截图，输出差异百分比和高亮差异图。

    优先使用 diffimg，不可用时回退到 pixelmatch。
    超时保护 15 秒。
    """
    from .path_security import validate_safe_path

    safe_old = validate_safe_path(old_path)
    safe_new = validate_safe_path(new_path)
    if safe_old is None or safe_new is None:
        return {"ok": False, "error": "路径安全校验失败"}

    async def _run_diff() -> dict:
        try:
            from diffimg import diff
            diff_percent = diff(
                safe_old, safe_new, delete_diff_file=False, diff_img_file=output_diff_path
            )
            return {
                "ok": True,
                "diff_percentage": round(diff_percent * 100.0, 2),
                "diff_image_path": output_diff_path,
            }
        except ImportError:
            logger.debug("diffimg 未安装，尝试 pixelmatch")
        except Exception as e:
            logger.warning("diffimg 调用失败: %s，尝试 pixelmatch", e)

        try:
            from pixelmatch.contrib.PIL import pixelmatch
            img1 = Image.open(safe_old).convert("RGBA")
            img2 = Image.open(safe_new).convert("RGBA")
            width, height = img1.size
            diff_img = Image.new("RGBA", (width, height))
            mismatch = pixelmatch(img1, img2, diff_img, threshold=0.1)
            diff_img.save(output_diff_path)
            diff_percent = (mismatch / (width * height)) * 100.0
            return {
                "ok": True,
                "diff_percentage": round(diff_percent, 2),
                "diff_image_path": output_diff_path,
            }
        except Exception as e2:
            logger.exception("截图差异检测失败")
            return {"ok": False, "error": str(e2)}

    try:
        return await asyncio.wait_for(_run_diff(), timeout=_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("截图差异检测超时 (%ds)", _TIMEOUT_SECONDS)
        return {"ok": False, "error": f"超时 {_TIMEOUT_SECONDS}s"}
