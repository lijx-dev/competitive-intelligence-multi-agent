"""
Palantir Ontology 关系图谱 — 20+ 种关系类型 + D3 图数据结构。

五层对象之间的语义关系边，供前端 React D3/AntV X6 可视化渲染。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════
# 关系类型枚举（20+ 种）
# ═══════════════════════════════════════════════════════

class RelationType(str, Enum):
    # ── L1 内部关系 ──
    COMPETITOR_HAS_BRAND = "competitor_has_brand"             # 竞品 → 品牌
    COMPETITOR_HAS_PRODUCT = "competitor_has_product"         # 竞品 → 产品
    BRAND_OWNS_PRODUCT = "brand_owns_product"                 # 品牌 → 产品
    COMPETITOR_COMPETES_WITH = "competitor_competes_with"     # 竞品 ←→ 竞品

    # ── L1 → L2 ──
    PRODUCT_HAS_FEATURE = "product_has_feature"               # 产品 → 功能
    PRODUCT_HAS_ARCHITECTURE = "product_has_architecture"     # 产品 → 架构
    PRODUCT_HAS_PRICING = "product_has_pricing"               # 产品 → 定价

    # ── L2 内部 ──
    FEATURE_DEPENDS_ON = "feature_depends_on"                 # 功能 → 功能（依赖）
    FEATURE_COMPETES_WITH = "feature_competes_with"           # 功能 → 功能（竞争）
    PRICING_COMPARED_TO = "pricing_compared_to"               # 定价 → 定价（对比）

    # ── L1 → L3 ──
    COMPETITOR_HAS_EVENT = "competitor_has_event"             # 竞品 → 市场事件
    PRODUCT_RECEIVES_FEEDBACK = "product_receives_feedback"   # 产品 → 用户反馈
    COMPETITOR_HAS_SENTIMENT = "competitor_has_sentiment"     # 竞品 → 情感信号

    # ── L3 → L4 ──
    EVENT_TRIGGERS_INSIGHT = "event_triggers_insight"         # 市场事件 → 洞察
    FEEDBACK_INFORMS_SCORECARD = "feedback_informs_scorecard" # 用户反馈 → 评分卡
    SENTIMENT_INFORMS_REPORT = "sentiment_informs_report"     # 情感信号 → 报告

    # ── L4 内部 ──
    REPORT_CONTAINS_SCORECARD = "report_contains_scorecard"   # 报告 → 评分卡
    SCORECARD_DERIVES_INSIGHT = "scorecard_derives_insight"   # 评分卡 → 洞察
    INSIGHT_RELATES_TO = "insight_relates_to"                 # 洞察 ←→ 洞察

    # ── L4 → L5 ──
    INSIGHT_TRIGGERS_ACTION = "insight_triggers_action"       # 洞察 → 响应动作
    REPORT_TRIGGERS_ALERT = "report_triggers_alert"           # 报告 → 告警规则
    EVENT_TRIGGERS_TASK = "event_triggers_task"               # 市场事件 → 监控任务

    # ── L5 内部 ──
    TASK_MONITORS_COMPETITOR = "task_monitors_competitor"     # 监控任务 → 竞品
    ALERT_NOTIFIES_CHANNEL = "alert_notifies_channel"         # 告警规则 → 渠道


# ═══════════════════════════════════════════════════════
# 关系边 / 图节点数据结构
# ═══════════════════════════════════════════════════════

class OntologyNode(BaseModel):
    """图谱节点 — D3/AntV X6 可视化单元"""
    id: str = Field(description="节点唯一标识")
    label: str = Field(description="节点显示名称")
    layer: str = Field(description="所属层级: L1/L2/L3/L4/L5")
    entity_type: str = Field(description="实体类型: Competitor/Product/Feature/Insight 等")
    properties: dict[str, Any] = Field(default_factory=dict, description="节点属性（供前端 tooltip）")
    x: float = Field(default=0, description="布局 X 坐标（前端计算）")
    y: float = Field(default=0, description="布局 Y 坐标（前端计算）")
    color: str = Field(default="#3B82F6", description="节点颜色")
    size: int = Field(default=20, ge=5, description="节点半径")


class OntologyRelation(BaseModel):
    """图谱关系边 — D3/AntV X6 可视化连线"""
    id: str = Field(description="关系边唯一标识")
    source: str = Field(description="源节点 ID")
    target: str = Field(description="目标节点 ID")
    relation_type: RelationType = Field(description="关系类型")
    label: str = Field(default="", description="边标签")
    weight: float = Field(default=1.0, ge=0.0, description="关系权重（影响连线粗细）")
    bidirectional: bool = Field(default=False, description="是否双向关系")
    properties: dict[str, Any] = Field(default_factory=dict, description="边属性（供前端 tooltip）")


class OntologyGraph(BaseModel):
    """完整 Ontology 图谱 — 供前端一次加载渲染"""
    nodes: list[OntologyNode] = Field(default_factory=list)
    relations: list[OntologyRelation] = Field(default_factory=list)
    generated_at: str = Field(default="")
    stats: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def empty(cls) -> OntologyGraph:
        return cls(nodes=[], relations=[], generated_at="", stats={})


# ═══════════════════════════════════════════════════════
# 图层级颜色映射（前端 React 使用）
# ═══════════════════════════════════════════════════════

LAYER_COLORS: dict[str, str] = {
    "L1": "#3B82F6",  # Blue — 核心实体
    "L2": "#10B981",  # Green — 功能维度
    "L3": "#F59E0B",  # Amber — 市场情报
    "L4": "#8B5CF6",  # Purple — 分析产出
    "L5": "#EF4444",  # Red — 执行动作
}

ENTITY_TYPE_COLORS: dict[str, str] = {
    "Competitor": LAYER_COLORS["L1"],
    "Product": LAYER_COLORS["L1"],
    "Brand": LAYER_COLORS["L1"],
    "Feature": LAYER_COLORS["L2"],
    "Architecture": LAYER_COLORS["L2"],
    "Pricing": LAYER_COLORS["L2"],
    "MarketEvent": LAYER_COLORS["L3"],
    "UserFeedback": LAYER_COLORS["L3"],
    "SentimentSignal": LAYER_COLORS["L3"],
    "ComparisonReport": LAYER_COLORS["L4"],
    "ScoreCard": LAYER_COLORS["L4"],
    "Insight": LAYER_COLORS["L4"],
    "AlertRule": LAYER_COLORS["L5"],
    "MonitorTask": LAYER_COLORS["L5"],
    "ResponseAction": LAYER_COLORS["L5"],
}


def build_demo_graph(competitor_name: str = "快手电商") -> OntologyGraph:
    """生成 Demo 图谱 — 用于前端开发调试和答辩展示。"""
    nodes: list[OntologyNode] = [
        # L1
        OntologyNode(id="comp_1", label=competitor_name, layer="L1", entity_type="Competitor",
                     color=LAYER_COLORS["L1"], size=28),
        OntologyNode(id="prod_1", label=f"{competitor_name} App", layer="L1", entity_type="Product",
                     color=LAYER_COLORS["L1"], size=20),
        OntologyNode(id="brand_1", label=f"{competitor_name} 品牌", layer="L1", entity_type="Brand",
                     color=LAYER_COLORS["L1"], size=18),
        # L2
        OntologyNode(id="feat_1", label="直播带货", layer="L2", entity_type="Feature",
                     color=LAYER_COLORS["L2"], size=16),
        OntologyNode(id="arch_1", label="推荐算法架构", layer="L2", entity_type="Architecture",
                     color=LAYER_COLORS["L2"], size=16),
        OntologyNode(id="price_1", label="佣金定价", layer="L2", entity_type="Pricing",
                     color=LAYER_COLORS["L2"], size=16),
        # L3
        OntologyNode(id="evt_1", label="GMV突破1.2万亿", layer="L3", entity_type="MarketEvent",
                     color=LAYER_COLORS["L3"], size=16),
        OntologyNode(id="sent_1", label="用户口碑趋势", layer="L3", entity_type="SentimentSignal",
                     color=LAYER_COLORS["L3"], size=14),
        # L4
        OntologyNode(id="rpt_1", label="竞品对比报告", layer="L4", entity_type="ComparisonReport",
                     color=LAYER_COLORS["L4"], size=20),
        OntologyNode(id="ins_1", label="流量增长放缓", layer="L4", entity_type="Insight",
                     color=LAYER_COLORS["L4"], size=14),
        # L5
        OntologyNode(id="alert_1", label="重大变更告警", layer="L5", entity_type="AlertRule",
                     color=LAYER_COLORS["L5"], size=16),
        OntologyNode(id="task_1", label="每日监控任务", layer="L5", entity_type="MonitorTask",
                     color=LAYER_COLORS["L5"], size=14),
    ]

    relations: list[OntologyRelation] = [
        OntologyRelation(id="r1", source="comp_1", target="brand_1", relation_type=RelationType.COMPETITOR_HAS_BRAND, weight=1.0),
        OntologyRelation(id="r2", source="comp_1", target="prod_1", relation_type=RelationType.COMPETITOR_HAS_PRODUCT, weight=1.0),
        OntologyRelation(id="r3", source="prod_1", target="feat_1", relation_type=RelationType.PRODUCT_HAS_FEATURE, weight=1.0),
        OntologyRelation(id="r4", source="prod_1", target="arch_1", relation_type=RelationType.PRODUCT_HAS_ARCHITECTURE, weight=0.8),
        OntologyRelation(id="r5", source="prod_1", target="price_1", relation_type=RelationType.PRODUCT_HAS_PRICING, weight=0.9),
        OntologyRelation(id="r6", source="comp_1", target="evt_1", relation_type=RelationType.COMPETITOR_HAS_EVENT, weight=1.0),
        OntologyRelation(id="r7", source="comp_1", target="sent_1", relation_type=RelationType.COMPETITOR_HAS_SENTIMENT, weight=0.7),
        OntologyRelation(id="r8", source="evt_1", target="ins_1", relation_type=RelationType.EVENT_TRIGGERS_INSIGHT, weight=0.8),
        OntologyRelation(id="r9", source="rpt_1", target="ins_1", relation_type=RelationType.REPORT_CONTAINS_SCORECARD, weight=1.0),
        OntologyRelation(id="r10", source="ins_1", target="alert_1", relation_type=RelationType.INSIGHT_TRIGGERS_ACTION, weight=0.9),
        OntologyRelation(id="r11", source="task_1", target="comp_1", relation_type=RelationType.TASK_MONITORS_COMPETITOR, weight=1.0),
    ]

    return OntologyGraph(
        nodes=nodes,
        relations=relations,
        generated_at="",
        stats={"nodes": len(nodes), "relations": len(relations), "layers": 5},
    )
