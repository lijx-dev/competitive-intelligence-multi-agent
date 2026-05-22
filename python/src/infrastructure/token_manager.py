"""
Token 预算治理系统 — 动态配额 + 预估 + 节流 + 趋势报告。

创新点：
  1. 动态 Token 配额：按 Agent 类型/场景配置不同配额
  2. 执行前自动预估 Token 消耗，超出阈值时提示降级策略
  3. 统计每日/每周 Token 消耗趋势，生成成本分析报告
  4. 超支时自动触发「Token 节流」（暂停非核心 Agent），而非直接终止

使用示例:
    tm = TokenManager()
    tm.set_quota(TokenQuota(agent_name="research", max_input_tokens=200_000))
    ok, msg = tm.check_before_execute("research", estimated_input=150_000)
    tm.consume("research", input_tokens=500, output_tokens=200)
    report = tm.daily_report()
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from .data_models import (
    TokenBudgetStatus,
    TokenQuota,
    TokenTrendReport,
    TokenUsage,
)

logger = logging.getLogger(__name__)

# 默认配额 — 按 Agent 角色分配
DEFAULT_QUOTAS = [
    TokenQuota(agent_name="*", scenario="*", max_input_tokens=500_000, max_output_tokens=100_000),
    TokenQuota(agent_name="monitor", scenario="*", max_input_tokens=100_000, max_output_tokens=30_000),
    TokenQuota(agent_name="research", scenario="*", max_input_tokens=200_000, max_output_tokens=50_000),
    TokenQuota(agent_name="compare", scenario="*", max_input_tokens=150_000, max_output_tokens=50_000),
    TokenQuota(agent_name="battlecard", scenario="*", max_input_tokens=150_000, max_output_tokens=80_000),
]

# 价格估算（元/千token），以通义千问 qwen-turbo 为例
TOKEN_PRICE_INPUT = 0.0008   # 输入价格
TOKEN_PRICE_OUTPUT = 0.002   # 输出价格


class TokenManager:
    """Token 预算治理 — 配额 / 预估 / 消耗 / 节流 / 报告"""

    def __init__(self):
        self._quotas: list[TokenQuota] = list(DEFAULT_QUOTAS)
        self._usages: list[TokenUsage] = []
        self._throttled_agents: set[str] = set()
        self._degradation_history: list[dict] = []

    # ------------------------------------------------------------------
    # 配额管理
    # ------------------------------------------------------------------

    def set_quota(self, quota: TokenQuota) -> None:
        """设置或更新 Agent/场景的 Token 配额"""
        for i, q in enumerate(self._quotas):
            if q.agent_name == quota.agent_name and q.scenario == quota.scenario:
                self._quotas[i] = quota
                return
        self._quotas.append(quota)

    def get_quota(self, agent_name: str, scenario: str = "*") -> TokenQuota:
        """获取指定 Agent 的配额（先精确匹配，再通配）"""
        # 精确匹配
        for q in self._quotas:
            if q.agent_name == agent_name and q.scenario == scenario:
                return q
        # Agent 级通配
        for q in self._quotas:
            if q.agent_name == agent_name and q.scenario == "*":
                return q
        # 全局通配
        for q in self._quotas:
            if q.agent_name == "*" and q.scenario == "*":
                return q
        return DEFAULT_QUOTAS[0]

    def get_all_quotas(self) -> list[TokenQuota]:
        return list(self._quotas)

    # ------------------------------------------------------------------
    # 预估 + 降级策略
    # ------------------------------------------------------------------

    def check_before_execute(
        self, agent_name: str, estimated_input: int, estimated_output: int = 0
    ) -> tuple[bool, str, list[str]]:
        """执行前预估 Token 消耗，返回 (是否允许, 消息, 降级建议)。

        降级策略（按优先级）：
          1. 缩短上下文（压缩历史消息）
          2. 使用更轻量的 LLM 模型
          3. 减少 max_tokens
          4. 延迟非核心 Agent 执行
        """
        quota = self.get_quota(agent_name)
        used = self._get_used(agent_name)

        remaining_input = quota.max_input_tokens - used["input"]
        remaining_output = quota.max_output_tokens - used["output"]
        suggestions = []

        if estimated_input <= remaining_input and estimated_output <= remaining_output:
            usage_ratio = (used["input"] + estimated_input) / max(quota.max_input_tokens, 1)
            if usage_ratio >= quota.warning_threshold:
                return True, f"⚠️ 预估用量已达配额的 {usage_ratio*100:.0f}%", self._suggest_degradation(agent_name)
            return True, "✅ Token 配额充足", []

        suggestions = self._suggest_degradation(agent_name)
        msg = (
            f"❌ 预估超出配额 — 输入: {remaining_input}剩余/{estimated_input}需要, "
            f"输出: {remaining_output}剩余/{estimated_output}需要"
        )
        return False, msg, suggestions

    def _suggest_degradation(self, agent_name: str) -> list[str]:
        suggestions = []
        quota = self.get_quota(agent_name)
        used = self._get_used(agent_name)
        ratio = used["input"] / max(quota.max_input_tokens, 1)

        if ratio > 0.7:
            suggestions.append(f"1. 🔧 缩短上下文：当前已用 {ratio*100:.0f}%，建议压缩历史消息或启用摘要")
        if ratio > 0.5:
            suggestions.append("2. 🔧 切换轻量模型：考虑从 qwen-max 降级到 qwen-turbo")
        if ratio > 0.3:
            suggestions.append("3. 🔧 减少 max_tokens：降低单次响应的最大 Token 数")
        suggestions.append("4. 🔧 延迟非核心 Agent：暂停 alert/battlecard，仅保留 monitor/research/compare")
        return suggestions

    # ------------------------------------------------------------------
    # 消耗 + 节流
    # ------------------------------------------------------------------

    def consume(
        self, agent_name: str, input_tokens: int, output_tokens: int = 0
    ) -> TokenBudgetStatus:
        """记录 Token 消耗，返回当前预算状态。超支时触发节流。"""
        usage = TokenUsage(
            agent_name=agent_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self._usages.append(usage)

        quota = self.get_quota(agent_name)
        used = self._get_used(agent_name)
        status = TokenBudgetStatus(
            agent_name=agent_name,
            quota_input=quota.max_input_tokens,
            quota_output=quota.max_output_tokens,
            used_input=used["input"],
            used_output=used["output"],
            remaining_input=max(0, quota.max_input_tokens - used["input"]),
            remaining_output=max(0, quota.max_output_tokens - used["output"]),
        )
        status.usage_ratio = max(
            used["input"] / max(quota.max_input_tokens, 1),
            used["output"] / max(quota.max_output_tokens, 1),
        )

        # 超支时触发节流（而非直接终止）
        if status.usage_ratio >= 1.0:
            status.is_throttled = True
            self._throttled_agents.add(agent_name)
            status.degradation_suggestions = self._suggest_degradation(agent_name)
            self._degradation_history.append({
                "agent_name": agent_name,
                "reason": "token_quota_exceeded",
                "usage_ratio": status.usage_ratio,
                "timestamp": datetime.now().isoformat(),
            })
            logger.warning(f"[TokenManager] {agent_name} throttled: usage_ratio={status.usage_ratio:.2f}")

        return status

    def is_throttled(self, agent_name: str) -> bool:
        return agent_name in self._throttled_agents

    def reset_throttle(self, agent_name: str) -> None:
        self._throttled_agents.discard(agent_name)

    # ------------------------------------------------------------------
    # 趋势报告
    # ------------------------------------------------------------------

    def daily_report(self, days: int = 7) -> TokenTrendReport:
        """生成每日 Token 消耗趋势报告"""
        return self._trend_report("daily", days)

    def weekly_report(self, weeks: int = 4) -> TokenTrendReport:
        return self._trend_report("weekly", weeks)

    def _trend_report(self, period: str, count: int) -> TokenTrendReport:
        now = datetime.now()
        if period == "daily":
            start = now - timedelta(days=count)
            bucket_key = lambda u: u.timestamp.strftime("%Y-%m-%d")
        else:
            start = now - timedelta(weeks=count)
            bucket_key = lambda u: u.timestamp.strftime("%Y-W%W")

        filtered = [u for u in self._usages if u.timestamp >= start]
        buckets: dict[str, dict] = defaultdict(lambda: {"input": 0, "output": 0})
        agent_totals: dict[str, dict] = defaultdict(lambda: {"input": 0, "output": 0})

        for u in filtered:
            k = bucket_key(u)
            buckets[k]["input"] += u.input_tokens
            buckets[k]["output"] += u.output_tokens
            agent_totals[u.agent_name]["input"] += u.input_tokens
            agent_totals[u.agent_name]["output"] += u.output_tokens

        total_input = sum(b["input"] for b in buckets.values())
        total_output = sum(b["output"] for b in buckets.values())
        estimated_cost = (
            total_input / 1000 * TOKEN_PRICE_INPUT
            + total_output / 1000 * TOKEN_PRICE_OUTPUT
        )

        top_agents = sorted(
            [{"agent": a, "input": s["input"], "output": s["output"],
              "total": s["input"] + s["output"]} for a, s in agent_totals.items()],
            key=lambda x: x["total"], reverse=True,
        )[:5]

        trend_data = [
            {"date": k, "input_tokens": v["input"], "output_tokens": v["output"]}
            for k, v in sorted(buckets.items())
        ]

        return TokenTrendReport(
            period=period,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=now.strftime("%Y-%m-%d"),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            top_agents=top_agents,
            trend_data=trend_data,
            estimated_cost=round(estimated_cost, 4),
        )

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def get_used(self, agent_name: str) -> dict:
        """公共接口：返回指定 Agent 的累计 Token 消耗。"""
        return self._get_used(agent_name)

    def _get_used(self, agent_name: str) -> dict:
        """获取指定 Agent 的累计 Token 消耗"""
        input_total = sum(
            u.input_tokens for u in self._usages if u.agent_name == agent_name
        )
        output_total = sum(
            u.output_tokens for u in self._usages if u.agent_name == agent_name
        )
        return {"input": input_total, "output": output_total}


# 全局单例
token_manager = TokenManager()
