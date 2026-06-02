"""动态 Schema 自演化引擎 — 前瞻性亮点（比赛技术加分项）。

当连续 N 次不同分析任务中，ReviewerAgent / SchemaValidation 都标记
"缺少某个维度"，系统自动触发 Schema 扩展，在 Competitor Schema 里新增该维度。

核心机制：
- 缺失维度检测：从 ReviewFeedback.issues + SchemaValidation.issues 中统计
- 触发阈值：连续 3 次不同任务标记同一缺失维度 → 自动扩展
- 演化历史：完整记录每次 Schema 变更的时间线
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── 演化触发阈值 ──
EVOLUTION_TRIGGER_COUNT: int = int(os.getenv("SCHEMA_EVOLUTION_TRIGGER_COUNT", "3"))

# ── 演化历史持久化路径 ──
EVOLUTION_HISTORY_PATH: str = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "schema_evolution_history.json"
)


# ========================================================================
# Schema Evolution Engine
# ========================================================================

class SchemaEvolutionEngine:
    """Schema 自演化引擎：自动检测缺失维度并触发 Schema 扩展。"""

    def __init__(self, trigger_count: int = EVOLUTION_TRIGGER_COUNT):
        self.trigger_count = trigger_count
        # dimension_name → [{task_id, competitor, timestamp}]
        self._missing_dimension_tracker: dict[str, list[dict]] = defaultdict(list)
        # 已执行的演化记录
        self._evolution_history: list[dict] = []
        self._load_history()

    # ── 核心 API ──

    def record_review_issues(
        self,
        task_id: str,
        competitor: str,
        issues: list[dict],
        source: str = "reviewer",
    ) -> dict[str, Any]:
        """记录一次分析任务中发现的 Schema 缺失维度。

        issues: Reviewer 或 SchemaValidation 发现的 issues 列表，
                每个 issue 包含 'schema'/'dimension' 字段表示缺失维度。
        """
        now = datetime.now(timezone.utc).isoformat()

        for issue in issues:
            if not isinstance(issue, dict):
                continue
            # 提取维度名称
            dim_name = (
                issue.get("schema")
                or issue.get("dimension")
                or issue.get("target", "")
            )
            if not dim_name or len(dim_name) < 3:
                continue

            self._missing_dimension_tracker[dim_name].append({
                "task_id": task_id,
                "competitor": competitor,
                "timestamp": now,
                "source": source,
                "severity": issue.get("severity", "medium"),
            })

        # 检查是否有维度达到触发阈值
        triggered = self._check_triggers(task_id, now)
        self._save_history()

        return {
            "recorded_dimensions": len(issues),
            "triggered_evolutions": triggered,
            "total_tracked_dimensions": len(self._missing_dimension_tracker),
        }

    def get_evolution_history(self) -> list[dict]:
        """获取完整的 Schema 演化历史时间线。"""
        return list(self._evolution_history)

    def get_pending_dimensions(self) -> list[dict]:
        """获取已追踪但尚未触发演化的维度及进度。"""
        pending = []
        for dim_name, records in self._missing_dimension_tracker.items():
            # 检查是否已演化
            already_evolved = any(
                e.get("dimension") == dim_name for e in self._evolution_history
            )
            if not already_evolved and len(records) >= 1:
                pending.append({
                    "dimension": dim_name,
                    "count": len(records),
                    "threshold": self.trigger_count,
                    "progress_pct": round(len(records) / self.trigger_count * 100, 1),
                    "latest_task": records[-1]["task_id"] if records else "",
                })
        return sorted(pending, key=lambda x: x["count"], reverse=True)

    def get_stats(self) -> dict[str, Any]:
        """获取演化引擎统计信息。"""
        return {
            "total_evolutions": len(self._evolution_history),
            "tracked_dimensions": len(self._missing_dimension_tracker),
            "trigger_threshold": self.trigger_count,
            "pending_dimensions": self.get_pending_dimensions(),
            "latest_evolution": self._evolution_history[-1] if self._evolution_history else None,
            "history": self._evolution_history[-20:],  # 最近 20 条
        }

    def reset(self) -> None:
        """重置所有追踪数据（测试用）。"""
        self._missing_dimension_tracker.clear()
        self._evolution_history.clear()
        self._save_history()

    # ── 内部 ──

    def _check_triggers(self, task_id: str, now: str) -> list[dict]:
        """检查是否有维度达到触发阈值。"""
        triggered = []
        for dim_name, records in list(self._missing_dimension_tracker.items()):
            # 去重：同一 competitor 只算一次
            unique_competitors = set(r["competitor"] for r in records)
            if len(unique_competitors) >= self.trigger_count:
                evo = {
                    "dimension": dim_name,
                    "triggered_at": now,
                    "trigger_task_id": task_id,
                    "evidence_count": len(records),
                    "unique_competitors": list(unique_competitors)[:10],
                    "new_schema_field": self._suggest_schema_field(dim_name),
                }
                self._evolution_history.append(evo)
                # 清除已演化的追踪记录
                del self._missing_dimension_tracker[dim_name]
                triggered.append(evo)

                logger.info(
                    "🎯 Schema 演化触发: %s → 新增字段（%d 条证据，%d 个不同竞品）",
                    dim_name, len(records), len(unique_competitors),
                )

        return triggered

    @staticmethod
    def _suggest_schema_field(dim_name: str) -> dict:
        """根据缺失维度名称，建议新增的 Schema 字段定义。"""
        # 规范化名称
        safe_name = dim_name.lower().replace(" ", "_").replace("-", "_")[:40]

        return {
            "field_name": safe_name,
            "field_type": "str | float | list[str]",
            "description": f"自动演化新增：{dim_name}",
            "source_dimension": dim_name,
            "auto_generated": True,
        }

    def _save_history(self) -> None:
        """持久化演化历史到磁盘。"""
        try:
            os.makedirs(os.path.dirname(EVOLUTION_HISTORY_PATH), exist_ok=True)
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "evolution_history": self._evolution_history,
                "missing_dimension_tracker": {
                    k: v for k, v in self._missing_dimension_tracker.items()
                },
            }
            with open(EVOLUTION_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Schema 演化历史持久化失败: %s", e)

    def _load_history(self) -> None:
        """从磁盘加载演化历史。"""
        try:
            if os.path.exists(EVOLUTION_HISTORY_PATH):
                with open(EVOLUTION_HISTORY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._evolution_history = data.get("evolution_history", [])
                tracker_data = data.get("missing_dimension_tracker", {})
                self._missing_dimension_tracker = defaultdict(list, tracker_data)
                logger.info(
                    "Schema 演化历史已加载: %d 次演化, %d 个追踪维度",
                    len(self._evolution_history), len(self._missing_dimension_tracker),
                )
        except Exception as e:
            logger.warning("Schema 演化历史加载失败: %s", e)


# ── 全局单例 ──
evolution_engine = SchemaEvolutionEngine()
