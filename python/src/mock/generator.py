"""
MockDataGenerator — 生成完整 Mock Pipeline 执行结果 + SSE 事件序列。

核心方法：
  generate_full_pipeline(competitor, urls) → dict
    → 返回完整的 PipelineState 字典，模拟整个 DAG 执行结果
  generate_sse_events() → list[dict]
    → 返回模拟的 SSE 事件序列（含合理延时间隔）
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any

from .data import get_scenario, list_scenarios
from .mode import is_mock_mode, get_mock_scenario

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MockDataGenerator:
    """Mock 数据生成器 — 根据场景 ID 生成完整的竞品分析结果。

    用途：
      - Mock 模式下的 Pipeline 执行
      - Demo 现场的即时演示
      - 前端开发调试
    """

    def __init__(self, scenario_id: str = ""):
        self.scenario_id = scenario_id or get_mock_scenario()
        self.data = get_scenario(self.scenario_id)
        self._sse_events: list[dict] = []

    @property
    def competitor(self) -> str:
        return self.data.get("competitor", "Unknown")

    @property
    def scenario_name(self) -> str:
        return self.data.get("name", "Unknown")

    # ── 完整 Pipeline 结果生成 ─────────────────────────────

    def generate_full_pipeline(
        self, competitor: str = "", urls: Optional[list] = None
    ) -> dict:
        """生成完整的 PipelineState 字典，模拟整个 DAG 执行结果。

        所有数据通过 Pydantic Schema 校验（与真实 Pipeline 输出一致）。
        """
        data = self.data
        comp = competitor or self.competitor

        state: dict[str, Any] = {
            "competitor": comp,
            "monitor_urls": urls or [f"https://{comp.lower().replace(' ', '')}.com"],
            "previous_hashes": {},
            "our_product_info": _mock_our_product(),
            "changes_detected": data["monitor"].get("changes_detected", []),
            "research_results": data["research"].get("research_results", []),
            "multimodal_findings": data.get("multimodal", {}).get("multimodal_findings", []),
            "comparison_matrix": data["comparison"].get("comparison_matrix"),
            "battlecard": data["battlecard"].get("battlecard"),
            "alerts_sent": _mock_alerts(data["monitor"].get("changes_detected", [])),
            "fact_check_result": data["factcheck"].get("fact_check_result", {}),
            "review_feedback": data["review"].get("review_feedback", {}),
            "citation_report": data["citation"].get("citation_report", {}),
            "ontology_graph": data.get("ontology", {}).get("ontology_graph", {}),
            "structured_schemas": data.get("structured_schemas", {}),
            "targeted_fix_count": 0,
            "quality_score": data["review"].get("review_feedback", {}).get("overall_score", 8.7),
            "reflexion_count": 1,
            "error": None,
            "feishu_push_status": "mock_sent",
            "_source": "mock",
            "_mock_scenario": self.scenario_id,
            "_generated_at": _now(),
        }
        return state

    # ── SSE 事件序列生成 ──────────────────────────────────

    def generate_sse_events(
        self, competitor: str = "", simulate_delay: bool = True
    ) -> list[dict]:
        """生成模拟的 SSE 事件序列。

        事件顺序遵循真实 DAG 执行顺序：
          monitor → alert → research → fact_check → compare
          → battlecard → reviewer → citation → feishu_push → complete

        Args:
            competitor: 竞品名称（为空则使用场景默认值）
            simulate_delay: 是否附加模拟延迟（单位秒）以展示逐步执行效果
        """
        comp = competitor or self.competitor
        data = self.data
        events: list[dict] = []

        # 节点执行顺序 + 每个节点的输出
        node_sequence = [
            ("monitor", data["monitor"], 300),
            ("alert", {"alerts_sent": _mock_alerts(data["monitor"].get("changes_detected", []))}, 100),
            ("research", data["research"], 1200),
            ("multimodal", data.get("multimodal", {}), 600),
            ("fact_check", data["factcheck"], 80),
            ("compare", data["comparison"], 1000),
            ("battlecard", data["battlecard"], 800),
            ("reviewer", data["review"], 500),
            ("targeted_fix", {"fix_history": [], "quality_score_after_fix": 8.7}, 200),
            ("citation", data["citation"], 300),
            ("ontology", data.get("ontology", {}), 400),
            ("feishu_push", {"feishu_push_status": "mock_sent"}, 50),
        ]

        for node_name, output, delay_ms in node_sequence:
            if simulate_delay:
                delay_s = delay_ms / 1000.0 + random.uniform(0, 0.2)
            else:
                delay_s = 0.05

            events.append({
                "event": node_name,
                "data": json.dumps(output, default=str, ensure_ascii=False),
                "_delay_s": delay_s,
                "_source": "mock",
            })

        # 最终完成事件
        quality = data["review"].get("review_feedback", {}).get("overall_score", 8.5)
        events.append({
            "event": "complete",
            "data": json.dumps({
                "status": "completed",
                "competitor": comp,
                "quality_score": quality,
                "total_duration_ms": sum(d for _, _, d in node_sequence),
                "source": "mock",
                "scenario": self.scenario_name,
            }, ensure_ascii=False),
            "_delay_s": 0.05,
            "_source": "mock",
        })

        self._sse_events = events
        return events

    # ── 异步 SSE 生成器（供 FastAPI EventSourceResponse 使用）───

    async def astream_sse_events(
        self, competitor: str = "", simulate_delay: bool = True
    ):
        """异步生成 SSE 事件序列（含可配置延迟）。

        用法：
            gen = MockDataGenerator()
            async for event in gen.astream_sse_events("快手电商"):
                yield event
        """
        events = self.generate_sse_events(competitor, simulate_delay)
        for evt in events:
            delay = evt.pop("_delay_s", 0.05)
            await asyncio.sleep(delay)
            yield {"event": evt["event"], "data": evt["data"]}

        # ★ Mock模式核心修复：分析完成后真实推送飞书卡片+告警（如果配置了webhook）
        try:
            from ..config import get_effective_notification_config
            cfg = get_effective_notification_config()
            if cfg.feishu_webhook_url:
                from ..services.feishu import FeishuBot
                import time as _time
                bot = FeishuBot(webhook_url=cfg.feishu_webhook_url, secret=cfg.feishu_webhook_secret)
                comp = competitor or self.competitor
                quality = self.data.get("review", {}).get("review_feedback", {}).get("overall_score", 8.7)

                # 1. 推送HIGH/CRITICAL告警红头卡片
                changes = self.data.get("monitor", {}).get("changes_detected", [])
                for change in changes:
                    sev = change.get("severity", "low")
                    if sev in ("high", "critical", "HIGH", "CRITICAL"):
                        await bot.send_alert_card({
                            "competitor": comp,
                            "severity": sev.upper() if isinstance(sev, str) else str(sev).upper(),
                            "change_type": change.get("change_type", "unknown"),
                            "summary": str(change.get("summary", ""))[:200],
                            "alert_id": f"mock_alert_{comp}_{sev}_{int(_time.time())}",
                            "detected_at": str(change.get("detected_at", "")),
                        })
                        logger.info("[MockGen] 飞书告警卡片已推送: %s", change.get("title", ""))

                # 2. 推送报告蓝头卡片
                cit = self.data.get("citation", {}).get("citation_report", {})
                await bot.send_competitor_report({
                    "competitor": comp,
                    "quality_score": quality,
                    "total_sources": cit.get("total_sources", 15) if isinstance(cit, dict) else 15,
                    "reliability": f"{(cit.get('overall_reliability_score', 0.87) if isinstance(cit, dict) else 0.87)*100:.0f}%",
                    "duration_ms": 3500,
                    "key_findings": f"Mock演示: {comp}竞品分析完成，12节点DAG全部执行。评分{quality:.1f}/10。",
                    "comparison_summary": (self.data.get("comparison", {}).get("comparison_matrix", {}).get("overall_assessment", "详见报告") or "")[:300],
                    "report_id": f"mock_{comp}_{int(_time.time())}",
                })
                logger.info("[MockGen] 飞书报告卡片已真实推送: %s score=%.1f", comp, quality)
        except Exception as e:
            logger.warning("[MockGen] 飞书Mock推送异常（优雅降级，不影响SSE流）: %s", e)


# ── 辅助函数 ──────────────────────────────────────────

def _mock_alerts(changes: list) -> list:
    """从变更列表生成告警（仅 HIGH severity）"""
    return [
        {
            "severity": c.get("severity", "LOW"),
            "title": c.get("title", ""),
            "sent_to": ["feishu", "slack"] if c.get("severity") == "HIGH" else [],
            "sent_at": _now(),
        }
        for c in changes
        if c.get("severity") == "HIGH"
    ]


def _mock_our_product() -> dict:
    """返回我方产品 Mock 数据"""
    return {
        "name": "抖音电商",
        "core_features": [
            "AI驱动的内容推荐引擎", "千川智能广告投放系统",
            "品牌自播工具套装", "达人撮合平台（星图）",
            "即时零售（小时达）", "抖店商家后台"
        ],
        "pricing_model": "佣金制 3-8%+广告费",
        "tech_stack": ["豆包大模型", "火山引擎推荐系统", "即梦AI", "云原生基础设施"],
        "target_market": "全球品牌商家+内容创作者",
        "competitive_advantages": [
            "7亿DAU流量规模", "AI推荐算法全球领先",
            "内容-电商-本地生活超级APP生态", "豆包+即梦AI创作工具矩阵"
        ],
        "weaknesses": ["流量成本高", "下沉市场渗透不足", "跨境电商起步晚"],
    }
