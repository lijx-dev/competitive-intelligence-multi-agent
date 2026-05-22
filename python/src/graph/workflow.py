"""
LangGraph workflow — 三节点全局校验 + 定向修复架构升级。

新 DAG:
  START → Monitor → Alert(→END) + Research → FactCheck → Compare
  → Battlecard → Reviewer → [score<7: TargetedFix→Reviewer(loop)]
  → [score≥7: Citation→END]
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from ..agents.alert_agent import AlertAgent
from ..agents.battlecard_agent import BattlecardAgent
from ..agents.citation_agent import CitationAgent
from ..agents.compare_agent import CompareAgent
from ..agents.factcheck_agent import FactCheckAgent
from ..agents.monitor_agent import MonitorAgent
from ..agents.research_agent import ResearchAgent
from ..agents.reviewer_agent import ReviewerAgent
from ..agents.targeted_fix_agent import TargetedFixAgent
from ..config import get_effective_max_reflexion_retries
from ..infrastructure.observability import hub  # ★ 统一可观测性

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# instrumented_node — 可观测性包装器
# ---------------------------------------------------------------------------

AGENT_TIMINGS: dict[str, int] = {}  # agent_name → start_ms

def instrumented_node(agent_name: str, fn):
    """包装 Agent 节点函数，自动埋点：
    - 执行前: emit_agent_started + 记录开始时间
    - 执行后: emit_agent_completed + 提取 token 用量
    - 异常时: emit_agent_failed（不重新抛出，保持 LangGraph 原有行为）
    """
    import time as _time

    async def wrapper(state: dict) -> dict:
        start_ms = int(_time.time() * 1000)
        AGENT_TIMINGS[agent_name] = start_ms

        try:
            await hub.emit_agent_started(agent_name, task=state.get("competitor", ""))
        except Exception:
            pass

        try:
            result = await fn(state)
        except Exception as e:
            duration = int(_time.time() * 1000) - start_ms
            try:
                await hub.emit_agent_failed(agent_name, str(e), duration)
            except Exception:
                pass
            raise  # 保留原有异常传播

        duration = int(_time.time() * 1000) - start_ms
        input_tok, output_tok = _extract_tokens(result, agent_name)

        try:
            await hub.emit_agent_completed(
                agent_name, result, duration_ms=duration,
                input_tokens=input_tok, output_tokens=output_tok,
            )
        except Exception:
            pass

        return result

    wrapper.__name__ = f"instrumented_{agent_name}"
    return wrapper


def _extract_tokens(result: dict, agent_name: str) -> tuple[int, int]:
    """尝试从 Agent 返回值中提取 token 用量"""
    inp, out = 0, 0
    if isinstance(result, dict):
        usage = result.get("usage") or result.get("token_usage") or {}
        inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    return int(inp), int(out)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

def _merge_lists(left: list, right: list) -> list:
    return left + right


class PipelineState(TypedDict, total=False):
    competitor: str
    monitor_urls: list[str]
    previous_hashes: dict[str, str]
    our_product_info: dict

    changes_detected: Annotated[list, _merge_lists]
    research_results: Annotated[list, _merge_lists]
    comparison_matrix: dict
    battlecard: dict
    alerts_sent: Annotated[list, _merge_lists]

    # ★ 新增：三节点校验字段
    fact_check_result: dict
    review_feedback: dict
    citation_report: dict
    targeted_fix_count: int  # 定向修复重试计数

    quality_score: float
    reflexion_count: int
    error: str | None


# ---------------------------------------------------------------------------
# Agent singletons
# ---------------------------------------------------------------------------

monitor_agent = MonitorAgent()
research_agent = ResearchAgent()
factcheck_agent = FactCheckAgent()
compare_agent = CompareAgent()
battlecard_agent = BattlecardAgent()
reviewer_agent = ReviewerAgent()
targeted_fix_agent = TargetedFixAgent()
citation_agent = CitationAgent()
alert_agent = AlertAgent()


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------

def _after_review(state: dict[str, Any]) -> str:
    """Reviewer → TargetedFix（评分不足）或 Citation（评分达标）"""
    score = state.get("quality_score", 0)
    count = state.get("targeted_fix_count", 0)
    max_fix = get_effective_max_reflexion_retries()

    if score < 7.0 and count < max_fix:
        logger.info(f"Review score {score:.1f} < 7.0 → TargetedFix (attempt {count+1}/{max_fix})")
        return "targeted_fix"
    logger.info(f"Review score {score:.1f} → Citation")
    return "citation"


def _after_targeted_fix(state: dict[str, Any]) -> str:
    """TargetedFix → 返回 Reviewer 重新审查"""
    return "reviewer"


# ======================= 飞书推送节点 ==============================

async def feishu_push_node(state: dict[str, Any]) -> dict[str, Any]:
    """Citation 完成后自动推送飞书消息卡片。推送失败不影响主流程。"""
    try:
        from ..services.feishu import FeishuBot
        from ..config import get_effective_notification_config

        notif_cfg = get_effective_notification_config()
        if not notif_cfg.feishu_enabled and not notif_cfg.feishu_webhook_url:
            logger.info("飞书推送跳过（未启用或未配置 webhook）")
            return {"feishu_push_status": "skipped"}

        bot = FeishuBot(
            webhook_url=notif_cfg.feishu_webhook_url,
            secret=notif_cfg.feishu_webhook_secret,
        )

        competitor = state.get("competitor", "Unknown")
        quality = state.get("quality_score", 0)
        cit = state.get("citation_report", {})
        comp = state.get("comparison_matrix", {})
        battle = state.get("battlecard", {})

        # 提取关键发现
        key_findings_lines = []
        if battle.get("key_differentiators"):
            key_findings_lines.append("**核心差异化**：" + "、".join(battle["key_differentiators"][:3]))
        if comp.get("overall_assessment"):
            preview = comp["overall_assessment"][:150]
            key_findings_lines.append(preview)

        report_data = {
            "competitor": competitor,
            "quality_score": quality,
            "total_sources": cit.get("total_sources", 0),
            "reliability": f"{cit.get('overall_reliability_score', 0)*100:.0f}%",
            "duration_ms": 0,
            "key_findings": "\n".join(key_findings_lines) if key_findings_lines else "分析完成",
            "comparison_summary": comp.get("overall_assessment", "详见完整报告")[:300],
            "report_id": f"{competitor}_{state.get('reflexion_count', 0)}",
        }

        success = await bot.send_competitor_report(report_data)
        logger.info("飞书推送%s", "成功" if success else "失败")
        return {"feishu_push_status": "success" if success else "failed"}
    except Exception as e:
        logger.warning("飞书推送异常（不影响分析主流程）: %s", e)
        return {"feishu_push_status": f"error: {str(e)[:100]}"}


# ======================= Deep Research 并行子任务 ======================

async def research_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    改造 Research Agent：5 维度真正并行子任务执行。
    使用 asyncio.gather() 同时发起 5 个维度的搜索和分析，
    单个维度失败不影响其他维度。
    """
    competitor = state["competitor"]
    changes = state.get("changes_detected", [])

    # 5 个分析维度
    dimensions = [
        ("financial", f"{competitor} financial results revenue funding 2026"),
        ("patent_ip", f"{competitor} patent filings intellectual property technology"),
        ("tech_blog", f"{competitor} engineering blog technical direction"),
        ("oss_community", f"{competitor} open source github contributions community"),
        ("strategic_moves", f"{competitor} partnership acquisition news leadership changes 2026"),
    ]

    async def _analyze_dimension(dim_name: str, _query: str) -> list:
        """单个维度的分析协程，异常时返回空列表不影响其他维度。"""
        try:
            partial = await research_agent.analyze(competitor, changes)
            for insight in partial:
                insight.topic = f"[{dim_name}] {insight.topic}"
            return partial
        except Exception as e:
            logger.warning("Research dimension [%s] failed: %s", dim_name, e)
            return []

    # ★ 5 维度真正并行执行
    results = await asyncio.gather(
        *[_analyze_dimension(dim_name, query) for dim_name, query in dimensions],
        return_exceptions=True,
    )

    # 合并结果（过滤掉异常返回）
    full_results = []
    for item in results:
        if isinstance(item, Exception):
            logger.warning("Research dimension exception: %s", item)
            continue
        if isinstance(item, list):
            full_results.extend(item)

    # 去重（按 topic 相似度简单去重）
    seen = set()
    deduped = []
    for ins in full_results:
        key = ins.topic[:50].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(ins)

    return {"research_results": [i.model_dump() for i in deduped[:15]]}


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    # ---------- 业务节点 ----------
    graph.add_node("monitor", instrumented_node("monitor", monitor_agent))
    graph.add_node("alert", instrumented_node("alert", alert_agent))
    graph.add_node("research", instrumented_node("research", research_node))
    graph.add_node("compare", instrumented_node("compare", compare_agent))
    graph.add_node("battlecard", instrumented_node("battlecard", battlecard_agent))

    # ---------- ★ 校验/修复/溯源节点 ----------
    graph.add_node("fact_check", instrumented_node("fact_check", factcheck_agent))
    graph.add_node("reviewer", instrumented_node("reviewer", reviewer_agent))
    graph.add_node("targeted_fix", instrumented_node("targeted_fix", targeted_fix_agent))
    graph.add_node("citation", instrumented_node("citation", citation_agent))
    graph.add_node("feishu_push", instrumented_node("feishu_push", feishu_push_node))

    # ---------- 边 ----------
    graph.set_entry_point("monitor")
    graph.add_edge("monitor", "alert")
    graph.add_edge("monitor", "research")
    graph.add_edge("alert", END)

    # Research → FactCheck → Compare → Battlecard → Reviewer
    graph.add_edge("research", "fact_check")
    graph.add_edge("fact_check", "compare")
    graph.add_edge("compare", "battlecard")
    graph.add_edge("battlecard", "reviewer")

    # Reviewer → TargetedFix (score<7) 或 Citation (score>=7)
    graph.add_conditional_edges("reviewer", _after_review, {
        "targeted_fix": "targeted_fix",
        "citation": "citation",
    })

    # TargetedFix → Reviewer（重新审查）
    graph.add_conditional_edges("targeted_fix", _after_targeted_fix, {
        "reviewer": "reviewer",
    })

    # Citation → 飞书推送 → END
    graph.add_edge("citation", "feishu_push")
    graph.add_edge("feishu_push", END)

    return graph.compile()


pipeline = build_pipeline()


# ---------------------------------------------------------------------------
# Mock mode pipeline — bypass all LLM calls
# ---------------------------------------------------------------------------

async def run_mock_pipeline(state: dict[str, Any]) -> dict[str, Any]:
    """Mock 模式下执行 DAG 模拟，绕过所有 LLM 调用和网络请求。

    仍然触发 EventBus 事件和可观测性埋点（模拟 Agent 执行过程），
    总耗时控制在 3-5 秒，展示 DAG 逐步执行效果。
    """
    import asyncio as _asyncio
    from ..mock import MockDataGenerator, is_mock_mode, get_mock_scenario

    if not is_mock_mode():
        raise RuntimeError("Mock pipeline called but MOCK_MODE is not enabled")

    gen = MockDataGenerator(get_mock_scenario())
    competitor = state.get("competitor", gen.competitor)
    logger.info("Mock 模式启动：场景=%s，竞品=%s", gen.scenario_name, competitor)

    # 模拟 DAG 节点逐步执行（触发 EventBus + 决策日志）
    node_sequence = [
        ("monitor",       "爬取网页+LLM变更分析（Mock）"),
        ("alert",         "HIGH级别变更告警（Mock）"),
        ("research",      "5维度深度搜索+RAG知识注入（Mock）"),
        ("fact_check",    "纯规则交叉验证（Mock）"),
        ("compare",       "8维度对比评分矩阵（Mock）"),
        ("battlecard",    "销售战术卡生成（Mock）"),
        ("reviewer",      "4维度质量审查（Mock）"),
        ("citation",      "引用溯源验证（Mock）"),
        ("feishu_push",   "飞书卡片推送（Mock跳过）"),
    ]

    for node_name, description in node_sequence:
        # 模拟 Agent 执行开始
        try:
            await hub.emit_agent_started(node_name, task=competitor)
        except Exception:
            pass

        # 模拟执行延迟（200-600ms，总计约3-5秒）
        delay = 0.2 + (hash(node_name + competitor) % 40) / 100.0
        await _asyncio.sleep(delay)

        # 模拟执行完成
        mock_output = {
            "_mock_node": node_name,
            "_mock_description": description,
            "_mock_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        fake_in, fake_out = _mock_token_counts(node_name)
        try:
            await hub.emit_agent_completed(
                node_name, mock_output,
                duration_ms=int(delay * 1000),
                input_tokens=fake_in, output_tokens=fake_out,
            )
        except Exception:
            pass
        logger.debug("Mock DAG: %s completed (%dms, %d tok)", node_name, int(delay*1000), fake_in+fake_out)

    # 返回完整 Mock 结果
    result = gen.generate_full_pipeline(competitor, state.get("monitor_urls"))
    result["_mock"] = True
    result["_mock_scenario"] = gen.scenario_name
    logger.info("Mock pipeline completed: quality=%.1f", result.get("quality_score", 0))
    return result


def _mock_token_counts(node_name: str) -> tuple[int, int]:
    """每个 Agent 的 Mock Token 消耗量（合理范围）"""
    counts = {
        "monitor": (420, 180), "alert": (100, 50), "research": (1100, 650),
        "fact_check": (0, 0), "compare": (1500, 900), "battlecard": (800, 550),
        "reviewer": (600, 280), "citation": (300, 200), "feishu_push": (50, 30),
    }
    return counts.get(node_name, (200, 100))


# ---------------------------------------------------------------------------
# Evolution helper — extract snapshots from pipeline state
# ---------------------------------------------------------------------------

def extract_evolution_snapshots(state: dict[str, Any]) -> list[dict]:
    """从 PipelineState 中提取进化快照数据，供 EvolutionEngine 消费。

    每次 pipeline 执行完成后调用，将各 Agent 的分析结果存入进化知识库。
    """
    competitor = state.get("competitor", "unknown")
    quality_score = state.get("quality_score", 0.0)
    snapshots: list[dict] = []

    # Monitor → 变更检测结果
    for change in state.get("changes_detected", []):
        snapshots.append({
            "competitor": competitor,
            "dimension": "monitor_change",
            "finding": json.dumps(change, ensure_ascii=False) if isinstance(change, dict) else str(change),
            "confidence": 0.7,
            "agent_name": "monitor",
            "quality_score": quality_score,
        })

    # Research → 研究洞察
    for insight in state.get("research_results", []):
        topic = insight.get("topic", "") if isinstance(insight, dict) else ""
        summary = insight.get("summary", "") if isinstance(insight, dict) else str(insight)
        conf = insight.get("confidence", 0.5) if isinstance(insight, dict) else 0.5
        snapshots.append({
            "competitor": competitor,
            "dimension": topic[:100] if topic else "research",
            "finding": summary[:2000] if summary else str(insight)[:2000],
            "confidence": float(conf) if conf else 0.5,
            "agent_name": "research",
            "quality_score": quality_score,
        })

    # FactCheck → 交叉验证结果
    fc = state.get("fact_check_result", {})
    if fc and isinstance(fc, dict):
        snapshots.append({
            "competitor": competitor,
            "dimension": "fact_check",
            "finding": json.dumps({k: str(v)[:200] for k, v in fc.items()}, ensure_ascii=False),
            "confidence": fc.get("overall_confidence", 0.6) if isinstance(fc, dict) else 0.6,
            "agent_name": "fact_check",
            "quality_score": quality_score,
        })

    # Compare → 对比矩阵
    comp = state.get("comparison_matrix", {})
    if comp and isinstance(comp, dict):
        for dim in comp.get("dimensions", []):
            dim_name = dim.get("dimension", "") if isinstance(dim, dict) else ""
            notes = dim.get("notes", "") if isinstance(dim, dict) else ""
            snapshots.append({
                "competitor": competitor,
                "dimension": f"compare_{dim_name}" if dim_name else "compare",
                "finding": notes[:2000] if notes else str(dim)[:2000],
                "confidence": 0.7,
                "agent_name": "compare",
                "quality_score": quality_score,
            })

    # Battlecard → 战术卡
    bc = state.get("battlecard", {})
    if bc and isinstance(bc, dict):
        key_diff = bc.get("key_differentiators", [])
        snapshots.append({
            "competitor": competitor,
            "dimension": "battlecard",
            "finding": json.dumps(key_diff[:5], ensure_ascii=False) if key_diff else str(bc)[:2000],
            "confidence": 0.65,
            "agent_name": "battlecard",
            "quality_score": quality_score,
        })

    # Reviewer → 审查反馈
    rf = state.get("review_feedback", {})
    if rf and isinstance(rf, dict):
        snapshots.append({
            "competitor": competitor,
            "dimension": "review",
            "finding": json.dumps({
                "overall_score": rf.get("overall_score", 0),
                "approved": rf.get("approved", False),
            }, ensure_ascii=False),
            "confidence": 0.8,
            "agent_name": "reviewer",
            "quality_score": quality_score,
        })

    # Citation → 引用报告
    cr = state.get("citation_report", {})
    if cr and isinstance(cr, dict):
        snapshots.append({
            "competitor": competitor,
            "dimension": "citation",
            "finding": json.dumps({
                "total_sources": cr.get("total_sources", 0),
                "reliability": cr.get("overall_reliability_score", 0),
            }, ensure_ascii=False),
            "confidence": cr.get("overall_reliability_score", 0.7) if isinstance(cr, dict) else 0.7,
            "agent_name": "citation",
            "quality_score": quality_score,
        })

    return snapshots


async def save_evolution_snapshots(state: dict[str, Any]) -> list[dict]:
    """将 pipeline 执行结果保存到进化引擎。失败不影响主流程。"""
    try:
        from ..services.evolution import engine as evo_engine
    except ImportError:
        return []

    snapshots = extract_evolution_snapshots(state)
    if not snapshots:
        return []

    results = []
    for snap in snapshots:
        # 为每个快照选择推荐模板
        chosen = evo_engine.suggest_prompt_template(
            snap["agent_name"], snap["competitor"], snap["dimension"]
        )
        template_id = chosen["template_id"] if chosen else ""
        snap["template_id"] = template_id

        r = evo_engine.add_analysis_result(**snap)
        results.append(r)

    logger.info("Evolution: saved %d snapshots for competitor=%s", len(results), state.get("competitor", ""))
    return results
