"""FastAPI server exposing the CI pipeline via REST + SSE endpoints."""
# __future__ 导入必须放在最开头（文档字符串后，其他导入前），且仅出现一次
from __future__ import annotations

# 新增：数据库操作导入
from ..db.sqlite import (
    init_db,
    create_competitor,
    get_all_competitors,
    get_competitor_by_id,
    update_competitor,
    delete_competitor,
    create_analysis_record,
    get_all_analysis_records,
    get_analysis_record_by_id,
    get_all_config,
    set_config_value,
    batch_set_config,
    export_config,
    import_config,
    get_config_history,
    rollback_config,
    get_db_stats,
    get_our_product,
    update_our_product,
    create_feedback_record,
    get_feedback_records,
    create_analysis_snapshot,
    get_snapshot_by_key,
    get_feedback_stats,
    update_template_score,
    get_template_ranking,
)
# 新增：Pydantic模型导入
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from ..graph.workflow import pipeline, PipelineState
from ..config import get_all_defaults, get_effective_notification_config
from ..tools.notification import send_slack, send_dingtalk, send_email

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    competitor: str
    urls: list[str] | None = None


class AnalyzeResponse(BaseModel):
    competitor: str
    changes_detected: list = []
    research_results: list = []
    comparison_matrix: dict | None = None
    battlecard: dict | None = None
    alerts_sent: list = []
    quality_score: float = 0.0


class HealthResponse(BaseModel):
    status: str
    timestamp: str

# ---------------------------------------------------------------------------
# 新增：竞品管理相关模型
# ---------------------------------------------------------------------------
class CompetitorCreateRequest(BaseModel):
    name: str = Field(description="竞品名称", min_length=1)
    urls: List[str] = Field(description="监控URL列表", default_factory=list)

class CompetitorUpdateRequest(BaseModel):
    name: str = Field(description="竞品名称", min_length=1)
    urls: List[str] = Field(description="监控URL列表", default_factory=list)

class CompetitorResponse(BaseModel):
    id: int
    name: str
    urls: List[str]
    created_at: str
    updated_at: str

# ---------------------------------------------------------------------------
# 新增：历史分析记录相关模型
# ---------------------------------------------------------------------------
class AnalysisRecordResponse(BaseModel):
    id: int
    competitor_id: Optional[int]
    competitor_name: str
    request_urls: List[str]
    analysis_result: Dict[str, Any]
    quality_score: float
    created_at: str
# ---------------------------------------------------------------------------
# 新增：系统配置相关模型
# ---------------------------------------------------------------------------
class ConfigSetRequest(BaseModel):
    alert: Optional[Dict[str, Any]] = None
    notification: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = None
    pipeline: Optional[Dict[str, Any]] = None


class NotificationTestRequest(BaseModel):
    channel: str = Field(description="通知渠道：slack / dingtalk / email")
    message: str = Field(default="🧪 这是一条来自竞品情报系统的测试通知。")


class ConfigImportRequest(BaseModel):
    configs: Dict[str, Any]


class ConfigRollbackRequest(BaseModel):
    key: str
    version: int

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CI Multi-Agent Pipeline started")
    # 新增：服务启动时自动初始化数据库
    init_db()
    logger.info("Database initialized successfully")
    # 进化引擎：初始化模板评分种子数据
    try:
        from ..services.evolution.knowledge_base import seed_default_templates
        seed_default_templates()
        logger.info("Evolution templates seeded")
    except Exception as e:
        logger.warning("Evolution template seeding skipped: %s", e)
    yield
    logger.info("CI Multi-Agent Pipeline shutting down")


app = FastAPI(
    title="Multi-Agent Competitive Intelligence System",
    description=(
        "Enterprise-grade CI system with 5 specialized agents: "
        "Monitor, Research, Compare, Battlecard, and Alert."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", timestamp=datetime.utcnow().isoformat())


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """Run the full pipeline synchronously and return the final state."""
    # ── Mock 模式：跳过 LLM，使用预生成数据 ──
    from ..mock import is_mock_mode
    if is_mock_mode():
        from ..graph.workflow import run_mock_pipeline
        logger.info("Mock 模式：分析 %s", req.competitor)
        initial_state: PipelineState = {
            "competitor": req.competitor,
            "monitor_urls": req.urls or [],
            "our_product_info": get_our_product(),
        }
        try:
            final = await run_mock_pipeline(initial_state)
        except Exception as exc:
            logger.exception("Mock pipeline failed")
            raise HTTPException(status_code=500, detail=str(exc))

        response_data = AnalyzeResponse(
            competitor=final.get("competitor", req.competitor),
            changes_detected=final.get("changes_detected", []),
            research_results=final.get("research_results", []),
            comparison_matrix=final.get("comparison_matrix"),
            battlecard=final.get("battlecard"),
            alerts_sent=final.get("alerts_sent", []),
            quality_score=final.get("quality_score", 0.0),
        )

        # 仍然存入数据库
        try:
            competitor_id = None
            for comp in get_all_competitors():
                if comp["name"] == req.competitor:
                    competitor_id = comp["id"]
                    break
            create_analysis_record(
                competitor_id=competitor_id,
                competitor_name=req.competitor,
                request_urls=req.urls or [],
                analysis_result=response_data.model_dump(),
                quality_score=response_data.quality_score
            )
        except Exception as e:
            logger.warning("Mock分析记录存库失败：%s", e)

        try:
            from ..graph.workflow import save_evolution_snapshots
            asyncio.create_task(save_evolution_snapshots(final))
        except Exception:
            pass

        return response_data

    # ── 生产模式：执行真实 Pipeline ──
    initial_state: PipelineState = {
        "competitor": req.competitor,
        "monitor_urls": req.urls or [],
        "previous_hashes": {},
        "our_product_info": get_our_product(),
        "changes_detected": [],
        "research_results": [],
        "comparison_matrix": None,
        "battlecard": None,
        "alerts_sent": [],
        "fact_check_result": {},
        "review_feedback": {},
        "citation_report": {},
        "targeted_fix_count": 0,
        "quality_score": 0.0,
        "reflexion_count": 0,
        "error": None,
    }
    try:
        final = await pipeline.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc))

    # 核心修复：递归遍历所有字段，把datetime全部转成ISO字符串
    def convert_datetime(obj):
        if isinstance(obj, dict):
            return {k: convert_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_datetime(i) for i in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    # 对最终结果做全量序列化转换
    final_safe = convert_datetime(final)

    # -------------------------- 新增：分析完成后自动存入数据库 --------------------------
    # 构造返回结果
    response_data = AnalyzeResponse(
        competitor=final_safe["competitor"],
        changes_detected=final_safe.get("changes_detected", []),
        research_results=final_safe.get("research_results", []),
        comparison_matrix=final_safe.get("comparison_matrix"),
        battlecard=final_safe.get("battlecard"),
        alerts_sent=final_safe.get("alerts_sent", []),
        quality_score=final_safe.get("quality_score", 0.0),
    )
    # 自动存入历史记录
    try:
        # 查找竞品ID（如果存在）
        competitor_id = None
        competitors = get_all_competitors()
        for comp in competitors:
            if comp["name"] == req.competitor:
                competitor_id = comp["id"]
                break
        # 存入数据库
        create_analysis_record(
            competitor_id=competitor_id,
            competitor_name=req.competitor,
            request_urls=req.urls or [],
            analysis_result=response_data.model_dump(),
            quality_score=response_data.quality_score
        )
        logger.info(f"分析记录已存入数据库，竞品：{req.competitor}")
    except Exception as e:
        logger.warning(f"分析记录存库失败：{str(e)}，不影响核心分析流程")
    # -------------------------- 进化引擎：保存分析快照 --------------------------
    try:
        from ..graph.workflow import save_evolution_snapshots
        import asyncio as _asyncio
        _asyncio.create_task(save_evolution_snapshots(final_safe))
    except Exception as e:
        logger.warning(f"进化快照保存失败：{str(e)}，不影响核心分析流程")
    # -----------------------------------------------------------------------------------

    return response_data


@app.post("/analyze/stream")
async def analyze_stream(req: AnalyzeRequest):
    """Stream pipeline events via Server-Sent Events (SSE) so the frontend
    can show real-time progress."""

    # ── Mock 模式：返回预生成 SSE 事件序列 ──
    from ..mock import is_mock_mode
    if is_mock_mode():
        from ..mock import MockDataGenerator, get_mock_scenario

        async def mock_event_generator() -> AsyncGenerator[dict, None]:
            gen = MockDataGenerator(get_mock_scenario())
            logger.info("Mock SSE 模式：场景=%s，竞品=%s", gen.scenario_name, req.competitor)
            async for evt in gen.astream_sse_events(req.competitor, simulate_delay=True):
                yield evt

            # SSE 完成后存库
            try:
                result = gen.generate_full_pipeline(req.competitor, req.urls)
                final_analysis_result = {
                    "changes_detected": result.get("changes_detected", []),
                    "research_results": result.get("research_results", []),
                    "comparison_matrix": result.get("comparison_matrix"),
                    "battlecard": result.get("battlecard"),
                    "alerts_sent": result.get("alerts_sent", []),
                }
                final_quality_score = result.get("quality_score", 0.0)
                competitor_id = None
                for comp in get_all_competitors():
                    if comp["name"] == req.competitor:
                        competitor_id = comp["id"]
                        break
                create_analysis_record(
                    competitor_id=competitor_id,
                    competitor_name=req.competitor,
                    request_urls=req.urls or [],
                    analysis_result=final_analysis_result,
                    quality_score=final_quality_score
                )
            except Exception as e:
                logger.warning("Mock SSE 存库失败：%s", e)

        return EventSourceResponse(mock_event_generator())

    # ── 生产模式：真实 SSE Pipeline ──

    async def event_generator() -> AsyncGenerator[dict, None]:
        initial_state: PipelineState = {
            "competitor": req.competitor,
            "monitor_urls": req.urls or [],
            "previous_hashes": {},
            "our_product_info": get_our_product(),
            "changes_detected": [],
            "research_results": [],
            "comparison_matrix": {},
            "battlecard": {},
            "alerts_sent": [],
            "fact_check_result": {},
            "review_feedback": {},
            "citation_report": {},
            "targeted_fix_count": 0,
            "quality_score": 0.0,
            "reflexion_count": 0,
            "error": None,
        }

        # 新增：收集所有节点的结果，用于最后存库
        node_results = {}

        try:
            async for event in pipeline.astream(initial_state):
                for node_name, node_output in event.items():
                    # 保存节点结果
                    node_results[node_name] = node_output
                    yield {
                        "event": node_name,
                        "data": json.dumps(node_output, default=str, ensure_ascii=False),
                    }

            # -------------------------- 新增：流式分析完成后自动存入数据库 --------------------------
            try:
                # 构造完整的分析结果
                final_analysis_result = {
                    "changes_detected": node_results.get("monitor", {}).get("changes_detected", []),
                    "research_results": node_results.get("research", {}).get("research_results", []),
                    "comparison_matrix": node_results.get("compare", {}).get("comparison_matrix"),
                    "battlecard": node_results.get("battlecard", {}).get("battlecard"),
                    "alerts_sent": node_results.get("alert", {}).get("alerts_sent", []),
                }
                final_quality_score = node_results.get("quality_check", {}).get("quality_score", 0.0)

                # 查找竞品ID
                competitor_id = None
                competitors = get_all_competitors()
                for comp in competitors:
                    if comp["name"] == req.competitor:
                        competitor_id = comp["id"]
                        break

                # 存入数据库
                create_analysis_record(
                    competitor_id=competitor_id,
                    competitor_name=req.competitor,
                    request_urls=req.urls or [],
                    analysis_result=final_analysis_result,
                    quality_score=final_quality_score
                )
                logger.info(f"流式分析记录已存入数据库，竞品：{req.competitor}")
            except Exception as e:
                logger.warning(f"流式分析记录存库失败：{str(e)}，不影响核心分析流程")
            # -------------------------- 进化引擎：保存分析快照 --------------------------
            try:
                from ..graph.workflow import save_evolution_snapshots
                # 合并 final node_results 为完整 state
                merged_state = {
                    "competitor": req.competitor,
                    "monitor_urls": req.urls or [],
                    "quality_score": final_quality_score,
                }
                for n, v in node_results.items():
                    if isinstance(v, dict):
                        for k2, v2 in v.items():
                            merged_state[k2] = v2
                asyncio.create_task(save_evolution_snapshots(merged_state))
            except Exception as e:
                logger.warning(f"进化快照保存失败：{str(e)}，不影响核心分析流程")
            # -----------------------------------------------------------------------------------

        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}),
            }

    return EventSourceResponse(event_generator())


@app.get("/competitors", summary="竞品列表（兼容旧版路径）")
async def legacy_list_competitors():
    """遗留端点 — 转发到标准 /competitors/all。"""
    return await list_all_competitors()
# ---------------------------------------------------------------------------
# 新增：竞品管理接口
# ---------------------------------------------------------------------------
@app.get("/competitors/all", response_model=List[CompetitorResponse], summary="获取所有竞品列表")
async def list_all_competitors():
    """获取竞品库中所有竞品的完整列表"""
    return get_all_competitors()

@app.get("/competitors/{competitor_id}", response_model=CompetitorResponse, summary="根据ID获取竞品详情")
async def get_competitor(competitor_id: int):
    """根据竞品ID获取详情，不存在则返回404"""
    competitor = get_competitor_by_id(competitor_id)
    if not competitor:
        raise HTTPException(status_code=404, detail=f"ID为{competitor_id}的竞品不存在")
    return competitor

@app.post("/competitors", response_model=CompetitorResponse, summary="新增竞品")
async def add_competitor(req: CompetitorCreateRequest):
    """新增竞品到竞品库，名称重复会报错"""
    try:
        return create_competitor(name=req.name, urls=req.urls)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/competitors/{competitor_id}", response_model=CompetitorResponse, summary="更新竞品信息")
async def edit_competitor(competitor_id: int, req: CompetitorUpdateRequest):
    """根据ID更新竞品的名称和监控URL"""
    try:
        return update_competitor(competitor_id=competitor_id, name=req.name, urls=req.urls)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/competitors/{competitor_id}", summary="删除竞品")
async def remove_competitor(competitor_id: int):
    """根据ID删除竞品，不存在则返回404"""
    try:
        delete_competitor(competitor_id)
        return {"status": "success", "message": f"竞品ID{competitor_id}删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ---------------------------------------------------------------------------
# 新增：历史分析记录接口
# ---------------------------------------------------------------------------
@app.get("/analysis/records", response_model=List[AnalysisRecordResponse], summary="获取所有分析记录")
async def list_analysis_records(competitor_id: Optional[int] = None):
    """获取所有历史分析记录，可按竞品ID筛选"""
    return get_all_analysis_records(competitor_id=competitor_id)

@app.get("/analysis/records/{record_id}", response_model=AnalysisRecordResponse, summary="根据ID获取分析记录详情")
async def get_analysis_record(record_id: int):
    """根据记录ID获取分析详情，不存在则返回404"""
    record = get_analysis_record_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"ID为{record_id}的分析记录不存在")
    return record


# ==================================================================
#  系统配置 API
# ==================================================================

@app.get("/api/config", summary="获取所有系统配置")
async def api_get_config():
    """返回用户已保存的配置（合并默认值）。"""
    defaults = get_all_defaults()
    saved = get_all_config()
    categories = ["alert", "notification", "llm", "pipeline"]
    result = {"defaults": defaults}
    for cat in categories:
        result[cat] = saved.get(cat, {}).get("value", {}) if cat in saved else {}
    return result


@app.put("/api/config", summary="保存系统配置")
async def api_set_config(req: ConfigSetRequest):
    """保存用户修改的配置项。每个 section 独立存储。"""
    try:
        payload = {}
        if req.alert is not None:
            payload["alert"] = req.alert
        if req.notification is not None:
            payload["notification"] = req.notification
        if req.llm is not None:
            payload["llm"] = req.llm
        if req.pipeline is not None:
            payload["pipeline"] = req.pipeline

        results = batch_set_config(payload)
        return {"status": "success", "updated": len(results), "keys": [r["key"] for r in results]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败：{str(e)}")


@app.post("/api/config/test-notification", summary="测试通知渠道")
async def api_test_notification(req: NotificationTestRequest):
    """向指定渠道发送一条测试通知。"""
    try:
        ok = False
        if req.channel == "slack":
            ok = await send_slack(req.message)
        elif req.channel == "dingtalk":
            ok = await send_dingtalk(req.message)
        elif req.channel == "email":
            ok = await send_email("竞品情报系统 - 测试通知", req.message)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的渠道：{req.channel}")
        return {"channel": req.channel, "success": ok, "message": "发送成功" if ok else "发送失败（请检查配置）"}
    except HTTPException:
        raise
    except Exception as e:
        return {"channel": req.channel, "success": False, "message": str(e)}


@app.post("/api/config/reset-llm", summary="重置LLM参数为默认值")
async def api_reset_llm():
    """将 LLM 配置恢复为系统默认值（来自 .env）。"""
    defaults = get_all_defaults()["llm"]
    set_config_value("llm", defaults)
    return {"status": "success", "llm": defaults}


@app.get("/api/config/history", summary="获取配置版本历史")
async def api_get_config_history(key: Optional[str] = None):
    """获取配置项的版本历史记录，可按 key 筛选。"""
    return get_config_history(key=key)


@app.post("/api/config/rollback", summary="回滚配置到指定版本")
async def api_rollback_config(req: ConfigRollbackRequest):
    """将指定配置项回滚到历史版本。"""
    try:
        result = rollback_config(req.key, req.version)
        return {"status": "success", "key": result["key"], "value": result["value"]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/config/export", summary="导出系统配置为JSON")
async def api_export_config():
    """导出全部配置（含版本信息），可用于备份和迁移。"""
    return export_config()


@app.post("/api/config/import", summary="从JSON导入系统配置")
async def api_import_config(req: ConfigImportRequest):
    """从导出的 JSON 数据导入配置。"""
    try:
        count = import_config(req.model_dump())
        return {"status": "success", "imported_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败：{str(e)}")


# ==================================================================
#  系统信息 API
# ==================================================================

@app.get("/api/system-info", summary="获取系统运行信息")
async def api_system_info():
    """返回当前服务的运行状态、数据库统计和资源使用情况。"""
    import sys
    import os
    import time

    stats = get_db_stats()
    process = None
    try:
        import psutil
        process = psutil.Process(os.getpid())
    except ImportError:
        pass

    return {
        "python_version": sys.version,
        "platform": sys.platform,
        "db_stats": stats,
        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1) if process else "N/A (pip install psutil)",
        "cpu_percent": process.cpu_percent(interval=0.1) if process else "N/A",
        "pid": os.getpid(),
    }


# ==================================================================
#  我方产品管理 API
# ==================================================================

class OurProductUpdateRequest(BaseModel):
    """我方产品信息更新请求体"""
    name: str = "My Product"
    core_features: List[str] = Field(default_factory=list)
    pricing_model: str = "订阅制"
    tech_stack: List[str] = Field(default_factory=list)
    target_market: str = ""
    competitive_advantages: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)


@app.get("/api/our-product", summary="获取我方产品信息")
async def api_get_our_product():
    """获取我方产品结构化信息，用于对比分析。"""
    return get_our_product()


@app.put("/api/our-product", summary="更新我方产品信息")
async def api_update_our_product(req: OurProductUpdateRequest):
    """更新我方产品信息，保存后下次分析立即生效。"""
    try:
        result = update_our_product(req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败：{str(e)}")


# ==================================================================
#  飞书 Bot API
# ==================================================================

class FeedbackRequest(BaseModel):
    """飞书卡片按钮回调请求"""
    action: str = Field(description="confirm / correct / ack")
    report_id: str = Field(default="", description="报告ID")
    comment: str = Field(default="", description="用户反馈备注")


@app.post("/api/v1/feishu/test", summary="测试飞书推送")
async def api_feishu_test():
    """向配置的飞书 Webhook 发送一条测试卡片，验证推送链路"""
    from ..services.feishu import FeishuBot
    from ..config import get_effective_notification_config

    cfg = get_effective_notification_config()
    if not cfg.feishu_webhook_url:
        raise HTTPException(status_code=400, detail="飞书 Webhook 未配置")

    bot = FeishuBot(webhook_url=cfg.feishu_webhook_url, secret=cfg.feishu_webhook_secret)
    ok = await bot.send_test_card()
    return {"success": ok, "message": "测试卡片已发送" if ok else "发送失败，请检查 Webhook 配置"}


@app.post("/api/v1/feishu/feedback", summary="接收飞书卡片按钮回调")
async def api_feishu_feedback(req: FeedbackRequest):
    """接收飞书卡片按钮回调（✅分析准确 / ❌需修正），记录反馈到数据库"""
    try:
        record = create_feedback_record(
            report_id=req.report_id or "unknown",
            action=req.action,
            comment=req.comment,
            operator="feishu_user",
        )
        logger.info("飞书反馈已记录: action=%s report=%s", req.action, req.report_id)
        return {"status": "success", "record": record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"记录反馈失败：{str(e)}")


@app.get("/api/v1/feishu/feedback", summary="获取飞书反馈记录")
async def api_get_feedback(report_id: str = ""):
    """获取飞书反馈记录，可按 report_id 筛选"""
    return get_feedback_records(report_id=report_id if report_id else None)


# ==================================================================
#  可观测性 API（M5 基础设施接线）
# ==================================================================

@app.get("/api/v1/infra/status", summary="系统整体状态")
async def api_infra_status():
    """返回活跃Agent、Token消耗、事件计数等整体状态"""
    try:
        return hub.get_stats()
    except Exception as e:
        return {"error": str(e), "dag": {"total_nodes": 10, "running": [], "completed": [], "failed": [], "progress": 0}}


@app.get("/api/v1/infra/decision-logs", summary="Agent决策日志")
async def api_decision_logs(
    agent: str = "", phase: str = "", has_anomaly: Optional[bool] = None,
    start: str = "", end: str = "", limit: int = Query(default=100, le=1000),
):
    """多维度筛选 Agent 决策日志"""
    from ..infrastructure.data_models import DecisionLogFilter
    flt = DecisionLogFilter()
    if agent:
        flt.agent_names = [agent]
    if phase:
        flt.phases = [phase]
    if has_anomaly is not None:
        flt.has_anomaly = has_anomaly
    logs = hub.agent_logger.query(flt)[:limit]
    return {"total": len(logs), "logs": [l.model_dump(mode="json") for l in logs]}


@app.get("/api/v1/infra/decision-logs/timeline", summary="决策日志时序回溯")
async def api_decision_log_timeline():
    return {"timeline": hub.agent_logger.timeline_replay()}


@app.get("/api/v1/infra/token-usage", summary="Token用量统计")
async def api_token_usage(agent: str = "", start: str = "", end: str = ""):
    """按Agent统计Token消耗"""
    from ..infrastructure.observability import DAG_NODES
    statuses = {}
    for nid, _, _, _ in DAG_NODES:
        used = hub.token_manager.get_used(nid)
        if used["input"] + used["output"] > 0:
            statuses[nid] = used
    return {"agents": statuses, "total_input": sum(s["input"] for s in statuses.values()),
            "total_output": sum(s["output"] for s in statuses.values())}


@app.get("/api/v1/infra/token-quota", summary="Token配额状态")
async def api_token_quota():
    quotas = {}
    for q in hub.token_manager.get_all_quotas():
        used = hub.token_manager.get_used(q.agent_name)
        quotas[q.agent_name] = {
            "quota_input": q.max_input_tokens, "quota_output": q.max_output_tokens,
            "used_input": used["input"], "used_output": used["output"],
        }
    return {"quotas": quotas}


@app.get("/api/v1/infra/events", summary="事件总线事件列表")
async def api_events(
    type: str = "", source: str = "", limit: int = Query(default=200, le=2000),
):
    events = hub.event_bus.get_recent(limit)
    if type:
        events = [e for e in events if e.event_type.value == type]
    if source:
        events = [e for e in events if source in e.source]
    return {"total": len(events), "events": [e.model_dump(mode="json") for e in events[-limit:]]}


@app.get("/api/v1/infra/events/{event_id}/trace", summary="事件溯源链路")
async def api_event_trace(event_id: str):
    chain = hub.event_bus.trace_chain(event_id)
    return {"chain": chain, "depth": len(chain)}


@app.get("/api/v1/infra/dag-snapshot", summary="当前DAG快照")
async def api_dag_snapshot():
    snapshot = hub.get_dag_snapshot()
    return snapshot.model_dump(mode="json")


@app.get("/api/v1/infra/dag-svg", summary="DAG SVG导出")
async def api_dag_svg():
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=hub.get_dag_html())


@app.get("/api/v1/infra/audit-logs", summary="审计日志")
async def api_audit_logs(action_type: str = "", operator: str = "", limit: int = Query(default=100)):
    from ..infrastructure.data_models import AuditFilter
    flt = AuditFilter()
    if action_type:
        flt.action_types = [action_type]
    if operator:
        flt.operators = [operator]
    logs = hub.audit_system.query(flt)[:limit]
    return {"total": len(logs), "logs": [a.model_dump(mode="json") for a in logs]}


@app.get("/api/v1/infra/anomalies", summary="异常检测报告")
async def api_anomalies():
    agent_anomalies = hub.agent_logger.detect_anomalies().model_dump(mode="json")
    audit_violations = hub.audit_system.detect_anomalies()
    token_report = hub.token_manager.daily_report(days=1).model_dump(mode="json")
    return {
        "agent_anomalies": agent_anomalies,
        "audit_violations": audit_violations,
        "token_report_preview": {"total_input": token_report["total_input_tokens"],
                                  "estimated_cost": token_report["estimated_cost"]},
    }


# ==================================================================
#  RAG 知识库 API
# ==================================================================

@app.post("/api/v1/rag/ingest", summary="重建知识库索引")
async def api_rag_ingest():
    """手动触发知识库索引重建（从 ecommerce_kb 目录重新加载全部 JSON）"""
    import os as _os
    from ..services.rag.core import rag

    kb_path = _os.getenv("RAG_KB_PATH", "")
    if not kb_path:
        raise HTTPException(status_code=400, detail="RAG_KB_PATH 环境变量未设置，请指定知识库路径")

    docs = rag.loader.ingest_directory(kb_path)
    count = rag.ingest_documents(docs)
    rag.retriever.save()
    return {"status": "indexed", "documents": len(docs), "chunks": count, "stats": rag.get_stats()}


@app.post("/api/v1/rag/query", summary="RAG 检索接口")
async def api_rag_query(query: str = "", k: int = Query(default=5, le=20),
                        industry: str = "", doc_type: str = ""):
    """RAG 检索（供调试和前端展示）"""
    if not query:
        raise HTTPException(status_code=400, detail="query 参数不能为空")
    from ..services.rag.core import rag
    filters = {}
    if industry:
        filters["industry"] = industry
    if doc_type:
        filters["type"] = doc_type
    results = rag.query(query, k=k, filters=filters if filters else None)
    return {"query": query, "results": results, "count": len(results)}


@app.get("/api/v1/rag/stats", summary="知识库统计")
async def api_rag_stats():
    """知识库统计信息"""
    from ..services.rag.core import rag
    return rag.get_stats()


# ==================================================================
#  系统自进化 API（M6 反馈驱动策略调整）
# ==================================================================

class EvolutionFeedbackRequest(BaseModel):
    """人类反馈请求 — 飞书回调 / 前端手动提交"""
    snapshot_id: int = Field(description="分析快照ID")
    is_correct: bool = Field(description="true=确认正确, false=标记错误")
    comment: str = Field(default="", description="反馈备注")
    operator: str = Field(default="feishu_user", description="操作者标识")


class EvolutionSnapshotQuery(BaseModel):
    """快照查询参数"""
    competitor: str = ""
    dimension: str = ""
    agent_name: str = ""
    limit: int = Field(default=50, le=200)


@app.post("/api/v1/evolution/feedback", summary="提交人类反馈")
async def api_evolution_feedback(req: EvolutionFeedbackRequest):
    """提交人类反馈（由飞书卡片回调或前端手动触发）。

    确认正确 → 提升置信度+0.1，标记错误 → 降低置信度-0.2。
    同时更新关联 Prompt 模板的 performance_score。
    """
    try:
        from ..services.evolution import engine as evo_engine
        result = evo_engine.process_human_feedback(
            snapshot_id=req.snapshot_id,
            is_correct=req.is_correct,
            comment=req.comment,
            operator=req.operator,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("error", "快照不存在"))
        # 同时写入审计日志
        try:
            from ..infrastructure.observability import hub
            hub.audit(
                action_type="evolution_feedback",
                operator=req.operator,
                target=f"snapshot:{req.snapshot_id}",
            )
        except Exception:
            pass
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"反馈处理失败：{str(e)}")


@app.get("/api/v1/evolution/stats", summary="进化统计信息")
async def api_evolution_stats():
    """返回进化统计：总分析数 / 人类验证数 / 知识覆盖率 / 准确率趋势"""
    try:
        from ..services.evolution import engine as evo_engine
        stats = evo_engine.get_evolution_stats()
        # 补充模板排行
        stats["template_ranking"] = get_template_ranking()
        return {"status": "success", "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取进化统计失败：{str(e)}")


@app.get("/api/v1/evolution/snapshots", summary="分析快照历史")
async def api_evolution_snapshots(
    competitor: str = "",
    dimension: str = "",
    agent_name: str = "",
    limit: int = Query(default=50, le=200),
):
    """查询分析快照历史，支持按竞品/维度/Agent筛选"""
    try:
        snapshots = get_snapshot_by_key(
            competitor=competitor if competitor else "",
            dimension=dimension if dimension else "",
            agent_name=agent_name if agent_name else "",
            limit=limit,
        )
        return {"status": "success", "total": len(snapshots), "snapshots": snapshots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取快照失败：{str(e)}")


@app.get("/api/v1/evolution/templates", summary="模板性能排行")
async def api_evolution_templates():
    """返回全部 Agent 模板的评分排行"""
    try:
        ranking = get_template_ranking()
        return {"status": "success", "templates": ranking}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模板排行失败：{str(e)}")


# ==================================================================
#  Mock 模式 API（Demo 零失败保障）
# ==================================================================

class MockToggleRequest(BaseModel):
    """Mock 模式切换请求"""
    enabled: bool = Field(description="true=启用Mock模式, false=关闭")
    scenario: str = Field(default="scenario1", description="Demo场景ID")


@app.get("/api/v1/mock/status", summary="Mock模式状态")
async def api_mock_status():
    """返回当前 Mock 模式状态和可用场景列表"""
    from ..mock import is_mock_mode, get_mock_scenario, list_scenarios
    return {
        "mock_mode": is_mock_mode(),
        "current_scenario": get_mock_scenario(),
        "available_scenarios": list_scenarios(),
        "env_var": "MOCK_MODE",
    }


@app.post("/api/v1/mock/toggle", summary="切换Mock模式")
async def api_mock_toggle(req: MockToggleRequest):
    """运行时切换 Mock 模式（无需重启服务）。

    - enabled=true: 开启 Mock 模式，所有分析使用预生成数据
    - enabled=false: 关闭 Mock 模式，恢复真实 LLM 调用
    """
    from ..mock import set_mock_mode, clear_mock_cache
    import os as _os

    clear_mock_cache()
    set_mock_mode(req.enabled)
    if req.scenario and req.scenario != "scenario1":
        _os.environ["MOCK_SCENARIO"] = req.scenario

    return {
        "status": "success",
        "mock_mode": req.enabled,
        "scenario": req.scenario,
        "message": f"Mock 模式已{'启用（所有分析将使用预生成数据，3秒内完成）' if req.enabled else '关闭（恢复真实LLM调用）'}",
    }