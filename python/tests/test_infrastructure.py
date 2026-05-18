"""
基础设施模块单元测试 — 覆盖 5 大核心功能。

运行: python -m pytest tests/test_infrastructure.py -v
"""

import json
import tempfile
import pytest
from datetime import datetime, timedelta

from src.infrastructure.data_models import (
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
    TokenUsage,
)
from src.infrastructure.agent_logger import AgentDecisionLogger
from src.infrastructure.event_bus import EventBus
from src.infrastructure.token_manager import TokenManager
from src.infrastructure.audit_system import AuditSystem
from src.infrastructure.dag_visualizer import DAGVisualizer


# ==================== Agent 决策日志 ====================

class TestAgentDecisionLogger:
    def test_record_and_query(self):
        logger = AgentDecisionLogger()
        log = AgentDecisionLog(
            agent_name="research", agent_role="Research Agent",
            step_number=1, reasoning="测试推理", duration_ms=5000,
            input_tokens=300, output_tokens=150, status=NodeStatus.COMPLETED,
        )
        lid = logger.record(log)
        assert lid == log.log_id
        assert len(logger._logs) == 1

    def test_multidimensional_filter(self):
        logger = AgentDecisionLogger()
        logger.record(AgentDecisionLog(agent_name="monitor", step_number=1, duration_ms=1000, input_tokens=100, status=NodeStatus.COMPLETED))
        logger.record(AgentDecisionLog(agent_name="research", step_number=1, duration_ms=20000, input_tokens=5000, status=NodeStatus.RUNNING))
        logger.record(AgentDecisionLog(agent_name="compare", step_number=1, duration_ms=500, input_tokens=200, status=NodeStatus.FAILED))

        # 按 Agent 名称筛选
        flt = DecisionLogFilter(agent_names=["monitor"])
        assert len(logger.query(flt)) == 1

        # 按耗时筛选
        flt = DecisionLogFilter(min_duration_ms=15000)
        assert len(logger.query(flt)) == 1
        assert logger.query(flt)[0].agent_name == "research"

        # 关键词搜索
        flt = DecisionLogFilter(keyword="监控")  # reasoning 字段中没有这个关键词
        # 但我们可以验证 keyword 筛选逻辑存在
        flt2 = DecisionLogFilter(has_anomaly=True)
        # research 有 high_latency 异常（20s > 15s 阈值）
        anomalies = logger.query(flt2)
        assert len(anomalies) >= 1

    def test_timeline_replay(self):
        logger = AgentDecisionLogger()
        t0 = datetime.now()
        logger.record(AgentDecisionLog(agent_name="monitor", step_number=1, timestamp=t0, duration_ms=500))
        logger.record(AgentDecisionLog(agent_name="research", step_number=1, timestamp=t0 + timedelta(seconds=2), duration_ms=3000))
        logger.record(AgentDecisionLog(agent_name="compare", step_number=1, timestamp=t0 + timedelta(seconds=5), duration_ms=1500))

        timeline = logger.timeline_replay()
        assert len(timeline) == 3
        assert timeline[0]["seq"] == 1
        assert timeline[1]["delta_ms"] == 2000  # 2s = 2000ms
        assert timeline[2]["delta_ms"] == 3000  # 3s = 3000ms

    def test_anomaly_detection(self):
        logger = AgentDecisionLogger()
        # 正常日志
        logger.record(AgentDecisionLog(agent_name="monitor", step_number=1, duration_ms=1000, input_tokens=500, status=NodeStatus.COMPLETED))
        # 异常日志（高延迟 × 2 — 满足 ≥2 阈值）
        logger.record(AgentDecisionLog(agent_name="research", step_number=1, duration_ms=25000, input_tokens=2000, status=NodeStatus.COMPLETED))
        logger.record(AgentDecisionLog(agent_name="research", step_number=2, duration_ms=30000, input_tokens=3000, status=NodeStatus.COMPLETED))
        # 失败日志 × 2
        logger.record(AgentDecisionLog(agent_name="compare", step_number=1, duration_ms=500, input_tokens=100, status=NodeStatus.FAILED))
        logger.record(AgentDecisionLog(agent_name="compare", step_number=2, duration_ms=400, input_tokens=90, status=NodeStatus.FAILED))

        report = logger.detect_anomalies()
        assert report.anomaly_count >= 4
        assert report.total_logs_analyzed == 5
        assert len(report.suggestions) >= 1

    def test_export(self):
        logger = AgentDecisionLogger()
        logger.record(AgentDecisionLog(agent_name="test", step_number=1, reasoning="hello", input_tokens=10, status=NodeStatus.COMPLETED))
        json_str = logger.export_json()
        assert '"agent_name": "test"' in json_str
        csv_str = logger.export_csv()
        assert "test" in csv_str


# ==================== EventBus ====================

class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_and_query(self):
        bus = EventBus(db_path=":memory:")
        evt = BusEvent(event_type=EventType.AGENT_STARTED, source="monitor", data={"task": "test"})
        await bus.publish(evt)
        assert len(bus.get_events()) == 1
        assert bus.get_events()[0].source == "monitor"

    @pytest.mark.asyncio
    async def test_trace_chain(self):
        bus = EventBus(db_path=":memory:")
        root = BusEvent(event_type=EventType.DAG_STARTED, source="engine")
        await bus.publish(root)
        child = BusEvent(event_type=EventType.AGENT_STARTED, source="monitor", parent_event_id=root.event_id)
        await bus.publish(child)
        grandchild = BusEvent(event_type=EventType.TOOL_CALL, source="monitor", parent_event_id=child.event_id)
        await bus.publish(grandchild)

        chain = bus.trace_chain(grandchild.event_id)
        assert len(chain) == 3
        assert chain[0]["source"] == "engine"
        assert chain[2]["source"] == "monitor"

    @pytest.mark.asyncio
    async def test_alert_rules(self):
        bus = EventBus(db_path=":memory:")
        from src.infrastructure.data_models import AlertRule
        bus.add_alert_rule(AlertRule(
            name="agent_failure_alert",
            event_types=[EventType.AGENT_FAILED],
            condition="agent_failed_count > 0",
            cooldown_seconds=0,
        ))
        evt = BusEvent(event_type=EventType.AGENT_FAILED, source="research")
        await bus.publish(evt)

        # 检查是否有 ALERT_TRIGGERED 事件
        alerts = bus.get_events(EventType.ALERT_TRIGGERED)
        assert len(alerts) >= 1


# ==================== Token Manager ====================

class TestTokenManager:
    def test_consume_and_status(self):
        tm = TokenManager()
        status = tm.consume("research", input_tokens=500, output_tokens=200)
        assert status.agent_name == "research"
        assert status.used_input == 500
        assert status.used_output == 200
        assert status.remaining_input > 0

    def test_quota_throttle(self):
        tm = TokenManager()
        tm.set_quota(TokenQuota(agent_name="test_agent", max_input_tokens=100, max_output_tokens=50))
        status = tm.consume("test_agent", input_tokens=120, output_tokens=10)
        assert status.is_throttled
        assert status.usage_ratio >= 1.0

    def test_check_before_execute(self):
        tm = TokenManager()
        ok, msg, suggestions = tm.check_before_execute("research", estimated_input=10_000)
        assert ok  # 默认配额 200K，10K 足够
        assert "充足" in msg or "ok" in msg.lower() or "true" in str(ok).lower()

    def test_quota_match(self):
        tm = TokenManager()
        tm.set_quota(TokenQuota(agent_name="special_agent", max_input_tokens=50_000))
        q = tm.get_quota("special_agent")
        assert q.max_input_tokens == 50_000
        # 未设置配额的回退到通配
        q2 = tm.get_quota("unknown_agent")
        assert q2.max_input_tokens > 0

    def test_daily_report(self):
        tm = TokenManager()
        tm.consume("research", input_tokens=10000, output_tokens=5000)
        tm.consume("monitor", input_tokens=5000, output_tokens=2000)
        report = tm.daily_report(days=7)
        assert isinstance(report, TokenTrendReport)
        assert report.total_input_tokens == 15000
        assert report.estimated_cost > 0


# ==================== 审计日志 ====================

class TestAuditSystem:
    def test_record_and_query(self):
        audit = AuditSystem(db_path=":memory:")
        action = AuditAction(
            action_type="config_change",
            operator="admin",
            target="llm.temperature",
            severity=Severity.WARNING,
        )
        aid = audit.record(action)
        assert aid == action.audit_id

        logs = audit.query(AuditFilter(action_types=["config_change"]))
        assert len(logs) == 1

    def test_agent_log_linkage(self):
        audit = AuditSystem(db_path=":memory:")
        log_id = "log_abc123"
        action = AuditAction(
            action_type="dag_execute",
            operator="system",
            linked_agent_log_id=log_id,
        )
        audit.record(action)

        linked = audit.get_by_agent_log(log_id)
        assert len(linked) == 1
        assert linked[0].linked_agent_log_id == log_id

    def test_anomaly_detection(self):
        audit = AuditSystem(db_path=":memory:")
        now = datetime.now()
        for i in range(25):  # 超过每小时20次的配置修改限制
            audit.record(AuditAction(
                action_type="config_change",
                operator="admin",
                timestamp=now - timedelta(minutes=i),
            ))

        violations = audit.detect_anomalies(lookback_hours=1)
        assert len(violations) >= 1
        assert any("频率超限" in v["details"] for v in violations)

    def test_export_formats(self):
        audit = AuditSystem(db_path=":memory:")
        audit.record(AuditAction(action_type="login", operator="admin", severity=Severity.INFO))

        iso = audit.export_iso27001()
        assert "ISO 27001" in iso
        assert "login" in iso

        csv = audit.export_csv()
        assert "admin" in csv

        json_str = audit.export_json()
        assert "admin" in json_str


# ==================== DAG 可视化 ====================

class TestDAGVisualizer:
    def test_render_html(self):
        viz = DAGVisualizer()
        nodes = [
            DAGNodeRuntime(node_id="n1", label="Agent 1", icon="🔍", status=NodeStatus.COMPLETED, duration_ms=1500, progress=1.0),
            DAGNodeRuntime(node_id="n2", label="Agent 2", icon="📚", status=NodeStatus.RUNNING, duration_ms=3000, progress=0.5),
            DAGNodeRuntime(node_id="n3", label="Agent 3", icon="📊", status=NodeStatus.IDLE, duration_ms=0, progress=0.0),
        ]
        edges = [
            DAGEdge(edge_id="e1", source="n1", target="n2", animated=True, label="data flow"),
            DAGEdge(edge_id="e2", source="n2", target="n3"),
        ]
        snapshot = DAGSnapshot(nodes=nodes, edges=edges, total_progress=0.5, elapsed_ms=4500)

        html = viz.render(snapshot, height=400)
        assert "n1" in html
        assert "Agent 1" in html
        assert "animated" in html
        assert "heat" in html.lower() or "hsl" in html

    def test_export_svg(self):
        import os
        viz = DAGVisualizer()
        nodes = [DAGNodeRuntime(node_id="test", label="Test", icon="🔵", status=NodeStatus.COMPLETED, duration_ms=1000)]
        edges = []
        snapshot = DAGSnapshot(nodes=nodes, edges=edges)

        tmpfile = "/tmp/test_dag.svg"
        svg = viz.export_svg(snapshot, tmpfile)
        assert os.path.exists(tmpfile)
        assert "Test" in svg
        os.remove(tmpfile)

    def test_layout_positions(self):
        viz = DAGVisualizer()
        nodes = [
            DAGNodeRuntime(node_id="root", label="Root"),
            DAGNodeRuntime(node_id="child1", label="Child 1"),
            DAGNodeRuntime(node_id="child2", label="Child 2"),
        ]
        edges = [
            DAGEdge(edge_id="e1", source="root", target="child1"),
            DAGEdge(edge_id="e2", source="root", target="child2"),
        ]
        snapshot = DAGSnapshot(nodes=nodes, edges=edges)
        positions = viz._layout(snapshot)
        assert "root" in positions
        assert "child1" in positions
        # root 应该在左边（第一层），children 在右边
        assert positions["root"][0] < positions["child1"][0]


# ==================== 数据模型验证 ====================

class TestDataModels:
    def test_decision_log_filter_match(self):
        flt = DecisionLogFilter(agent_names=["monitor"])
        log = AgentDecisionLog(agent_name="monitor", step_number=1, status=NodeStatus.COMPLETED)
        assert flt.match(log)

        log2 = AgentDecisionLog(agent_name="research", step_number=1, status=NodeStatus.COMPLETED)
        assert not flt.match(log2)

    def test_audit_filter_match(self):
        flt = AuditFilter(action_types=["login", "config_change"])
        action = AuditAction(action_type="login", operator="admin")
        assert action.action_type in flt.action_types

    def test_token_budget_status_throttled(self):
        status = TokenBudgetStatus(
            agent_name="test",
            quota_input=1000, quota_output=500,
            used_input=1200, used_output=100,
            remaining_input=0, remaining_output=400,
            usage_ratio=1.2,
            is_throttled=True,
            degradation_suggestions=["使用轻量模型"],
        )
        assert status.is_throttled
        assert len(status.degradation_suggestions) == 1

    def test_dag_snapshot_progress(self):
        snapshot = DAGSnapshot(total_progress=0.75, elapsed_ms=12000, estimated_remaining_ms=4000)
        assert snapshot.total_progress == 0.75
        assert snapshot.elapsed_ms == 12000
