"""
Palantir Ontology 核心Schema — 五层对象体系。

L1 核心实体: Competitor / Product / Brand
L2 功能维度: Feature / Architecture / Pricing
L3 市场情报: MarketEvent / UserFeedback / SentimentSignal
L4 分析产出: ComparisonReport / ScoreCard / Insight
L5 执行动作: AlertRule / MonitorTask / ResponseAction

所有类继承 BaseSchema，Pydantic v2 完整类型定义。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field

from .schemas import BaseSchema


# ═══════════════════════════════════════════════════════
# L1 — 核心实体层
# ═══════════════════════════════════════════════════════

class CompetitorCategory(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    POTENTIAL = "potential"
    SUBSTITUTE = "substitute"


class CompetitorLifecycle(str, Enum):
    EMERGING = "emerging"
    GROWING = "growing"
    MATURE = "mature"
    DECLINING = "declining"


class OntologyCompetitor(BaseSchema):
    """竞品本体 — 竞品情报系统核心实体"""
    name: str = Field(description="竞品名称", min_length=1)
    aliases: list[str] = Field(default_factory=list, description="别名/简称列表")
    category: CompetitorCategory = Field(default=CompetitorCategory.DIRECT, description="竞品分类")
    lifecycle: CompetitorLifecycle = Field(default=CompetitorLifecycle.GROWING, description="生命周期阶段")
    founded_year: Optional[int] = Field(default=None, ge=1900, description="成立年份")
    headquarters: str = Field(default="", description="总部所在地")
    employee_count: Optional[int] = Field(default=None, ge=0, description="员工数量估算")
    revenue_estimate: str = Field(default="", description="营收估算（区间或精确值）")
    website_urls: list[str] = Field(default_factory=list, description="官网及子站URL列表")
    social_handles: dict[str, str] = Field(default_factory=dict, description="社交媒体账号 {platform: handle}")
    tags: list[str] = Field(default_factory=list, description="行业标签")
    description: str = Field(default="", description="一句话描述")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProductType(str, Enum):
    CORE = "core"
    NEW = "new"
    DISCONTINUED = "discontinued"
    ACQUIRED = "acquired"


class OntologyProduct(BaseSchema):
    """产品本体 — 竞品旗下的具体产品线"""
    name: str = Field(description="产品名称", min_length=1)
    parent_competitor: str = Field(description="所属竞品名称")
    product_type: ProductType = Field(default=ProductType.CORE)
    target_market: str = Field(default="", description="目标市场")
    user_base_estimate: str = Field(default="", description="用户量估算")
    launch_date: Optional[datetime] = Field(default=None, description="首次发布/上线日期")
    pricing_tiers: list[dict] = Field(default_factory=list, description="定价层级 [{tier, price, billing_cycle}]")
    key_differentiators: list[str] = Field(default_factory=list, description="核心差异化特性")
    swot_tags: list[str] = Field(default_factory=list, description="SWOT分类标签")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BrandLevel(str, Enum):
    CORPORATE = "corporate"
    PRODUCT_LINE = "product_line"
    SUB_BRAND = "sub_brand"


class OntologyBrand(BaseSchema):
    """品牌本体 — 竞品的品牌资产"""
    name: str = Field(description="品牌名称", min_length=1)
    parent_competitor: str = Field(description="所属竞品名称")
    level: BrandLevel = Field(default=BrandLevel.CORPORATE)
    brand_awareness_score: float = Field(default=0.0, ge=0.0, le=10.0, description="品牌知名度评分")
    nps_estimate: Optional[float] = Field(default=None, ge=-100.0, le=100.0, description="NPS估算值")
    social_followers: dict[str, int] = Field(default_factory=dict, description="各平台粉丝数 {platform: count}")
    sentiment_trend: str = Field(default="stable", description="品牌口碑趋势: rising/stable/declining")
    key_messages: list[str] = Field(default_factory=list, description="品牌核心传播信息")


# ═══════════════════════════════════════════════════════
# L2 — 功能维度层
# ═══════════════════════════════════════════════════════

class MaturityLevel(str, Enum):
    PLANNED = "planned"
    ALPHA = "alpha"
    BETA = "beta"
    GA = "ga"
    DEPRECATED = "deprecated"


class OntologyFeature(BaseSchema):
    """功能本体 — 产品功能的细粒度建模"""
    name: str = Field(description="功能名称", min_length=1)
    parent_product: str = Field(description="所属产品名称")
    parent_competitor: str = Field(default="", description="所属竞品名称（冗余便于查询）")
    description: str = Field(default="", description="功能描述")
    maturity: MaturityLevel = Field(default=MaturityLevel.GA, description="功能成熟度")
    our_parity: str = Field(default="unknown", description="我方对标情况: ahead/parity/behind/unknown")
    competitive_advantage: bool = Field(default=False, description="是否为竞品核心优势功能")
    user_adoption_estimate: str = Field(default="", description="用户采用率估算")
    linked_dimensions: list[str] = Field(default_factory=list, description="关联对比维度名称")


class ArchitectureTier(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    INFRASTRUCTURE = "infrastructure"
    DATA = "data"
    AI_ML = "ai_ml"


class OntologyArchitecture(BaseSchema):
    """技术架构本体 — 竞品技术栈建模"""
    competitor: str = Field(description="所属竞品名称")
    tier: ArchitectureTier = Field(description="架构层级")
    tech_stack: list[str] = Field(default_factory=list, description="技术栈列表")
    cloud_providers: list[str] = Field(default_factory=list, description="云服务商")
    open_source_adoption: str = Field(default="", description="开源采用程度")
    patent_count: Optional[int] = Field(default=None, ge=0, description="相关专利数量")
    engineering_blog_url: str = Field(default="", description="技术博客URL")
    github_org: str = Field(default="", description="GitHub组织名")
    architecture_notes: str = Field(default="", description="架构分析备注")


class PricingModel(str, Enum):
    FREE = "free"
    FREEMIUM = "freemium"
    SUBSCRIPTION = "subscription"
    USAGE_BASED = "usage_based"
    ENTERPRISE = "enterprise"
    HYBRID = "hybrid"


class OntologyPricing(BaseSchema):
    """定价本体 — 竞品定价策略建模"""
    competitor: str = Field(description="所属竞品名称")
    product: str = Field(default="", description="关联产品名称")
    model: PricingModel = Field(description="定价模型")
    entry_price_monthly: Optional[float] = Field(default=None, ge=0, description="最低月费")
    mid_tier_price_monthly: Optional[float] = Field(default=None, ge=0, description="中级月费")
    enterprise_price: str = Field(default="", description="企业版定价（通常为联系销售）")
    free_tier_limits: str = Field(default="", description="免费版限制说明")
    discount_strategy: str = Field(default="", description="折扣策略（年付/批量/教育等）")
    price_change_trend: str = Field(default="stable", description="价格变动趋势: rising/stable/lowering")
    compared_to_us: str = Field(default="similar", description="与我方对比: cheaper/similar/premium")


# ═══════════════════════════════════════════════════════
# L3 — 市场情报层
# ═══════════════════════════════════════════════════════

class MarketEventType(str, Enum):
    FUNDING = "funding"
    ACQUISITION = "acquisition"
    PRODUCT_LAUNCH = "product_launch"
    EXECUTIVE_CHANGE = "executive_change"
    PARTNERSHIP = "partnership"
    REGULATORY = "regulatory"
    LAYOFF = "layoff"
    OTHER = "other"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OntologyMarketEvent(BaseSchema):
    """市场事件本体 — 竞品重大动态追踪"""
    title: str = Field(description="事件标题", min_length=1)
    competitor: str = Field(description="关联竞品名称")
    event_type: MarketEventType = Field(description="事件类型")
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM, description="严重级别")
    summary: str = Field(description="事件摘要")
    source_urls: list[str] = Field(default_factory=list, description="来源URL列表")
    detected_at: datetime = Field(default_factory=datetime.utcnow, description="检测时间")
    occurred_at: Optional[datetime] = Field(default=None, description="事件发生时间")
    impact_assessment: str = Field(default="", description="对我方影响评估")
    recommended_action: str = Field(default="", description="建议应对动作")


class SentimentLabel(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class OntologyUserFeedback(BaseSchema):
    """用户反馈本体 — 竞品用户评价收集"""
    competitor: str = Field(description="关联竞品名称")
    product: str = Field(default="", description="关联产品")
    source_platform: str = Field(description="来源平台（App Store/Google Play/TrustPilot/Reddit等）")
    rating: float = Field(default=0.0, ge=0.0, le=5.0, description="用户评分")
    review_text: str = Field(default="", description="评价原文")
    sentiment: SentimentLabel = Field(default=SentimentLabel.NEUTRAL, description="情感标签")
    keywords: list[str] = Field(default_factory=list, description="提取的关键词")
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="采集时间")
    review_date: Optional[datetime] = Field(default=None, description="评价发布时间")


class OntologySentimentSignal(BaseSchema):
    """情感信号本体 — 聚合情感分析结果"""
    competitor: str = Field(description="关联竞品名称")
    period: str = Field(description="统计周期（如 2026-W21）")
    total_mentions: int = Field(default=0, ge=0, description="总提及量")
    positive_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="正面比例")
    negative_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="负面比例")
    nps_estimate: Optional[float] = Field(default=None, ge=-100.0, le=100.0, description="NPS估算")
    trending_topics: list[str] = Field(default_factory=list, description="趋势话题")
    sentiment_shift: str = Field(default="stable", description="情感变化: improving/stable/deteriorating")
    top_pain_points: list[str] = Field(default_factory=list, description="高频痛点")
    source_breakdown: dict[str, int] = Field(default_factory=dict, description="来源分布 {platform: count}")


# ═══════════════════════════════════════════════════════
# L4 — 分析产出层
# ═══════════════════════════════════════════════════════

class ReportStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OntologyComparisonReport(BaseSchema):
    """对比报告本体 — 竞品分析完整报告"""
    title: str = Field(description="报告标题", min_length=1)
    competitor: str = Field(description="分析对象竞品名称")
    status: ReportStatus = Field(default=ReportStatus.DRAFT, description="报告状态")
    quality_score: float = Field(default=0.0, ge=0.0, le=10.0, description="质量评分")
    dimensions: list[dict] = Field(default_factory=list, description="各维度评分详情")
    overall_assessment: str = Field(default="", description="综合评估")
    our_overall_score: float = Field(default=0.0, ge=0.0, le=10.0, description="我方综合评分")
    competitor_overall_score: float = Field(default=0.0, ge=0.0, le=10.0, description="竞品综合评分")
    citations_count: int = Field(default=0, ge=0, description="引用来源数")
    citation_reliability: float = Field(default=0.0, ge=0.0, le=1.0, description="引用整体可信度")
    review_passed: bool = Field(default=False, description="是否通过审查")
    fix_history: list[dict] = Field(default_factory=list, description="修复历史记录")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = Field(default="ci-pipeline", description="生成者标识")


class OntologyScoreCard(BaseSchema):
    """评分卡片本体 — 单维度评分详细记录"""
    competitor: str = Field(description="竞品名称")
    dimension: str = Field(description="评分维度")
    our_score: float = Field(default=5.0, ge=0.0, le=10.0, description="我方评分")
    competitor_score: float = Field(default=5.0, ge=0.0, le=10.0, description="竞品评分")
    evidence: list[str] = Field(default_factory=list, description="评分依据")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="评分置信度")
    data_tier: str = Field(default="B", description="数据可达性等级: A/B/C/D")
    notes: str = Field(default="", description="评分备注")


class InsightCategory(str, Enum):
    OPPORTUNITY = "opportunity"
    THREAT = "threat"
    WEAKNESS = "weakness"
    STRENGTH = "strength"
    TREND = "trend"


class OntologyInsight(BaseSchema):
    """洞察本体 — 从分析中提炼的可执行洞察"""
    title: str = Field(description="洞察标题", min_length=1)
    category: InsightCategory = Field(description="洞察分类")
    competitor: str = Field(default="", description="关联竞品")
    dimension: str = Field(default="", description="关联维度")
    description: str = Field(description="洞察详细描述")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")
    supporting_evidence: list[str] = Field(default_factory=list, description="支撑证据")
    actionable: bool = Field(default=False, description="是否可立即执行")
    priority: int = Field(default=3, ge=1, le=5, description="优先级 1-5（1最高）")
    derived_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════
# L5 — 执行动作层
# ═══════════════════════════════════════════════════════

class MonitorFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class OntologyAlertRule(BaseSchema):
    """告警规则本体 — 自动化竞品变更告警"""
    name: str = Field(description="规则名称", min_length=1)
    competitor_filter: str = Field(default="*", description="竞品筛选（*表示全部）")
    event_types: list[MarketEventType] = Field(default_factory=list, description="关注的事件类型")
    severity_threshold: SeverityLevel = Field(default=SeverityLevel.MEDIUM, description="触发告警的最低严重级别")
    channels: list[str] = Field(default_factory=list, description="推送渠道: feishu/slack/dingtalk/email")
    enabled: bool = Field(default=True, description="是否启用")
    cooldown_minutes: int = Field(default=60, ge=1, description="冷却时间（分钟）")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OntologyMonitorTask(BaseSchema):
    """监控任务本体 — 竞品监控执行任务"""
    name: str = Field(description="任务名称", min_length=1)
    competitor: str = Field(description="目标竞品")
    frequency: MonitorFrequency = Field(default=MonitorFrequency.DAILY, description="执行频率")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="当前状态")
    last_run_at: Optional[datetime] = Field(default=None, description="上次执行时间")
    next_run_at: Optional[datetime] = Field(default=None, description="下次执行时间")
    last_result_summary: str = Field(default="", description="上次执行结果摘要")
    error_count: int = Field(default=0, ge=0, description="累计失败次数")
    enabled: bool = Field(default=True, description="是否启用")


class ActionType(str, Enum):
    NOTIFY = "notify"
    DEEP_DIVE = "deep_dive"
    UPDATE_BATTLECARD = "update_battlecard"
    ALERT_TEAM = "alert_team"
    SCHEDULE_REVIEW = "schedule_review"


class OntologyResponseAction(BaseSchema):
    """响应动作本体 — 基于分析结果的行动建议"""
    title: str = Field(description="动作标题", min_length=1)
    trigger_event: str = Field(description="触发该动作的事件或条件")
    action_type: ActionType = Field(description="动作类型")
    description: str = Field(description="动作详细描述")
    assignee: str = Field(default="", description="建议执行人/团队")
    urgency: SeverityLevel = Field(default=SeverityLevel.MEDIUM, description="紧急程度")
    due_by: Optional[datetime] = Field(default=None, description="建议完成时间")
    status: str = Field(default="pending", description="执行状态: pending/in_progress/completed")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════
# 多模态扩展实体层
# ═══════════════════════════════════════════════════════

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    SCREENSHOT = "screenshot"
    INFOGRAPHIC = "infographic"


class OntologyMultimodalAsset(BaseSchema):
    """多模态素材本体 — 所有图片/视频/音频/截图统一建模"""
    asset_id: str = Field(description="素材唯一ID")
    competitor: str = Field(description="关联竞品名称")
    media_type: MediaType = Field(description="媒体类型")
    local_path: str = Field(default="", description="本地存储路径")
    source_url: str = Field(default="", description="原始来源URL")
    source_platform: str = Field(default="", description="来源平台: weibo/bilibili/36kr/...")
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    ocr_text: str = Field(default="", description="OCR提取纯文本")
    ocr_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    vision_summary: str = Field(default="", description="视觉内容摘要（豆包多模态输出）")
    vision_style_tags: list[str] = Field(default_factory=list, description="视觉风格标签")
    main_colors: list[str] = Field(default_factory=list, description="主色调列表")
    brand_logo_detected: bool = Field(default=False, description="是否检测到品牌Logo")
    key_selling_points: list[str] = Field(default_factory=list, description="提取出的核心卖点")
    price_info_extracted: str = Field(default="", description="从海报提取到的定价信息")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class OntologyScreenshotDiff(BaseSchema):
    """截图差异本体 — UI改版像素级对比结果"""
    diff_id: str = Field(description="差异唯一ID")
    competitor: str = Field(description="关联竞品名称")
    page_url: str = Field(description="对比的页面URL")
    old_screenshot_path: str = Field(default="", description="历史截图路径")
    new_screenshot_path: str = Field(default="", description="最新截图路径")
    diff_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="差异百分比")
    diff_image_path: str = Field(default="", description="高亮差异图存储路径")
    change_type: str = Field(default="unknown", description="变化类型: ui_redesign / new_banner / price_change / ...")
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    impact_assessment: str = Field(default="", description="对我方的影响评估")


class OntologyVideoTranscript(BaseSchema):
    """视频转录本体 — 视频关键帧+音频转录结果"""
    video_id: str = Field(description="视频唯一ID")
    competitor: str = Field(description="关联竞品名称")
    title: str = Field(default="", description="视频标题")
    source_url: str = Field(default="", description="视频源URL")
    total_duration_seconds: int = Field(default=0, ge=0)
    key_frames: list[str] = Field(default_factory=list, description="关键帧图片本地路径列表")
    full_transcript_text: str = Field(default="", description="音频完整转录文本")
    transcript_segments: list[dict] = Field(default_factory=list, description="带时间戳的分段转录 [{start, end, text}]")
    key_moments: list[str] = Field(default_factory=list, description="识别出的关键时间点事件")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
