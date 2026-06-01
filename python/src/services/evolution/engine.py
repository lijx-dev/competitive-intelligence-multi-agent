"""
EvolutionEngine — 系统自进化核心引擎。

最小可用闭环：
  人类反馈"分析偏了" → 记录反馈 → 降低该 Agent 该场景的置信度
  → 下次同样场景选择不同 Prompt 模板 → 置信度逐步恢复

设计原则：
  - 所有操作 try-except 包裹，不阻塞主分析流程
  - 依赖注入 ObservabilityHub（可选），无 hub 也能独立运行
  - 与 workflow.py / server.py 松耦合
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from . import knowledge_base as kb
from . import prompt_templates as pt

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """自进化引擎 — 全局单例"""

    _instance: Optional[EvolutionEngine] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, observability_hub: Any = None):
        if self._initialized:
            return
        self._initialized = True
        self._hub = observability_hub

    # ── 分析结果保存 ─────────────────────────────────────────

    def add_analysis_result(
        self,
        competitor: str,
        dimension: str,
        finding: str,
        confidence: float,
        agent_name: str,
        template_id: str = "",
        quality_score: float = 0.0,
    ) -> dict:
        """保存一次分析快照。

        高置信度（≥0.8）自动提交，低置信度标记待审核。
        """
        try:
            snapshot = kb.create_analysis_snapshot(
                competitor=competitor,
                agent_name=agent_name,
                finding=finding,
                confidence=confidence,
                dimension=dimension,
                template_id=template_id,
                quality_score=quality_score,
            )

            # 同步更新模板使用计数
            if template_id:
                kb.upsert_template_performance(
                    agent_name=agent_name,
                    template_id=template_id,
                    usage_count=1,
                )

            status = "auto_committed" if confidence >= 0.8 else "pending_review"
            logger.debug(
                "Evolution: saved snapshot #%s [%s] %s/%s conf=%.2f %s",
                snapshot["id"], agent_name, competitor, dimension, confidence, status,
            )
            return {"status": status, "snapshot": snapshot}
        except Exception as e:
            logger.warning("Evolution add_analysis_result failed: %s", e)
            return {"status": "error", "error": str(e)[:200]}

    def add_batch_results(self, results: list[dict]) -> list[dict]:
        """批量保存分析结果。

        每项格式: {competitor, dimension, finding, confidence, agent_name, template_id, quality_score}
        """
        return [self.add_analysis_result(**r) for r in results]

    # ── 人类反馈处理 ─────────────────────────────────────────

    def process_human_feedback(
        self,
        snapshot_id: int,
        is_correct: bool,
        comment: str = "",
        operator: str = "feishu_user",
    ) -> dict:
        """处理人类反馈：确认正确 → 提升置信度 +0.1，标记错误 → 降低 -0.2。

        同时更新关联模板的 performance_score。
        """
        try:
            snapshots = kb.get_snapshots(limit=1)
            target = None
            for s in snapshots:
                if s["id"] == snapshot_id:
                    target = s
                    break

            if not target:
                # 回退：直接查 DB
                import sqlite3
                conn = sqlite3.connect(kb.DB_PATH, check_same_thread=False)
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, competitor, dimension, agent_name, confidence, template_id FROM analysis_snapshots WHERE id = ?",
                    (snapshot_id,),
                )
                row = cur.fetchone()
                conn.close()
                if not row:
                    return {"status": "error", "error": f"snapshot #{snapshot_id} not found"}
                target = {
                    "id": row[0], "competitor": row[1], "dimension": row[2],
                    "agent_name": row[3], "confidence": row[4], "template_id": row[5],
                }

            old_conf = target["confidence"]
            new_conf = min(1.0, old_conf + 0.10) if is_correct else max(0.0, old_conf - 0.20)

            # 记录反馈
            kb.create_evolution_feedback(
                snapshot_id=snapshot_id,
                action="confirm" if is_correct else "correct",
                old_confidence=old_conf,
                new_confidence=new_conf,
                comment=comment,
                operator=operator,
            )

            # 更新模板评分
            agent_name = target.get("agent_name", "")
            template_id = target.get("template_id", "")
            if agent_name and template_id:
                pt.update_template_score(agent_name, template_id, is_correct)
                # 同步 DB
                new_t_score = pt.get_template_performance(agent_name)
                for t in new_t_score:
                    if t["id"] == template_id:
                        kb.upsert_template_performance(
                            agent_name=agent_name,
                            template_id=template_id,
                            performance_score=t["score"],
                            success_count=1 if is_correct else 0,
                        )
                        break

            logger.info(
                "Evolution feedback: snapshot #%s [%s] %s → conf %.2f→%.2f",
                snapshot_id, agent_name, "confirmed" if is_correct else "corrected",
                old_conf, new_conf,
            )
            return {
                "status": "confirmed" if is_correct else "corrected",
                "snapshot_id": snapshot_id,
                "old_confidence": old_conf,
                "new_confidence": new_conf,
            }
        except Exception as e:
            logger.warning("Evolution process_human_feedback failed: %s", e)
            return {"status": "error", "error": str(e)[:200]}

    # ── 置信度调整 ───────────────────────────────────────────

    def get_confidence_adjustment(
        self, agent_name: str, competitor: str = "", dimension: str = ""
    ) -> float:
        """查询该 Agent 在该场景下的置信度调整系数（0.5~1.5）。

        基于历史反馈的准确率计算：准确率越高系数越接近 1.5（加权），
        准确率越低系数越接近 0.5（降权）。
        """
        try:
            # 精确匹配
            snaps = kb.get_snapshots(
                agent_name=agent_name, competitor=competitor, dimension=dimension, limit=20,
            )
            if not snaps:
                # 回退到仅按 agent_name
                snaps = kb.get_snapshots(agent_name=agent_name, limit=20)

            if not snaps:
                return 1.0  # 无历史数据，不调整

            verified = [s for s in snaps if s["human_verified"]]
            if len(verified) < 2:
                return 1.0

            # 计算反馈准确率
            correct = sum(1 for s in verified if s["confidence"] >= 0.7)
            accuracy = correct / max(len(verified), 1)

            # 映射到 0.5 ~ 1.5
            coefficient = 0.5 + accuracy
            return round(max(0.5, min(1.5, coefficient)), 2)
        except Exception as e:
            logger.warning("Evolution get_confidence_adjustment failed: %s", e)
            return 1.0

    # ── 模板推荐 ──────────────────────────────────────────────

    def suggest_prompt_template(
        self, agent_name: str, competitor: str = "", dimension: str = ""
    ) -> Optional[dict]:
        """根据历史反馈推荐最优 Prompt 模板。

        优先从 SQLite 读取评分（含运行时更新），回退到内存注册表。
        """
        try:
            # 优先用 DB 评分
            ranking = kb.get_template_ranking()
            agent_templates = [r for r in ranking if r["agent_name"] == agent_name]
            if agent_templates:
                best = agent_templates[0]
                return {
                    "template_id": best["template_id"],
                    "desc": best["template_desc"],
                    "score": best["performance_score"],
                    "source": "db",
                }

            # 回退：内存加权随机
            chosen = pt.select_template(agent_name, competitor, dimension)
            if chosen:
                return {
                    "template_id": chosen["id"],
                    "desc": chosen["desc"],
                    "score": chosen.get("performance_score", 0.5),
                    "source": "memory",
                }
            return None
        except Exception as e:
            logger.warning("Evolution suggest_prompt_template failed: %s", e)
            return None

    # ── 进化统计 ──────────────────────────────────────────────

    def get_evolution_stats(self) -> dict:
        """返回进化统计：总分析数 / 人类验证数 / 知识覆盖率 / 准确率趋势"""
        try:
            snap_stats = kb.get_snapshot_stats()
            fb_stats = kb.get_feedback_stats()
            return {
                "total_snapshots": snap_stats["total_snapshots"],
                "human_verified": snap_stats["human_verified"],
                "verification_rate": snap_stats["verification_rate"],
                "by_agent": snap_stats["by_agent"],
                "feedback": fb_stats,
                "knowledge_coverage": len(snap_stats.get("by_agent", [])),
            }
        except Exception as e:
            logger.warning("Evolution get_evolution_stats failed: %s", e)
            return {"error": str(e)[:200], "total_snapshots": 0, "human_verified": 0}

    # ── 导出 ──────────────────────────────────────────────────

    def export_report(self) -> dict:
        """导出完整进化报告（JSON 格式）"""
        try:
            return {
                "generated_at": kb._now(),
                "stats": self.get_evolution_stats(),
                "template_ranking": kb.get_template_ranking(),
                "recent_snapshots": kb.get_snapshots(limit=30),
            }
        except Exception as e:
            logger.warning("Evolution export_report failed: %s", e)
            return {"error": str(e)[:200]}


# ── 全局单例 ──
engine = EvolutionEngine()
