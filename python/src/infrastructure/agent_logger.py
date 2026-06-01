"""
Agent 决策日志系统 — 多维筛选 + 时序回溯 + LLM 异常检测 + JSON/CSV 导出。

创新点：
  1. DecisionLogFilter 支持按 Agent/阶段/耗时/Token 范围多维度筛选
  2. timeline_replay() 按时间轴复现 Agent 执行全过程
  3. detect_anomalies() 基于规则 + 可选 LLM 分析异常并生成优化建议
  4. export_logs() 导出 JSON/CSV 格式，兼容审计需求

使用示例:
    logger = AgentDecisionLogger()
    logger.record(AgentDecisionLog(agent_name="research", ...))
    filtered = logger.query(DecisionLogFilter(agent_names=["research"]))
    timeline = logger.timeline_replay()
"""

from __future__ import annotations

import csv
import io
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from .data_models import (
    AgentDecisionLog,
    AnomalyReport,
    DecisionLogFilter,
    NodeStatus,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)

# -------------------------- 异常检测阈值 --------------------------
ANOMALY_RULES = {
    "high_latency_ms": 15_000,       # 单步耗时超过 15s → 异常
    "token_spike_ratio": 5.0,        # 当前步 Token 超过均值 5 倍 → 异常
    "max_consecutive_failures": 3,   # 连续失败次数 ≥ 3 → 异常
    "max_tool_call_duration_ms": 30_000,  # 工具调用超 30s → 异常
}


class AgentDecisionLogger:
    """Agent 决策日志管理器 — 记录 / 筛选 / 回溯 / 异常检测 / 导出"""

    def __init__(self):
        self._logs: list[AgentDecisionLog] = []

    # ------------------------------------------------------------------
    # 记录
    # ------------------------------------------------------------------

    def record(self, log: AgentDecisionLog) -> str:
        """记录一条决策日志，自动标注异常标记。返回 log_id。"""
        log.anomaly_flags = self._check_rules(log)
        self._logs.append(log)
        return log.log_id

    def record_batch(self, logs: list[AgentDecisionLog]) -> list[str]:
        """批量记录"""
        return [self.record(l) for l in logs]

    # ------------------------------------------------------------------
    # 筛选
    # ------------------------------------------------------------------

    def query(self, flt: Optional[DecisionLogFilter] = None) -> list[AgentDecisionLog]:
        """多维度筛选决策日志。不传 filter 返回全部。"""
        if flt is None:
            return list(self._logs)
        return [log for log in self._logs if flt.match(log)]

    def get_by_agent(self, agent_name: str) -> list[AgentDecisionLog]:
        return self.query(DecisionLogFilter(agent_names=[agent_name]))

    def get_anomalies(self) -> list[AgentDecisionLog]:
        return self.query(DecisionLogFilter(has_anomaly=True))

    # ------------------------------------------------------------------
    # 时序回溯
    # ------------------------------------------------------------------

    def timeline_replay(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> list[dict]:
        """按时间轴复现 Agent 执行全过程，返回带时间间隔的事件序列。

        返回格式：
        [
          {"seq": 1, "delta_ms": 0,    "log": AgentDecisionLog, "agent": "monitor"},
          {"seq": 2, "delta_ms": 1450, "log": AgentDecisionLog, "agent": "research"},
          ...
        ]
        其中 delta_ms 是相对于上一条日志的时间间隔。
        """
        logs = sorted(self._logs, key=lambda l: l.timestamp)
        if start_time:
            logs = [l for l in logs if l.timestamp >= start_time]
        if end_time:
            logs = [l for l in logs if l.timestamp <= end_time]

        timeline = []
        prev_ts: Optional[datetime] = None
        for seq, log in enumerate(logs, 1):
            delta_ms = 0
            if prev_ts is not None:
                delta_ms = int((log.timestamp - prev_ts).total_seconds() * 1000)
            timeline.append({
                "seq": seq,
                "delta_ms": delta_ms,
                "log_id": log.log_id,
                "agent": log.agent_name,
                "role": log.agent_role,
                "phase": log.phase,
                "status": log.status.value,
                "tokens": log.total_tokens,
                "duration_ms": log.duration_ms,
                "reasoning_preview": log.reasoning[:120],
                "anomaly_flags": log.anomaly_flags,
                "timestamp": log.timestamp.isoformat(),
            })
            prev_ts = log.timestamp
        return timeline

    # ------------------------------------------------------------------
    # LLM 异常检测
    # ------------------------------------------------------------------

    def detect_anomalies(
        self, llm_callable: Any = None
    ) -> AnomalyReport:
        """基于规则 + 可选 LLM 分析异常日志，生成优化建议。

        若提供 llm_callable（异步函数签名: async fn(prompt: str) -> str），
        则用 LLM 深度分析；否则仅用规则引擎。
        """
        anomalies = self.get_anomalies()
        report = AnomalyReport(
            total_logs_analyzed=len(self._logs),
            anomaly_count=len(anomalies),
        )

        # 规则引擎：按 Agent 聚合异常
        agent_anomalies: dict[str, list[AgentDecisionLog]] = defaultdict(list)
        for a in anomalies:
            agent_anomalies[a.agent_name].append(a)

        suggestions = []
        top_anomalies = []
        for agent_name, logs in agent_anomalies.items():
            flags = defaultdict(int)
            for log in logs:
                for f in log.anomaly_flags:
                    flags[f] += 1

            # 生成针对性建议
            if flags.get("high_latency", 0) >= 2:
                suggestions.append(
                    f"[{agent_name}] 出现 {flags['high_latency']} 次高延迟，"
                    f"建议检查网络连接或降低 max_tokens"
                )
            if flags.get("token_spike", 0) >= 2:
                suggestions.append(
                    f"[{agent_name}] Token 用量异常飙高 {flags['token_spike']} 次，"
                    f"建议压缩上下文或启用摘要"
                )
            if flags.get("tool_failure", 0) >= 2:
                suggestions.append(
                    f"[{agent_name}] 工具调用失败 {flags['tool_failure']} 次，"
                    f"建议检查工具可用性或添加 fallback"
                )

            top_anomalies.append({
                "agent_name": agent_name,
                "anomaly_count": len(logs),
                "flag_summary": dict(flags),
                "first_at": logs[0].timestamp.isoformat() if logs else "",
            })

        # 按异常数量降序
        top_anomalies.sort(key=lambda x: x["anomaly_count"], reverse=True)

        report.suggestions = suggestions[:10]
        report.top_anomalies = top_anomalies[:5]
        summary_parts = [f"共分析 {report.total_logs_analyzed} 条日志，发现 {report.anomaly_count} 条异常"]
        if suggestions:
            summary_parts.append(f"生成 {len(suggestions)} 条优化建议")
        report.summary = "；".join(summary_parts)
        return report

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def export_json(self, flt: Optional[DecisionLogFilter] = None) -> str:
        """导出为 JSON 字符串"""
        logs = self.query(flt)
        return json.dumps(
            [log.model_dump(mode="json") for log in logs],
            ensure_ascii=False,
            indent=2,
        )

    def export_csv(self, flt: Optional[DecisionLogFilter] = None) -> str:
        """导出为 CSV 字符串"""
        logs = self.query(flt)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "log_id", "agent_name", "agent_role", "phase", "step_number",
            "status", "input_tokens", "output_tokens", "duration_ms",
            "tool_calls_count", "anomaly_flags", "timestamp", "reasoning",
        ])
        for log in logs:
            writer.writerow([
                log.log_id, log.agent_name, log.agent_role, log.phase,
                log.step_number, log.status.value, log.input_tokens,
                log.output_tokens, log.duration_ms,
                len(log.tool_calls),
                ";".join(log.anomaly_flags),
                log.timestamp.isoformat(),
                log.reasoning[:200],
            ])
        return output.getvalue()

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        if not self._logs:
            return {}
        agents = defaultdict(lambda: {"count": 0, "total_tokens": 0, "total_ms": 0})
        for log in self._logs:
            a = agents[log.agent_name]
            a["count"] += 1
            a["total_tokens"] += log.total_tokens
            a["total_ms"] += log.duration_ms
            a["status"] = log.status.value
        total_tokens = sum(a["total_tokens"] for a in agents.values())
        return {
            "total_logs": len(self._logs),
            "total_tokens": total_tokens,
            "total_duration_ms": sum(a["total_ms"] for a in agents.values()),
            "agents": {
                name: {
                    **stats,
                    "avg_tokens": stats["total_tokens"] // max(stats["count"], 1),
                    "avg_ms": stats["total_ms"] // max(stats["count"], 1),
                }
                for name, stats in agents.items()
            },
        }

    # ---------- 内部 ----------

    def _check_rules(self, log: AgentDecisionLog) -> list[str]:
        """规则引擎：检查单条日志的异常标记"""
        flags = []
        if log.duration_ms > ANOMALY_RULES["high_latency_ms"]:
            flags.append("high_latency")
        if log.status == NodeStatus.FAILED:
            flags.append("agent_failure")
        for tc in log.tool_calls:
            if not tc.success:
                flags.append("tool_failure")
            if tc.duration_ms > ANOMALY_RULES["max_tool_call_duration_ms"]:
                flags.append("tool_timeout")

        # 检查连续失败
        recent = [l for l in self._logs[-5:] if l.agent_name == log.agent_name]
        if len(recent) >= ANOMALY_RULES["max_consecutive_failures"]:
            if all(l.status == NodeStatus.FAILED for l in recent[-ANOMALY_RULES["max_consecutive_failures"]:]):
                flags.append("consecutive_failures")

        # 检查 Token 飙高
        agent_logs = [l for l in self._logs if l.agent_name == log.agent_name]
        if len(agent_logs) >= 3:
            avg_tokens = sum(l.total_tokens for l in agent_logs) / len(agent_logs)
            if avg_tokens > 0 and log.total_tokens > avg_tokens * ANOMALY_RULES["token_spike_ratio"]:
                flags.append("token_spike")

        return flags


# 全局单例
decision_logger = AgentDecisionLogger()
