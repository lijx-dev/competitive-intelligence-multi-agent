"""
知识快照存储 — SQLite 持久化分析快照、反馈记录、模板表现。

三张表：
  analysis_snapshots  — 每次分析结果的快照（按 竞品+维度+Agent 索引）
  feedback_records    — 人类反馈记录（确认/纠正 + 置信度变化）
  template_performance — 各 Agent 模板的评分历史
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = "ci_system.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# ── 表初始化 ────────────────────────────────────────────────────

def init_evolution_tables():
    """在 init_db() 中调用，确保进化相关表存在"""
    conn = _conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS analysis_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competitor TEXT NOT NULL,
        dimension TEXT NOT NULL DEFAULT '',
        agent_name TEXT NOT NULL,
        finding TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 0.5,
        template_id TEXT NOT NULL DEFAULT '',
        quality_score REAL DEFAULT 0.0,
        human_verified INTEGER DEFAULT 0,
        feedback_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS evolution_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        action TEXT NOT NULL,
        comment TEXT DEFAULT '',
        old_confidence REAL DEFAULT 0.0,
        new_confidence REAL DEFAULT 0.0,
        operator TEXT DEFAULT 'unknown',
        created_at TEXT NOT NULL,
        FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshots(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS template_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        template_id TEXT NOT NULL,
        template_desc TEXT DEFAULT '',
        performance_score REAL DEFAULT 0.5,
        usage_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        updated_at TEXT NOT NULL,
        UNIQUE(agent_name, template_id)
    )
    """)

    conn.commit()
    conn.close()


# ── analysis_snapshots CRUD ──────────────────────────────────────

def create_analysis_snapshot(
    competitor: str,
    agent_name: str,
    finding: str = "",
    confidence: float = 0.5,
    dimension: str = "",
    template_id: str = "",
    quality_score: float = 0.0,
) -> dict[str, Any]:
    """保存一次分析快照"""
    conn = _conn()
    cur = conn.cursor()
    now = _now()
    cur.execute(
        """INSERT INTO analysis_snapshots
           (competitor, dimension, agent_name, finding, confidence, template_id, quality_score, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (competitor, dimension, agent_name, finding[:2000], confidence, template_id, quality_score, now),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return {
        "id": sid, "competitor": competitor, "dimension": dimension,
        "agent_name": agent_name, "confidence": confidence,
        "template_id": template_id, "created_at": now,
    }


def get_snapshots(
    competitor: str = "", dimension: str = "", agent_name: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按条件查询分析快照"""
    conn = _conn()
    cur = conn.cursor()
    clauses = []
    params: list[Any] = []
    if competitor:
        clauses.append("competitor = ?"); params.append(competitor)
    if dimension:
        clauses.append("dimension = ?"); params.append(dimension)
    if agent_name:
        clauses.append("agent_name = ?"); params.append(agent_name)
    where = " AND ".join(clauses) if clauses else "1=1"
    cur.execute(
        f"SELECT id, competitor, dimension, agent_name, finding, confidence, template_id, quality_score, human_verified, feedback_count, created_at FROM analysis_snapshots WHERE {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "competitor": r[1], "dimension": r[2],
            "agent_name": r[3], "finding": r[4], "confidence": r[5],
            "template_id": r[6], "quality_score": r[7],
            "human_verified": bool(r[8]), "feedback_count": r[9],
            "created_at": r[10],
        }
        for r in rows
    ]


def get_snapshot_stats() -> dict[str, Any]:
    """获取快照统计：总数、已验证数、按Agent分布"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM analysis_snapshots")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM analysis_snapshots WHERE human_verified = 1")
    verified = cur.fetchone()[0]
    cur.execute(
        "SELECT agent_name, COUNT(*) as cnt, AVG(confidence) as avg_conf FROM analysis_snapshots GROUP BY agent_name ORDER BY cnt DESC"
    )
    by_agent = [{"agent": r[0], "count": r[1], "avg_confidence": round(r[2], 3)} for r in cur.fetchall()]
    conn.close()
    return {
        "total_snapshots": total,
        "human_verified": verified,
        "verification_rate": round(verified / max(total, 1), 3),
        "by_agent": by_agent,
    }


# ── evolution_feedback CRUD ──────────────────────────────────────

def create_evolution_feedback(
    snapshot_id: int,
    action: str,
    old_confidence: float = 0.0,
    new_confidence: float = 0.0,
    comment: str = "",
    operator: str = "unknown",
) -> dict[str, Any]:
    """记录一条人类反馈"""
    conn = _conn()
    cur = conn.cursor()
    now = _now()
    cur.execute(
        """INSERT INTO evolution_feedback (snapshot_id, action, comment, old_confidence, new_confidence, operator, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_id, action, comment, old_confidence, new_confidence, operator, now),
    )
    conn.commit()
    fid = cur.lastrowid

    # 同步更新 analysis_snapshots 的 human_verified 和 feedback_count
    cur.execute(
        "UPDATE analysis_snapshots SET human_verified = 1, feedback_count = feedback_count + 1 WHERE id = ?",
        (snapshot_id,),
    )
    conn.commit()
    conn.close()
    return {"id": fid, "snapshot_id": snapshot_id, "action": action, "created_at": now}


def get_feedback_stats() -> dict[str, Any]:
    """反馈统计：总反馈数、确认/纠正比例、准确率趋势"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM evolution_feedback")
    total = cur.fetchone()[0]
    cur.execute("SELECT action, COUNT(*) FROM evolution_feedback GROUP BY action")
    by_action = {r[0]: r[1] for r in cur.fetchall()}
    confirm = by_action.get("confirm", 0)
    correct = by_action.get("correct", 0)

    # 按日期统计趋势
    cur.execute(
        "SELECT DATE(created_at) as d, COUNT(*) as cnt, "
        "SUM(CASE WHEN action='confirm' THEN 1 ELSE 0 END) as confirms "
        "FROM evolution_feedback GROUP BY d ORDER BY d DESC LIMIT 30"
    )
    trend = [
        {"date": r[0], "total": r[1], "confirms": r[2],
         "accuracy": round(r[2] / max(r[1], 1), 3)}
        for r in cur.fetchall()
    ]
    conn.close()
    return {
        "total_feedback": total,
        "confirm_count": confirm,
        "correct_count": correct,
        "accuracy": round(confirm / max(total, 1), 3),
        "trend": trend,
    }


# ── template_performance CRUD ────────────────────────────────────

def upsert_template_performance(
    agent_name: str,
    template_id: str,
    template_desc: str = "",
    performance_score: float = 0.5,
    usage_count: int = 0,
    success_count: int = 0,
) -> dict[str, Any]:
    """更新或插入模板评分"""
    conn = _conn()
    cur = conn.cursor()
    now = _now()
    cur.execute(
        """INSERT INTO template_performance (agent_name, template_id, template_desc, performance_score, usage_count, success_count, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(agent_name, template_id) DO UPDATE SET
             performance_score = excluded.performance_score,
             usage_count = excluded.usage_count,
             success_count = excluded.success_count,
             updated_at = excluded.updated_at""",
        (agent_name, template_id, template_desc, performance_score, usage_count, success_count, now),
    )
    conn.commit()
    conn.close()
    return {"agent_name": agent_name, "template_id": template_id, "score": performance_score}


def get_template_ranking() -> list[dict[str, Any]]:
    """获取全部模板评分排行（按 score 降序）"""
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT agent_name, template_id, template_desc, performance_score, usage_count, success_count, updated_at "
        "FROM template_performance ORDER BY performance_score DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "agent_name": r[0], "template_id": r[1], "template_desc": r[2],
            "performance_score": r[3], "usage_count": r[4],
            "success_count": r[5], "updated_at": r[6],
        }
        for r in rows
    ]


def seed_default_templates():
    """将 prompt_templates.py 中的默认模板同步到 SQLite（仅首次）"""
    from .prompt_templates import TEMPLATE_REGISTRY

    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM template_performance")
    if cur.fetchone()[0] > 0:
        conn.close()
        return  # 已有数据，跳过

    now = _now()
    for agent_name, templates in TEMPLATE_REGISTRY.items():
        for t in templates:
            cur.execute(
                "INSERT OR IGNORE INTO template_performance (agent_name, template_id, template_desc, performance_score, usage_count, success_count, updated_at) VALUES (?, ?, ?, ?, 0, 0, ?)",
                (agent_name, t["id"], t["desc"], t["performance_score"], now),
            )
    conn.commit()
    conn.close()
    logger.info("已初始化默认模板评分数据")
