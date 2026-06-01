"""Compare Agent – multi-dimensional competitor comparison matrix.

评分基于我方产品真实信息 + 竞品研究洞察，禁止凭空估计。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..services.llm import LLMFactory
from ..models.schemas import ComparisonMatrix, DimensionScore

logger = logging.getLogger(__name__)

# ── 03 方案模块接入（可选依赖，缺失时自动跳过增强） ──
try:
    from ..services.weight_fusion_engine import (
        FusionEngine, DynamicWeightEngine,
        Evidence, DataSource, DataTier, AHPCalculator
    )
    _WEIGHT_FUSION_AVAILABLE = True
except ImportError as _e:
    _WEIGHT_FUSION_AVAILABLE = False
    logger.debug("weight_fusion_engine 未就绪: %s", _e)

try:
    from ..services.competitive_intelligence_framework import (
        ReputationAssessmentFramework,
        DataAccessibilityMatrix,
        SurrogateMetricsEngine,
    )
    _CI_FRAMEWORK_AVAILABLE = True
except ImportError as _e:
    _CI_FRAMEWORK_AVAILABLE = False
    logger.debug("competitive_intelligence_framework 未就绪: %s", _e)

SYSTEM_PROMPT = """\
You are a Competitive Intelligence Comparison Agent.
Given OUR PRODUCT's real information and RESEARCH INSIGHTS about a competitor,
produce a structured comparison matrix scoring BOTH products across these
dimensions (each scored 0-10):

  1. Product Features
  2. Pricing & Value
  3. User Experience / UX
  4. Market Share & Momentum
  5. Customer Sentiment / Reviews
  6. Technology & Innovation
  7. Ecosystem & Integrations
  8. Support & Documentation

CRITICAL RULES:
- our_score MUST be based on the provided OUR PRODUCT INFO, not guessed.
- competitor_score MUST be based on the provided RESEARCH INSIGHTS.
- If a dimension lacks data, score 5.0 (neutral) and note in "notes" that data is insufficient.
- notes field should be specific, comparing our real data vs competitor data.

Return a JSON object with keys:
  dimensions: [{dimension, our_score, competitor_score, notes}],
  overall_assessment: <string>.
"""

DIMENSIONS = [
    "Product Features",
    "Pricing & Value",
    "User Experience",
    "Market Share & Momentum",
    "Customer Sentiment",
    "Technology & Innovation",
    "Ecosystem & Integrations",
    "Support & Documentation",
]


def _format_product_info(info: dict) -> str:
    """将我方产品 dict 格式化为 LLM 可读的结构化文本。"""
    if not info:
        return "⚠️ OUR PRODUCT INFO NOT CONFIGURED. Use neutral scores (5.0) for all our_score and note this clearly."

    name = info.get("name", "My Product")
    features = info.get("core_features", [])
    pricing = info.get("pricing_model", "N/A")
    tech = info.get("tech_stack", [])
    market = info.get("target_market", "N/A")
    advantages = info.get("competitive_advantages", [])
    weaknesses = info.get("weaknesses", [])

    parts = [f"Product Name: {name}"]

    if features:
        parts.append("Core Features:\n  - " + "\n  - ".join(features))
    else:
        parts.append("Core Features: (not specified)")

    parts.append(f"Pricing Model: {pricing}")

    if tech:
        parts.append("Tech Stack:\n  - " + "\n  - ".join(tech))
    else:
        parts.append("Tech Stack: (not specified)")

    parts.append(f"Target Market: {market if market else '(not specified)'}")

    if advantages:
        parts.append("Competitive Advantages:\n  - " + "\n  - ".join(advantages))
    else:
        parts.append("Competitive Advantages: (not specified)")

    if weaknesses:
        parts.append("Known Weaknesses:\n  - " + "\n  - ".join(weaknesses))
    else:
        parts.append("Known Weaknesses: (not specified)")

    return "\n".join(parts)


class CompareAgent:

    def _get_llm(self):
        """统一 LLM 工厂 — 支持豆包/通义千问动态切换"""
        return LLMFactory.get_llm("compare")

    # ------------------------------------------------------------------
    # 03 方案数据增强 — 多源融合 + 情感分析 + 冲突检测
    # ------------------------------------------------------------------

    async def _enrich_research_data(
        self,
        research_results: list[dict],
        competitor: str,
    ) -> str:
        """使用 weight_fusion_engine + competitive_intelligence_framework
        对研究数据进行增强，返回供 LLM 参考的文本片段。
        所有步骤失败安全（try-except），不影响主流程。"""
        parts: list[str] = []

        # 1. 口碑情感分析（ReputationAssessmentFramework）
        if _CI_FRAMEWORK_AVAILABLE:
            try:
                reviews = []
                for r in research_results:
                    topic = (r.get("topic") or "").lower()
                    if any(k in topic for k in ("sentiment", "review", "口碑", "用户反馈", "评价", "customer")):
                        text = r.get("summary", "")
                        if text:
                            reviews.append({
                                "text": text,
                                "platform": "research",
                                "rating": min(max((r.get("confidence", 0.5) * 5), 1), 5),
                            })
                if reviews:
                    rep = ReputationAssessmentFramework(use_transformers=False)
                    sentiment = rep.analyze_batch_reviews(reviews)
                    pos = sentiment.get("positive_ratio", 0)
                    neg = sentiment.get("negative_ratio", 0)
                    nps = sentiment.get("nps_estimate", "N/A")
                    parts.append(
                        f"=== 用户口碑情感分析（基于 {sentiment.get('sample_size', 0)} 条研究洞察）===\n"
                        f"正面比例: {pos*100:.1f}% | 负面比例: {neg*100:.1f}% | "
                        f"NPS估算: {nps}\n"
                        f"口碑指数: {sentiment.get('reputation_index', 'N/A')}\n"
                    )
            except Exception as e:
                logger.debug("情感分析增强跳过: %s", e)

            # 2. 数据可达性评估（DataAccessibilityMatrix）
            try:
                matrix = DataAccessibilityMatrix()
                summary = matrix.summary()
                parts.append(
                    f"=== 数据可达性评估 ===\n"
                    f"A类(直接获取): {summary.get('A', 0)} 项 | "
                    f"B类(间接推断): {summary.get('B', 0)} 项 | "
                    f"C类(模型预测): {summary.get('C', 0)} 项 | "
                    f"D类(推测性): {summary.get('D', 0)} 项\n"
                )
            except Exception as e:
                logger.debug("数据可达性评估跳过: %s", e)

        # 3. 多源冲突检测（weight_fusion_engine 简化版）
        if _WEIGHT_FUSION_AVAILABLE:
            try:
                topic_groups: dict[str, list[dict]] = {}
                for r in research_results:
                    topic = r.get("topic", "unknown")
                    topic_groups.setdefault(topic, []).append(r)

                conflicts: list[str] = []
                for topic, items in topic_groups.items():
                    if len(items) >= 2:
                        confs = [i.get("confidence", 0.5) for i in items]
                        if max(confs) - min(confs) > 0.3:
                            conflicts.append(
                                f"  - {topic}: 来源间置信度差异 {min(confs):.2f} ~ {max(confs):.2f}"
                            )
                if conflicts:
                    parts.append(
                        "=== 多源信息冲突提示 ===\n"
                        "以下维度存在来源间显著差异，评分时请降低置信度:\n"
                        + "\n".join(conflicts) + "\n"
                    )
            except Exception as e:
                logger.debug("冲突检测增强跳过: %s", e)

        return "\n".join(parts) if parts else ""

    async def compare(
        self,
        competitor: str,
        research_results: list[dict],
        our_product_info: Optional[dict] = None,
        fact_check_result: Optional[dict] = None,
    ) -> ComparisonMatrix:
        # ★ 03 方案数据增强
        enrichment_text = await self._enrich_research_data(research_results, competitor)

        our_info_text = _format_product_info(our_product_info or {})
        research_text = json.dumps(
            [r.model_dump() if hasattr(r, 'model_dump') else r for r in research_results],
            ensure_ascii=False, indent=2,
        )

        # ★ L3 方法论检索：评分锚定标准 + 对比维度定义
        rag_docs = []
        try:
            from ..services.rag.core import rag
            l3_docs = rag.retriever.search(
                f"电商 8维度评分 标准 锚定 {competitor}",
                k=3, filters={"doc_type": "methodology"},
            )
            if l3_docs:
                rag_docs.extend(l3_docs)
                logger.debug("L3 methodology docs retrieved: %d", len(l3_docs))
        except Exception as e:
            logger.debug("L3 RAG 检索跳过: %s", e)

        # 注入交叉验证结果
        fc_note = ""
        if fact_check_result:
            inconsistencies = fact_check_result.get("inconsistencies", [])
            confidence = fact_check_result.get("confidence_adjustments", {})
            if inconsistencies:
                fc_note = (
                    "\n\n=== FACT CHECK WARNING ===\n"
                    "The following claims were flagged as inconsistent or unverified. "
                    "Reduce confidence in competitor_score for dimensions relying on these claims:\n"
                    f"{json.dumps(inconsistencies[:5], ensure_ascii=False)}\n"
                )
            if confidence.get("verification_rate", 1.0) < 0.5:
                fc_note += (
                    f"\nOverall verification rate is only {confidence.get('verification_rate', 0)*100:.0f}%. "
                    "Please clearly note this in the overall_assessment."
                )

        # 组装增强上下文
        enrichment_block = f"\n\n=== DATA ENRICHMENT (03方案多源融合分析) ===\n{enrichment_text}\n" if enrichment_text else ""

        user_msg = (
            f"=== OUR PRODUCT INFO (use this for our_score) ===\n"
            f"{our_info_text}\n\n"
            f"=== COMPETITOR: {competitor} ===\n\n"
            f"=== RESEARCH INSIGHTS (use this for competitor_score) ===\n"
            f"{research_text}"
            f"{fc_note}"
            f"{enrichment_block}\n\n"
            "Generate a comparison matrix as JSON. Base our_score on the OUR PRODUCT INFO above. "
            "Base competitor_score on the RESEARCH INSIGHTS above. "
            "If DATA ENRICHMENT indicates conflicts or low confidence for a dimension, "
            "reflect this by lowering the competitor_score and noting the uncertainty."
        )
        # 注入 L3 方法论知识
        from ..services.rag.rag_agent import RAGEnhancedAgent
        user_msg = RAGEnhancedAgent.augment_prompt(user_msg, rag_docs, max_docs=2)

        response = await self._get_llm().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])

        return self._parse_matrix(response.content, competitor)

    # ------------------------------------------------------------------
    # LangGraph node
    # ------------------------------------------------------------------

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        competitor = state["competitor"]
        research = state.get("research_results", [])
        our_info = state.get("our_product_info", {})
        fact_check = state.get("fact_check_result", {})

        matrix = await self.compare(competitor, research, our_info, fact_check)
        return {
            "comparison_matrix": matrix.model_dump(),
        }

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _default_matrix(competitor: str) -> ComparisonMatrix:
        """LLM 返回异常时的默认兜底矩阵"""
        return ComparisonMatrix(
            competitor=competitor,
            dimensions=[
                DimensionScore(dimension=d, our_score=5.0, competitor_score=5.0, notes="LLM 响应异常，使用默认评分")
                for d in DIMENSIONS
            ],
            overall_assessment="无法解析 LLM 返回的对比矩阵，已使用默认值。",
        )

    @staticmethod
    def _parse_matrix(llm_output: str, competitor: str) -> ComparisonMatrix:
        try:
            text = llm_output.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Could not parse comparison matrix (invalid JSON)")
            return CompareAgent._default_matrix(competitor)

        # 容错：LLM 返回数组而非对象时回退到默认矩阵
        if not isinstance(data, dict):
            logger.warning("Comparison matrix: expected dict, got %s", type(data).__name__)
            return CompareAgent._default_matrix(competitor)

        try:
            dims = []
            for d in data.get("dimensions", []):
                dims.append(
                    DimensionScore(
                        dimension=d.get("dimension", "Unknown"),
                        our_score=float(d.get("our_score", 5.0)),
                        competitor_score=float(d.get("competitor_score", 5.0)),
                        notes=d.get("notes", ""),
                    )
                )
            return ComparisonMatrix(
                competitor=competitor,
                dimensions=dims,
                overall_assessment=data.get("overall_assessment", ""),
            )
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning("Failed to parse comparison matrix dimensions: %s", e)
            return CompareAgent._default_matrix(competitor)


# ═══════════════════════════════════════════════════════════
# 多模态融合引擎 — 60%文本 + 40%视觉加权评分
# ═══════════════════════════════════════════════════════════

class MultimodalFusionEngine:
    """多模态融合引擎：文本评分 60% + 视觉评分 40% 加权融合。

    所有步骤 try-except 保护，无多模态素材时自动回退纯文本模式。
    """

    TEXT_WEIGHT = 0.6
    VISUAL_WEIGHT = 0.4

    def __init__(self):
        self._multimodal_available = False
        try:
            from ..services.multimodal.doubao_vl_service import analyze_competitor_poster
            from ..services.multimodal.ocr_service import extract_text_from_image
            self._analyze_poster = analyze_competitor_poster
            self._ocr_extract = extract_text_from_image
            self._multimodal_available = True
        except ImportError:
            logger.debug("多模态服务未就绪，融合引擎工作于纯文本模式")

    @property
    def is_available(self) -> bool:
        return self._multimodal_available

    async def enrich_dimension(
        self,
        dimension_name: str,
        text_score: float,
        multimodal_assets: Optional[list[dict]] = None,
    ) -> dict:
        """对单个对比维度做多模态增强评分。

        Args:
            dimension_name: 维度名称（如 "Product Features"）
            text_score: LLM 文本分析给出的原始评分 (0-10)
            multimodal_assets: 多模态素材列表 [{"path": ..., "type": ...}]

        Returns:
            {"fused_score": float, "visual_score": float, "visual_evidence": str}
        """
        if not self._multimodal_available or not multimodal_assets:
            return {"fused_score": text_score, "visual_score": text_score, "visual_evidence": ""}

        visual_scores: list[float] = []
        evidence_parts: list[str] = []

        for asset in multimodal_assets:
            path = asset.get("path", "")
            asset_type = asset.get("type", "")

            try:
                if asset_type in ("poster", "screenshot"):
                    poster_result = await self._analyze_poster(path)
                    if poster_result.get("parse_success") is not False:
                        selling_points = poster_result.get("core_selling_points", [])
                        pricing = poster_result.get("pricing_info", "")
                        if selling_points:
                            evidence_parts.append(f"视觉卖点: {'; '.join(selling_points[:3])}")
                        if pricing:
                            evidence_parts.append(f"视觉定价: {pricing}")
                        # 卖点数量映射到评分 (1-5个卖点 → 6-9分)
                        v_score = min(9.0, 6.0 + len(selling_points) * 0.6)
                        visual_scores.append(v_score)

                if asset_type in ("ocr",):
                    ocr_result = await self._ocr_extract(path)
                    if ocr_result.get("ok"):
                        ocr_text = ocr_result.get("text", "")
                        ocr_conf = ocr_result.get("confidence", 0)
                        if ocr_text:
                            evidence_parts.append(f"OCR提取: {ocr_text[:150]}")
                        # 置信度映射到评分
                        v_score = 5.0 + ocr_conf * 4.0
                        visual_scores.append(min(9.0, v_score))
            except Exception as e:
                logger.debug("多模态增强跳过维度 %s: %s", dimension_name, e)

        if not visual_scores:
            return {"fused_score": text_score, "visual_score": text_score, "visual_evidence": ""}

        avg_visual = sum(visual_scores) / len(visual_scores)
        fused = self.TEXT_WEIGHT * text_score + self.VISUAL_WEIGHT * avg_visual
        evidence = "; ".join(evidence_parts[:3])

        return {
            "fused_score": round(min(10.0, fused), 1),
            "visual_score": round(avg_visual, 1),
            "visual_evidence": evidence[:500],
        }

    async def enrich_comparison_matrix(
        self,
        text_matrix: dict,
        multimodal_context: dict[str, list[dict]] | None = None,
    ) -> dict:
        """对完整 8 维度对比矩阵做多模态增强。

        multimodal_context: {dimension_name: [multimodal_assets]}
        """
        if not self._multimodal_available or not multimodal_context:
            return text_matrix

        enriched_dims = []
        for dim in text_matrix.get("dimensions", []):
            dim_name = dim.get("dimension", "")
            assets = multimodal_context.get(dim_name, [])
            if assets:
                enrichment = await self.enrich_dimension(
                    dim_name,
                    float(dim.get("competitor_score", 5.0)),
                    assets,
                )
                enriched_dims.append({
                    **dim,
                    "competitor_score": enrichment["fused_score"],
                    "notes": (
                        str(dim.get("notes", ""))
                        + (f" | 视觉增强: {enrichment['visual_evidence']}"
                           if enrichment["visual_evidence"] else "")
                    ),
                })
            else:
                enriched_dims.append(dim)

        return {**text_matrix, "dimensions": enriched_dims}


# 全局单例
fusion_engine = MultimodalFusionEngine()
