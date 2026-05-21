"""
Mock 模式管理 — 一键切换生产/Demo 模式。

使用方式：
  Demo 现场三步操作：
    export MOCK_MODE=true
    python -m src.infrastructure.main
    # 打开 Streamlit → 选择竞品 → 点击「启动分析」→ 3秒出完整结果
"""

from __future__ import annotations

import os
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

_MOCK_MODE_ENV_KEY = "MOCK_MODE"
_MOCK_SCENARIO_ENV_KEY = "MOCK_SCENARIO"

# 模块级缓存
_cached_mock_mode: Optional[bool] = None


def is_mock_mode() -> bool:
    """检测当前是否处于 Mock/Demo 模式。

    优先级：环境变量 MOCK_MODE > 模块级缓存
    """
    global _cached_mock_mode
    if _cached_mock_mode is not None:
        return _cached_mock_mode
    val = os.getenv(_MOCK_MODE_ENV_KEY, "false").lower()
    _cached_mock_mode = val in ("true", "1", "yes", "on")
    return _cached_mock_mode


def set_mock_mode(enabled: bool):
    """运行时切换 Mock 模式（同时更新环境变量和模块缓存）。

    注意：此修改仅在当前进程中生效，重启后恢复 .env 设置。
    """
    global _cached_mock_mode
    _cached_mock_mode = enabled
    os.environ[_MOCK_MODE_ENV_KEY] = "true" if enabled else "false"
    logger.info("Mock 模式已%s", "启用（Demo 状态）" if enabled else "关闭（生产状态）")


def get_mock_scenario() -> str:
    """获取指定的 Demo 场景 ID，默认 scenario1"""
    return os.getenv(_MOCK_SCENARIO_ENV_KEY, "scenario1")


def clear_mock_cache():
    """清除 Mock 模式缓存，强制重新读取环境变量"""
    global _cached_mock_mode
    _cached_mock_mode = None


@contextmanager
def MockContext(enabled: bool = True):
    """Mock 模式上下文管理器 — 在 with 块内临时切换模式。

    用法：
        with MockContext(True):
            result = run_analysis()  # 使用 Mock 数据
        # 退出后自动恢复原模式
    """
    previous = is_mock_mode()
    set_mock_mode(enabled)
    try:
        yield
    finally:
        set_mock_mode(previous)
