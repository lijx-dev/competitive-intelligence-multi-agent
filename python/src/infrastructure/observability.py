"""
ObservabilityHub — 统一可观测性管理器（单例）。

接线5个基础设施组件到Agent工作流：
  EventBus → 事件发布/溯源
  AgentDecisionLogger → 决策日志/异常检测
  AuditSystem → 操作审计/合规
  TokenManager → Token预算/节流
  DAGVisualizer → DAG快照/HTML渲染

所有操作 try-except 包裹，不阻塞 Agent 执行。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

from .event_bus import EventBus
from .agent_logger import AgentDecisionLogger, decision_logger
from .audit_system import AuditSystem, audit_system
from .token_manager import TokenManager, token_manager
from .dag_visualizer import DAGVisualizer, dag_visualizer
from .data_models import (
    AgentDecisionLog, AuditAction, BusEvent, DAGEdge, DAGNodeRuntime,
    DAGSnapshot, EventType, NodeStatus, Severity, TokenUsage,
)

logger = logging.getLogger(__name__)

# ── DAG 节点定义（与 workflow.py 的 12 节点一致）────────────────
DAG_NODES = [
    ("monitor",       "🔍", "监控Agent",        "网页变更检测"),
    ("alert",         "🚨", "告警Agent",        "重大变更推送"),
    ("research",      "📚", "研究Agent",        "5维度深度分析"),
    ("fact_check",    "🟠", "交叉验证Agent",     "Monitor vs Research一致性"),
    ("compare",       "📊", "对比Agent",        "8维度评分矩阵"),
    ("battlecard",    "🎯", "战术卡Agent",      "销售战术生成"),
    ("reviewer",      "🟠", "审查Agent",        "4维度质量评分"),
    ("targeted_fix",  "🟡", "定向修复Agent",    "精准修补"),
    ("citation",      "🟢", "溯源Agent",        "引用验证"),
    ("feishu_push",   "📨", "飞书推送",         "报告卡片推送"),
]

DAG_EDGES = [
    ("monitor", "alert"), ("monitor", "research"),
    ("research", "fact_check"), ("fact_check", "compare"),
    ("compare", "battlecard"), ("battlecard", "reviewer"),
    ("reviewer", "targeted_fix"), ("reviewer", "citation"),
    ("targeted_fix", "reviewer"), ("citation", "feishu_push"),
    ("feishu_push", "__end__"),
]


class ObservabilityHub:
    """统一可观测性管理器 — 全局单例"""

    _instance: Optional[ObservabilityHub] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.event_bus: EventBus = EventBus()
        self.agent_logger: AgentDecisionLogger = decision_logger
        self.audit_system: AuditSystem = audit_system
        self.token_manager: TokenManager = token_manager
        self.dag_viz: DAGVisualizer = dag_visualizer

        # DAG 运行时状态
        self._dag_nodes: dict[str, DAGNodeRuntime] = {}
        self._dag_started_at: Optional[datetime] = None
        self._init_dag()

    def _init_dag(self):
        """初始化 DAG 节点（全部 IDLE 状态）"""
        for nid, icon, label, desc in DAG_NODES:
            self._dag_nodes[nid] = DAGNodeRuntime(
                node_id=nid, icon=icon, label=label,
                status=NodeStatus.IDLE, progress=0.0, duration_ms=0,
            )

    # ── 事件发布（不阻塞主流程）─────────────────────────────────

    def _safe_emit(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning("ObservabilityHub emit error: %s", e)

    async def emit_agent_started(self, agent_name: str, task: str = ""):
        self._dag_started_at = self._dag_started_at or datetime.now()

        # 更新 DAG 状态
        if agent_name in self._dag_nodes:
            self._dag_nodes[agent_name].status = NodeStatus.RUNNING
            self._dag_nodes[agent_name].started_at = datetime.now()

        # 发布事件
        event = BusEvent(
            event_type=EventType.AGENT_STARTED, source=agent_name,
            data={"task": task[:200]},
        )
        await self._safe_emit(self.event_bus.publish, event)

    async def emit_agent_completed(
        self, agent_name: str, output: dict, duration_ms: int = 0,
        input_tokens: int = 0, output_tokens: int = 0, phase: str = "execution",
    ):
        # DAG
        if agent_name in self._dag_nodes:
            node = self._dag_nodes[agent_name]
            node.status = NodeStatus.COMPLETED
            node.completed_at = datetime.now()
            node.duration_ms = duration_ms
            node.progress = 1.0

        # 决策日志
        log = AgentDecisionLog(
            agent_name=agent_name, agent_role=agent_name, phase=phase,
            step_number=len(self.agent_logger._logs) + 1,
            reasoning=str(output)[:500], input_tokens=input_tokens,
            output_tokens=output_tokens, duration_ms=duration_ms,
            status=NodeStatus.COMPLETED,
        )
        self._safe_emit(self.agent_logger.record, log)

        # Token
        if input_tokens + output_tokens > 0:
            self._safe_emit(self.token_manager.consume, agent_name, input_tokens, output_tokens)

        # EventBus
        event = BusEvent(
            event_type=EventType.AGENT_COMPLETED, source=agent_name,
            data={"duration_ms": duration_ms, "input_tokens": input_tokens},
        )
        await self._safe_emit(self.event_bus.publish, event)

    async def emit_agent_failed(self, agent_name: str, error: str, duration_ms: int = 0):
        if agent_name in self._dag_nodes:
            node = self._dag_nodes[agent_name]
            node.status = NodeStatus.FAILED
            node.error_message = error[:200]
            node.duration_ms = duration_ms

        log = AgentDecisionLog(
            agent_name=agent_name, agent_role=agent_name, phase="execution",
            step_number=len(self.agent_logger._logs) + 1,
            reasoning=f"ERROR: {error[:300]}", duration_ms=duration_ms,
            status=NodeStatus.FAILED, error_message=error[:300],
        )
        self._safe_emit(self.agent_logger.record, log)

        event = BusEvent(
            event_type=EventType.AGENT_FAILED, source=agent_name,
            data={"error": error[:200]},
        )
        await self._safe_emit(self.event_bus.publish, event)

    async def emit_token_consumed(self, agent_name: str, input_tokens: int, output_tokens: int):
        self._safe_emit(self.token_manager.consume, agent_name, input_tokens, output_tokens)
        event = BusEvent(
            event_type=EventType.TOKEN_CONSUMED, source=agent_name,
            data={"input_tokens": input_tokens, "output_tokens": output_tokens},
        )
        await self._safe_emit(self.event_bus.publish, event)

    def audit(self, action_type: str, operator: str = "system", target: str = "",
              agent_log_id: str = "", event_id: str = ""):
        self._safe_emit(
            self.audit_system.record,
            AuditAction(action_type=action_type, operator=operator, target=target,
                        linked_agent_log_id=agent_log_id, linked_event_id=event_id,
                        severity=Severity.INFO),
        )

    # ── DAG 快照 ───────────────────────────────────────────────

    def get_dag_snapshot(self) -> DAGSnapshot:
        nodes = list(self._dag_nodes.values())
        edges = [DAGEdge(edge_id=f"e_{s}_{t}", source=s, target=t, animated=False)
                 for s, t in DAG_EDGES]

        completed = sum(1 for n in nodes if n.status == NodeStatus.COMPLETED)
        total_nodes = [nid for nid, _, _, _ in DAG_NODES if nid != "alert"]
        progress = completed / max(len(total_nodes), 1)

        elapsed = 0
        if self._dag_started_at:
            elapsed = int((datetime.now() - self._dag_started_at).total_seconds() * 1000)

        return DAGSnapshot(
            nodes=nodes, edges=edges,
            total_progress=round(progress, 2),
            elapsed_ms=elapsed,
        )

    def get_dag_html(self) -> str:
        snapshot = self.get_dag_snapshot()
        return self.dag_viz.render(snapshot, height=450, interactive=True)

    # ── 统计 ───────────────────────────────────────────────────

    def get_stats(self) -> dict:
        nodes = list(self._dag_nodes.values())
        running = [n.node_id for n in nodes if n.status == NodeStatus.RUNNING]
        completed = [n.node_id for n in nodes if n.status == NodeStatus.COMPLETED]
        failed = [n.node_id for n in nodes if n.status == NodeStatus.FAILED]

        token_statuses = {}
        for nid, _, _, _ in DAG_NODES:
            used = self.token_manager.get_used(nid)
            if used["input"] + used["output"] > 0:
                token_statuses[nid] = used

        agent_stats = self.agent_logger.get_stats()
        audit_stats = self.audit_system.get_stats()

        return {
            "dag": {
                "total_nodes": len(nodes),
                "running": running, "completed": completed, "failed": failed,
                "progress": self.get_dag_snapshot().total_progress,
            },
            "tokens": {
                "agents": token_statuses,
                "total_input": sum(t.get("input", 0) for t in token_statuses.values()),
                "total_output": sum(t.get("output", 0) for t in token_statuses.values()),
            },
            "agents": agent_stats,
            "audit": audit_stats,
            "events_count": len(self.event_bus.get_all()),
        }


# ── 全局单例 ──
hub = ObservabilityHub()
