"""多模态竞品分析服务 — 字节豆包优先 + 开源免费方案打底。

五大免费核心能力 + 安全防护：
  1. doubao_vl_service       — 豆包多模态视觉分析（海报/截图/VL理解）
  2. ocr_service             — PaddleOCR 本地中文识别
  3. screenshot_diff_service — 像素级UI改版差异检测
  4. video_frame_service     — FFmpeg关键帧采样提取
  5. whisper_audio_service   — 本地Whisper音频转录+时间戳
  6. path_security           — 路径穿越攻击防护
  7. image_preprocess        — 大图自动压缩（减少LLM Token消耗）
"""

from .doubao_vl_service import analyze_competitor_poster, analyze_product_screenshot
from .ocr_service import get_paddle_ocr, extract_text_from_image
from .screenshot_diff_service import compare_two_screenshots
from .video_frame_service import extract_key_frames
from .whisper_audio_service import transcribe_audio_local
from .path_security import validate_safe_path
from .image_preprocess import compress_large_image

__all__ = [
    "analyze_competitor_poster",
    "analyze_product_screenshot",
    "get_paddle_ocr",
    "extract_text_from_image",
    "compare_two_screenshots",
    "extract_key_frames",
    "transcribe_audio_local",
    "validate_safe_path",
    "compress_large_image",
]
