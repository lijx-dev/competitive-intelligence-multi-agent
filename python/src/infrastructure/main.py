"""
基础设施集成入口 — FastAPI 路由 + Streamlit 嵌入示例 + 部署说明。

运行方式:
  1. 嵌入现有 FastAPI 后端:
     from src.infrastructure.main import register_routes
     register_routes(app)

  2. Streamlit 中嵌入 DAG 可视化:
     from src.infrastructure.main import render_dag_for_streamlit
     st.components.v1.html(render_dag_for_streamlit(snapshot), height=600)

  3. 独立测试:
     python -m src.infrastructure.main
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .data_models import (
    AgentDecisionLog,
    AuditAction,
    AuditFilter,
    BusEvent,
    ComplianceRule,
    DAGEdge,
    DAGNodeRuntime,
    DAGSnapshot,
    DecisionLogFilter,
    EventType,
    NodeStatus,
    Severity,
    TokenBudgetStatus,
    TokenQuota,
    TokenTrendReport,
)
from .agent_logger import decision_logger
from .event_bus import event_bus
from .token_manager import token_manager
from .audit_system import audit_system
from .dag_visualizer import dag_visualizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/infra", tags=["infrastructure"])


# ============================================================
# FastAPI 路由
# ============================================================

# ---------- Agent 决策日志 ----------

@router.post("/agent-logs", summary="记录 Agent 决策日志")
async def record_agent_log(log: AgentDecisionLog):
    log_id = decision_logger.record(log)
    return {"status": "recorded", "log_id": log_id}


@router.get("/agent-logs", summary="查询 Agent 决策日志")
async def query_agent_logs(
    agent_name: str = "", phase: str = "", status: str = "",
    min_duration_ms: int = 0, max_duration_ms: int = 0,
    has_anomaly: bool | None = None, keyword: str = "",
    limit: int = Query(default=100, le=1000),
):
    flt = DecisionLogFilter(keyword=keyword)
    if agent_name:
        flt.agent_names = [agent_name]
    if phase:
        flt.phases = [phase]
    if status:
        flt.statuses = [NodeStatus(s) for s in status.split(",")]
    if min_duration_ms:
        flt.min_duration_ms = min_duration_ms
    if max_duration_ms:
        flt.max_duration_ms = max_duration_ms
    if has_anomaly is not None:
        flt.has_anomaly = has_anomaly

    logs = decision_logger.query(flt)[:limit]
    return {
        "total": len(logs),
        "logs": [l.model_dump(mode="json") for l in logs],
    }


@router.get("/agent-logs/timeline", summary="时序回溯")
async def get_timeline():
    return {"timeline": decision_logger.timeline_replay()}


@router.get("/agent-logs/anomalies", summary="异常检测报告")
async def get_anomaly_report():
    report = decision_logger.detect_anomalies()
    return report.model_dump(mode="json")


@router.get("/agent-logs/export", summary="导出决策日志")
async def export_agent_logs(format: str = Query(default="json", pattern="^(json|csv)$")):
    if format == "csv":
        return {"data": decision_logger.export_csv()}
    return {"data": decision_logger.export_json()}


@router.get("/agent-logs/stats", summary="决策日志统计")
async def get_agent_log_stats():
    return decision_logger.get_stats()


# ---------- EventBus ----------

@router.post("/events/publish", summary="发布事件")
async def publish_event(event: BusEvent):
    await event_bus.publish(event)
    return {"status": "published", "event_id": event.event_id}


@router.get("/events", summary="查询事件")
async def query_events(
    event_type: str = "", source: str = "", limit: int = Query(default=100),
):
    et = EventType(event_type) if event_type else None
    events = event_bus.get_events(event_type=et, source=source or None)
    return {"total": len(events), "events": [e.model_dump(mode="json") for e in events[-limit:]]}


@router.get("/events/trace/{event_id}", summary="事件溯源")
async def trace_event(event_id: str):
    chain = event_bus.trace_chain(event_id)
    return {"chain": chain, "depth": len(chain)}


# ---------- Token 管理 ----------

@router.put("/token/quota", summary="设置 Token 配额")
async def set_token_quota(quota: TokenQuota):
    token_manager.set_quota(quota)
    return {"status": "saved", "agent_name": quota.agent_name}


@router.get("/token/quotas", summary="获取全部配额")
async def get_token_quotas():
    return {"quotas": [q.model_dump() for q in token_manager.get_all_quotas()]}


@router.post("/token/check", summary="预估 Token 消耗")
async def check_token_usage(
    agent_name: str, estimated_input: int, estimated_output: int = 0,
):
    ok, msg, suggestions = token_manager.check_before_execute(
        agent_name, estimated_input, estimated_output,
    )
    return {"allowed": ok, "message": msg, "degradation_suggestions": suggestions}


@router.post("/token/consume", summary="记录 Token 消耗")
async def consume_tokens(agent_name: str, input_tokens: int, output_tokens: int = 0):
    status = token_manager.consume(agent_name, input_tokens, output_tokens)
    return status.model_dump()


@router.get("/token/report", summary="Token 趋势报告")
async def get_token_report(period: str = Query(default="daily", pattern="^(daily|weekly)$"), count: int = 7):
    if period == "daily":
        report = token_manager.daily_report(days=count)
    else:
        report = token_manager.weekly_report(weeks=count)
    return report.model_dump(mode="json")


# ---------- 审计日志 ----------

@router.post("/audit/record", summary="记录审计日志")
async def record_audit(action: AuditAction):
    audit_id = audit_system.record(action)
    return {"status": "recorded", "audit_id": audit_id}


@router.get("/audit", summary="查询审计日志")
async def query_audit(
    action_type: str = "", operator: str = "",
    severity: str = "", keyword: str = "", limit: int = Query(default=100),
):
    flt = AuditFilter(keyword=keyword)
    if action_type:
        flt.action_types = [action_type]
    if operator:
        flt.operators = [operator]
    if severity:
        flt.severities = [Severity(s) for s in severity.split(",")]
    logs = audit_system.query(flt)[:limit]
    return {"total": len(logs), "logs": [a.model_dump(mode="json") for a in logs]}


@router.get("/audit/anomalies", summary="审计异常检测")
async def get_audit_anomalies(lookback_hours: int = 24):
    violations = audit_system.detect_anomalies(lookback_hours)
    return {"violations": violations}


@router.get("/audit/export", summary="导出审计日志")
async def export_audit(format: str = Query(default="iso27001", pattern="^(iso27001|json|csv)$")):
    if format == "iso27001":
        return {"data": audit_system.export_iso27001()}
    elif format == "csv":
        return {"data": audit_system.export_csv()}
    return {"data": audit_system.export_json()}


@router.get("/audit/by-agent-log/{agent_log_id}", summary="审计-Agent 联动查询")
async def audit_by_agent_log(agent_log_id: str):
    logs = audit_system.get_by_agent_log(agent_log_id)
    return {"total": len(logs), "logs": [a.model_dump(mode="json") for a in logs]}


# ---------- DAG 可视化 ----------

class DAGRenderRequest(BaseModel):
    snapshot: DAGSnapshot
    height: int = Field(default=600, ge=300, le=2000)
    interactive: bool = True


@router.post("/dag/render", summary="渲染 DAG 为 HTML")
async def render_dag(req: DAGRenderRequest):
    html = dag_visualizer.render(req.snapshot, height=req.height, interactive=req.interactive)
    return {"html": html}


@router.post("/dag/export-svg", summary="导出 DAG 为 SVG")
async def export_dag_svg(snapshot: DAGSnapshot, filepath: str = "dag_output.svg"):
    svg = dag_visualizer.export_svg(snapshot, filepath)
    return {"status": "exported", "filepath": filepath, "svg_preview": svg[:500]}


# ============================================================
# Streamlit 嵌入示例
# ============================================================

def render_dag_for_streamlit(
    snapshot: DAGSnapshot,
    decision_logs: dict[str, list[dict]] | None = None,
    height: int = 600,
) -> str:
    """便捷函数：直接在 Streamlit 中渲染 DAG 可视化。

    Usage in Streamlit:
        import streamlit as st
        from src.infrastructure.main import render_dag_for_streamlit

        snapshot = DAGSnapshot(nodes=[...], edges=[...])
        st.components.v1.html(render_dag_for_streamlit(snapshot, height=600), height=620)
    """
    return dag_visualizer.render(snapshot, decision_logs, height=height, interactive=True)


def register_routes(app):
    """将基础设施路由注册到 FastAPI app"""
    app.include_router(router)


# ============================================================
# 部署说明与 React 迁移指南
# ============================================================

DEPLOYMENT_GUIDE = """
## 部署说明

### 1. Streamlit 嵌入
```python
import streamlit as st
from src.infrastructure.main import render_dag_for_streamlit

# 在 Streamlit 页面中嵌入 DAG
st.components.v1.html(render_dag_for_streamlit(your_snapshot, height=600), height=620)
```

### 2. FastAPI 集成
```python
from src.infrastructure.main import register_routes
register_routes(app)  # 注册 /api/infra/* 全部路由
```

### 3. React 迁移方案
- 所有数据通过 `/api/infra/*` REST API 获取（JSON 格式）
- DAG 渲染：前端可复用当前的 SVG 布局算法，或替换为 ReactFlow
- 事件订阅：前端可使用 SSE (EventSource) 监听 `/api/infra/events` 或 WebSocket
- Token 配额：前端展示 TokenTrendReport，使用 recharts 渲染趋势图
- 审计日志：前端使用表格组件展示，支持筛选和导出
"""


# ============================================================
# 独立运行示例
# ============================================================

if __name__ == "__main__":
    import asyncio

    async def demo():
        print("=== Infrastructure Demo ===\n")

        # 1. Agent 决策日志
        print("1. Agent Decision Log")
        log = AgentDecisionLog(
            agent_name="research",
            agent_role="Research Agent",
            phase="execution",
            step_number=3,
            reasoning="分析竞品字节跳动的 AI 产品矩阵，发现豆包在 C 端用户数领先",
            input_tokens=850,
            output_tokens=420,
            duration_ms=3200,
            status=NodeStatus.COMPLETED,
        )
        lid = decision_logger.record(log)
        print(f"   Recorded: {lid}")

        # 2. EventBus
        print("2. EventBus")
        evt = BusEvent(
            event_type=EventType.AGENT_STARTED,
            source="research",
            data={"task": "analyze competitor"},
        )
        await event_bus.publish(evt)
        print(f"   Published: {evt.event_id}")

        # 3. Token Manager
        print("3. Token Manager")
        tm_status = token_manager.consume("research", input_tokens=500, output_tokens=200)
        print(f"   Status: used={tm_status.used_input}/{tm_status.quota_input}, ratio={tm_status.usage_ratio:.2f}")

        # 4. Audit System
        print("4. Audit System")
        audit = AuditAction(
            action_type="dag_execute",
            operator="admin",
            target="DAG-Analysis-2026",
            linked_agent_log_id=lid,
        )
        aid = audit_system.record(audit)
        print(f"   Recorded: {aid}")

        # 5. DAG Visualizer
        print("5. DAG Visualizer")
        nodes = [
            DAGNodeRuntime(node_id="monitor", label="监控Agent", icon="🔍", status=NodeStatus.COMPLETED, duration_ms=1500),
            DAGNodeRuntime(node_id="research", label="研究Agent", icon="📚", status=NodeStatus.RUNNING, duration_ms=3200, progress=0.7),
            DAGNodeRuntime(node_id="compare", label="对比Agent", icon="📊", status=NodeStatus.IDLE, duration_ms=0, progress=0),
        ]
        edges = [
            DAGEdge(edge_id="e1", source="monitor", target="research", animated=True),
            DAGEdge(edge_id="e2", source="research", target="compare"),
        ]
        snapshot = DAGSnapshot(nodes=nodes, edges=edges, total_progress=0.4, elapsed_ms=5000)
        html = dag_visualizer.render(snapshot, height=450)
        print(f"   HTML rendered: {len(html)} chars")

        # 6. Export SVG
        dag_visualizer.export_svg(snapshot, "/tmp/dag_demo.svg")
        print(f"   SVG exported to /tmp/dag_demo.svg")

        print("\n=== Demo Complete ===")

    asyncio.run(demo())
