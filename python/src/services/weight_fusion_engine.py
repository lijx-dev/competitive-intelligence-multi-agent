
"""
============================================================
多平台数据源权重分配与融合引擎
Multi-Source Data Weighting & Fusion Engine
============================================================
用于AI驱动的竞品分析Agent协作系统
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json

# ============================================================
# 核心数据模型
# ============================================================

class ConflictStrategy(Enum):
    """冲突处理策略枚举"""
    AUTHORITY_WINS = "authority_wins"    # 权威优先
    MAJORITY_VOTE = "majority_vote"      # 多数投票
    RECENCY_WINS = "recency_wins"        # 时效优先
    WEIGHTED_AVG = "weighted_average"    # 加权平均
    MARK_SUSPICIOUS = "mark_suspicious"  # 标记存疑


class DataTier(Enum):
    """数据源梯队枚举"""
    TIER1_OFFICIAL = "第一梯队(官方)"       # 权重最高
    TIER2_MEDIA = "第二梯队(行业媒体)"      # 权重次高
    TIER3_SOCIAL = "第三梯队(社交社区)"     # 权重中等
    TIER4_UGC = "第四梯队(UGC评论)"        # 权重较低


@dataclass
class DataSource:
    """数据源定义"""
    name: str                           # 来源名称
    tier: DataTier                      # 所属梯队
    base_weight: float                  # 基础权重
    quality_score: float = 0.5          # 质量评分 [0,1]
    credibility_history: float = 1.0    # 历史可信度
    lambda_decay: float = 0.1           # 时效衰减系数


@dataclass
class Evidence:
    """证据（单条信息）"""
    source: DataSource                  # 来源
    dimension: str                      # 所属维度
    value: float                        # 提取的值
    timestamp: datetime                 # 采集时间
    raw_text: str = ""                  # 原始文本
    confidence: float = 1.0             # 初始置信度


@dataclass
class DimensionConfig:
    """分析维度配置"""
    name: str                           # 维度名称
    weight: float                       # AHP权重
    tier_applicability: Dict[DataTier, float]  # 各梯队适用性


# ============================================================
# AHP权重计算器
# ============================================================

class AHPCalculator:
    """层次分析法权重计算器"""

    RI_TABLE = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 
                6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}

    @staticmethod
    def build_comparison_matrix(comparisons: List[Tuple[int, int, float]]) -> np.ndarray:
        """
        根据成对比较构建判断矩阵
        comparisons: [(i, j, value), ...] 表示第i个元素相对于第j个元素的重要性比值
        """
        n = max(max(i, j) for i, j, _ in comparisons)
        A = np.eye(n)
        for i, j, v in comparisons:
            A[i-1, j-1] = v
            A[j-1, i-1] = 1.0 / v
        return A

    @staticmethod
    def calculate_weights(matrix: np.ndarray) -> Tuple[np.ndarray, float, float, bool]:
        """
        计算权重向量
        Returns: (weights, lambda_max, CR, is_consistent)
        """
        n = matrix.shape[0]
        eigenvalues, eigenvectors = np.linalg.eig(matrix)
        max_idx = np.argmax(eigenvalues.real)
        lambda_max = eigenvalues[max_idx].real
        w = eigenvectors[:, max_idx].real
        w = w / w.sum()

        CI = (lambda_max - n) / (n - 1)
        RI = AHPCalculator.RI_TABLE.get(n, 1.49)
        CR = CI / RI if RI > 0 else 0

        return w, lambda_max, CR, CR < 0.1

    @staticmethod
    def consistency_check(matrix: np.ndarray) -> Dict[str, float]:
        """一致性检验"""
        n = matrix.shape[0]
        _, lambda_max, CR, passed = AHPCalculator.calculate_weights(matrix)
        CI = (lambda_max - n) / (n - 1)
        return {
            "lambda_max": lambda_max,
            "CI": CI,
            "RI": AHPCalculator.RI_TABLE.get(n),
            "CR": CR,
            "passed": passed
        }


# ============================================================
# 动态权重调整引擎
# ============================================================

class DynamicWeightEngine:
    """动态权重调整引擎"""

    # 行业适配因子
    INDUSTRY_FACTORS = {
        "SaaS/企业软件": {
            "功能": 1.3, "定价": 1.2, "市场": 1.0, "团队": 0.9,
            "技术": 1.3, "用户口碑": 1.1, "战略": 1.0, "风险": 1.0
        },
        "电商/零售": {
            "功能": 1.1, "定价": 1.4, "市场": 1.3, "团队": 0.7,
            "技术": 0.9, "用户口碑": 1.2, "战略": 1.1, "风险": 0.9
        },
        "社交/内容": {
            "功能": 1.2, "定价": 0.8, "市场": 1.3, "团队": 1.0,
            "技术": 1.1, "用户口碑": 1.4, "战略": 1.2, "风险": 1.1
        },
        "金融科技": {
            "功能": 1.1, "定价": 1.1, "市场": 0.9, "团队": 1.2,
            "技术": 1.3, "用户口碑": 0.9, "战略": 1.0, "风险": 1.5
        },
        "教育": {
            "功能": 1.2, "定价": 1.3, "市场": 1.0, "团队": 0.8,
            "技术": 1.0, "用户口碑": 1.4, "战略": 1.1, "风险": 0.7
        },
    }

    # 时效衰减系数
    LAMBDA_VALUES = {
        DataTier.TIER1_OFFICIAL: 0.02,
        DataTier.TIER2_MEDIA: 0.10,
        DataTier.TIER3_SOCIAL: 0.25,
        DataTier.TIER4_UGC: 0.20
    }

    @staticmethod
    def time_factor(days_ago: float, tier: DataTier) -> float:
        """计算时效性衰减因子 T(t) = exp(-λ × Δt)"""
        lam = DynamicWeightEngine.LAMBDA_VALUES.get(tier, 0.1)
        return np.exp(-lam * days_ago)

    @staticmethod
    def industry_factor(dimension: str, industry: str = "通用") -> float:
        """获取行业适配因子"""
        factors = DynamicWeightEngine.INDUSTRY_FACTORS.get(industry, {})
        return factors.get(dimension, 1.0)

    @staticmethod
    def quality_factor(source: DataSource) -> float:
        """计算综合质量因子"""
        return source.quality_score * source.credibility_history

    @classmethod
    def compute_final_weight(
        cls,
        source: DataSource,
        dimension: str,
        dimension_weight: float,
        days_ago: float,
        industry: str = "通用"
    ) -> float:
        """
        计算最终动态权重
        W_final = W_base × W_dim × T(t) × Q(s) × I(industry)
        """
        base_w = source.base_weight
        dim_w = dimension_weight
        time_f = cls.time_factor(days_ago, source.tier)
        quality_f = cls.quality_factor(source)
        ind_f = cls.industry_factor(dimension, industry)

        return base_w * dim_w * time_f * quality_f * ind_f


# ============================================================
# 数据融合引擎
# ============================================================

class FusionEngine:
    """多源数据融合引擎"""

    def __init__(self, weight_engine: DynamicWeightEngine):
        self.weight_engine = weight_engine
        self.conflict_threshold = 2.0

    def fuse(
        self,
        evidences: List[Evidence],
        dimension: str,
        dimension_weight: float,
        industry: str = "通用"
    ) -> Dict[str, Any]:
        """
        多源数据融合

        Returns: {
            "fused_score": float,      # 融合后评分
            "confidence": float,        # 结论置信度
            "contributions": List,      # 各来源贡献明细
            "conflicts": List           # 检测到的冲突
        }
        """
        contributions = []
        total_weight = 0
        weighted_sum = 0

        for ev in evidences:
            days_ago = (datetime.now() - ev.timestamp).days
            w = self.weight_engine.compute_final_weight(
                ev.source, dimension, dimension_weight, days_ago, industry
            )

            contributions.append({
                "source": ev.source.name,
                "value": ev.value,
                "weight": w,
                "timestamp": ev.timestamp.isoformat()
            })

            total_weight += w
            weighted_sum += w * ev.value

        fused_score = weighted_sum / total_weight if total_weight > 0 else 0

        # 计算结论置信度
        confidence = self._compute_confidence(evidences, contributions)

        # 冲突检测
        conflicts = self._detect_conflicts(evidences)

        return {
            "fused_score": round(fused_score, 4),
            "confidence": round(confidence, 4),
            "contributions": contributions,
            "conflicts": conflicts
        }

    def _compute_confidence(
        self,
        evidences: List[Evidence],
        contributions: List[Dict]
    ) -> float:
        """计算结论置信度"""
        if not evidences:
            return 0.0

        # 来源覆盖率
        source_coverage = min(len(evidences) / 4, 1.0)

        # 加权平均置信度
        total_w = sum(c["weight"] for c in contributions)
        avg_cred = sum(
            ev.source.credibility_history * c["weight"]
            for ev, c in zip(evidences, contributions)
        ) / total_w if total_w > 0 else 0

        # 信息一致性（方差倒数）
        values = [ev.value for ev in evidences]
        variance = np.var(values) if len(values) > 1 else 0
        consistency = 1 / (1 + variance)

        return 0.3 * source_coverage + 0.4 * avg_cred + 0.3 * consistency

    def _detect_conflicts(self, evidences: List[Evidence]) -> List[Dict]:
        """检测信息冲突"""
        conflicts = []
        for i in range(len(evidences)):
            for j in range(i + 1, len(evidences)):
                diff = abs(evidences[i].value - evidences[j].value)
                threshold = self.conflict_threshold

                if diff > threshold:
                    conflicts.append({
                        "source_a": evidences[i].source.name,
                        "source_b": evidences[j].source.name,
                        "value_a": evidences[i].value,
                        "value_b": evidences[j].value,
                        "diff": round(diff, 4),
                        "severity": "high" if diff > threshold * 2 else "medium"
                    })

        return conflicts

    def resolve_conflict(
        self,
        evidences: List[Evidence],
        strategy: ConflictStrategy = None
    ) -> Tuple[float, ConflictStrategy]:
        """
        冲突解决
        自动选择最优策略
        """
        if not evidences:
            return 0.0, ConflictStrategy.WEIGHTED_AVG

        # 按梯队和可信度排序
        ranked = sorted(
            evidences,
            key=lambda e: (e.source.tier.value, e.source.credibility_history),
            reverse=True
        )

        # 策略1: 权威优先
        top_tier = [e for e in ranked if e.source.tier == DataTier.TIER1_OFFICIAL]
        if len(top_tier) == 1:
            return top_tier[0].value, ConflictStrategy.AUTHORITY_WINS
        elif len(top_tier) >= 2:
            # 两个权威来源冲突 → 标记存疑但返回加权平均
            values = [e.value for e in ranked]
            weights = [e.source.credibility_history for e in ranked]
            avg = np.average(values, weights=weights)
            return avg, ConflictStrategy.MARK_SUSPICIOUS

        # 策略2: 多数投票
        values = [e.value for e in ranked]
        mean_v = np.mean(values)
        cluster = [e for e in ranked if abs(e.value - mean_v) < mean_v * 0.1]
        if len(cluster) >= len(ranked) * 0.6:
            return np.mean([e.value for e in cluster]), ConflictStrategy.MAJORITY_VOTE

        # 策略3: 时效优先
        latest = max(ranked, key=lambda e: e.timestamp)
        if (datetime.now() - latest.timestamp).days < 7:
            return latest.value, ConflictStrategy.RECENCY_WINS

        # 策略4: 加权平均
        weights = [e.source.credibility_history for e in ranked]
        avg = np.average([e.value for e in ranked], weights=weights)
        return avg, ConflictStrategy.WEIGHTED_AVG


# ============================================================
# 综合竞品评分引擎
# ============================================================

# 别名兼容旧名称（向后兼容）
DataAccessibilityMatrix = DynamicWeightEngine
ReputationAssessmentFramework = FusionEngine

class CompetitorScoringEngine:
    """竞品综合评分引擎"""

    def __init__(self):
        self.ahp = AHPCalculator()
        self.weight_engine = DynamicWeightEngine()
        self.fusion = FusionEngine(self.weight_engine)

    def score_competitor(
        self,
        competitor_name: str,
        dimension_evidences: Dict[str, List[Evidence]],
        dimension_weights: Dict[str, float],
        industry: str = "通用"
    ) -> Dict[str, Any]:
        """
        计算竞品综合评分

        dimension_evidences: {维度名: [Evidence, ...]}
        dimension_weights: {维度名: AHP权重}
        """
        dimension_scores = {}
        total_score = 0
        total_weight = 0
        all_conflicts = []

        for dim, evidences in dimension_evidences.items():
            dim_w = dimension_weights.get(dim, 0.125)

            result = self.fusion.fuse(evidences, dim, dim_w, industry)

            dimension_scores[dim] = {
                "score": result["fused_score"],
                "confidence": result["confidence"],
                "sources": len(evidences),
                "top_source": max(
                    result["contributions"],
                    key=lambda x: x["weight"],
                    default={"source": "N/A"}
                )["source"]
            }

            total_score += result["fused_score"] * dim_w
            total_weight += dim_w
            all_conflicts.extend(result["conflicts"])

        final_score = total_score / total_weight if total_weight > 0 else 0

        return {
            "competitor": competitor_name,
            "final_score": round(final_score, 4),
            "dimension_breakdown": dimension_scores,
            "conflicts": all_conflicts,
            "data_completeness": len(dimension_evidences) / len(dimension_weights),
            "reliability": self._assess_reliability(dimension_scores)
        }

    def _assess_reliability(self, dimension_scores: Dict) -> str:
        """评估结果可靠性"""
        confidences = [s["confidence"] for s in dimension_scores.values()]
        avg_conf = np.mean(confidences) if confidences else 0

        if avg_conf >= 0.8:
            return "high"
        elif avg_conf >= 0.5:
            return "medium"
        return "low"


# ============================================================
# 使用示例
# ============================================================

def demo():
    """完整使用示例"""
    engine = CompetitorScoringEngine()

    # 定义数据源
    official_web = DataSource(
        name="竞品官网", tier=DataTier.TIER1_OFFICIAL,
        base_weight=0.0942, quality_score=0.92, lambda_decay=0.02
    )
    media_36kr = DataSource(
        name="36氪", tier=DataTier.TIER2_MEDIA,
        base_weight=0.0656, quality_score=0.82, lambda_decay=0.10
    )
    zhihu = DataSource(
        name="知乎", tier=DataTier.TIER3_SOCIAL,
        base_weight=0.0196, quality_score=0.65, lambda_decay=0.25
    )

    # 构建证据
    evidences = {
        "功能": [
            Evidence(official_web, "功能", 8.5, datetime.now() - timedelta(days=5)),
            Evidence(media_36kr, "功能", 7.8, datetime.now() - timedelta(days=10)),
        ],
        "定价": [
            Evidence(official_web, "定价", 299, datetime.now() - timedelta(days=3)),
            Evidence(zhihu, "定价", 349, datetime.now() - timedelta(days=2)),
        ]
    }

    # 维度权重（来自AHP计算）
    dim_weights = {
        "功能": 0.1905, "定价": 0.1374, "市场": 0.1792, "团队": 0.0597,
        "技术": 0.1035, "用户口碑": 0.1873, "战略": 0.1035, "风险": 0.0389
    }

    # 计算竞品评分
    result = engine.score_competitor("竞品A", evidences, dim_weights, "SaaS/企业软件")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo()
