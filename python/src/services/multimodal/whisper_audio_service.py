"""
本地Whisper音频转录服务 — 完全开源免费。
支持中文音频带时间戳分段转录，无需任何云API。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)
_whisper_model = None

_TIMEOUT_SECONDS = 120

SUPPORTED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".mp4", ".m4b"}


async def transcribe_audio_local(audio_path: str, model_name: str = "base") -> dict:
    """本地加载Whisper tiny/base模型进行音频转录。

    格式校验 + 超时保护。
    第一次运行自动下载模型到本地缓存。
    返回: {"ok": bool, "full_text": str, "language": str, "segments": list[dict]}
    """
    # 格式校验
    ext = audio_path[audio_path.rfind("."):].lower() if "." in audio_path else ""
    if ext not in SUPPORTED_AUDIO_SUFFIXES:
        logger.warning("不支持的音频格式: %s (支持: %s)", ext, SUPPORTED_AUDIO_SUFFIXES)
        return {"ok": False, "error": f"不支持的音频格式: {ext}"}

    global _whisper_model
    try:
        import whisper
        if _whisper_model is None:
            logger.info("正在加载Whisper模型: %s", model_name)
            _whisper_model = whisper.load_model(model_name)

        result = await asyncio.wait_for(
            asyncio.to_thread(_whisper_model.transcribe, audio_path, word_timestamps=True),
            timeout=_TIMEOUT_SECONDS,
        )
        segments: list[dict] = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg.get("start", 0.0), 2),
                "end": round(seg.get("end", 0.0), 2),
                "text": seg.get("text", ""),
            })

        return {
            "ok": True,
            "full_text": result.get("text", ""),
            "language": result.get("language", ""),
            "segments": segments,
        }
    except asyncio.TimeoutError:
        logger.warning("音频转录超时 (%ds)", _TIMEOUT_SECONDS)
        return {"ok": False, "error": f"超时 {_TIMEOUT_SECONDS}s"}
    except ImportError:
        logger.warning("Whisper未安装。安装: pip install openai-whisper")
        return {"ok": False, "error": "whisper not installed"}
    except Exception as e:
        logger.exception("音频转录失败")
        return {"ok": False, "error": str(e)}
