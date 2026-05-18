"""
审计日志系统（原创设计）— 操作留痕 + 合规审计 + 异常检测 + 联动 Agent 日志。

创新点：
  1. 审计日志与 Agent 决策日志通过 linked_agent_log_id 联动
  2. 内置合规审计规则（敏感操作/操作人/时间/IP 全记录）
  3. 异常行为检测（高频修改配置、非授权数据导出等）触发实时告警
  4. 审计日志支持按 ISO 27001 格式导出

使用示例:
    audit = AuditSystem()
    audit.record(AuditAction(action_type="config_change", operator="admin", target="llm.temperature"))
    violations = audit.detect_anomalies()  # 检测异常行为
    audit.export_iso27001()
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from .data_models import (
    AuditAction,
    AuditFilter,
    ComplianceRule,
    Severity,
)

logger = logging.getLogger(__name__)

# 内置合规规则
DEFAULT_COMPLIANCE_RULES = [
    ComplianceRule(
        name="config_change_limit",
        description="配置修改频率限制：每小时不超过 20 次",
        action_patterns=["config_change"],
        max_frequency_per_hour=20,
    ),
    ComplianceRule(
        name="data_export_audit",
        description="数据导出操作必须留痕",
        action_patterns=["data_export", "report_export"],
        require_approval=False,
    ),
    ComplianceRule(
        name="agent_config_modify",
        description="Agent 配置修改为敏感操作",
        action_patterns=["agent_config_change"],
        require_approval=True,
    ),
    ComplianceRule(
        name="unauthorized_access",
        description="非授权访问检测",
        action_patterns=["unauthorized_access", "permission_violation"],
        max_frequency_per_hour=5,
    ),
]


class AuditSystem:
    """审计日志系统 — 记录 / 筛选 / 联动 / 异常检测 / 合规导出"""

    def __init__(self, db_path: str = "audit.db"):
        self._logs: list[AuditAction] = []
        self._compliance_rules: list[ComplianceRule] = list(DEFAULT_COMPLIANCE_RULES)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                operator TEXT NOT NULL,
                operator_ip TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL DEFAULT '{}',
                severity TEXT NOT NULL DEFAULT 'info',
                linked_agent_log_id TEXT,
                linked_event_id TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_logs(action_type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_operator ON audit_logs(operator)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp)')
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # 记录
    # ------------------------------------------------------------------

    def record(self, action: AuditAction) -> str:
        """记录审计日志并持久化"""
        self._logs.append(action)
        self._persist(action)
        logger.info(f"[AUDIT] {action.operator} → {action.action_type} → {action.target} ({action.severity.value})")
        return action.audit_id

    def _persist(self, action: AuditAction):
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute(
                'INSERT OR IGNORE INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    action.audit_id, action.action_type, action.operator,
                    action.operator_ip, action.target,
                    json.dumps(action.details, ensure_ascii=False),
                    action.severity.value, action.linked_agent_log_id,
                    action.linked_event_id, action.timestamp.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Audit persist failed: {e}")

    # ------------------------------------------------------------------
    # 查询 / 联动
    # ------------------------------------------------------------------

    def query(self, flt: AuditFilter | None = None) -> list[AuditAction]:
        if flt is None:
            return list(self._logs)
        results = self._logs
        if flt.action_types:
            results = [a for a in results if a.action_type in flt.action_types]
        if flt.operators:
            results = [a for a in results if a.operator in flt.operators]
        if flt.severities:
            results = [a for a in results if a.severity in flt.severities]
        if flt.start_time:
            results = [a for a in results if a.timestamp >= flt.start_time]
        if flt.end_time:
            results = [a for a in results if a.timestamp <= flt.end_time]
        if flt.keyword:
            kw = flt.keyword.lower()
            results = [a for a in results if kw in a.target.lower() or kw in json.dumps(a.details, ensure_ascii=False).lower()]
        return results

    def get_by_agent_log(self, agent_log_id: str) -> list[AuditAction]:
        """通过 Agent 决策日志 ID 反查关联的审计记录（联动功能）"""
        return [a for a in self._logs if a.linked_agent_log_id == agent_log_id]

    # ------------------------------------------------------------------
    # 异常行为检测
    # ------------------------------------------------------------------

    def detect_anomalies(self, lookback_hours: int = 24) -> list[dict]:
        """检测异常行为：高频操作 / 非授权导出 / 可疑配置变更。

        返回: [{"rule": ..., "severity": ..., "details": ..., "matched_actions": [...]}]
        """
        violations = []
        now = datetime.now()
        cutoff = now - timedelta(hours=lookback_hours)
        recent = [a for a in self._logs if a.timestamp >= cutoff]

        for rule in self._compliance_rules:
            if not rule.enabled:
                continue
            # 按操作类型匹配
            matched = [a for a in recent if a.action_type in rule.action_patterns]

            # 频率检查
            if rule.max_frequency_per_hour and len(matched) > rule.max_frequency_per_hour:
                violations.append({
                    "rule": rule.name,
                    "severity": "warning",
                    "details": f"操作频率超限：{len(matched)}次/{lookback_hours}h，限额{rule.max_frequency_per_hour}次/h",
                    "matched_count": len(matched),
                    "latest": matched[-1].timestamp.isoformat() if matched else "",
                })

            # 审批检查
            if rule.require_approval and matched:
                unapproved = [a for a in matched if not a.details.get("approved", False)]
                if unapproved:
                    violations.append({
                        "rule": rule.name,
                        "severity": "critical",
                        "details": f"发现 {len(unapproved)} 条未经审批的敏感操作",
                        "matched_count": len(unapproved),
                        "latest": unapproved[-1].timestamp.isoformat() if unapproved else "",
                    })

        # 通用异常：深夜操作
        night_ops = [
            a for a in recent
            if a.timestamp.hour < 6 or a.timestamp.hour >= 23
        ]
        if len(night_ops) >= 3:
            violations.append({
                "rule": "night_operations",
                "severity": "info",
                "details": f"深夜时段（23:00-06:00）检测到 {len(night_ops)} 次操作",
                "matched_count": len(night_ops),
            })

        return violations

    def add_compliance_rule(self, rule: ComplianceRule) -> str:
        self._compliance_rules.append(rule)
        return rule.rule_id

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def export_json(self, flt: AuditFilter | None = None) -> str:
        return json.dumps(
            [a.model_dump(mode="json") for a in self.query(flt)],
            ensure_ascii=False, indent=2,
        )

    def export_csv(self, flt: AuditFilter | None = None) -> str:
        logs = self.query(flt)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "audit_id", "action_type", "operator", "operator_ip",
            "target", "severity", "linked_agent_log_id", "timestamp",
        ])
        for log in logs:
            writer.writerow([
                log.audit_id, log.action_type, log.operator, log.operator_ip,
                log.target, log.severity.value, log.linked_agent_log_id or "",
                log.timestamp.isoformat(),
            ])
        return output.getvalue()

    def export_iso27001(self, flt: AuditFilter | None = None) -> str:
        """按 ISO 27001 A.12.4 格式导出审计日志"""
        logs = self.query(flt)
        lines = [
            "# ISO 27001 A.12.4 Audit Log Export",
            f"# Generated: {datetime.now().isoformat()}",
            f"# Total Records: {len(logs)}",
            "# Fields: EventID | Timestamp | Actor | Action | Object | Outcome | SourceIP",
            "",
        ]
        for log in logs:
            lines.append(
                f"{log.audit_id} | "
                f"{log.timestamp.isoformat()} | "
                f"{log.operator} | "
                f"{log.action_type} | "
                f"{log.target} | "
                f"{'success' if log.severity != Severity.CRITICAL else 'violation'} | "
                f"{log.operator_ip}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        if not self._logs:
            return {}
        actions = defaultdict(int)
        operators = defaultdict(int)
        for a in self._logs:
            actions[a.action_type] += 1
            operators[a.operator] += 1
        return {
            "total_records": len(self._logs),
            "action_distribution": dict(actions),
            "top_operators": sorted(operators.items(), key=lambda x: x[1], reverse=True)[:5],
            "earliest": self._logs[0].timestamp.isoformat() if self._logs else "",
            "latest": self._logs[-1].timestamp.isoformat() if self._logs else "",
        }


# 全局单例
audit_system = AuditSystem()
