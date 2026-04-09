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
    get_analysis_record_by_id
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
# Application factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CI Multi-Agent Pipeline started")
    # 新增：服务启动时自动初始化数据库
    init_db()
    logger.info("Database initialized successfully")
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
    initial_state: PipelineState = {
        "competitor": req.competitor,
        "monitor_urls": req.urls or [],
        "previous_hashes": {},
        "changes_detected": [],
        "research_results": [],
        "comparison_matrix": None,
        "battlecard": None,
        "alerts_sent": [],
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
    # -----------------------------------------------------------------------------------

    return response_data


@app.post("/analyze/stream")
async def analyze_stream(req: AnalyzeRequest):
    """Stream pipeline events via Server-Sent Events (SSE) so the frontend
    can show real-time progress."""

    async def event_generator() -> AsyncGenerator[dict, None]:
        initial_state: PipelineState = {
            "competitor": req.competitor,
            "monitor_urls": req.urls or [],
            "previous_hashes": {},
            "changes_detected": [],
            "research_results": [],
            "comparison_matrix": {},
            "battlecard": {},
            "alerts_sent": [],
            "quality_score": 0.0,
            "reflexion_count": 0,
            "error": None,
        }

        try:
            async for event in pipeline.astream(initial_state):
                for node_name, node_output in event.items():
                    yield {
                        "event": node_name,
                        "data": json.dumps(node_output, default=str, ensure_ascii=False),
                    }
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}),
            }

    return EventSourceResponse(event_generator())


@app.get("/competitors")
async def list_competitors():
    """Return a list of pre-configured competitors (demo endpoint)."""
    return {
        "competitors": [
            {"name": "CompetitorA", "website": "https://competitora.com"},
            {"name": "CompetitorA", "website": "https://competitora.com"},
            {"name": "CompetitorB", "website": "https://competitorb.com"},
            {"name": "CompetitorC", "website": "https://competitorc.com"},
        ]
    }
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