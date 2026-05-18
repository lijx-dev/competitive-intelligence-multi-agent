"""
基础设施数据模型 — Pydantic v2 定义全部核心类型。

模块: AgentDecisionLog / DAGNode / Event / TokenBudget / AuditLog
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 通用枚举
# ============================================================

class NodeStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class EventType(str, Enum):
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_PAUSED = "agent_paused"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOKEN_CONSUMED = "token_consumed"
    TOKEN_THROTTLED = "token_throttled"
    DAG_STARTED = "dag_started"
    DAG_COMPLETED = "dag_completed"
    DAG_NODE_CHANGED = "dag_node_changed"
    AUDIT_ACTION = "audit_action"
    ALERT_TRIGGERED = "alert_triggered"
    CONFIG_CHANGED = "config_changed"
    DATA_EXPORTED = "data_exported"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ============================================================
# Agent 决策日志模型
# ============================================================

class ToolCallRecord(BaseModel):
    """单次工具调用记录"""
    tool_name: str = Field(description="工具名称")
    params: dict = Field(default_factory=dict, description="调用参数")
    result_summary: str = Field(default="", description="结果摘要（截断至200字）")
    success: bool = Field(default=True, description="是否成功")
    duration_ms: int = Field(default=0, description="工具调用耗时（毫秒）")


class AgentDecisionLog(BaseModel):
    """Agent 单步决策日志 — 可观测性核心数据结构"""
    log_id: str = Field(default_factory=lambda: f"log_{uuid.uuid4().hex[:8]}")
    agent_name: str = Field(description="Agent 名称（如 monitor/research/compare）")
    agent_role: str = Field(default="agent", description="Agent 角色标签")
    phase: str = Field(default="execution", description="执行阶段（planning/execution/verification）")

    step_number: int = Field(default=0, ge=0, description="当前步数序号")
    reasoning: str = Field(default="", description="LLM 推理过程（截断至500字）")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0, description="本步耗时（毫秒）")

    status: NodeStatus = Field(default=NodeStatus.RUNNING)
    error_message: str = Field(default="")
    anomaly_flags: list[str] = Field(default_factory=list, description="异常标记（如 high_latency, token_spike）")

    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @field_validator("tool_calls", mode="before")
    @classmethod
    def parse_tool_calls(cls, v: Any) -> list[ToolCallRecord]:
        if isinstance(v, list):
            return [ToolCallRecord(**tc) if isinstance(tc, dict) else tc for tc in v]
        return []


class DecisionLogFilter(BaseModel):
    """决策日志多维度筛选器"""
    agent_names: list[str] = Field(default_factory=list, description="按 Agent 名称筛选")
    phases: list[str] = Field(default_factory=list, description="按执行阶段筛选")
    statuses: list[NodeStatus] = Field(default_factory=list, description="按状态筛选")
    min_duration_ms: Optional[int] = Field(default=None, description="最小耗时（毫秒）")
    max_duration_ms: Optional[int] = Field(default=None, description="最大耗时（毫秒）")
    min_input_tokens: Optional[int] = Field(default=None)
    max_input_tokens: Optional[int] = Field(default=None)
    has_anomaly: Optional[bool] = Field(default=None, description="仅查看有异常的日志")
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    keyword: str = Field(default="", description="关键词搜索（匹配 reasoning 字段）")

    def match(self, log: AgentDecisionLog) -> bool:
        if self.agent_names and log.agent_name not in self.agent_names:
            return False
        if self.phases and log.phase not in self.phases:
            return False
        if self.statuses and log.status not in self.statuses:
            return False
        if self.min_duration_ms is not None and log.duration_ms < self.min_duration_ms:
            return False
        if self.max_duration_ms is not None and log.duration_ms > self.max_duration_ms:
            return False
        if self.min_input_tokens is not None and log.input_tokens < self.min_input_tokens:
            return False
        if self.max_input_tokens is not None and log.input_tokens > self.max_input_tokens:
            return False
        if self.has_anomaly is True and not log.anomaly_flags:
            return False
        if self.has_anomaly is False and log.anomaly_flags:
            return False
        if self.start_time and log.timestamp < self.start_time:
            return False
        if self.end_time and log.timestamp > self.end_time:
            return False
        if self.keyword and self.keyword.lower() not in log.reasoning.lower():
            return False
        return True


class AnomalyReport(BaseModel):
    """LLM 自动生成的异常分析报告"""
    report_id: str = Field(default_factory=lambda: f"anomaly_{uuid.uuid4().hex[:8]}")
    detected_at: datetime = Field(default_factory=datetime.now)
    total_logs_analyzed: int = Field(default=0)
    anomaly_count: int = Field(default=0)
    suggestions: list[str] = Field(default_factory=list, description="优化建议")
    top_anomalies: list[dict] = Field(default_factory=list, description="Top 异常详情")
    summary: str = Field(default="")


# ============================================================
# DAG 可视化模型
# ============================================================

class DAGNodeConfig(BaseModel):
    """DAG 节点配置"""
    node_id: str
    label: str = ""
    icon: str = "🔵"  # emoji 图标
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)


class DAGNodeRuntime(BaseModel):
    """DAG 节点运行时状态"""
    node_id: str
    label: str = ""
    icon: str = "🔵"
    status: NodeStatus = NodeStatus.IDLE
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="执行进度 0-1")
    duration_ms: int = Field(default=0, description="累计耗时（毫秒）")
    heat_color: str = Field(default="", description="热力图颜色（HSL）")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""


class DAGEdge(BaseModel):
    """DAG 边"""
    edge_id: str
    source: str
    target: str
    animated: bool = Field(default=False, description="是否显示流动动画")
    label: str = ""


class DAGSnapshot(BaseModel):
    """DAG 快照 — 某一时刻的完整 DAG 状态"""
    snapshot_id: str = Field(default_factory=lambda: f"dag_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=datetime.now)
    nodes: list[DAGNodeRuntime] = Field(default_factory=list)
    edges: list[DAGEdge] = Field(default_factory=list)
    total_progress: float = Field(default=0.0, ge=0.0, le=1.0)
    elapsed_ms: int = Field(default=0)
    estimated_remaining_ms: int = Field(default=0)


# ============================================================
# EventBus 事件模型
# ============================================================

class BusEvent(BaseModel):
    """事件总线事件 — 支持持久化和溯源"""
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    event_type: EventType
    source: str = Field(description="事件源（Agent名称或系统组件）")
    data: dict = Field(default_factory=dict)
    parent_event_id: Optional[str] = Field(default=None, description="父事件 ID（用于溯源链）")
    timestamp: datetime = Field(default_factory=datetime.now)
    persisted: bool = Field(default=False, description="是否已持久化")


class AlertRule(BaseModel):
    """事件告警规则"""
    rule_id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    name: str = Field(description="规则名称")
    event_types: list[EventType] = Field(default_factory=list, description="触发事件类型")
    condition: str = Field(default="", description="触发条件表达式（如 agent_failed_count > 3）")
    cooldown_seconds: int = Field(default=300, ge=0, description="冷却时间（秒）")
    enabled: bool = Field(default=True)
    last_triggered: Optional[datetime] = None


# ============================================================
# Token 预算治理模型
# ============================================================

class TokenQuota(BaseModel):
    """单个 Agent/场景的 Token 配额"""
    agent_name: str = Field(default="*", description="Agent 名称，* 表示默认")
    scenario: str = Field(default="*", description="场景名称，* 表示默认")
    max_input_tokens: int = Field(default=500_000, ge=0)
    max_output_tokens: int = Field(default=100_000, ge=0)
    warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="告警阈值比例")


class TokenUsage(BaseModel):
    """Token 使用记录"""
    record_id: str = Field(default_factory=lambda: f"tku_{uuid.uuid4().hex[:8]}")
    agent_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class TokenBudgetStatus(BaseModel):
    """Token 预算状态"""
    agent_name: str
    quota_input: int
    quota_output: int
    used_input: int = 0
    used_output: int = 0
    remaining_input: int = 0
    remaining_output: int = 0
    usage_ratio: float = Field(default=0.0, description="已使用比例")
    is_throttled: bool = Field(default=False, description="是否已触发节流")
    degradation_suggestions: list[str] = Field(default_factory=list)


class TokenTrendReport(BaseModel):
    """Token 消耗趋势报告"""
    period: str = Field(description="统计周期（daily/weekly）")
    start_date: str = ""
    end_date: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    top_agents: list[dict] = Field(default_factory=list, description="消耗 Top 5 Agent")
    trend_data: list[dict] = Field(default_factory=list, description="每日/周趋势数据")
    estimated_cost: float = Field(default=0.0, description="预估成本（元）")


# ============================================================
# 审计日志模型（原创设计）
# ============================================================

class AuditAction(BaseModel):
    """单条审计记录"""
    audit_id: str = Field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:8]}")
    action_type: str = Field(description="操作类型（login/config_change/dag_execute/data_export/...）")
    operator: str = Field(default="system", description="操作人")
    operator_ip: str = Field(default="127.0.0.1")
    target: str = Field(default="", description="操作对象（Agent名称/配置项/数据项）")
    details: dict = Field(default_factory=dict, description="操作详情")
    severity: Severity = Severity.INFO
    linked_agent_log_id: Optional[str] = Field(default=None, description="关联的 Agent 决策日志 ID")
    linked_event_id: Optional[str] = Field(default=None, description="关联的 EventBus 事件 ID")
    timestamp: datetime = Field(default_factory=datetime.now)


class AuditFilter(BaseModel):
    """审计日志筛选器"""
    action_types: list[str] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    severities: list[Severity] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    keyword: str = ""


class ComplianceRule(BaseModel):
    """合规审计规则"""
    rule_id: str = Field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    action_patterns: list[str] = Field(default_factory=list, description="匹配的操作类型")
    max_frequency_per_hour: Optional[int] = Field(default=None, description="每小时最大允许次数")
    require_approval: bool = Field(default=False, description="是否需要审批")
    enabled: bool = Field(default=True)
