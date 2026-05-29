"""多模态路径安全白名单防护 — 禁止路径穿越攻击。"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# 默认多模态素材根目录
DEFAULT_MULTIMODAL_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "multimodal")
)
os.makedirs(DEFAULT_MULTIMODAL_ROOT, exist_ok=True)


def validate_safe_path(user_input_path: str, allowed_root: str = DEFAULT_MULTIMODAL_ROOT) -> str | None:
    """校验用户输入的路径是否在白名单根目录下，阻止 ../../etc/passwd 路径穿越。

    校验失败返回 None，校验成功返回规范化的绝对路径。
    """
    try:
        normalized = os.path.abspath(os.path.realpath(user_input_path))
        allowed_normalized = os.path.abspath(os.path.realpath(allowed_root))
        if not normalized.startswith(allowed_normalized + os.sep) and normalized != allowed_normalized:
            logger.warning(
                "路径穿越攻击拦截: input=%s allowed_root=%s", user_input_path, allowed_root
            )
            return None
        return normalized
    except Exception as e:
        logger.warning("路径校验异常: %s", e)
        return None


# ── P1-4: 多模态上传文件后缀白名单 ──
ALLOWED_UPLOAD_SUFFIXES: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mp3", ".wav", ".flac"
}


def validate_allowed_suffix(path: str) -> bool:
    """禁止上传 .php/.exe 等危险后缀文件。"""
    suffix = os.path.splitext(path.lower())[1]
    return suffix in ALLOWED_UPLOAD_SUFFIXES
