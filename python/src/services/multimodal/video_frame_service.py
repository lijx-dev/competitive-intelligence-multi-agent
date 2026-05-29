"""
视频关键帧提取服务 — 基于本地FFmpeg subprocess调用，完全免费。
从发布会视频/演示视频中自动采样提取关键帧图片。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 300


def _check_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


async def extract_key_frames(video_path: str, output_dir: str, fps: int = 1) -> list[str]:
    """从视频中按指定帧率提取关键帧图片。

    fps=1 表示每秒提取1帧。
    FFmpeg 存在性检查 + 超时保护。
    返回所有生成的关键帧图片本地路径列表。
    """
    if not _check_ffmpeg_available():
        logger.warning("FFmpeg 未安装或不在 PATH 中，请先安装 FFmpeg")
        return []

    os.makedirs(output_dir, exist_ok=True)
    output_pattern = os.path.join(output_dir, "frame_%06d.jpg")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        output_pattern,
        "-y",
    ]

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=10,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("视频关键帧提取超时 (%ds)", _TIMEOUT_SECONDS)
        return []

    if proc.returncode != 0:
        logger.warning("FFmpeg返回非零: %s", stderr.decode("utf-8", errors="ignore")[:200])

    frames: list[str] = []
    for p in sorted(Path(output_dir).glob("frame_*.jpg")):
        frames.append(str(p.resolve()))

    logger.info("提取完成，共 %d 帧 -> %s", len(frames), output_dir)
    return frames
