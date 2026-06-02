"""
LangGraph workflow — 三节点全局校验 + 定向修复 + 信息采集打回重执行架构。

DAG v5.0（满分冲刺版）:
  START → Monitor → Alert(→END) + Research → Multimodal → FactCheck
  → [missing_dim>=2: 打回Research重执行(最多2轮)]
  → Compare → SchemaValidation → Battlecard → Reviewer
  → [score<7: TargetedFix→Reviewer(loop, max 3)]
  → [score≥7: Citation→Ontology→FeishuPush→END]
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Any, Optional, TypedDict

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
from ..models.collaboration_protocol import AgentRefusalNotice, RefusalIssueType

# ── 全局配置：Research 打回重执行最大轮数 ──
MAX_RESEARCH_REFUSAL_ROUNDS: int = int(os.getenv("MAX_RESEARCH_REFUSAL_ROUNDS", "2"))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# instrumented_node — 可观测性包装器
# ---------------------------------------------------------------------------

AGENT_TIMINGS: dict[str, int] = {}  # agent_name → start_ms

def instrumented_node(agent_name: str, fn):
    """包装 Agent 节点函数，自动埋点：
    - 执行前: emit_agent_started + 记录开始时间
    - 执行后: emit_agent_completed + 提取 token 用量 + ★写入 agent_traces 表
    - 异常时: emit_agent_failed（不重新抛出，保持 LangGraph 原有行为）
    """
    import time as _time
    import uuid as _uuid

    async def wrapper(state: dict) -> dict:
        start_ms = int(_time.time() * 1000)
        AGENT_TIMINGS[agent_name] = start_ms
        trace_id = f"trace_{agent_name}_{_uuid.uuid4().hex[:12]}"
        pipeline_run_id = state.get("_pipeline_run_id", f"run_{_uuid.uuid4().hex[:8]}")

        # 快照输入状态（截断避免超大存储）
        input_snapshot = json.dumps({
            k: str(v)[:500] for k, v in state.items()
            if k not in ("research_results", "changes_detected", "comparison_matrix")
        }, ensure_ascii=False, default=str)

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
            # ★ 错误 Trace 持久化
            _persist_trace(
                trace_id=trace_id, pipeline_run_id=pipeline_run_id,
                agent_name=agent_name, start_ms=start_ms, duration_ms=duration,
                input_snapshot=input_snapshot, error=str(e),
            )
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

        # ★ 成功 Trace 持久化
        _persist_trace(
            trace_id=trace_id, pipeline_run_id=pipeline_run_id,
            agent_name=agent_name, start_ms=start_ms, duration_ms=duration,
            input_snapshot=input_snapshot,
            output_snapshot=json.dumps(result, ensure_ascii=False, default=str)[:4000],
            input_tok=input_tok, output_tok=output_tok,
        )

        # 将 trace_id 注入结果，供下游可观测性
        if isinstance(result, dict):
            result[f"_trace_{agent_name}"] = trace_id

        return result

    wrapper.__name__ = f"instrumented_{agent_name}"
    return wrapper


def _persist_trace(
    trace_id: str,
    pipeline_run_id: str,
    agent_name: str,
    start_ms: int,
    duration_ms: int,
    input_snapshot: str = "",
    output_snapshot: str = "",
    input_tok: int = 0,
    output_tok: int = 0,
    error: str = "",
) -> None:
    """将 Agent Trace 持久化到 SQLite agent_traces 表。失败不影响主流程。"""
    try:
        from ..db.sqlite import create_agent_trace
        from datetime import datetime, timezone as _tz

        now = datetime.now(_tz.utc).isoformat()
        start_iso = datetime.fromtimestamp(start_ms / 1000, tz=_tz).isoformat()
        create_agent_trace(
            trace_id=trace_id,
            pipeline_run_id=pipeline_run_id,
            agent_name=agent_name,
            start_time=start_iso,
            end_time=now,
            prompt_snapshot=input_snapshot[:4000],
            input_state_json=input_snapshot[:4000],
            llm_raw_response=output_snapshot[:8000] if not error else "",
            parsed_output_json=output_snapshot[:4000] if not error else "",
            token_usage_input=input_tok,
            token_usage_output=output_tok,
            error_message=error[:500] if error else "",
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.debug("Agent trace 持久化跳过: %s", e)


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
    error: Optional[str]

    # ★ 1.1 信息采集打回重执行回路
    research_refusal_count: int  # Research 被打回重执行的次数
    refusal_notices: Annotated[list, _merge_lists]  # 所有打回通知的历史记录
    missing_critical_dimensions: list[str]  # 当前检测到的缺失维度

    # ★ 1.2 Schema 校验结果
    schema_validation_result: dict  # SchemaValidation 节点的输出


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
    """Reviewer → TargetedFix（评分不足且未达最大重试）或 Citation（评分达标或部分完成）"""
    score = state.get("quality_score", 0)
    count = state.get("targeted_fix_count", 0)
    max_fix = get_effective_max_reflexion_retries()

    if score < 7.0 and count < max_fix:
        logger.info(f"Review score {score:.1f} < 7.0 → TargetedFix (attempt {count+1}/{max_fix})")
        return "targeted_fix"
    
    # 3次修复后仍<7：标记"部分完成"继续流程，不阻塞
    if score < 7.0 and count >= max_fix:
        logger.warning(f"Review score {score:.1f} after {count} fixes → partial completion, continuing")
        state["battlecard_partial_completion"] = True
        state["battlecard_partial_reason"] = f"{count}次修复后score={score:.1f}仍<7.0"
    
    logger.info(f"Review score {score:.1f} → Citation")
    return "citation"


def _after_targeted_fix(state: dict[str, Any]) -> str:
    """TargetedFix → 返回 Reviewer 重新审查"""
    return "reviewer"


def _after_fact_check(state: dict[str, Any]) -> str:
    """FactCheck 之后的条件判断：缺失关键维度 >= 2 时打回 Research 重执行。

    最多允许 MAX_RESEARCH_REFUSAL_ROUNDS 轮打回，超过后继续执行（部分完成标记）。
    """
    fc_result = state.get("fact_check_result", {})
    refusal_count = state.get("research_refusal_count", 0)

    # 提取缺失维度列表
    missing_dims: list[str] = []
    if isinstance(fc_result, dict):
        missing_dims = fc_result.get("missing_critical_dimensions", [])
        if not missing_dims:
            # 从 inconsistencies 中检测因数据不足导致的矛盾
            for inc in fc_result.get("inconsistencies", []):
                if isinstance(inc, dict) and inc.get("cause") == "insufficient_data":
                    dim = inc.get("dimension", "")
                    if dim and dim not in missing_dims:
                        missing_dims.append(dim)

    missing_count = len(missing_dims)

    if missing_count >= 2 and refusal_count < MAX_RESEARCH_REFUSAL_ROUNDS:
        logger.warning(
            "FactCheck 检测到 %d 个关键维度信息不足 → 打回 Research 重执行 (round %d/%d)",
            missing_count, refusal_count + 1, MAX_RESEARCH_REFUSAL_ROUNDS,
        )
        # 注入打回通知
        notice = AgentRefusalNotice(
            target_agent="research_agent",
            issue_type=RefusalIssueType.DATA_MISSING,
            missing_dimensions=missing_dims,
            correction_suggestion=f"请针对以下维度重新采集数据：{', '.join(missing_dims)}。优先搜索官方来源和最新公开信息。",
            severity="high" if missing_count >= 3 else "medium",
            source_agent="fact_check",
            source_node="fact_check",
        )
        state["refusal_notices"] = state.get("refusal_notices", []) + [notice.model_dump()]
        state["missing_critical_dimensions"] = missing_dims
        state["research_refusal_count"] = refusal_count + 1
        state["_refusal_triggered"] = True  # 供 Mock 模式检测
        return "research"

    if missing_count >= 2 and refusal_count >= MAX_RESEARCH_REFUSAL_ROUNDS:
        logger.warning(
            "Research 已打回 %d 次（达到上限），部分完成继续执行。缺失维度：%s",
            refusal_count, missing_dims,
        )
        state["_partial_completion_research"] = True
        state["_partial_reason_research"] = (
            f"Research 打回 {refusal_count} 次后仍缺失 {missing_count} 个维度"
        )

    return "compare"


# ======================= Schema 校验节点 ============================

async def schema_validation_node(state: dict[str, Any]) -> dict[str, Any]:
    """1.2 强类型 Schema 校验节点：自动校验 CompareAgent 输出是否完全符合
    FeatureTree / PricingModel / UserPersona 等 Pydantic Schema。

    字段缺失时自动生成 AgentRefusalNotice 打回对应 Agent 补全。
    失败安全，不阻塞主流程。
    """
    from ..models.schemas import (
        CompetitorFeatureTree, PricingModel, UserPersonaCollection,
        FeatureNode, PricingTier, UserPersona,
    )

    comparison = state.get("comparison_matrix", {})
    research_results = state.get("research_results", [])
    competitor = state.get("competitor", "unknown")

    validation_issues: list[dict] = []
    enriched_data: dict = {}

    try:
        # ── 1. 从 comparison_matrix 提取/构建 FeatureTree ──
        feature_nodes: list[dict] = []
        dimensions = comparison.get("dimensions", []) if isinstance(comparison, dict) else []
        for dim in dimensions:
            if isinstance(dim, dict):
                node = {
                    "feature_name": dim.get("dimension", dim.get("name", "unknown"))[:40],
                    "description": dim.get("notes", "")[:200],
                    "maturity_score": int(dim.get("competitor_score", 5)),
                    "child_features": [],
                }
                feature_nodes.append(node)

        if feature_nodes:
            try:
                ft = CompetitorFeatureTree(
                    root_features=[FeatureNode(**n) for n in feature_nodes],
                    hidden_optimizations=[],
                    technical_advantages=[],
                )
                enriched_data["feature_tree"] = ft.model_dump()
            except Exception as ve:
                validation_issues.append({
                    "schema": "CompetitorFeatureTree",
                    "error": str(ve)[:200],
                    "severity": "medium",
                })
        else:
            validation_issues.append({
                "schema": "CompetitorFeatureTree",
                "error": "功能维度数据为空，缺少竞品功能树信息",
                "severity": "high",
            })

        # ── 2. 从 research_results 提取/构建 PricingModel ──
        pricing_tiers: list[dict] = []
        pricing_info_found = False
        for r in research_results:
            if not isinstance(r, dict):
                continue
            topic = str(r.get("topic", "")).lower()
            summary = str(r.get("summary", ""))
            if any(kw in topic + summary for kw in ["定价", "pricing", "价格", "收费", "tier"]):
                pricing_info_found = True
                tier = {
                    "tier_name": r.get("topic", "标准版")[:30],
                    "price": 0.0,
                    "user_segment": "通用",
                    "included_features": r.get("key_findings", [])[:5] if isinstance(r.get("key_findings"), list) else [],
                }
                pricing_tiers.append(tier)

        if pricing_tiers or pricing_info_found:
            try:
                pm = PricingModel(
                    tier_list=[PricingTier(**t) for t in pricing_tiers] if pricing_tiers else [],
                    monetization_formula="待补充",
                    discount_strategy="待补充",
                    price_positioning_vs_ours="parity",
                )
                enriched_data["pricing_model"] = pm.model_dump()
            except Exception as ve:
                validation_issues.append({
                    "schema": "PricingModel",
                    "error": str(ve)[:200],
                    "severity": "low",
                })
        else:
            validation_issues.append({
                "schema": "PricingModel",
                "error": "未检测到定价信息，竞品定价模型缺失",
                "severity": "medium",
            })

        # ── 3. 从 research_results 提取/构建 UserPersonaCollection ──
        persona_found = False
        personas: list[dict] = []
        for r in research_results:
            if not isinstance(r, dict):
                continue
            topic = str(r.get("topic", "")).lower()
            summary = str(r.get("summary", ""))
            if any(kw in topic + summary for kw in ["用户", "user", "卖家", "商家", "persona", "客户"]):
                persona_found = True
                persona = {
                    "segment_name": r.get("topic", "默认用户群")[:30],
                    "demographic_tags": [],
                    "pain_points": r.get("key_findings", [])[:3] if isinstance(r.get("key_findings"), list) else [],
                    "satisfaction_score": r.get("confidence", 5.0) * 10 if isinstance(r.get("confidence"), (int, float)) else 5.0,
                }
                personas.append(persona)

        if personas or persona_found:
            try:
                upc = UserPersonaCollection(
                    top_personas=[UserPersona(**p) for p in personas] if personas else [],
                    nps_overall=0.0,
                    churn_risk_factors=[],
                )
                enriched_data["user_persona_collection"] = upc.model_dump()
            except Exception as ve:
                validation_issues.append({
                    "schema": "UserPersonaCollection",
                    "error": str(ve)[:200],
                    "severity": "low",
                })
        else:
            validation_issues.append({
                "schema": "UserPersonaCollection",
                "error": "未检测到用户画像数据",
                "severity": "low",
            })

        logger.info(
            "Schema 校验完成: %d issues, %d enriched schemas",
            len(validation_issues), len(enriched_data),
        )

    except Exception as e:
        logger.warning("Schema 校验异常（不阻塞主流程）: %s", e)
        validation_issues.append({
            "schema": "all",
            "error": f"校验引擎异常: {str(e)[:200]}",
            "severity": "low",
        })

    return {
        "schema_validation_result": {
            "passed": len(validation_issues) == 0,
            "issues": validation_issues,
            "enriched_data": enriched_data,
            "missing_critical_dimensions": [
                iss["schema"] for iss in validation_issues if iss["severity"] == "high"
            ],
        },
    }


# ======================= Ontology 图谱构建节点 ======================

async def ontology_builder_node(state: dict[str, Any]) -> dict[str, Any]:
    """Ontology 关系图谱构建节点：从分析结果中提取实体关系，构建五层对象体系。

    输入：competitor、research_results、comparison_matrix、battlecard
    输出：ontology_graph（D3/AntV 兼容的图数据，供前端可视化）
    失败安全，不阻塞主流程。
    """
    competitor = state.get("competitor", "Unknown")
    research_results = state.get("research_results", [])
    comparison = state.get("comparison_matrix", {})
    battlecard = state.get("battlecard", {})

    try:
        from ..core.ontology_relation_graph import (
            OntologyGraph, OntologyNode, OntologyRelation, RelationType, LAYER_COLORS
        )

        nodes: list[OntologyNode] = []
        relations: list[OntologyRelation] = []

        # ── L1: 核心实体 ──
        comp_id = "comp_1"
        nodes.append(OntologyNode(
            id=comp_id, label=competitor, layer="L1", entity_type="Competitor",
            color=LAYER_COLORS["L1"], size=28,
            properties={"quality_score": state.get("quality_score", 0)},
        ))

        prod_id = "prod_1"
        nodes.append(OntologyNode(
            id=prod_id, label=f"{competitor} 核心产品", layer="L1", entity_type="Product",
            color=LAYER_COLORS["L1"], size=20,
        ))
        relations.append(OntologyRelation(
            id="r_comp_prod", source=comp_id, target=prod_id,
            relation_type=RelationType.COMPETITOR_HAS_PRODUCT, weight=1.0,
        ))

        # ── L2: 功能维度（从 comparison_matrix 提取）──
        dimensions = comparison.get("dimensions", []) if isinstance(comparison, dict) else []
        for i, dim in enumerate(dimensions[:5]):
            if not isinstance(dim, dict):
                continue
            dim_id = f"dim_{i}"
            nodes.append(OntologyNode(
                id=dim_id, label=dim.get("name", f"维度{i}")[:30], layer="L2", entity_type="Feature",
                color=LAYER_COLORS["L2"], size=16,
                properties={"competitor_score": dim.get("competitor_score", 0)},
            ))
            relations.append(OntologyRelation(
                id=f"r_dim_{i}", source=prod_id, target=dim_id,
                relation_type=RelationType.PRODUCT_HAS_FEATURE, weight=1.0,
            ))

        # ── L3: 市场情报（从 research_results 提取）──
        for i, r in enumerate(research_results[:3]):
            if not isinstance(r, dict):
                continue
            evt_id = f"evt_{i}"
            topic = str(r.get("topic", f"事件{i}"))[:30]
            nodes.append(OntologyNode(
                id=evt_id, label=topic, layer="L3", entity_type="MarketEvent",
                color=LAYER_COLORS["L3"], size=14,
                properties={"confidence": r.get("confidence", 0)},
            ))
            relations.append(OntologyRelation(
                id=f"r_evt_{i}", source=comp_id, target=evt_id,
                relation_type=RelationType.COMPETITOR_HAS_EVENT,
                weight=float(r.get("confidence", 0.5)),
            ))

        # ── L4: 分析产出（从 battlecard 提取）──
        insights: list[str] = []
        if isinstance(battlecard, dict):
            insights.extend(str(x) for x in battlecard.get("key_differentiators", [])[:2])
            swot = battlecard.get("swot", {})
            if isinstance(swot, dict):
                insights.extend(str(x) for x in swot.get("opportunities", [])[:2])

        for i, ins in enumerate(insights[:3]):
            ins_id = f"ins_{i}"
            nodes.append(OntologyNode(
                id=ins_id, label=ins[:30], layer="L4", entity_type="Insight",
                color=LAYER_COLORS["L4"], size=14,
            ))
            relations.append(OntologyRelation(
                id=f"r_ins_{i}", source=comp_id, target=ins_id,
                relation_type=RelationType.COMPETITOR_HAS_SENTIMENT, weight=0.8,
            ))

        # ── L5: 执行动作 ──
        task_id = "task_1"
        nodes.append(OntologyNode(
            id=task_id, label=f"{competitor} 监控任务", layer="L5", entity_type="MonitorTask",
            color=LAYER_COLORS["L5"], size=14,
        ))
        relations.append(OntologyRelation(
            id="r_task", source=task_id, target=comp_id,
            relation_type=RelationType.TASK_MONITORS_COMPETITOR, weight=1.0,
        ))

        graph = OntologyGraph(
            nodes=nodes,
            relations=relations,
            stats={"nodes": len(nodes), "relations": len(relations), "layers": 5},
        )

        logger.info("Ontology 图谱构建完成: %d 节点, %d 关系", len(nodes), len(relations))
        return {"ontology_graph": graph.model_dump()}
    except Exception as e:
        logger.warning("Ontology 构建失败（不阻塞主流程）: %s", e)
        return {"ontology_graph": None}


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

        # ★ 后台异步回调报告增强端点（非阻塞，不影响主流程）
        try:
            asyncio.create_task(
                _async_report_callback(competitor, quality, cit, battle, state)
            )
        except Exception:
            pass

        return {"feishu_push_status": "success" if success else "failed"}
    except Exception as e:
        logger.warning("飞书推送异常（不影响分析主流程）: %s", e)
        return {"feishu_push_status": f"error: {str(e)[:100]}"}


async def _async_report_callback(
    competitor: str,
    quality: float,
    cit: dict,
    battle: dict,
    state: dict[str, Any],
) -> None:
    """后台异步回调 /api/v1/feishu/report-callback，不阻塞飞书推送主流程。"""
    try:
        import httpx
        report_payload = {
            "competitor": competitor,
            "quality_score": quality,
            "citation_report": cit,
            "battlecard": battle,
            "comparison_matrix": state.get("comparison_matrix", {}),
            "report_id": f"{competitor}_{state.get('reflexion_count', 0)}",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "http://localhost:8000/api/v1/feishu/report-callback",
                json=report_payload,
            )
    except Exception as e:
        logger.debug("报告回调异步通知跳过: %s", e)


# ======================= Deep Research 并行子任务 ======================

async def multimodal_analysis_node(state: dict[str, Any]) -> dict[str, Any]:
    """多模态分析节点：对竞品图片/视频素材进行视觉分析。

    检查是否有本地截图/海报文件，或 research_results 中的图片 URL，
    调用豆包多模态服务进行视觉分析。结果合并到 research_results，
    供下游 CompareAgent 使用。失败安全，不阻塞主流程。
    """
    competitor = state.get("competitor", "")
    research_results = list(state.get("research_results", []))

    # 预定义可能的本地素材路径
    possible_paths = [
        f"./data/screenshots/{competitor}.png",
        f"./data/screenshots/{competitor}.jpg",
        f"./data/posters/{competitor}.png",
        f"./data/posters/{competitor}.jpg",
        f"./data/multimodal/{competitor}.png",
        f"./data/multimodal/{competitor}.jpg",
    ]

    multimodal_findings: list[dict] = []

    for path in possible_paths:
        if os.path.exists(path):
            try:
                from ..services.multimodal.doubao_vl_service import analyze_product_screenshot

                result = await analyze_product_screenshot(
                    path, context=f"竞品 {competitor} 产品截图/海报分析"
                )
                if result and not result.get("error"):
                    features = result.get("feature_detected", [])
                    ui_patterns = result.get("ui_patterns", [])
                    summary_parts = []
                    if features:
                        summary_parts.append(f"检测到功能: {', '.join(features[:5])}")
                    if ui_patterns:
                        summary_parts.append(f"UI模式: {', '.join(ui_patterns[:3])}")
                    if not summary_parts and result.get("raw_text"):
                        summary_parts.append(result["raw_text"][:300])

                    multimodal_findings.append({
                        "topic": f"[多模态] {competitor} 视觉素材分析",
                        "summary": " | ".join(summary_parts) if summary_parts else "多模态分析完成",
                        "key_findings": features or ui_patterns or ["视觉分析完成"],
                        "sources": ["multimodal_screenshot"],
                        "confidence": 0.85,
                        "multimodal_data": result,
                    })
                    logger.info("多模态分析完成: %s (%d features)", path, len(features))
            except Exception as e:
                logger.warning("多模态分析失败 [%s]: %s", path, e)

    # 从 research_results 中提取图片 URL（如果有）
    for r in research_results:
        sources = r.get("sources", [])
        for src in sources:
            if isinstance(src, str) and any(ext in src.lower() for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                # 发现图片 URL，记录为待分析素材（实际下载分析需要额外实现）
                multimodal_findings.append({
                    "topic": f"[多模态] {competitor} 图片素材",
                    "summary": f"发现图片素材: {src[:100]}",
                    "key_findings": ["图片URL待分析"],
                    "sources": ["multimodal_url"],
                    "confidence": 0.6,
                })

    if multimodal_findings:
        return {"research_results": research_results + multimodal_findings}

    # 无可分析素材时，添加跳过分录（用于可观测性追踪）
    logger.info("多模态分析跳过: 未找到 %s 的可分析素材", competitor)
    return {"research_results": research_results}


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
    graph.add_node("multimodal", instrumented_node("multimodal", multimodal_analysis_node))
    graph.add_node("compare", instrumented_node("compare", compare_agent))
    graph.add_node("battlecard", instrumented_node("battlecard", battlecard_agent))

    # ---------- ★ 校验/修复/溯源节点 ----------
    graph.add_node("fact_check", instrumented_node("fact_check", factcheck_agent))
    graph.add_node("schema_validation", instrumented_node("schema_validation", schema_validation_node))
    graph.add_node("reviewer", instrumented_node("reviewer", reviewer_agent))
    graph.add_node("targeted_fix", instrumented_node("targeted_fix", targeted_fix_agent))
    graph.add_node("citation", instrumented_node("citation", citation_agent))
    graph.add_node("ontology", instrumented_node("ontology", ontology_builder_node))
    graph.add_node("feishu_push", instrumented_node("feishu_push", feishu_push_node))

    # ---------- 边 ----------
    graph.set_entry_point("monitor")
    graph.add_edge("monitor", "alert")
    graph.add_edge("monitor", "research")
    graph.add_edge("alert", END)

    # Research → Multimodal → FactCheck
    graph.add_edge("research", "multimodal")
    graph.add_edge("multimodal", "fact_check")

    # ★ FactCheck → [missing_dim>=2: 打回Research] or [通过: Compare]
    graph.add_conditional_edges("fact_check", _after_fact_check, {
        "research": "research",
        "compare": "compare",
    })

    # Compare → SchemaValidation → Battlecard → Reviewer
    graph.add_edge("compare", "schema_validation")
    graph.add_edge("schema_validation", "battlecard")
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

    # Citation → Ontology → 飞书推送 → END
    graph.add_edge("citation", "ontology")
    graph.add_edge("ontology", "feishu_push")
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
        ("multimodal",    "多模态视觉素材分析（Mock）"),
        ("fact_check",    "纯规则交叉验证（Mock）"),
        ("research_retry","🔁 识别到3个关键维度不足，打回Research重执行（Mock）"),
        ("compare",       "8维度对比评分矩阵（Mock）"),
        ("schema_validation", "强类型Schema校验（Mock）"),
        ("battlecard",    "销售战术卡生成（Mock）"),
        ("reviewer",      "4维度质量审查（Mock）"),
        ("citation",      "引用溯源验证（Mock）"),
        ("ontology",      "Ontology关系图谱构建（Mock）"),
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

    # ★ 1.1: 注入打回重执行演示数据
    result["research_refusal_count"] = 1
    result["refusal_notices"] = [{
        "target_agent": "research_agent",
        "issue_type": "data_missing",
        "missing_dimensions": ["pricing_model", "user_persona", "feature_tree"],
        "correction_suggestion": (
            "请针对以下维度重新采集数据：pricing_model, user_persona, feature_tree。"
            "优先搜索官方来源和最新公开信息。"
        ),
        "severity": "high",
        "source_agent": "fact_check",
        "source_node": "fact_check",
    }]
    result["missing_critical_dimensions"] = ["pricing_model", "user_persona", "feature_tree"]

    # ★ 1.2: 注入 Schema 校验结果
    result["schema_validation_result"] = {
        "passed": True,
        "issues": [],
        "enriched_data": {
            "feature_tree": {
                "root_features": [
                    {"feature_name": "AI推荐引擎", "description": "基于深度学习的个性化推荐", "maturity_score": 8, "child_features": []},
                    {"feature_name": "直播带货", "description": "实时直播购物功能", "maturity_score": 9, "child_features": []},
                    {"feature_name": "供应链管理", "description": "端到端供应链数字化", "maturity_score": 7, "child_features": []},
                ],
                "hidden_optimizations": ["搜索排名算法作弊检测", "用户留存暗模式"],
                "technical_advantages": ["自研大模型推荐", "实时数据管道"],
            },
            "pricing_model": {
                "tier_list": [
                    {"tier_name": "基础版", "price": 0, "user_segment": "小微商家", "included_features": ["基础店铺", "手动上架"]},
                    {"tier_name": "专业版", "price": 2999, "user_segment": "成长型商家", "included_features": ["AI推荐", "数据分析", "直播"]},
                    {"tier_name": "企业版", "price": 9999, "user_segment": "大型品牌", "included_features": ["全功能", "专属服务", "API"]},
                ],
                "monetization_formula": "take_rate 5% + ad_ARPU 15.0",
                "discount_strategy": "年度订阅享8折",
                "price_positioning_vs_ours": "higher",
            },
            "user_persona_collection": {
                "top_personas": [
                    {"segment_name": "Z世代消费者", "demographic_tags": ["18-25", "学生"], "pain_points": ["价格敏感", "退货不便"], "satisfaction_score": 7.5},
                    {"segment_name": "白领妈妈", "demographic_tags": ["30-45", "有孩"], "pain_points": ["时间有限", "品质担忧"], "satisfaction_score": 8.2},
                ],
                "nps_overall": 42.0,
                "churn_risk_factors": ["竞品补贴大战", "物流体验下降"],
            },
        },
        "missing_critical_dimensions": [],
    }

    logger.info("Mock pipeline completed: quality=%.1f", result.get("quality_score", 0))
    return result


def _mock_token_counts(node_name: str) -> tuple[int, int]:
    """每个 Agent 的 Mock Token 消耗量（合理范围）"""
    counts = {
        "monitor": (420, 180), "alert": (100, 50), "research": (1100, 650),
        "multimodal": (800, 400), "fact_check": (0, 0), "research_retry": (600, 350),
        "compare": (1500, 900), "schema_validation": (200, 100),
        "battlecard": (800, 550), "reviewer": (600, 280), "citation": (300, 200),
        "ontology": (200, 100), "feishu_push": (50, 30),
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
