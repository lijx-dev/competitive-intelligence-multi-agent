"""Mock 模式 — 一键切换 Demo/生产，确保 Demo 零失败。

使用方式：
    # Demo 现场：
    export MOCK_MODE=true
    python -m src.infrastructure.main
    # 3秒出完整竞品分析报告
"""

from .mode import is_mock_mode, set_mock_mode, get_mock_scenario, MockContext, clear_mock_cache
from .data import get_scenario, list_scenarios
from .generator import MockDataGenerator

__all__ = [
    "is_mock_mode",
    "set_mock_mode",
    "get_mock_scenario",
    "MockContext",
    "clear_mock_cache",
    "get_scenario",
    "list_scenarios",
    "MockDataGenerator",
]
