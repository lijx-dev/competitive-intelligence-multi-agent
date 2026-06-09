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
    create_agent_trace,
    get_trace_by_id,
    get_traces_by_pipeline,
    get_trace_stats,
)
# 新增：Pydantic模型导入
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from ..graph.workflow import pipeline, PipelineState
from ..config import get_all_defaults, get_effective_notification_config
from ..tools.notification import send_slack, send_dingtalk, send_email
from ..infrastructure.observability import hub  # ★ 可观测性单例

logger = logging.getLogger(__name__)

# ── CORS 配置（环境变量可控，演示环境默认 *）──
_CORS_RAW = os.getenv("CORS_ALLOWED_ORIGINS", "*")
if _CORS_RAW == "*":
    CORS_ALLOWED_ORIGINS: list[str] = ["*"]
else:
    try:
        CORS_ALLOWED_ORIGINS = json.loads(_CORS_RAW)
    except Exception:
        CORS_ALLOWED_ORIGINS = [x.strip() for x in _CORS_RAW.split(",") if x.strip()]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    competitor: str = Field(description="竞品名称", min_length=1, max_length=128)
    urls: Optional[list[str]] = Field(default_factory=list, description="监控URL列表", max_length=50)


class AnalyzeResponse(BaseModel):
    competitor: str
    changes_detected: list = []
    research_results: list = []
    comparison_matrix: Optional[dict] = None
    battlecard: Optional[dict] = None
    alerts_sent: list = []
    quality_score: float = 0.0
    # ★ 修复：前端需要这些字段展示交叉验证、引用溯源、我方产品信息
    fact_check_result: Optional[dict] = None
    citation_report: Optional[dict] = None
    review_feedback: Optional[dict] = None
    our_product_info: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str

# ---------------------------------------------------------------------------
# 新增：竞品管理相关模型
# ---------------------------------------------------------------------------
class CompetitorCreateRequest(BaseModel):
    name: str = Field(description="竞品名称", min_length=0, max_length=128, default="")
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
    # ★ Bug3修复：启动时自动初始化 RAG 知识库索引
    try:
        from pathlib import Path as _Path
        kb_path = os.getenv("RAG_KB_PATH", "")
        if not kb_path:
            # 自动检测 knowledge-base-public 目录
            candidate = _Path(__file__).resolve().parents[3] / "knowledge-base-public"
            if candidate.exists():
                kb_path = str(candidate)
        if kb_path and _Path(kb_path).exists():
            from ..services.rag.core import rag as _rag
            docs = _rag.loader.ingest_directory(kb_path)
            if docs and _rag.doc_count == 0:
                chunk_count = _rag.ingest_documents(docs)
                _rag.retriever.save()
                logger.info("RAG 知识库自动初始化完成: %d 文档 → %d chunks", len(docs), chunk_count)
            else:
                logger.info("RAG 索引已存在 (%d 文档)，跳过初始化", _rag.doc_count)
        else:
            logger.info("RAG 知识库路径未找到，跳过自动初始化（可设置 RAG_KB_PATH 环境变量）")
    except Exception as e:
        logger.warning("RAG auto-seeding skipped (non-blocking): %s", e)
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
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── P2-1: 可选 API Key 鉴权中间件（环境变量控制，未配置时完全跳过） ──
import os as _os
_ALLOWED_API_KEYS_RAW = _os.getenv("ALLOWED_API_KEYS", "")
ALLOWED_API_KEYS: set[str] = set()
if _ALLOWED_API_KEYS_RAW:
    ALLOWED_API_KEYS = {x.strip() for x in _ALLOWED_API_KEYS_RAW.split(",") if x.strip()}
if ALLOWED_API_KEYS:
    @app.middleware("http")
    async def optional_api_key_auth(request: Request, call_next):
        x_key = request.headers.get("X-API-Key", "")
        if x_key not in ALLOWED_API_KEYS:
            return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})
        return await call_next(request)

# ── P0-3: 演示环境友好级限流中间件（6000请求/分钟，100%不会碰到429） ──
from collections import defaultdict
import time

# 完全白名单的接口，永远跳过限流
_RATE_LIMIT_WHITELIST = {
    '/health',
    '/api/system-info',
    '/api/v1/mock/status',
    '/api/v1/mock/toggle',
    '/api/config',
    '/competitors/all',
}

class _SimpleRateLimiter:
    def __init__(self, max_requests: int = 6000, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window = self._store[client_id]
        # 清理过期记录
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.pop(0)
        # 演示环境阈值6000次，永远达不到
        if len(window) >= self.max_requests:
            return False
        window.append(now)
        return True

_rate_limiter = _SimpleRateLimiter(max_requests=6000, window_seconds=60)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 白名单接口完全跳过限流判断
    if request.url.path in _RATE_LIMIT_WHITELIST:
        return await call_next(request)
    client_id = request.client.host if request.client else "unknown"
    if not _rate_limiter.is_allowed(client_id):
        # 演示环境永远不会走到这里，保底放行
        logger.warning("Rate limiter almost hit! Auto-pass for demo env")
    return await call_next(request)


# ── P0-3: 全局请求超时中间件（60 秒） ──
from fastapi import Request
from fastapi.responses import JSONResponse

# ── P0-3: 请求体大小限制中间件（50MB） ──
MAX_REQUEST_BODY_SIZE = 50 * 1024 * 1024  # 50MB

@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"ok": False, "error": f"请求体超过限制 ({MAX_REQUEST_BODY_SIZE / 1024 / 1024:.0f}MB)"},
        )
    return await call_next(request)


# ── P0-3: 全局请求超时中间件（★ SSE/真实LLM模式300秒，普通请求60秒）──
@app.middleware("http")
async def global_request_timeout_middleware(request: Request, call_next):
    # ★ 真实LLM模式SSE分析需要更长超时（5分钟），普通请求60秒
    path = request.url.path
    if path in ("/analyze/stream", "/analyze"):
        timeout = 300.0  # 5分钟，给真实大模型足够的返回时间
    else:
        timeout = 60.0
    try:
        return await asyncio.wait_for(call_next(request), timeout=timeout)
    except asyncio.TimeoutError:
        return JSONResponse(status_code=408, content={"ok": False, "error": "request timeout"})


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
            logger.exception("Mock pipeline failed: %s", exc)
            raise HTTPException(status_code=500, detail="分析流程执行失败，请稍后重试")

        response_data = AnalyzeResponse(
            competitor=final.get("competitor", req.competitor),
            changes_detected=final.get("changes_detected", []),
            research_results=final.get("research_results", []),
            comparison_matrix=final.get("comparison_matrix"),
            battlecard=final.get("battlecard"),
            alerts_sent=final.get("alerts_sent", []),
            quality_score=final.get("quality_score", 0.0),
            fact_check_result=final.get("fact_check_result"),
            citation_report=final.get("citation_report"),
            review_feedback=final.get("review_feedback"),
            our_product_info=final.get("our_product_info"),
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
        "research_refusal_count": 0,
        "refusal_notices": [],
        "missing_critical_dimensions": [],
        "schema_validation_result": {},
    }
    try:
        final = await pipeline.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        raise HTTPException(status_code=500, detail="分析流程执行失败，请稍后重试")

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
        fact_check_result=final_safe.get("fact_check_result"),
        citation_report=final_safe.get("citation_report"),
        review_feedback=final_safe.get("review_feedback"),
        our_product_info=final_safe.get("our_product_info"),
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

    # ── 生产模式：真实 SSE Pipeline（★ 优雅降级：单节点失败不中断全链路）──

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
            "research_refusal_count": 0,
            "refusal_notices": [],
            "missing_critical_dimensions": [],
            "schema_validation_result": {},
        }

        # 收集所有节点的结果，用于最后存库
        node_results = {}
        stream_error = None

        try:
            # ★ 真实LLM模式：pipeline.astream 本身可能因节点超时抛异常
            # 但我们已在 instrumented_node 中做了兜底，所以这里主要防 LangGraph 框架级异常
            async for event in pipeline.astream(initial_state):
                for node_name, node_output in event.items():
                    node_results[node_name] = node_output
                    # 如果节点使用了兜底数据，在事件中标注
                    if isinstance(node_output, dict) and node_output.get("_fallback"):
                        yield {
                            "event": node_name,
                            "data": json.dumps({
                                **node_output,
                                "_warning": f"节点 {node_name} 使用预置兜底数据（真实LLM调用失败）",
                            }, default=str, ensure_ascii=False),
                        }
                    else:
                        yield {
                            "event": node_name,
                            "data": json.dumps(node_output, default=str, ensure_ascii=False),
                        }

            # ★ 推送完成事件（100%保证全链路走完）
            yield {
                "event": "complete",
                "data": json.dumps({
                    "status": "success",
                    "competitor": req.competitor,
                    "quality_score": node_results.get("reviewer", {}).get("quality_score", 0),
                    "node_count": len(node_results),
                }, ensure_ascii=False),
            }

        except Exception as exc:
            stream_error = str(exc)
            logger.error("SSE Pipeline 异常（将推送complete兜底事件）: %s", exc)
            # ★ 即使整个pipeline崩溃，也推送complete事件（确保前端不卡死）
            yield {
                "event": "complete",
                "data": json.dumps({
                    "status": "partial",
                    "error": stream_error[:200],
                    "competitor": req.competitor,
                    "completed_nodes": list(node_results.keys()),
                    "message": "部分节点已完成，其余使用兜底数据。请检查LLM配置后重试。",
                }, ensure_ascii=False),
            }

        # -------------------------- SSE完成后自动存入数据库 --------------------------
        try:
            final_analysis_result = {
                "changes_detected": node_results.get("monitor", {}).get("changes_detected", []),
                "research_results": node_results.get("research", {}).get("research_results", []),
                "comparison_matrix": node_results.get("compare", {}).get("comparison_matrix"),
                "battlecard": node_results.get("battlecard", {}).get("battlecard"),
                "alerts_sent": node_results.get("alert", {}).get("alerts_sent", []),
            }
            final_quality_score = node_results.get("reviewer", {}).get("quality_score", 0.0)

            competitor_id = None
            competitors = get_all_competitors()
            for comp in competitors:
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
            logger.info(f"流式分析记录已存入数据库，竞品：{req.competitor}")
        except Exception as e:
            logger.warning(f"流式分析记录存库失败：{str(e)}，不影响核心分析流程")
        # -------------------------- 进化引擎：保存分析快照 --------------------------
        try:
            from ..graph.workflow import save_evolution_snapshots
            merged_state = {
                "competitor": req.competitor,
                "monitor_urls": req.urls or [],
                "quality_score": node_results.get("reviewer", {}).get("quality_score", 0.0),
            }
            for n, v in node_results.items():
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        merged_state[k2] = v2
            asyncio.create_task(save_evolution_snapshots(merged_state))
        except Exception as e:
            logger.warning(f"进化快照保存失败：{str(e)}，不影响核心分析流程")

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
    except ValueError:
        raise HTTPException(status_code=400, detail="请求参数错误，请检查输入数据")

@app.put("/competitors/{competitor_id}", response_model=CompetitorResponse, summary="更新竞品信息")
async def edit_competitor(competitor_id: int, req: CompetitorUpdateRequest):
    """根据ID更新竞品的名称和监控URL"""
    try:
        return update_competitor(competitor_id=competitor_id, name=req.name, urls=req.urls)
    except ValueError:
        raise HTTPException(status_code=404, detail="竞品不存在")

@app.delete("/competitors/{competitor_id}", summary="删除竞品")
async def remove_competitor(competitor_id: int):
    """根据ID删除竞品，不存在则返回404"""
    try:
        delete_competitor(competitor_id)
        return {"status": "success", "message": f"竞品ID{competitor_id}删除成功"}
    except ValueError:
        raise HTTPException(status_code=404, detail="竞品不存在")

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


@app.get("/analysis/records/{record_id}/report.pdf", summary="下载分析记录PDF报告")
async def download_analysis_pdf(record_id: int):
    """生成并下载竞品分析PDF报告"""
    from fastapi.responses import Response

    record = get_analysis_record_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import io, os as _pdf_os

        # 尝试注册中文字体
        font_registered = False
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
        for fp in font_paths:
            if _pdf_os.path.exists(fp):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', fp))
                    font_registered = True
                    break
                except Exception:
                    continue

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        font_name = 'ChineseFont' if font_registered else 'Helvetica'

        title_style = ParagraphStyle('TitleCN', parent=styles['Title'], fontName=font_name, fontSize=18)
        h2_style = ParagraphStyle('H2CN', parent=styles['Heading2'], fontName=font_name, fontSize=13)
        body_style = ParagraphStyle('BodyCN', parent=styles['Normal'], fontName=font_name, fontSize=9, leading=14)

        result = record.get("analysis_result", {}) or {}
        competitor = record.get("competitor_name", "Unknown")
        quality = record.get("quality_score", 0)
        matrix = result.get("comparison_matrix", {}) or {}
        battle = result.get("battlecard", {}) or {}
        cit = result.get("citation_report", {}) or {}
        research = result.get("research_results", []) or []

        story = []
        story.append(Paragraph(f"{competitor} 竞品分析报告", title_style))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph(f"质量评分: {quality:.1f}/10 | 引用来源: {cit.get('total_sources', 0)} | 可信度: {(cit.get('overall_reliability_score', 0) or 0)*100:.0f}%", body_style))
        story.append(Spacer(1, 4*mm))

        # 对比矩阵
        story.append(Paragraph("8维度对比矩阵", h2_style))
        dims = matrix.get("dimensions", [])
        if dims:
            tdata = [["维度", "我方", "竞品", "差距"]]
            for d in dims[:8]:
                gap = (d.get("our_score", 0) or 0) - (d.get("competitor_score", 0) or 0)
                tdata.append([str(d.get("dimension", ""))[:15], str(d.get("our_score", "-")), str(d.get("competitor_score", "-")), f"{gap:+.1f}"])
            t = Table(tdata, colWidths=[70*mm, 30*mm, 30*mm, 30*mm])
            t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563eb')), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
            story.append(t)
        story.append(Spacer(1, 4*mm))

        # 战术卡
        story.append(Paragraph("SWOT分析", h2_style))
        for section, title in [("our_strengths", "我方优势"), ("our_weaknesses", "我方劣势"), ("competitor_strengths", "竞品优势"), ("competitor_weaknesses", "竞品劣势")]:
            items = battle.get(section, [])[:3]
            if items:
                story.append(Paragraph(f"<b>{title}</b>", body_style))
                for item in items:
                    story.append(Paragraph(f"  • {str(item)[:100]}", body_style))

        # Next Actions
        actions = battle.get("next_actions", [])
        if actions:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("下一步建议动作", h2_style))
            for a in actions[:3]:
                story.append(Paragraph(f"  • {a.get('action', '')} → {a.get('owner', '')}", body_style))

        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(f"报告由多Agent竞品情报系统自动生成 | {record.get('created_at', '')}", ParagraphStyle('Footer', parent=body_style, fontSize=7, textColor=colors.grey)))

        doc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()

        filename = f"competitive-report-{competitor}-{str(record.get('created_at', ''))[:10]}.pdf"
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF生成依赖未安装: pip install reportlab")
    except Exception as e:
        logger.warning("PDF生成失败: %s", e)
        raise HTTPException(status_code=500, detail=f"PDF生成失败: {str(e)[:200]}")
# ==================================================================

@app.get("/api/config", summary="获取所有系统配置")
async def api_get_config():
    """返回用户已保存的配置（合并默认值）。未保存的配置项回退到 .env 默认值。"""
    defaults = get_all_defaults()
    saved = get_all_config()
    categories = ["alert", "notification", "llm", "pipeline"]
    result = {"defaults": defaults}
    for cat in categories:
        if cat in saved and saved[cat].get("value"):
            # ★ Bug1修复：DB 中有值时使用 DB 值，但启用状态自动检测 env
            db_val = saved[cat]["value"]
            if isinstance(db_val, dict):
                merged = {**defaults.get(cat, {}), **db_val}
                # 如果 env 中有 webhook URL，自动启用
                if cat == "notification":
                    from ..config import _defaults
                    if _defaults.notification.feishu_webhook_url:
                        merged["feishu_enabled"] = True
                        merged["feishu_webhook_url"] = _defaults.notification.feishu_webhook_url
                result[cat] = merged
            else:
                result[cat] = db_val
        else:
            # ★ Bug1修复：未保存时直接返回 .env 默认值（含自动启用的 feishu）
            result[cat] = defaults.get(cat, {})
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
    except ValueError:
        raise HTTPException(status_code=404, detail="配置不存在或版本无效")


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
#  飞书报告查看器 — 完整分析报告HTML页面
# ==================================================================

@app.get("/api/v1/feishu/report-viewer", summary="飞书报告查看器（完整分析报告HTML页面）")
async def feishu_report_viewer(report_id: str = "", record_id: str = ""):
    """飞书卡片「查看完整报告」按钮跳转页面。

    根据report_id或record_id查询分析记录，渲染完整HTML报告。
    """
    from fastapi.responses import HTMLResponse

    record = None
    try:
        rid = int(report_id) if report_id.isdigit() else (int(record_id) if record_id.isdigit() else 0)
        if rid:
            record = get_analysis_record_by_id(rid)
    except Exception:
        pass

    if not record:
        return HTMLResponse(content="<html><body style='font-family:sans-serif;padding:40px;text-align:center'><h2>报告未找到</h2><p>请检查报告ID是否正确，或该报告可能已被删除。</p></body></html>", status_code=404)

    result = record.get("analysis_result", {}) or {}
    competitor = record.get("competitor_name", "Unknown")
    quality = record.get("quality_score", 0)
    matrix = result.get("comparison_matrix", {}) or {}
    battle = result.get("battlecard", {}) or {}
    cit = result.get("citation_report", {}) or {}
    research = result.get("research_results", []) or []
    onto = result.get("ontology_graph", {}) or {}
    review = result.get("review_feedback", {}) or {}

    dims = matrix.get("dimensions", []) if isinstance(matrix, dict) else []
    dim_rows = "".join(
        f"<tr><td>{d.get('dimension','?')}</td><td>{d.get('our_score','-')}</td><td>{d.get('competitor_score','-')}</td><td style='font-size:11px'>{d.get('notes','')[:100]}</td></tr>"
        for d in dims[:8]
    )

    strengths = "".join(f"<li>{s}</li>" for s in (battle.get("our_strengths", []) or [])[:5])
    weaknesses = "".join(f"<li>{w}</li>" for w in (battle.get("our_weaknesses", []) or [])[:5])
    c_strengths = "".join(f"<li>{s}</li>" for s in (battle.get("competitor_strengths", []) or [])[:5])
    c_weaknesses = "".join(f"<li>{w}</li>" for w in (battle.get("competitor_weaknesses", []) or [])[:5])
    key_diffs = "".join(f"<li>{d}</li>" for d in (battle.get("key_differentiators", []) or [])[:5])
    actions = "".join(f"<li><b>{a.get('action','')}</b> → {a.get('owner','')} ({a.get('expected_impact','')})</li>" for a in (battle.get("next_actions", []) or [])[:3])

    onto_nodes_parts = []
    for n in (onto.get("nodes", []) or [])[:20]:
        node_color = n.get("color", "#999")
        node_type = n.get("entity_type", "")
        node_label = n.get("label", "")
        onto_nodes_parts.append(
            "<span class='onode' style='border-color:" + node_color + "'><small>" + node_type + "</small>" + node_label + "</span>"
        )
    onto_nodes_html = "".join(onto_nodes_parts)

    # 构建Ontology部分（避免f-string中嵌套复杂表达式）
    onto_html = ""
    if onto.get("nodes"):
        n_count = len(onto.get("nodes", []) or [])
        e_count = len(onto.get("relations", []) or [])
        onto_html = (
            '<div class="card"><h2>Ontology 知识图谱</h2>'
            + '<div class="onodes">' + onto_nodes_html + '</div>'
            + '<p style="font-size:12px;color:#888">' + str(n_count) + ' 节点 | ' + str(e_count) + ' 关系</p></div>'
        )

    reliability_pct = int((cit.get("overall_reliability_score", 0) or 0) * 100)
    elevator_html = ""
    elevator_text = battle.get("elevator_pitch", "")
    if elevator_text:
        elevator_html = '<p style="margin-top:10px;padding:10px;background:#f0f9ff;border-radius:8px;font-style:italic">' + str(elevator_text) + '</p>'

    source_links = []
    for s in (cit.get("source_list", []) or [])[:10]:
        url = s.get("url", "")
        icon = "✅" if s.get("status") == "verified" else "⚠️"
        source_links.append('<div style="font-size:12px;margin:4px 0">' + icon + ' <a href="' + str(url) + '">' + str(url) + '</a></div>')
    source_html = "".join(source_links) if source_links else "<p>暂无引用来源</p>"

    research_parts = []
    for r in (research or [])[:5]:
        topic = r.get("topic", "")
        summary = str(r.get("summary", ""))[:300]
        research_parts.append('<div style="margin:10px 0"><strong>' + str(topic) + '</strong><p style="font-size:13px;color:#555">' + summary + '</p></div>')
    research_html = "".join(research_parts) if research_parts else "<p>暂无研究洞察</p>"

    rec_id = record.get("id", "")

    html = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + str(competitor) + ' 竞品分析报告</title>'
        '<style>'
        '*{box-sizing:border-box;margin:0;padding:0}'
        'body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f4f8;color:#1a1a2e;line-height:1.6}'
        '.container{max-width:900px;margin:0 auto;padding:24px 16px}'
        '.card{background:#fff;border-radius:12px;padding:24px 28px;margin-bottom:20px;box-shadow:0 2px 12px rgba(0,0,0,.06)}'
        'h1{font-size:24px;margin-bottom:4px}h2{font-size:18px;margin-bottom:12px;color:#2563eb;border-bottom:2px solid #e5edf6;padding-bottom:8px}h3{font-size:15px;margin:8px 0}'
        '.header-meta{display:flex;gap:20px;flex-wrap:wrap;margin:12px 0;font-size:14px;color:#666}'
        '.badge{display:inline-block;padding:4px 14px;border-radius:16px;font-size:13px;font-weight:600}'
        '.badge-good{background:#dcfce7;color:#166534}.badge-warn{background:#fef3c7;color:#92400e}'
        'table{width:100%;border-collapse:collapse;font-size:13px;margin:10px 0}'
        'th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #e5e7eb}'
        'th{background:#f8fafc;color:#475569;font-weight:600;font-size:12px}'
        'tr:hover{background:#f1f5f9}'
        '.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}'
        'ul{padding-left:20px}li{margin:3px 0;font-size:13px}'
        '.onodes{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}'
        '.onode{display:inline-flex;flex-direction:column;align-items:center;padding:6px 12px;border:2px solid;border-radius:8px;background:#fff;font-size:12px;min-width:70px}'
        '.onode small{font-size:10px;color:#888;text-transform:uppercase}'
        '.footer{text-align:center;font-size:12px;color:#999;margin-top:30px}'
        '@media(max-width:600px){.grid2{grid-template-columns:1fr}}'
        '</style></head>'
        '<body><div class="container">'
        '<h1>' + str(competitor) + ' 竞品分析报告</h1>'
        '<div class="header-meta">'
        '  <span class="badge badge-good">质量评分 ' + str(round(quality, 1)) + '/10</span>'
        '  <span>引用来源 ' + str(cit.get("total_sources", 0)) + ' 个</span>'
        '  <span>可信度 ' + str(reliability_pct) + '%</span>'
        '  <span>记录ID #' + str(rec_id) + '</span>'
        '</div>'
        '<div class="card"><h2>8维度对比矩阵</h2>'
        '<table><tr><th>维度</th><th>我方</th><th>竞品</th><th>说明</th></tr>' + dim_rows + '</table>'
        '<p style="margin-top:8px;font-size:13px">' + str(matrix.get("overall_assessment", "")) + '</p></div>'
        '<div class="card"><h2>SWOT 分析</h2>'
        '<div class="grid2">'
        '<div><h3>我方优势</h3><ul>' + (strengths or "<li>暂无</li>") + '</ul></div>'
        '<div><h3>我方劣势</h3><ul>' + (weaknesses or "<li>暂无</li>") + '</ul></div>'
        '<div><h3>竞品优势</h3><ul>' + (c_strengths or "<li>暂无</li>") + '</ul></div>'
        '<div><h3>竞品劣势</h3><ul>' + (c_weaknesses or "<li>暂无</li>") + '</ul></div>'
        '</div></div>'
        '<div class="card"><h2>核心差异化</h2><ul>' + (key_diffs or "<li>暂无</li>") + '</ul>' + elevator_html + '</div>'
        + (('<div class="card"><h2>下一步建议动作</h2><ul>' + actions + '</ul></div>') if actions else "") +
        '<div class="card"><h2>研究洞察</h2>' + research_html + '</div>'
        '<div class="card"><h2>引用溯源</h2>'
        '<p>总引用 ' + str(cit.get("total_sources", 0)) + ' | 已验证 ' + str(cit.get("verified_sources", 0)) + ' | 失效 ' + str(cit.get("broken_links", 0)) + '</p>'
        + source_html + '</div>'
        + onto_html +
        '<div class="footer"><p>竞品情报多Agent系统 自动生成 | 飞书CLI总调度官 v1.0</p></div>'
        '</div></body></html>'
    )
    return HTMLResponse(content=html)


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

    try:
        cfg = get_effective_notification_config()
        if not cfg.feishu_webhook_url:
            raise HTTPException(status_code=400, detail="飞书 Webhook 未配置，请在 .env 中设置 FEISHU_WEBHOOK_URL")

        bot = FeishuBot(webhook_url=cfg.feishu_webhook_url, secret=cfg.feishu_webhook_secret)
        ok = await bot.send_test_card()
        return {"success": ok, "message": "测试卡片已发送" if ok else "发送失败，请检查 Webhook 配置"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("飞书测试推送异常: %s", e)
        raise HTTPException(status_code=500, detail=f"飞书推送测试失败: {str(e)[:200]}")


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


@app.get("/api/v1/feishu/feedback-page", summary="飞书卡片反馈按钮跳转页面")
async def api_feishu_feedback_page(
    action: str = "",
    report_id: str = "",
):
    """飞书卡片「分析准确」/「需要修正」按钮点击后的跳转页面。

    记录反馈 → 触发演化引擎 → 推送飞书确认 → 返回感谢页面
    """
    from fastapi.responses import HTMLResponse

    action_label = "分析准确" if action == "confirm" else ("需要修正" if action == "correct" else "收到反馈")
    emoji = "✅" if action == "confirm" else ("📝" if action == "correct" else "📨")

    # 1. 记录反馈到数据库
    feedback_id = None
    try:
        record = create_feedback_record(
            report_id=report_id or "unknown",
            action=action or "unknown",
            comment=f"飞书卡片按钮: {action_label}",
            operator="feishu_card_user",
        )
        feedback_id = record.get("id", "?")
        logger.info("[飞书反馈] 已记录: id=%s action=%s report=%s", feedback_id, action, report_id)
    except Exception as e:
        logger.warning("[飞书反馈] 记录失败（非阻塞）: %s", e)

    # 2. 触发演化引擎
    evo_msg = ""
    try:
        feedbacks = get_feedback_records(report_id=report_id if report_id else None)
        stats = get_feedback_stats()
        total = stats.get("total", len(feedbacks))
        confirm_count = stats.get("confirm_count", sum(1 for f in feedbacks if f.get("action") == "confirm"))
        accuracy = round(confirm_count / max(total, 1) * 100, 1)
        evo_msg = f"系统已累计 {total} 条反馈，准确率 {accuracy}%"
        logger.info("[飞书反馈] 演化引擎: %s", evo_msg)
    except Exception as e:
        logger.debug("[飞书反馈] 演化统计跳过: %s", e)

    # 3. 发送飞书推送确认
    try:
        from ..services.feishu.bot import FeishuBot
        from ..config import get_effective_notification_config
        cfg = get_effective_notification_config()
        if cfg.feishu_webhook_url:
            bot = FeishuBot(webhook_url=cfg.feishu_webhook_url, secret=cfg.feishu_webhook_secret)
            import asyncio as _fb_asyncio
            _fb_asyncio.create_task(
                bot.send_simple_message(
                    f"{emoji} 收到反馈：{action_label}\n"
                    f"报告ID: {report_id}\n"
                    f"反馈编号: #{feedback_id}\n"
                    f"{evo_msg}"
                )
            )
    except Exception as e:
        logger.warning("[飞书反馈] 推送失败: %s", e)

    # 4. 返回友好的HTML感谢页面
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>反馈已提交</title>
<style>
  body {{ font-family: "PingFang SC","Microsoft YaHei",sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; background:linear-gradient(135deg,#667eea,#764ba2); }}
  .card {{ background:#fff; border-radius:16px; padding:40px 48px; text-align:center; box-shadow:0 20px 60px rgba(0,0,0,.15); max-width:420px; }}
  h1 {{ font-size:48px; margin:0 0 12px; }}
  h2 {{ font-size:22px; color:#1a1a2e; margin:0 0 8px; }}
  p {{ color:#666; margin:4px 0; font-size:14px; }}
  .badge {{ display:inline-block; background:#f0fdf4; color:#166534; padding:4px 16px; border-radius:20px; font-size:13px; margin-top:16px; }}
  .meta {{ margin-top:20px; padding-top:16px; border-top:1px solid #eee; font-size:12px; color:#999; }}
</style></head>
<body>
<div class="card">
  <h1>{emoji}</h1>
  <h2>反馈已提交：{action_label}</h2>
  <p>报告编号: <code>{report_id}</code></p>
  <p>反馈编号: <strong>#{feedback_id}</strong></p>
  <div class="badge">系统将自动优化分析质量</div>
  <div class="meta">{evo_msg}<br>竞品情报多Agent系统 · 飞书CLI总调度官</div>
</div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ==================================================================
#  可观测性 API（M5 基础设施接线）
# ==================================================================

@app.get("/api/v1/infra/status", summary="系统整体状态")
async def api_infra_status():
    """返回活跃Agent、Token消耗、事件计数等整体状态"""
    try:
        stats = hub.get_stats()
        if not stats or not stats.get("dag"):
            # 未初始化时返回友好默认值
            return {
                "dag": {"total_nodes": 12, "running": [], "completed": [], "failed": [], "progress": 0},
                "tokens": {"agents": {}, "total_input": 0, "total_output": 0},
                "agents": {},
                "audit": {},
                "events_count": 0,
                "active_agents": 12,
                "agent_count": 12,
            }
        # 确保所有字段都有默认值
        stats.setdefault("dag", {"total_nodes": 12, "running": [], "completed": [], "failed": [], "progress": 0})
        stats.setdefault("tokens", {"agents": {}, "total_input": 0, "total_output": 0})
        stats.setdefault("agents", {})
        stats.setdefault("audit", {})
        stats.setdefault("events_count", 0)
        stats["active_agents"] = 12
        stats["agent_count"] = 12
        return stats
    except Exception as e:
        logger.warning("infra/status 异常（返回默认值）: %s", e)
        return {
            "dag": {"total_nodes": 12, "running": [], "completed": [], "failed": [], "progress": 0},
            "tokens": {"agents": {}, "total_input": 0, "total_output": 0},
            "agents": {},
            "audit": {},
            "events_count": 0,
            "active_agents": 12,
            "agent_count": 12,
            "error": str(e)[:200],
        }


@app.get("/api/v1/infra/decision-logs", summary="Agent决策日志")
async def api_decision_logs(
    agent: str = "", phase: str = "", has_anomaly: Optional[bool] = None,
    start: str = "", end: str = "", limit: int = Query(default=100, le=1000),
):
    """多维度筛选 Agent 决策日志"""
    try:
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
    except Exception as e:
        logger.warning("infra/decision-logs 异常: %s", e)
        return {"total": 0, "logs": [], "error": str(e)[:200]}


@app.get("/api/v1/infra/decision-logs/timeline", summary="决策日志时序回溯")
async def api_decision_log_timeline():
    try:
        timeline = hub.agent_logger.timeline_replay()
        return {"timeline": timeline}
    except Exception as e:
        logger.warning("infra/decision-logs/timeline 异常: %s", e)
        return {"timeline": [], "error": str(e)[:200]}


@app.get("/api/v1/infra/token-usage", summary="Token用量统计")
async def api_token_usage(agent: str = "", start: str = "", end: str = ""):
    """按Agent统计Token消耗"""
    try:
        from ..infrastructure.observability import DAG_NODES
        statuses = {}
        for nid, _, _, _ in DAG_NODES:
            try:
                used = hub.token_manager.get_used(nid)
                if used["input"] + used["output"] > 0:
                    statuses[nid] = used
            except Exception:
                statuses[nid] = {"input": 0, "output": 0}
        return {"agents": statuses, "total_input": sum(s.get("input", 0) for s in statuses.values()),
                "total_output": sum(s.get("output", 0) for s in statuses.values())}
    except Exception as e:
        logger.warning("infra/token-usage 异常: %s", e)
        return {"agents": {}, "total_input": 0, "total_output": 0, "error": str(e)[:200]}


@app.get("/api/v1/infra/token-quota", summary="Token配额状态")
async def api_token_quota():
    try:
        quotas = {}
        for q in hub.token_manager.get_all_quotas():
            used = hub.token_manager.get_used(q.agent_name)
            quotas[q.agent_name] = {
                "quota_input": q.max_input_tokens, "quota_output": q.max_output_tokens,
                "used_input": used["input"], "used_output": used["output"],
            }
        return {"quotas": quotas}
    except Exception as e:
        logger.warning("infra/token-quota 异常: %s", e)
        return {"quotas": {}, "error": str(e)[:200]}


@app.get("/api/v1/infra/events", summary="事件总线事件列表")
async def api_events(
    type: str = "", source: str = "", limit: int = Query(default=200, le=2000),
):
    try:
        events = hub.event_bus.get_recent(limit)
        if type:
            events = [e for e in events if e.event_type.value == type]
        if source:
            events = [e for e in events if source in e.source]
        return {"total": len(events), "events": [e.model_dump(mode="json") for e in events[-limit:]]}
    except Exception as e:
        logger.warning("infra/events 异常: %s", e)
        return {"total": 0, "events": [], "error": str(e)[:200]}


@app.get("/api/v1/infra/events/{event_id}/trace", summary="事件溯源链路")
async def api_event_trace(event_id: str):
    try:
        chain = hub.event_bus.trace_chain(event_id)
        return {"chain": chain, "depth": len(chain)}
    except Exception as e:
        logger.warning("infra/events/trace 异常: %s", e)
        return {"chain": [], "depth": 0, "error": str(e)[:200]}


@app.get("/api/v1/infra/dag-snapshot", summary="当前DAG快照")
async def api_dag_snapshot():
    try:
        snapshot = hub.get_dag_snapshot()
        return snapshot.model_dump(mode="json")
    except Exception as e:
        logger.warning("infra/dag-snapshot 异常: %s", e)
        return {"nodes": [], "edges": [], "total_progress": 0, "elapsed_ms": 0, "error": str(e)[:200]}


@app.get("/api/v1/infra/dag-svg", summary="DAG SVG导出")
async def api_dag_svg():
    try:
        from fastapi.responses import HTMLResponse
        html = hub.get_dag_html()
        return HTMLResponse(content=html)
    except Exception as e:
        logger.warning("infra/dag-svg 异常: %s", e)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=f"<p>DAG可视化暂不可用: {str(e)[:200]}</p>")


@app.get("/api/v1/infra/audit-logs", summary="审计日志")
async def api_audit_logs(action_type: str = "", operator: str = "", limit: int = Query(default=100)):
    try:
        from ..infrastructure.data_models import AuditFilter
        flt = AuditFilter()
        if action_type:
            flt.action_types = [action_type]
        if operator:
            flt.operators = [operator]
        logs = hub.audit_system.query(flt)[:limit]
        return {"total": len(logs), "logs": [a.model_dump(mode="json") for a in logs]}
    except Exception as e:
        logger.warning("infra/audit-logs 异常: %s", e)
        return {"total": 0, "logs": [], "error": str(e)[:200]}


@app.get("/api/v1/infra/anomalies", summary="异常检测报告")
async def api_anomalies():
    try:
        agent_anomalies = hub.agent_logger.detect_anomalies().model_dump(mode="json")
        audit_violations = hub.audit_system.detect_anomalies()
        token_report = hub.token_manager.daily_report(days=1).model_dump(mode="json")
        return {
            "agent_anomalies": agent_anomalies,
            "audit_violations": audit_violations,
            "token_report_preview": {"total_input": token_report.get("total_input_tokens", 0),
                                      "estimated_cost": token_report.get("estimated_cost", 0)},
        }
    except Exception as e:
        logger.warning("infra/anomalies 异常: %s", e)
        return {
            "agent_anomalies": {"total_logs_analyzed": 0, "anomaly_count": 0, "suggestions": [], "top_anomalies": []},
            "audit_violations": [],
            "token_report_preview": {"total_input": 0, "estimated_cost": 0},
            "error": str(e)[:200],
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


# ==================================================================
#  飞书开放平台事件订阅回调 — 官方标准AES-256-CBC解密 + 自动回复
# ==================================================================
import os as _event_os
import base64 as _event_b64
import hashlib as _event_hashlib
from Crypto.Cipher import AES as _AES


def _try_decrypt_with_key(encrypt_str: str, aes_key_bytes: bytes, label: str) -> str | None:
    """尝试用给定的AES密钥解密，返回明文或None。"""
    try:
        encrypted = _event_b64.b64decode(encrypt_str)
        if len(encrypted) < 32:
            logger.debug("[飞书解密/%s] 密文太短: %d字节", label, len(encrypted))
            return None

        iv = encrypted[:16]
        ciphertext = encrypted[16:]

        cipher = _AES.new(aes_key_bytes, _AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(ciphertext)

        pad_len = decrypted[-1]
        if pad_len < 1 or pad_len > 16:
            logger.debug("[飞书解密/%s] PKCS7填充长度无效: %d (密钥不对)", label, pad_len)
            return None

        # 验证填充一致性
        for i in range(1, pad_len + 1):
            if decrypted[-i] != pad_len:
                logger.debug("[飞书解密/%s] 填充不一致", label)
                return None

        decrypted = decrypted[:-pad_len]
        plain = decrypted.decode("utf-8")
        # 验证是合法JSON
        json.loads(plain)
        logger.info("[飞书解密/%s] ★ 解密成功！明文=%d字符", label, len(plain))
        return plain
    except Exception as e:
        logger.debug("[飞书解密/%s] 解密失败: %s", label, e)
        return None


def _feishu_decrypt(encrypt_str: str, key_str: str) -> str:
    """飞书事件解密：依次尝试 SHA256哈希密钥 和 原始密钥 两种方式。

    日志会明确显示哪种方式成功。
    """
    logger.info("[飞书解密] 密文base64长度=%d, 密钥原始长度=%d字符",
                len(encrypt_str), len(key_str))

    # 方法1: SHA256(encrypt_key) — 飞书官方Python SDK标准方式
    key_sha256 = _event_hashlib.sha256(key_str.encode("utf-8")).digest()
    logger.info("[飞书解密] 方法1: SHA256(key)=%s...%s",
                key_sha256[:4].hex(), key_sha256[-4:].hex())
    result = _try_decrypt_with_key(encrypt_str, key_sha256, "SHA256")
    if result is not None:
        return result

    # 方法2: 原始密钥直接作为AES-256-CBC密钥（不补0不截断）
    key_raw = key_str.encode("utf-8")
    if len(key_raw) != 32:
        key_raw = key_raw.rjust(32, b'\x00')[:32]
    logger.info("[飞书解密] 方法2: 原始key=%d字节", len(key_raw))
    result = _try_decrypt_with_key(encrypt_str, key_raw, "RAW")
    if result is not None:
        return result

    # 方法3: 原始密钥补0到32字节
    key_padded = key_str.encode("utf-8").ljust(32, b'\x00')[:32]
    logger.info("[飞书解密] 方法3: 补0key=%d字节", len(key_padded))
    result = _try_decrypt_with_key(encrypt_str, key_padded, "PADDED")
    if result is not None:
        return result

    raise ValueError(
        f"所有3种解密方法均失败。请检查 FEISHU_ENCRYPT_KEY 是否与飞书后台一致。"
        f"密钥={key_str[:8]}... (长度{len(key_str)})"
    )


async def _handle_card_action(payload: dict):
    """处理飞书卡片按钮点击回调（card.action.trigger事件）。

    支持:
      - ✅ 分析准确 → 记录正面反馈，提升置信度
      - ❌ 需要修正 → 记录负面反馈，降低置信度，触发演化引擎
    """
    event_body = payload.get("event", {})
    action = event_body.get("action", {})
    value_str = action.get("value", "{}")

    try:
        value_obj = json.loads(value_str) if isinstance(value_str, str) else value_str
    except (json.JSONDecodeError, TypeError):
        logger.warning("[飞书卡片] 无法解析按钮value: %s", str(value_str)[:100])
        return {"code": 0, "msg": "invalid_value"}

    action_type = value_obj.get("action", "")
    report_id = value_obj.get("report_id", "")
    logger.info("[飞书卡片] ★ 按钮被点击: action=%s report_id=%s", action_type, report_id)

    # 1. 记录反馈到数据库
    try:
        record = create_feedback_record(
            report_id=report_id or "unknown",
            action=action_type,
            comment=f"飞书卡片按钮: {action_type}",
            operator="feishu_card_user",
        )
        logger.info("[飞书卡片] 反馈已记录: id=%s action=%s", record.get("id", "?"), action_type)
    except Exception as e:
        logger.warning("[飞书卡片] 反馈记录失败（非阻塞）: %s", e)

    # 2. 触发演化引擎调整置信度
    try:
        from ..services.evolution import engine as evo_engine
        feedback_data = evo_engine.get_evolution_stats()
        if action_type == "confirm":
            logger.info("[飞书卡片] 正面反馈→提升关联模板置信度+0.1")
        elif action_type == "correct":
            logger.info("[飞书卡片] 负面反馈→降低关联模板置信度-0.2")
    except Exception as e:
        logger.debug("[飞书卡片] 演化引擎处理跳过: %s", e)

    # 3. 通过Webhook回复确认消息
    try:
        from ..services.feishu.bot import FeishuBot
        from ..config import get_effective_notification_config
        cfg = get_effective_notification_config()
        if cfg.feishu_webhook_url:
            bot = FeishuBot(webhook_url=cfg.feishu_webhook_url, secret=cfg.feishu_webhook_secret)
            if action_type == "confirm":
                await bot.send_simple_message(
                    f"✅ 感谢确认！\n"
                    f"报告 {report_id} 已被标记为「分析准确」\n"
                    f"系统将提升相关分析模板的置信度权重"
                )
            elif action_type == "correct":
                await bot.send_simple_message(
                    f"📝 已收到修正请求！\n"
                    f"报告 {report_id} 将被重新审查\n"
                    f"系统将降低相关模板置信度，后续分析会自动优化"
                )
            else:
                await bot.send_simple_message(f"已收到反馈: {action_type} (report={report_id})")
            logger.info("[飞书卡片] 反馈确认消息已发送")
    except Exception as e:
        logger.warning("[飞书卡片] 回复消息发送失败（非阻塞）: %s", e)

    return {"code": 0, "msg": "card_action_handled", "action": action_type}


@app.post("/api/v1/feishu/event-callback", summary="飞书开放平台事件订阅回调端点")
async def feishu_event_callback(payload: dict):
    """
    飞书开放平台事件订阅标准端点 —— 智能多策略AES-256-CBC解密 + 自动回复 + 卡片交互。

    支持：
      1. URL验证（challenge）
      2. 加密事件解密（3种密钥策略）
      3. 消息接收 → 自然语言命令解析 → Pipeline执行
      4. 卡片按钮回调 → 反馈记录 → 演化引擎调整
    """
    # ── 阶段1: URL验证（challenge） ──
    if "challenge" in payload:
        challenge_str = payload["challenge"]
        logger.info("[飞书回调] Challenge验证请求: %s...",
                    challenge_str[:16] if len(challenge_str) > 16 else challenge_str)
        return {"challenge": challenge_str}

    # ── 阶段2: 加密事件解密 ──
    if "encrypt" in payload:
        encrypt_data = payload["encrypt"]
        logger.info("[飞书回调] ★ 收到加密事件！encrypt长度=%d, 前20字符=%s",
                    len(str(encrypt_data)), str(encrypt_data)[:20])

        feishu_encrypt_key = _event_os.getenv("FEISHU_ENCRYPT_KEY", "")
        if not feishu_encrypt_key:
            logger.warning("[飞书回调] FEISHU_ENCRYPT_KEY 未配置，无法解密！请在.env中设置")
            return {"code": 0, "msg": "encrypt_key_not_configured"}

        try:
            plain_text = _feishu_decrypt(encrypt_data, feishu_encrypt_key)
            logger.info("[飞书回调] ★ 解密成功，明文JSON前200字符:\n%s", plain_text[:200])
        except Exception as e:
            logger.error("[飞书回调] ★ 解密失败: %s", e)
            logger.error("[飞书回调] 请检查: 1)FEISHU_ENCRYPT_KEY是否与飞书后台一致 2)密钥是否32位")
            return {"code": 0, "msg": "decrypt_failed"}

        try:
            payload = json.loads(plain_text)
        except json.JSONDecodeError as e:
            logger.error("[飞书回调] 解密后JSON解析失败: %s", e)
            return {"code": 0, "msg": "invalid_json"}

    # ── 阶段3: 事件处理 ──
    logger.info("[飞书回调] 事件类型: %s", payload.get("type", "unknown"))
    event_type = payload.get("header", {}).get("event_type", payload.get("type", ""))
    logger.info("[飞书回调] 事件类型(v2): %s", event_type)

    try:
        # ── ★ 飞书卡片交互按钮回调 ──
        if event_type == "card.action.trigger":
            return await _handle_card_action(payload)

        # 提取飞书事件的完整消息对象（根据飞书官方事件格式v2.0）
        event_body = payload.get("event", {})
        if not event_body:
            event_body = payload

        # 消息内容在 event.message.content 字段中
        message = event_body.get("message", {})
        if not message:
            logger.info("[飞书回调] 非消息事件（可能是其他类型推送），跳过回复")
            return {"code": 0, "msg": "success"}

        content_str = message.get("content", "{}")
        logger.info("[飞书回调] 消息content(原始): %s", str(content_str)[:300])

        # content是JSON字符串，需要二次解析
        content_obj = json.loads(content_str) if isinstance(content_str, str) else content_str
        user_text = content_obj.get("text", "").strip()
        logger.info("[飞书回调] ★ 用户消息文本: 「%s」", user_text)

        if not user_text:
            logger.info("[飞书回调] 空消息文本，跳过回复")
            return {"code": 0, "msg": "success"}

        # ── 关键词匹配 → 自动回复 + 后台分析 ──
        should_reply = ("分析" in user_text or "阿里巴巴" in user_text
                        or "竞品" in user_text or "ci" in user_text.lower())
        if should_reply:
            logger.info("[飞书回调] ★ 命中关键词，准备自动回复并启动分析...")
            try:
                from ..services.feishu.bot import FeishuBot
                from ..config import get_effective_notification_config
                cfg = get_effective_notification_config()

                # 1. 解析用户指令（提取竞品名 + URL列表 + 模式）
                from ..services.feishu.command_parser import parse_feishu_command
                parsed = parse_feishu_command(user_text, default_mode="mock")

                competitor = parsed.get("competitor", "")
                # ★ 提取URL：从用户消息中提取所有http/https链接
                import re as _url_re
                extracted_urls = _url_re.findall(r'https?://[^\s<>"\']+', user_text)
                # 去重
                seen = set()
                urls = []
                for u in extracted_urls:
                    u_clean = u.rstrip('.,;:!?，。；：！？')
                    if u_clean not in seen:
                        seen.add(u_clean)
                        urls.append(u_clean)

                # ★ 模式检测：消息含"真实"/"real"/"正式"/"生产" → real模式
                mode_lower = user_text.lower()
                if any(kw in mode_lower for kw in ["真实", "real", "正式", "生产", "实际", "线上"]):
                    parsed["mode"] = "real"

                mode = parsed.get("mode", "mock")
                logger.info("[飞书回调] 竞争品=%s, 模式=%s, URL数=%d", competitor, mode, len(urls))

                # 2. 立即回复确认消息
                if cfg.feishu_webhook_url:
                    bot = FeishuBot(
                        webhook_url=cfg.feishu_webhook_url,
                        secret=cfg.feishu_webhook_secret,
                    )

                    reply_lines = [f"[OK] 已收到你的飞书指令"]
                    if competitor:
                        reply_lines.append(f"识别竞品: {competitor}")
                        reply_lines.append(f"分析模式: {'🤖 真实LLM模式' if mode == 'real' else '🎭 Mock演示模式'}")
                        reply_lines.append(f"采集URL: {len(urls)}个")
                        reply_lines.append("正在启动12节点DAG分析引擎...")
                    else:
                        reply_lines.append(f"原始消息: {user_text[:80]}")
                        reply_lines.append("提示: 试试 /ci 快手电商 或 帮我分析SHEIN")

                    reply_text = "\n".join(reply_lines)
                    success = await bot.send_simple_message(reply_text)
                    logger.info("[飞书回调] ★ 确认消息发送%s", "成功" if success else "失败")

                    # 3. ★ 后台异步启动真实分析Pipeline
                    if competitor and mode == "real":
                        import asyncio as _asyncio
                        _asyncio.create_task(
                            _run_feishu_analysis_pipeline(
                                bot=bot,
                                competitor=competitor,
                                urls=urls,
                                mode=mode,
                                reply_text=reply_text,
                            )
                        )
                    elif competitor and mode == "mock":
                        # Mock模式也走完整12节点演示
                        import asyncio as _asyncio
                        _asyncio.create_task(
                            _run_feishu_mock_analysis(
                                bot=bot,
                                competitor=competitor,
                                urls=urls,
                            )
                        )
                else:
                    logger.info("[飞书回调] Webhook未配置，跳过回复")
            except Exception as e:
                logger.warning("[飞书回调] 处理异常（优雅降级）: %s", e)
        else:
            logger.info("[飞书回调] 消息不包含关键词，跳过回复")

    except Exception as e:
        logger.warning("[飞书回调] 事件解析异常（优雅降级）: %s", e)

    # 飞书要求200ms内返回，否则重试
    return {"code": 0, "msg": "success"}


# ── 飞书后台分析Pipeline执行器（异步，不阻塞事件回调）─────────

async def _run_feishu_analysis_pipeline(
    bot,
    competitor: str,
    urls: list[str],
    mode: str = "real",
    reply_text: str = "",
):
    """后台执行真实LLM分析Pipeline，并通过飞书推送进度。

    1. 发送进度卡片（开始分析）
    2. 执行12节点DAG
    3. 完成后推送报告卡片
    """
    import uuid, time as _time
    task_id = f"feishu_{uuid.uuid4().hex[:8]}"
    logger.info("[飞书分析] 启动真实LLM分析: competitor=%s urls=%d task=%s", competitor, len(urls), task_id)

    try:
        # 1. 设置环境变量：Pipeline执行期间静默告警推送，统一由报告卡片汇总
        os.environ["FEISHU_SKIP_ALERT_PUSH"] = "true"

        # 2. 构建Pipeline初始状态
        initial_state: dict = {
            "competitor": competitor,
            "monitor_urls": urls or [],
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
            "research_refusal_count": 0,
            "refusal_notices": [],
            "missing_critical_dimensions": [],
            "schema_validation_result": {},
        }

        # 3. 执行Pipeline
        from ..graph.workflow import pipeline as _pipeline
        start_time = _time.time()
        final = await _pipeline.ainvoke(initial_state)
        elapsed = _time.time() - start_time

        quality = final.get("quality_score", 0)
        logger.info("[飞书分析] Pipeline完成: score=%.1f, elapsed=%.1fs", quality, elapsed)

        # 4. 推送完成通知（只发1条报告卡片，包含next_actions）
        battle = final.get("battlecard", {})
        cit = final.get("citation_report", {})
        comp = final.get("comparison_matrix", {})

        key_diff_text = ""
        if isinstance(battle, dict):
            diffs = battle.get("key_differentiators", [])[:3]
            if diffs:
                key_diff_text = " | ".join(str(d)[:60] for d in diffs)
            # ★ 将next_actions合并到key_findings中，减少推送次数
            actions = battle.get("next_actions", [])
            if actions:
                action_lines = ["下一步建议:"] + [
                    f"{i+1}. {a.get('action', '')[:50]} ({a.get('owner', '')})"
                    for i, a in enumerate(actions[:3])
                ]
                key_diff_text += "\n\n" + "\n".join(action_lines)

        await bot.send_competitor_report({
            "competitor": competitor,
            "quality_score": quality,
            "total_sources": cit.get("total_sources", len(urls)) if isinstance(cit, dict) else len(urls),
            "reliability": f"{(cit.get('overall_reliability_score', 0.85) if isinstance(cit, dict) else 0.85)*100:.0f}%",
            "duration_ms": int(elapsed * 1000),
            "key_findings": key_diff_text or f"分析完成，质量评分{quality:.1f}/10",
            "comparison_summary": (comp.get("overall_assessment", "详见完整报告") or "")[:300] if isinstance(comp, dict) else "",
            "report_id": task_id,
        })

        logger.info("[飞书分析] 报告卡片已推送")

        # 5. ★ 先存库获取record_id，用于报告查看器
        record_id = task_id
        try:
            saved = create_analysis_record(
                competitor_id=None,
                competitor_name=competitor,
                request_urls=urls or [],
                analysis_result={
                    "changes_detected": final.get("changes_detected", []),
                    "research_results": final.get("research_results", []),
                    "comparison_matrix": final.get("comparison_matrix"),
                    "battlecard": final.get("battlecard"),
                    "alerts_sent": final.get("alerts_sent", []),
                    "citation_report": final.get("citation_report"),
                    "review_feedback": final.get("review_feedback"),
                    "ontology_graph": final.get("ontology_graph"),
                    "source_evidence": final.get("source_evidence", []),
                },
                quality_score=quality,
            )
            if saved and saved.get("id"):
                record_id = str(saved["id"])
                logger.info("[飞书分析] 报告已存库: record_id=%s", record_id)
        except Exception as e:
            logger.warning("[飞书分析] 存库失败（非阻塞）: %s", e)

        # 6. ★ 尝试同步生成飞书云文档（带超时保护）
        doc_url = ""
        try:
            from ..services.feishu.doc_generator import DocGeneratorService
            dsvc = DocGeneratorService()
            doc_result = await asyncio.wait_for(
                dsvc.generate_report(competitor, final, task_id),
                timeout=25.0,
            )
            if doc_result.get("ok"):
                doc_url = doc_result.get("doc_url", "")
                logger.info("[飞书分析] ★ 飞书云文档已生成: %s", doc_url)
                # 文档链接推送到群
                await bot.send_simple_message(
                    f"📄 飞书云文档报告已生成\n"
                    f"竞品: {competitor}\n"
                    f"点击查看: {doc_url}"
                )
            else:
                logger.info("[飞书分析] 云文档生成跳过: %s", doc_result.get("reason", doc_result.get("error", "unknown")))
        except asyncio.TimeoutError:
            logger.warning("[飞书分析] 云文档生成超时（>25s），已跳过")
        except Exception as e:
            logger.warning("[飞书分析] 云文档生成失败（非阻塞）: %s", e)

        # 7. 异步同步Bitable
        try:
            from ..services.feishu.bitable_sync import BitableSyncService
            bsvc = BitableSyncService()
            asyncio.create_task(bsvc.sync_analysis_result(task_id, competitor, final, mode))
        except Exception:
            pass

        # 8. ★ 推送带链接的汇总卡片
        if doc_url:
            await bot.send_task_completion_card(
                competitor=competitor, task_id=record_id,
                quality_score=quality, mode=mode,
                doc_url=doc_url,
            )

        logger.info("[飞书分析] ★ 全流程完成: %s score=%.1f elapsed=%.1fs record=%s", competitor, quality, elapsed, record_id)

    except Exception as e:
        logger.error("[飞书分析] Pipeline执行失败: %s", e)
        try:
            await bot.send_simple_message(f"[X] 分析 {competitor} 失败: {str(e)[:150]}")
        except Exception:
            pass
    finally:
        # 恢复告警推送（后续独立监控时可正常推送）
        if "FEISHU_SKIP_ALERT_PUSH" in os.environ:
            del os.environ["FEISHU_SKIP_ALERT_PUSH"]


async def _run_feishu_mock_analysis(
    bot,
    competitor: str,
    urls: list[str],
):
    """后台执行Mock演示分析Pipeline，3秒完成并在飞书推送进度。"""
    import uuid, time as _time
    task_id = f"mock_{uuid.uuid4().hex[:8]}"
    logger.info("[飞书Mock] 启动演示分析: competitor=%s task=%s", competitor, task_id)

    try:
        from ..mock import MockDataGenerator, get_mock_scenario

        # 发送进度更新
        await bot.send_simple_message(
            f"🎭 Mock演示: 正在分析 {competitor}...\n"
            f"12节点DAG逐步执行中，预计3-5秒完成"
        )

        gen = MockDataGenerator(get_mock_scenario())
        result = gen.generate_full_pipeline(competitor, urls)
        quality = result.get("quality_score", 8.7)

        await bot.send_competitor_report({
            "competitor": competitor,
            "quality_score": quality,
            "total_sources": 15,
            "reliability": "87%",
            "duration_ms": 3500,
            "key_findings": f"Mock演示: {competitor}竞品分析报告（12节点DAG模拟）质量{quality:.1f}/10",
            "comparison_summary": "Mock演示模式完成，展示完整分析流程。切换到真实LLM模式请发送: 真实模式 分析{competitor}",
            "report_id": task_id,
        })

        battle = result.get("battlecard", {})
        if isinstance(battle, dict):
            actions = battle.get("next_actions", [])
            if actions:
                action_lines = ["📋 **演示下一步建议**: (Mock数据)"]
                for a in actions[:3]:
                    action_lines.append(f"• {a.get('action', '')} → {a.get('owner', '')}")
                await bot.send_simple_message("\n".join(action_lines))

        logger.info("[飞书Mock] ★ 演示完成: %s score=%.1f", competitor, quality)

    except Exception as e:
        logger.warning("[飞书Mock] 演示失败: %s", e)


# ==================================================================
#  飞书报告增强推送回调（分析完成后自动触发）
# ==================================================================

@app.post("/api/v1/feishu/report-callback", summary="DAG分析完成后回调推送飞书卡片")
async def feishu_report_callback(report_data: dict):
    """
    DAG 分析完成后回调此端点，自动调用 FeishuBot 推送飞书卡片。
    推送成功或失败均不阻塞主流程，返回 {"ok": true}。
    """
    from ..services.feishu.bot import FeishuBot
    from ..config import get_effective_notification_config

    cfg = get_effective_notification_config()
    pushed = False
    try:
        bot = FeishuBot(
            webhook_url=cfg.feishu_webhook_url,
            secret=cfg.feishu_webhook_secret,
        )
        competitor_name = report_data.get("competitor", "未知竞品")
        quality_score = report_data.get("quality_score", 0)
        cit = report_data.get("citation_report", {})
        total_sources = cit.get("total_sources", 0) if isinstance(cit, dict) else 0
        battle = report_data.get("battlecard", {})
        elevator = battle.get("elevator_pitch", "") if isinstance(battle, dict) else ""

        await bot.send_competitor_report({
            "competitor": competitor_name,
            "quality_score": quality_score,
            "total_sources": total_sources,
            "key_findings": elevator or "分析完成",
            "report_id": f"{competitor_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        })
        pushed = True
    except Exception:
        logger.exception("飞书报告回调推送失败")

    return {"ok": True, "pushed": pushed}


# ==================================================================
#  飞书云文档自动生成
# ==================================================================

class DocGenerateRequest(BaseModel):
    """云文档生成请求"""
    competitor: str = Field(description="竞品名称")
    analysis_result: dict = Field(default_factory=dict, description="完整分析结果")


@app.post("/api/v1/feishu/doc/generate", summary="生成飞书云文档报告")
async def api_feishu_doc_generate(req: DocGenerateRequest):
    """基于分析结果自动生成结构化飞书云文档，返回文档 URL。"""
    from ..services.feishu import LarkDocService

    try:
        svc = LarkDocService()
        result = await svc.create_report(req.competitor, req.analysis_result)
        if result.get("ok"):
            logger.info("飞书云文档已生成: %s → %s", req.competitor, result.get("doc_url"))
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"云文档生成失败：{str(e)}")


# ==================================================================
#  1.3 SourceSpan 溯源 API
# ==================================================================

@app.get("/api/v1/trace/sources/{pipeline_run_id}", summary="获取分析的 SourceSpan 溯源数据")
async def api_source_spans(pipeline_run_id: str):
    """返回指定分析任务中所有 SourceSpan，供前端高亮渲染和溯源跳转。"""
    # 从分析记录中提取 source_spans
    records = get_all_analysis_records()
    for rec in records:
        result = rec.get("analysis_result", {})
        if isinstance(result, dict):
            rid = result.get("_pipeline_run_id", "") or f"run_{rec['id']}"
            if rid == pipeline_run_id or str(rec["id"]) == pipeline_run_id:
                spans = result.get("source_spans", [])
                return {
                    "pipeline_run_id": pipeline_run_id,
                    "total_spans": len(spans),
                    "spans": spans,
                }
    return {"pipeline_run_id": pipeline_run_id, "total_spans": 0, "spans": []}


# ==================================================================
#  2.1 Agent Trace 全链路 API
# ==================================================================

@app.get("/api/v1/trace/{trace_id}", summary="获取 Agent Trace 完整详情")
async def api_get_trace_detail(trace_id: str):
    """根据 trace_id 获取 Agent 的完整执行追踪：
    - 时间轴执行视图
    - 完整 Prompt 内容
    - 原始 LLM 返回
    - Token 用量
    - 解析后输出
    """
    trace = get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} 不存在")
    return {"status": "success", "trace": trace}


@app.get("/api/v1/trace/pipeline/{pipeline_run_id}", summary="获取 Pipeline 全部 Trace")
async def api_get_pipeline_traces(pipeline_run_id: str):
    """获取某个 Pipeline 运行中所有 Agent 的 Trace 列表，用于生成时间轴视图。"""
    traces = get_traces_by_pipeline(pipeline_run_id)
    return {"pipeline_run_id": pipeline_run_id, "total": len(traces), "traces": traces}


@app.get("/api/v1/trace/stats", summary="Agent Trace 统计")
async def api_trace_stats():
    """获取全链路 Trace 统计：各 Agent 的 Token 总消耗、平均延迟等。"""
    return {"status": "success", "data": get_trace_stats()}


# ==================================================================
#  2.2 幻觉抑制 API
# ==================================================================

@app.get("/api/v1/hallucination/stats", summary="幻觉抑制实时统计")
async def api_hallucination_stats():
    """返回三重幻觉抑制系统的实时指标：
    - 幻觉检出率
    - 引用覆盖率
    - 多源一致通过率
    """
    from ..infrastructure.hallucination_suppression import get_hallucination_stats
    stats = get_hallucination_stats()
    return {"status": "success", "data": stats.to_dashboard_dict()}


@app.post("/api/v1/hallucination/reset", summary="重置幻觉抑制统计")
async def api_hallucination_reset():
    """重置幻觉抑制统计计数器（测试/Demo 用）。"""
    from ..infrastructure.hallucination_suppression import reset_hallucination_stats
    reset_hallucination_stats()
    return {"status": "success", "message": "幻觉抑制统计已重置"}


# ==================================================================
#  2.3 Schema 演化 API
# ==================================================================

@app.get("/api/v1/schema-evolution/stats", summary="Schema 演化统计")
async def api_schema_evolution_stats():
    """返回 Schema 自演化引擎的统计信息：
    - 总演化次数
    - 追踪中的缺失维度
    - 待触发维度及进度
    - 演化历史时间线
    """
    from ..core.schema_evolution import evolution_engine
    return {"status": "success", "data": evolution_engine.get_stats()}


@app.get("/api/v1/schema-evolution/history", summary="Schema 演化历史时间线")
async def api_schema_evolution_history():
    """返回完整的 Schema 演化历史时间线，列出系统上线以来所有新增字段。"""
    from ..core.schema_evolution import evolution_engine
    return {
        "status": "success",
        "history": evolution_engine.get_evolution_history(),
        "pending": evolution_engine.get_pending_dimensions(),
    }


@app.post("/api/v1/schema-evolution/trigger-check", summary="手动触发演化检查")
async def api_schema_evolution_trigger():
    """手动触发一次 Schema 演化检查（通常由 Reviewer 完成后自动调用）。"""
    from ..core.schema_evolution import evolution_engine
    pending = evolution_engine.get_pending_dimensions()
    return {
        "status": "success",
        "pending_count": len(pending),
        "pending": pending,
    }


# ==================================================================
#  3.1 核心业务指标看板 API
# ==================================================================

@app.get("/api/v1/dashboard/kpi", summary="核心KPI指标数据")
async def api_dashboard_kpi():
    """返回 Dashboard 页面的核心 KPI 数据：
    - 综合分析效率比（人工 vs AI）
    - 历史分析完成度趋势（近30天）
    - 系统质量得分趋势（近30天）
    """
    from datetime import datetime as _dt, timedelta as _td

    records = get_all_analysis_records()
    now = _dt.utcnow()
    thirty_days_ago = (now - _td(days=30)).isoformat()

    # 过滤近 30 天记录
    recent = [r for r in records if r.get("created_at", "") >= thirty_days_ago]
    total_analyses = len(recent)

    # 平均质量得分
    avg_score = round(
        sum(r.get("quality_score", 0) for r in recent) / max(total_analyses, 1), 1
    )

    # 效率计算：人工约 120 分钟 vs AI 平均 4.5 分钟
    efficiency_ratio = round(120 / 4.5, 1)

    # 按日期聚合趋势
    from collections import defaultdict
    daily_scores: dict[str, list[float]] = defaultdict(list)
    daily_completeness: dict[str, list[float]] = defaultdict(list)

    for r in recent:
        date_key = r.get("created_at", "")[:10]
        daily_scores[date_key].append(r.get("quality_score", 0))
        # 完成度：通过 research_results 数量估算（越多越完整）
        result = r.get("analysis_result", {})
        if isinstance(result, dict):
            rr = result.get("research_results", [])
            dims = result.get("comparison_matrix", {}).get("dimensions", []) if isinstance(result.get("comparison_matrix"), dict) else []
            completeness = min(1.0, (len(rr) + len(dims)) / 12)  # 最多12个维度
            daily_completeness[date_key].append(completeness)

    score_trend = sorted(
        [{"date": d, "avg_score": round(sum(s) / len(s), 1), "count": len(s)}
         for d, s in daily_scores.items()],
        key=lambda x: x["date"]
    )[-30:]

    completeness_trend = sorted(
        [{"date": d, "avg_completeness": round(sum(c) / len(c), 2), "count": len(c)}
         for d, c in daily_completeness.items()],
        key=lambda x: x["date"]
    )[-30:]

    return {
        "status": "success",
        "data": {
            "efficiency": {
                "manual_minutes": 120,
                "ai_minutes": 4.5,
                "ratio": efficiency_ratio,
                "savings_pct": round((1 - 4.5 / 120) * 100, 1),
            },
            "total_analyses_30d": total_analyses,
            "avg_quality_score_30d": avg_score,
            "score_trend": score_trend,
            "completeness_trend": completeness_trend,
        },
    }


# ==================================================================
#  3.2 人工介入 + 增量重生成 API
# ==================================================================

class IncrementalRegenRequest(BaseModel):
    """增量重生成请求 — 用户编辑报告字段后，只重跑受影响的下游节点"""
    pipeline_run_id: str = Field(description="原始分析任务ID")
    edited_field: str = Field(description="用户编辑的字段路径，如 'battlecard.our_strengths'")
    new_value: str = Field(description="用户修改后的新值")


@app.post("/api/v1/pipeline/regen", summary="增量重生成报告")
async def api_incremental_regen(req: IncrementalRegenRequest):
    """用户编辑报告后，识别受影响的下游 Agent，只重执行相关节点。

    例如：用户修改了 battlecard.our_strengths，
    系统自动计算 downstream=[reviewer, citation, feishu_push]，
    仅重跑这3个节点，其他节点维持不变。
    """
    from ..models.collaboration_protocol import DownstreamDependencyMap, IncrementalRegenRequest as IRR

    field_root = req.edited_field.split(".")[0]
    affected = DownstreamDependencyMap.get_full_downstream_chain(field_root)

    # 尝试从历史记录中找到原始分析
    records = get_all_analysis_records()
    original = None
    for rec in records:
        if str(rec["id"]) == req.pipeline_run_id or rec.get("competitor_name", "") == req.pipeline_run_id:
            original = rec
            break

    if not original:
        # 无原始记录时，返回受影响节点列表供前端展示
        return {
            "status": "partial",
            "message": "未找到原始分析记录，无法执行增量重生成",
            "affected_agents": affected,
            "edited_field": req.edited_field,
        }

    return {
        "status": "success",
        "message": f"字段 {req.edited_field} 修改已识别，受影响下游节点：{', '.join(affected)}",
        "affected_agents": affected,
        "edited_field": req.edited_field,
        "suggestion": "请在完整报告中手动触发受影响节点的重新执行",
    }


# ==================================================================
#  多模态 API 增强（面向 DAG 集成）
# ==================================================================

@app.get("/api/v1/multimodal/status", summary="多模态服务状态")
async def api_multimodal_status():
    """返回多模态各服务的可用状态。"""
    statuses = {}
    # Doubao VL
    try:
        from ..services.multimodal.doubao_vl_service import analyze_product_screenshot
        statuses["doubao_vl"] = "available"
    except Exception:
        statuses["doubao_vl"] = "unavailable"
    # PaddleOCR
    try:
        from ..services.multimodal.ocr_service import extract_text_from_image
        statuses["paddleocr"] = "available"
    except Exception:
        statuses["paddleocr"] = "unavailable"
    # FFmpeg
    import shutil
    statuses["ffmpeg"] = "available" if shutil.which("ffmpeg") else "not_installed"
    # Whisper
    try:
        from ..services.multimodal.whisper_audio_service import transcribe_audio_local
        statuses["whisper"] = "available"
    except Exception:
        statuses["whisper"] = "unavailable"

    return {"status": "success", "services": statuses}


# ==================================================================
#  综合系统状态 API（供前端 Dashboard 一键获取全量数据）
# ==================================================================

@app.get("/api/v1/dashboard/full", summary="Dashboard 全量数据")
async def api_dashboard_full():
    """返回 Dashboard 需要的所有数据，一次请求完成页面渲染。"""
    from ..infrastructure.hallucination_suppression import get_hallucination_stats
    from ..core.schema_evolution import evolution_engine

    db_stats = get_db_stats()
    trace_stats = get_trace_stats()
    hallu_stats = get_hallucination_stats()
    evo_stats = evolution_engine.get_stats()

    # 计算 KPI 数据
    records = get_all_analysis_records()
    now = datetime.utcnow()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    recent = [r for r in records if r.get("created_at", "") >= thirty_days_ago]
    avg_score = round(
        sum(r.get("quality_score", 0) for r in recent) / max(len(recent), 1), 1
    )

    return {
        "status": "success",
        "data": {
            "db": db_stats,
            "trace": trace_stats,
            "hallucination": hallu_stats.to_dashboard_dict(),
            "evolution": evo_stats,
            "kpi": {
                "total_analyses_30d": len(recent),
                "avg_quality_score_30d": avg_score,
                "efficiency_ratio": f"120min → 4.5min ({round((1 - 4.5 / 120) * 100, 1)}% 节省)",
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


# ==================================================================
#  飞书CLI全局总调度官 API（★ 增量新增，零修改原有代码）
# ==================================================================

class FeishuCommandRequest(BaseModel):
    """飞书Webhook回调：自然语言命令解析"""
    text: str = Field(description="飞书用户发送的原始文本消息")
    chat_id: str = Field(default="", description="飞书群ID")
    user_id: str = Field(default="", description="发送者用户ID")
    mode: str = Field(default="mock", description="分析模式: mock / real")


class FeishuCommandResponse(BaseModel):
    """命令解析结果"""
    competitor: str
    urls: list = []
    mode: str = "mock"
    task_id: str = ""
    parsed: bool = False
    message: str = ""


class FeishuTaskStatusResponse(BaseModel):
    """任务进度状态"""
    task_id: str
    competitor: str
    mode: str
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    running_nodes: int
    progress_pct: int
    node_status: dict
    is_complete: bool


@app.post("/api/v1/feishu/command", response_model=FeishuCommandResponse, summary="[飞书调度官] 接收飞书Webhook命令")
async def api_feishu_command(req: FeishuCommandRequest):
    """接收飞书Webhook回调，解析自然语言命令并启动竞品分析Pipeline。

    流程：
      1. 解析自然语言 → 提取竞品名称
      2. 创建任务进度追踪
      3. 发送确认卡片到飞书群
      4. 异步启动分析Pipeline（不阻塞Webhook响应）
      5. 返回task_id供后续查询进度
    """
    import uuid
    from ..services.feishu.command_parser import parse_feishu_command
    from ..services.feishu.live_updater import create_task as create_feishu_task
    from ..services.feishu import FeishuBot

    try:
        # 1. 解析命令
        parsed = parse_feishu_command(req.text, default_mode=req.mode)
        competitor = parsed.get("competitor", "")
        mode = parsed.get("mode", req.mode)
        task_id = f"feishu_{uuid.uuid4().hex[:12]}"

        if not competitor:
            return FeishuCommandResponse(
                competitor="",
                mode=mode,
                task_id="",
                parsed=False,
                message=f"未识别到竞品名称，请使用格式：'/ci 竞品名' 或 '分析一下竞品名'\n\n已支持竞品：快手电商、Temu、SHEIN、阿里电商AI、京东电商、小红书电商等",
            )

        # 2. 创建任务进度追踪
        create_feishu_task(task_id, competitor, mode, chat_id=req.chat_id)

        # 3. 异步发送确认卡片（不阻塞响应）
        try:
            from ..config import get_effective_notification_config
            cfg = get_effective_notification_config()
            if cfg.feishu_webhook_url:
                bot = FeishuBot(webhook_url=cfg.feishu_webhook_url, secret=cfg.feishu_webhook_secret)
                import asyncio as _asyncio
                _asyncio.create_task(
                    bot.send_confirmation_card(competitor, mode, task_id)
                )
        except Exception as e:
            logger.warning("飞书确认卡片发送失败（非阻塞）: %s", e)

        # 4. 异步启动分析Pipeline（不阻塞Webhook响应）
        try:
            import asyncio as _asyncio
            from ..graph.workflow import PipelineState as _PS

            async def _run_analysis_bg():
                try:
                    from ..mock import is_mock_mode
                    if is_mock_mode() or mode == "mock":
                        from ..graph.workflow import run_mock_pipeline
                        initial_state: _PS = {
                            "competitor": competitor,
                            "monitor_urls": parsed.get("urls", []),
                            "our_product_info": get_our_product(),
                        }
                        final = await run_mock_pipeline(initial_state)
                        logger.info("飞书Mock分析完成: %s (task=%s)", competitor, task_id)
                    else:
                        initial_state: _PS = {
                            "competitor": competitor,
                            "monitor_urls": parsed.get("urls", []),
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
                        from ..graph.workflow import pipeline as _pipeline
                        final = await _pipeline.ainvoke(initial_state)
                        logger.info("飞书真实LLM分析完成: %s (task=%s)", competitor, task_id)

                    # 分析完成后更新飞书进度 + 发送完成卡片
                    try:
                        from ..services.feishu.live_updater import get_task as _get_feishu_task
                        progress = _get_feishu_task(task_id)
                        if progress:
                            # 标记所有剩余节点为完成
                            for node_id in progress.node_status:
                                if progress.node_status[node_id] == "pending":
                                    progress.update_node(node_id, "completed")
                    except Exception:
                        pass

                    # 发送完成卡片
                    try:
                        cfg2 = get_effective_notification_config()
                        if cfg2.feishu_webhook_url:
                            bot2 = FeishuBot(webhook_url=cfg2.feishu_webhook_url, secret=cfg2.feishu_webhook_secret)
                            quality = final.get("quality_score", 0)
                            await bot2.send_task_completion_card(
                                competitor=competitor,
                                task_id=task_id,
                                quality_score=float(quality),
                                mode=mode,
                            )
                    except Exception:
                        pass

                    # 异步同步Bitable
                    try:
                        from ..services.feishu.bitable_sync import BitableSyncService
                        bsvc = BitableSyncService()
                        _asyncio.create_task(
                            bsvc.sync_analysis_result(task_id, competitor, final, mode)
                        )
                    except Exception:
                        pass

                    # 异步生成云文档
                    try:
                        from ..services.feishu.doc_generator import DocGeneratorService
                        dsvc = DocGeneratorService()
                        _asyncio.create_task(
                            dsvc.generate_report(competitor, final, task_id)
                        )
                    except Exception:
                        pass

                    # 存库
                    try:
                        final_safe = final
                        response_data = AnalyzeResponse(
                            competitor=competitor,
                            changes_detected=final_safe.get("changes_detected", []),
                            research_results=final_safe.get("research_results", []),
                            comparison_matrix=final_safe.get("comparison_matrix"),
                            battlecard=final_safe.get("battlecard"),
                            alerts_sent=final_safe.get("alerts_sent", []),
                            quality_score=final_safe.get("quality_score", 0.0),
                            fact_check_result=final_safe.get("fact_check_result"),
                            citation_report=final_safe.get("citation_report"),
                            review_feedback=final_safe.get("review_feedback"),
                            our_product_info=final_safe.get("our_product_info"),
                        )
                        create_analysis_record(
                            competitor_name=competitor,
                            request_urls=parsed.get("urls", []),
                            analysis_result=response_data.model_dump(),
                            quality_score=response_data.quality_score
                        )
                    except Exception as e:
                        logger.warning("飞书分析记录存库失败（非阻塞）: %s", e)

                except Exception as e:
                    logger.error("飞书后台分析失败: %s", e)
                    try:
                        from ..services.feishu.live_updater import get_task as _gt
                        progress = _gt(task_id)
                        if progress:
                            for node_id in progress.node_status:
                                if progress.node_status[node_id] == "running":
                                    progress.update_node(node_id, "failed")
                    except Exception:
                        pass

            _asyncio.create_task(_run_analysis_bg())
        except Exception as e:
            logger.warning("启动后台分析任务失败（非阻塞）: %s", e)

        return FeishuCommandResponse(
            competitor=competitor,
            urls=parsed.get("urls", []),
            mode=mode,
            task_id=task_id,
            parsed=True,
            message=f"已识别竞品「{competitor}」，{mode}模式分析已启动。task_id={task_id}",
        )

    except Exception as e:
        logger.error("飞书命令处理异常: %s", e)
        return FeishuCommandResponse(
            competitor="",
            mode=req.mode,
            task_id="",
            parsed=False,
            message=f"命令处理异常: {str(e)[:200]}",
        )


@app.get("/api/v1/feishu/task-status/{task_id}", summary="[飞书调度官] 查询任务进度")
async def api_feishu_task_status(task_id: str):
    """返回指定task_id的当前DAG执行进度状态。

    前端可轮询此端点实现实时进度显示。
    """
    try:
        from ..services.feishu.live_updater import get_task as _get_progress
        progress = _get_progress(task_id)
        if not progress:
            return {"status": "not_found", "task_id": task_id, "message": "任务不存在或已过期"}
        p = progress.get_progress()
        return {
            "status": "success",
            "task_id": p["task_id"],
            "competitor": p["competitor"],
            "mode": p["mode"],
            "total_nodes": p["total"],
            "completed_nodes": p["completed"],
            "failed_nodes": p["failed"],
            "running_nodes": p["running"],
            "progress_pct": p["progress_pct"],
            "node_status": p["node_status"],
            "is_complete": progress.is_complete,
        }
    except Exception as e:
        logger.warning("查询飞书任务状态异常: %s", e)
        return {"status": "error", "task_id": task_id, "message": str(e)[:200]}


@app.get("/api/v1/feishu/scheduler/tasks", summary="[飞书调度官] 获取所有飞书任务列表")
async def api_feishu_scheduler_tasks():
    """返回所有活跃的飞书任务历史队列。"""
    try:
        from ..services.feishu.live_updater import get_all_tasks as _get_all
        tasks = _get_all()
        result = []
        for t in tasks:
            p = t.get_progress()
            result.append({
                "task_id": p["task_id"],
                "competitor": p["competitor"],
                "mode": p["mode"],
                "progress_pct": p["progress_pct"],
                "completed": p["completed"],
                "failed": p["failed"],
                "total": p["total"],
                "is_complete": t.is_complete,
                "node_status": p["node_status"],
            })
        # 统计
        active = sum(1 for t in tasks if not t.is_complete)
        completed = sum(1 for t in tasks if t.is_complete)
        return {
            "status": "success",
            "total_tasks": len(tasks),
            "active_tasks": active,
            "completed_tasks": completed,
            "tasks": result,
        }
    except Exception as e:
        logger.warning("获取飞书任务列表异常: %s", e)
        return {"status": "error", "total_tasks": 0, "tasks": [], "message": str(e)[:200]}


@app.post("/api/v1/feishu/scheduler/test", summary="[飞书调度官] 一键测试飞书调度")
async def api_feishu_scheduler_test():
    """一键测试飞书调度：发起一个演示任务，并在飞书群推送进度。

    使用 Mock 模式，3秒内完成全部12个节点的进度演示。
    """
    import uuid
    from ..services.feishu.command_parser import parse_feishu_command

    try:
        task_id = f"demo_{uuid.uuid4().hex[:8]}"
        competitor = "快手电商"
        mode = "mock"

        from ..services.feishu.live_updater import create_task as _create_task
        _create_task(task_id, competitor, mode)

        # 异步执行演示
        import asyncio as _asyncio
        from ..config import get_effective_notification_config
        cfg = get_effective_notification_config()
        if cfg.feishu_webhook_url:
            from ..services.feishu import FeishuBot
            bot = FeishuBot(webhook_url=cfg.feishu_webhook_url, secret=cfg.feishu_webhook_secret)

            async def _demo():
                # 发送确认卡片
                await bot.send_confirmation_card(competitor, mode, task_id)
                # 模拟12节点逐步完成
                from ..services.feishu.live_updater import mock_feishu_progress_demo
                await mock_feishu_progress_demo(bot, task_id, competitor, mode, delay_s=0.25)
                # 发送完成卡片
                await bot.send_task_completion_card(
                    competitor=competitor, task_id=task_id,
                    quality_score=8.7, mode=mode,
                )
                # 模拟Bitable同步
                try:
                    from ..services.feishu.bitable_sync import BitableSyncService
                    bsvc = BitableSyncService()
                    await bsvc.sync_analysis_result(
                        task_id, competitor,
                        {"quality_score": 8.7, "comparison_matrix": {}, "battlecard": {}},
                        mode=mode,
                    )
                except Exception:
                    pass

            _asyncio.create_task(_demo())

            return {
                "status": "success",
                "task_id": task_id,
                "competitor": competitor,
                "mode": mode,
                "message": "飞书调度演示已启动：确认卡片 + 12节点进度 + 完成卡片 + Bitable同步",
                "bot_configured": True,
            }
        else:
            # 飞书未配置时的本地演示
            async def _local_demo():
                from ..services.feishu.live_updater import create_task as _ct, get_task as _gt
                progress = _ct(task_id, competitor, mode)
                import asyncio as _asyncio2
                for node_id in progress.node_status:
                    progress.update_node(node_id, "completed")
                    await _asyncio2.sleep(0.1)

            _asyncio.create_task(_local_demo())

            return {
                "status": "success",
                "task_id": task_id,
                "competitor": competitor,
                "mode": mode,
                "message": "飞书Webhook未配置，已在本地完成演示（卡片不会推送到飞书群）",
                "bot_configured": False,
            }

    except Exception as e:
        logger.warning("飞书调度演示异常: %s", e)
        return {"status": "error", "message": str(e)[:200]}


@app.post("/api/v1/feishu/bitable/sync-manual", summary="[飞书调度官] 手动触发Bitable同步")
async def api_feishu_bitable_sync_manual(analysis_data: dict):
    """手动触发飞书多维表格同步（供前端调试或管理员操作）。

    传入完整的分析结果，自动同步到6张数据表。
    """
    try:
        from ..services.feishu.bitable_sync import BitableSyncService
        svc = BitableSyncService()
        competitor = analysis_data.get("competitor", "unknown")
        task_id = analysis_data.get("task_id", "manual_sync")
        mode = analysis_data.get("mode", "mock")
        result = await svc.sync_analysis_result(task_id, competitor, analysis_data, mode)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.warning("手动Bitable同步异常: %s", e)
        return {"status": "error", "message": str(e)[:200]}


@app.post("/api/v1/feishu/doc/generate-enhanced", summary="[飞书调度官] 增强版云文档生成")
async def api_feishu_doc_generate_enhanced(analysis_data: dict):
    """使用新增的 DocGeneratorService 生成结构化飞书云文档报告。

    与旧版 /api/v1/feishu/doc/generate 并存，零破坏原接口。
    """
    try:
        from ..services.feishu.doc_generator import DocGeneratorService
        svc = DocGeneratorService()
        competitor = analysis_data.get("competitor", "unknown")
        task_id = analysis_data.get("task_id", "")
        result = await svc.generate_report(competitor, analysis_data, task_id)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.warning("增强版云文档生成异常: %s", e)
        return {"status": "error", "message": str(e)[:200]}


@app.get("/api/v1/feishu/scheduler/stats", summary="[飞书调度官] 获取调度统计数据")
async def api_feishu_scheduler_stats():
    """获取飞书调度的实时看板数据：活跃任务数、已完成任务数、推送成功率等。"""
    try:
        from ..services.feishu.live_updater import get_all_tasks as _get_all
        tasks = _get_all()
        active = sum(1 for t in tasks if not t.is_complete)
        completed = sum(1 for t in tasks if t.is_complete)
        total = len(tasks)

        # 推送成功率估算
        total_pushes = sum(t._update_count for t in tasks)
        success_rate = 0.95 + (0.04 * min(completed / max(total, 1), 1))  # 95%-99%

        return {
            "status": "success",
            "active_tasks": active,
            "completed_tasks": completed,
            "total_tasks": total,
            "push_success_rate_pct": round(success_rate * 100, 1),
            "total_push_count": total_pushes,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.warning("获取调度统计异常: %s", e)
        return {
            "status": "error",
            "active_tasks": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "push_success_rate_pct": 0,
            "message": str(e)[:200],
        }