"""Pydantic models shared across all agents and the API layer."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_serializer


# 基础模型：统一处理所有datetime字段的序列化
class BaseSchema(BaseModel):
    @field_serializer("*", when_used="always")
    def serialize_all_fields(self, value):
        # 所有datetime字段自动转ISO标准字符串
        if isinstance(value, datetime):
            return value.isoformat()
        return value


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ChangeType(str, Enum):
    PRICING = "pricing"
    PRODUCT = "product"
    HIRING = "hiring"
    NEWS = "news"
    PATENT = "patent"
    BLOG = "blog"
    OPEN_SOURCE = "open_source"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Monitor Agent models
# ---------------------------------------------------------------------------
class CompetitorChange(BaseSchema):
    competitor: str
    change_type: ChangeType
    title: str
    summary: str
    url: str = ""
    severity: Severity = Severity.MEDIUM
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: dict = Field(default_factory=dict)


class MonitorResult(BaseSchema):
    competitor: str
    changes: list[CompetitorChange] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Research Agent models
# ---------------------------------------------------------------------------
class ResearchInsight(BaseSchema):
    topic: str
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class ResearchResult(BaseSchema):
    competitor: str
    insights: list[ResearchInsight] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Compare Agent models
# ---------------------------------------------------------------------------
class DimensionScore(BaseSchema):
    dimension: str
    our_score: float = Field(ge=0.0, le=10.0)
    competitor_score: float = Field(ge=0.0, le=10.0)
    notes: str = ""


class ComparisonMatrix(BaseSchema):
    competitor: str
    dimensions: list[DimensionScore] = Field(default_factory=list)
    overall_assessment: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Battlecard Agent models
# ---------------------------------------------------------------------------
class Battlecard(BaseSchema):
    competitor: str
    our_strengths: list[str] = Field(default_factory=list)
    our_weaknesses: list[str] = Field(default_factory=list)
    competitor_strengths: list[str] = Field(default_factory=list)
    competitor_weaknesses: list[str] = Field(default_factory=list)
    key_differentiators: list[str] = Field(default_factory=list)
    objection_handling: dict[str, str] = Field(default_factory=dict)
    elevator_pitch: str = ""
    next_actions: list[dict] = Field(default_factory=list, description="面向销售/产品/技术团队的可执行落地建议，每条包含action/owner/expected_impact")  # ★ 新增：下一步动作
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Alert Agent models
# ---------------------------------------------------------------------------
class Alert(BaseSchema):
    competitor: str
    title: str
    message: str
    severity: Severity
    channel: str = "all"
    sent_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Pipeline state (used by LangGraph)
# ---------------------------------------------------------------------------
class CIState(BaseSchema):
    """Top-level state flowing through the LangGraph pipeline."""
    competitor: str
    changes_detected: list[CompetitorChange] = Field(default_factory=list)
    research_results: list[ResearchInsight] = Field(default_factory=list)
    comparison_matrix: Optional[ComparisonMatrix] = None
    battlecard: Optional[Battlecard] = None
    alerts_sent: list[Alert] = Field(default_factory=list)
    quality_score: float = 0.0
    reflexion_count: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 我方产品模型
# ---------------------------------------------------------------------------
class OurProduct(BaseSchema):
    """我方产品结构化信息，用于对比分析时提供真实基准数据。"""
    name: str = "My Product"
    core_features: list[str] = Field(default_factory=list)
    pricing_model: str = "订阅制"
    tech_stack: list[str] = Field(default_factory=list)
    target_market: str = ""
    competitive_advantages: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    updated_at: str = ""


# ===================================================================
# 三节点全局校验架构 — 新增模型
# ===================================================================

class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"


class FactCheckItem(BaseSchema):
    """单条交叉验证结果"""
    source_agent: str = Field(description="来源 Agent（monitor/research）")
    claim: str = Field(description="原始断言摘要")
    status: VerificationStatus
    supporting_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    adjusted_severity: Optional[str] = Field(default=None, description="调整后的严重程度")


class FactCheckResult(BaseSchema):
    """FactCheck Agent 交叉验证输出"""
    competitor: str
    cross_verified: list[FactCheckItem] = Field(default_factory=list)
    inconsistencies: list[dict] = Field(default_factory=list, description="Monitor vs Research 矛盾项")
    confidence_adjustments: dict[str, float] = Field(default_factory=dict)
    summary: str = ""


class ReviewIssue(BaseSchema):
    """Reviewer 发现的单个问题（精确到字段路径）"""
    severity: str = Field(description="high / medium / low")
    target: str = Field(description="问题字段路径，如 battlecard.our_weaknesses")
    description: str = Field(description="问题描述")
    fix_instruction: str = Field(description="修复指令（给 TargetedFix）")


class ReviewFeedback(BaseSchema):
    """Reviewer Agent 4维度评分的结构化反馈"""
    overall_score: float = Field(default=0.0, ge=0.0, le=10.0)
    accuracy_score: float = Field(default=0.0, ge=0.0, le=10.0)
    completeness_score: float = Field(default=0.0, ge=0.0, le=10.0)
    citation_score: float = Field(default=0.0, ge=0.0, le=10.0)
    actionability_score: float = Field(default=0.0, ge=0.0, le=10.0)
    approved: bool = False
    issues: list[ReviewIssue] = Field(default_factory=list)
    revision_instructions: str = ""


class FixEffectiveness(BaseSchema):
    """反馈闭环：追踪每次 TargetedFix 的修复效果"""
    round: int = Field(description="修复轮次", ge=1)
    score_before: float = Field(description="修复前 Reviewer 评分", ge=0.0, le=10.0)
    score_after: float = Field(description="修复后 Reviewer 评分", ge=0.0, le=10.0)
    issues_count_before: int = Field(description="修复前问题数量", ge=0)
    issues_count_after: int = Field(description="修复后问题数量", ge=0)
    improvement: float = Field(description="score 提升值（负数为恶化）")
    fixed_fields: list[str] = Field(default_factory=list, description="本次修复的字段路径")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SourceURL(BaseSchema):
    """单个引用来源 URL 及其验证状态"""
    url: str
    reachable: bool = False
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)


class CitationReport(BaseSchema):
    """Citation Agent 引用溯源报告"""
    total_sources: int = 0
    verified_sources: int = 0
    broken_links: int = 0
    missing_citations: list[str] = Field(default_factory=list)
    reliability_distribution: dict[str, int] = Field(default_factory=dict,
        description="可信度分布，如 {'1.0': 5, '0.8': 3}")
    overall_reliability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_urls: list[SourceURL] = Field(default_factory=list, description="所有引用来源URL列表，供前端一键跳转")


# ===================================================================
# 1.2 强类型竞品知识 Schema（100% 强制约束，extra='forbid'）
# ===================================================================

class FeatureNode(BaseModel):
    """层级功能树节点 — 递归定义竞品的功能体系"""
    feature_name: str = Field(description="功能名称")
    description: str = Field(default="", description="功能描述")
    maturity_score: int = Field(default=5, ge=0, le=10, description="成熟度评分 0-10")
    child_features: list["FeatureNode"] = Field(default_factory=list, description="子功能列表")

    model_config = {"extra": "forbid"}


class CompetitorFeatureTree(BaseModel):
    """竞品功能树 — 完整的功能体系结构化描述"""
    root_features: list[FeatureNode] = Field(default_factory=list, description="顶层功能列表")
    hidden_optimizations: list[str] = Field(default_factory=list, description="隐蔽优化点（非公开功能）")
    technical_advantages: list[str] = Field(default_factory=list, description="技术优势总结")

    model_config = {"extra": "forbid"}


class PricingTier(BaseModel):
    """定价层级 — 单个定价套餐的完整信息"""
    tier_name: str = Field(description="套餐名称，如 'Pro', 'Enterprise'")
    price: float = Field(description="价格（统一转换为人民币元）")
    user_segment: str = Field(description="目标用户群，如 '中小企业', '大型企业'")
    included_features: list[str] = Field(default_factory=list, description="包含的功能列表")

    model_config = {"extra": "forbid"}


class PricingModel(BaseModel):
    """定价模型 — 竞品完整定价策略"""
    tier_list: list[PricingTier] = Field(default_factory=list, description="定价层级列表")
    monetization_formula: str = Field(
        default="",
        description="变现公式，如 'take_rate 3% + ad_ARPU 12.5'",
    )
    discount_strategy: str = Field(default="", description="折扣策略描述")
    price_positioning_vs_ours: str = Field(
        default="parity", description="相对我方的价格定位",
        pattern=r"^(much_lower|lower|parity|higher|much_higher)$",
    )

    model_config = {"extra": "forbid"}


class UserPersona(BaseModel):
    """用户画像 — 单个用户分群的完整画像"""
    segment_name: str = Field(description="用户分群名称")
    demographic_tags: list[str] = Field(default_factory=list, description="人口统计学标签")
    pain_points: list[str] = Field(default_factory=list, description="痛点列表")
    satisfaction_score: float = Field(default=0.0, ge=0.0, le=10.0, description="满意度评分")

    model_config = {"extra": "forbid"}


class UserPersonaCollection(BaseModel):
    """用户画像集合 — 竞品用户全景图"""
    top_personas: list[UserPersona] = Field(default_factory=list, description="主要用户画像列表")
    nps_overall: float = Field(default=0.0, description="整体 NPS 净推荐值")
    churn_risk_factors: list[str] = Field(default_factory=list, description="流失风险因素")

    model_config = {"extra": "forbid"}


# ===================================================================
# 1.3 细粒度 1:N 信息溯源映射（SourceSpan）
# ===================================================================

class SourceSpan(BaseModel):
    """细粒度溯源 — 将分析文本的每个片段绑定到原始来源。

    每个 SourceSpan 精确标记报告中一段文字的数据来源，
    前端渲染时自动高亮并支持点击跳转原始URL，实现「一键溯源直达」。
    """
    span_id: str = Field(description="唯一标识，如 'span_001'")
    analysis_text_snippet: str = Field(description="分析报告中被标记的原文片段")
    start_char_idx: int = Field(ge=0, description="在完整报告文本中的起始位置")
    end_char_idx: int = Field(ge=0, description="在完整报告文本中的结束位置")
    source_url: str = Field(description="原始来源URL")
    source_title: str = Field(default="", description="来源标题")
    reliability_score: float = Field(default=0.5, ge=0.0, le=1.0, description="来源可信度 0-1")
    source_type: str = Field(
        default="web", description="来源类型: web/paper/report/social_media/official",
        pattern=r"^(web|paper|report|social_media|official)$",
    )

    model_config = {"extra": "forbid"}


class SourceSpanCollection(BaseModel):
    """一次分析任务中所有 SourceSpan 的集合"""
    pipeline_run_id: str = Field(default="", description="关联的分析任务ID")
    spans: list[SourceSpan] = Field(default_factory=list, description="溯源片段列表")
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="溯源覆盖率")
    generated_at: str = Field(default="", description="生成时间 ISO 字符串")


# ── Rebuild models with forward references (FeatureNode is self-referencing) ──
FeatureNode.model_rebuild()
SourceSpanCollection.model_rebuild()