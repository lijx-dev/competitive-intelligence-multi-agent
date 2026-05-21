"""系统自进化模块 — 人类反馈驱动策略调整，系统越用越准。"""

from .engine import EvolutionEngine, engine
from .knowledge_base import (
    init_evolution_tables,
    create_analysis_snapshot,
    create_evolution_feedback,
    get_snapshots,
    get_snapshot_stats,
    get_feedback_stats,
    get_template_ranking,
    upsert_template_performance,
    seed_default_templates,
)
from .prompt_templates import (
    select_template,
    update_template_score,
    get_template_performance,
    get_all_template_performance,
)

__all__ = [
    "EvolutionEngine",
    "engine",
    "init_evolution_tables",
    "create_analysis_snapshot",
    "create_evolution_feedback",
    "get_snapshots",
    "get_snapshot_stats",
    "get_feedback_stats",
    "get_template_ranking",
    "upsert_template_performance",
    "seed_default_templates",
    "select_template",
    "update_template_score",
    "get_template_performance",
    "get_all_template_performance",
]
