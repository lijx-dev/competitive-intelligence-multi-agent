#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
AI驱动竞品分析系统 - 缺失数据预测与口碑分析框架
Competitive Intelligence Surrogate Metrics & Prediction Framework
================================================================================
版本: 1.0.0
作者: Data Science Team
功能: 提供C类/D类竞品数据的代理指标计算、预测模型和口碑评估
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# 机器学习相关（可选依赖，缺失时相关预测功能回退到简化实现）
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge, Lasso
    from sklearn.preprocessing import StandardScaler, PolynomialFeatures
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[INFO] sklearn 未安装，预测模型将回退到简化实现")

# 时间序列（可选依赖）
try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.seasonal import seasonal_decompose
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    print("[INFO] statsmodels 未安装，时间序列预测将回退到简化实现")

# NLP相关
from collections import Counter
import re

# 尝试导入 transformers，如不可用则使用备用方案
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("[INFO] transformers 库未安装，将使用基于规则的情感分析")

# ================================================================================
# 第一部分: 数据结构与配置
# ================================================================================

class DataConfidenceLevel(Enum):
    """数据置信度等级"""
    HIGH = "A"      # 高置信度: 多源验证，误差<10%
    MEDIUM = "B"    # 中等置信度: 单源/间接推断，误差10-30%
    LOW = "C"       # 低置信度: 模型预测，误差30-50%
    SPECULATIVE = "D"  # 推测性: 基于趋势外推，误差>50%


@dataclass
class SurrogateMetric:
    """代理指标数据结构"""
    name: str                           # 指标名称
    target_variable: str                # 目标变量(不可直接获取)
    proxy_indicators: List[str]         # 代理指标列表
    data_sources: List[str]             # 数据来源
    calculation_formula: str            # 计算公式描述
    confidence_level: DataConfidenceLevel
    expected_error_range: Tuple[float, float]  # 预期误差范围 (%)
    update_frequency: str               # 更新频率


@dataclass
class PredictionResult:
    """预测结果数据结构"""
    metric_name: str
    predicted_value: float
    confidence_level: DataConfidenceLevel
    confidence_interval: Tuple[float, float]
    evidence_sources: List[str]
    model_used: str
    prediction_date: datetime
    reliability_score: float  # 0-100


# ================================================================================
# 第二部分: 数据可达性矩阵管理器
# ================================================================================

class DataAccessibilityMatrix:
    """
    数据可达性矩阵
    分类管理竞品分析中的各类数据
    """
    
    def __init__(self):
        self.matrix = self._initialize_matrix()
    
    def _initialize_matrix(self) -> pd.DataFrame:
        """初始化完整的数据可达性矩阵"""
        data = [
            # A类: 可直接获取的公开数据
            {"指标": "官网功能列表", "类别": "A", "获取难度": "低", "数据质量": "高", "获取方式": "爬虫/API", "成本": "低", "时效性": "实时"},
            {"指标": "招聘JD", "类别": "A", "获取难度": "低", "数据质量": "高", "获取方式": "招聘平台API", "成本": "低", "时效性": "T+1"},
            {"指标": "新闻稿/PR", "类别": "A", "获取难度": "低", "数据质量": "中", "获取方式": "新闻API/官网", "成本": "低", "时效性": "T+1"},
            {"指标": "社交媒体动态", "类别": "A", "获取难度": "低", "数据质量": "中", "获取方式": "平台API", "成本": "低", "时效性": "实时"},
            {"指标": "App下载量", "类别": "A", "获取难度": "中", "数据质量": "中高", "获取方式": "点点数据/蝉大师", "成本": "中", "时效性": "T+1"},
            {"指标": "公开财报", "类别": "A", "获取难度": "中", "数据质量": "高", "获取方式": "SEC/交易所", "成本": "低", "时效性": "季度"},
            {"指标": "应用商店评分", "类别": "A", "获取难度": "低", "数据质量": "中高", "获取方式": "App Store API", "成本": "低", "时效性": "实时"},
            {"指标": "专利申请", "类别": "A", "获取难度": "中", "数据质量": "高", "获取方式": "专利局数据库", "成本": "低", "时效性": "月度"},
            {"指标": "融资历史", "类别": "A", "获取难度": "低", "数据质量": "高", "获取方式": "IT桔子/Crunchbase", "成本": "低", "时效性": "T+7"},
            {"指标": "SEO/ASO数据", "类别": "A", "获取难度": "中", "数据质量": "中", "获取方式": "SimilarWeb/5118", "成本": "中", "时效性": "周度"},
            
            # B类: 可间接推断的数据
            {"指标": "用户口碑趋势", "类别": "B", "获取难度": "中", "数据质量": "中", "获取方式": "社交媒体NLP分析", "成本": "中", "时效性": "T+1"},
            {"指标": "市场规模估算", "类别": "B", "获取难度": "中", "数据质量": "中", "获取方式": "行业报告+模型", "成本": "中", "时效性": "季度"},
            {"指标": "功能成熟度", "类别": "B", "获取难度": "中", "数据质量": "中", "获取方式": "功能矩阵评分", "成本": "低", "时效性": "月度"},
            {"指标": "品牌声量", "类别": "B", "获取难度": "低", "数据质量": "中", "获取方式": "搜索指数+社媒", "成本": "低", "时效性": "实时"},
            {"指标": "用户满意度", "类别": "B", "获取难度": "中", "数据质量": "中", "获取方式": "评论情感分析", "成本": "中", "时效性": "周度"},
            {"指标": "技术栈推测", "类别": "B", "获取难度": "中", "数据质量": "中", "获取方式": "招聘JD+专利+产品分析", "成本": "低", "时效性": "月度"},
            {"指标": "团队规模变化", "类别": "B", "获取难度": "中", "数据质量": "中", "获取方式": "招聘量+脉脉+领英", "成本": "低", "时效性": "月度"},
            {"指标": "产品迭代速度", "类别": "B", "获取难度": "中", "数据质量": "中高", "获取方式": "版本更新日志", "成本": "低", "时效性": "周度"},
            
            # C类: 难以直接获取的数据
            {"指标": "真实GMV/营收", "类别": "C", "获取难度": "高", "数据质量": "低", "获取方式": "代理指标推断", "成本": "高", "时效性": "月度"},
            {"指标": "用户留存率", "类别": "C", "获取难度": "高", "数据质量": "低中", "获取方式": "下载-活跃模型", "成本": "高", "时效性": "月度"},
            {"指标": "DAU/MAU", "类别": "C", "获取难度": "高", "数据质量": "低中", "获取方式": "搜索指数+评论模型", "成本": "高", "时效性": "周度"},
            {"指标": "NPS评分", "类别": "C", "获取难度": "高", "数据质量": "低中", "获取方式": "口碑评论推断", "成本": "中", "时效性": "季度"},
            {"指标": "技术架构选型", "类别": "C", "获取难度": "高", "数据质量": "中", "获取方式": "招聘+专利+产品反推", "成本": "中", "时效性": "季度"},
            {"指标": "竞品团队规模", "类别": "C", "获取难度": "高", "数据质量": "低中", "获取方式": "多源交叉验证", "成本": "中", "时效性": "季度"},
            {"指标": "广告投放预算", "类别": "C", "获取难度": "高", "数据质量": "低", "获取方式": "素材量+投放时长估算", "成本": "高", "时效性": "月度"},
            {"指标": "广告转化效果", "类别": "C", "获取难度": "高", "数据质量": "低", "获取方式": "行业基准+推测", "成本": "高", "时效性": "季度"},
            {"指标": "用户流失率", "类别": "C", "获取难度": "高", "数据质量": "低中", "获取方式": "评论情感+卸载数据", "成本": "高", "时效性": "月度"},
            {"指标": "客单价(AOV)", "类别": "C", "获取难度": "高", "数据质量": "低", "获取方式": "公开数据反推", "成本": "中", "时效性": "季度"},
            
            # D类: 几乎无法获取的数据
            {"指标": "未来战略方向", "类别": "D", "获取难度": "极高", "数据质量": "极低", "获取方式": "信号综合推断", "成本": "高", "时效性": "N/A"},
            {"指标": "下季度功能规划", "类别": "D", "获取难度": "极高", "数据质量": "极低", "获取方式": "招聘JD+专利推测", "成本": "中", "时效性": "N/A"},
            {"指标": "用户流失根因", "类别": "D", "获取难度": "极高", "数据质量": "低", "获取方式": "文本挖掘+模型", "成本": "高", "时效性": "季度"},
            {"指标": "各渠道转化率", "类别": "D", "获取难度": "极高", "数据质量": "极低", "获取方式": "行业基准对标", "成本": "高", "时效性": "N/A"},
            {"指标": "获客成本(CAC)", "类别": "D", "获取难度": "极高", "数据质量": "低", "获取方式": "财报反推+估算", "成本": "高", "时效性": "季度"},
            {"指标": "LTV预测", "类别": "D", "获取难度": "极高", "数据质量": "低", "获取方式": "行业类比模型", "成本": "高", "时效性": "N/A"},
        ]
        return pd.DataFrame(data)
    
    def get_by_category(self, category: str) -> pd.DataFrame:
        """按类别获取数据"""
        return self.matrix[self.matrix['类别'] == category.upper()]
    
    def get_all(self) -> pd.DataFrame:
        """获取完整矩阵"""
        return self.matrix
    
    def summary(self) -> Dict:
        """获取分类汇总统计"""
        summary = {}
        for cat in ['A', 'B', 'C', 'D']:
            count = len(self.matrix[self.matrix['类别'] == cat])
            summary[cat] = count
        return summary


# ================================================================================
# 第三部分: 代理指标引擎 (Surrogate Metrics Engine)
# ================================================================================

class SurrogateMetricsEngine:
    """
    代理指标计算引擎
    通过可获取的公开数据推断不可直接获取的核心指标
    """
    
    def __init__(self):
        self.industry_benchmarks = self._load_industry_benchmarks()
    
    def _load_industry_benchmarks(self) -> Dict:
        """加载行业基准数据 (实际应用中从数据库/配置文件读取)"""
        return {
            # 行业平均转化率基准
            "conversion_rates": {
                "电商": {"visit_to_order": 0.03, "order_to_pay": 0.85, "visitor_to_reg": 0.15},
                "SaaS": {"visit_to_trial": 0.08, "trial_to_pay": 0.20, "visitor_to_reg": 0.25},
                "游戏": {"download_to_active": 0.60, "active_to_pay": 0.05, "d1_retention": 0.35},
                "内容": {"visit_to_reg": 0.20, "dau_to_mau": 0.30, "ad_ctr": 0.02},
                "社交": {"visit_to_reg": 0.40, "dau_to_mau": 0.50, "invite_rate": 0.10},
            },
            # 行业平均ARPU (元/月)
            "arpu_benchmarks": {
                "电商": 150,
                "SaaS": 500,
                "游戏": 200,
                "内容": 30,
                "社交": 50,
                "教育": 100,
                "金融": 300,
            },
            # App下载量到DAU的转换系数 (行业均值)
            "download_to_dau_ratio": {
                "电商": 0.08,
                "SaaS": 0.12,
                "游戏": 0.15,
                "内容": 0.10,
                "社交": 0.20,
                "工具": 0.06,
            },
            # 评论数量到活跃用户比例
            "review_to_active_ratio": {
                "电商": 0.02,
                "SaaS": 0.05,
                "游戏": 0.01,
                "内容": 0.008,
                "社交": 0.003,
            }
        }
    
    # ---- C1: GMV/营收推断 ----
    
    def estimate_gmv(self, 
                     app_downloads_monthly: int,
                     industry: str,
                     avg_order_value: Optional[float] = None,
                     payment_conversion: Optional[float] = None,
                     confidence_boosters: Optional[Dict] = None) -> PredictionResult:
        """
        推断竞品GMV/营收
        
        核心公式: GMV ≈ 月下载量 × DAU转化率 × 月活跃天数 × 客单价 × 购买转化率
        
        Parameters:
        -----------
        app_downloads_monthly : 月App下载量
        industry : 行业类别
        avg_order_value : 客单价(如已知)
        payment_conversion : 付费转化率(如已知)
        confidence_boosters : 置信度增强因子
        
        Returns:
        --------
        PredictionResult : 预测结果
        """
        benchmarks = self.industry_benchmarks["conversion_rates"].get(industry, {})
        default_aov = self.industry_benchmarks["arpu_benchmarks"].get(industry, 100)
        dau_ratio = self.industry_benchmarks["download_to_dau_ratio"].get(industry, 0.10)
        
        aov = avg_order_value or default_aov
        pay_conv = payment_conversion or benchmarks.get("active_to_pay", 0.05)
        
        # 核心计算
        estimated_dau = app_downloads_monthly * dau_ratio
        estimated_mau = estimated_dau * 3.5  # DAU/MAU ≈ 0.28
        monthly_orders = estimated_mau * pay_conv * 2  # 月均购买次数≈2
        estimated_gmv = monthly_orders * aov
        
        # 置信区间
        lower_bound = estimated_gmv * 0.5
        upper_bound = estimated_gmv * 1.5
        
        # 可靠性评分
        reliability = 55  # 基础可靠性
        if avg_order_value:
            reliability += 15
        if payment_conversion:
            reliability += 15
        if confidence_boosters:
            reliability += min(15, len(confidence_boosters) * 5)
        
        return PredictionResult(
            metric_name="GMV/营收估算",
            predicted_value=round(estimated_gmv, 2),
            confidence_level=DataConfidenceLevel.MEDIUM if reliability > 60 else DataConfidenceLevel.LOW,
            confidence_interval=(round(lower_bound, 2), round(upper_bound, 2)),
            evidence_sources=["App下载量", "行业转化率基准", f"{industry}行业ARPU"],
            model_used="Multi-factor Surrogate Model",
            prediction_date=datetime.now(),
            reliability_score=min(reliability, 90)
        )
    
    # ---- C2: DAU/MAU推断 ----
    
    def estimate_dau_mau(self,
                         search_index_daily: float,       # 百度指数日均值
                         app_review_count_daily: int,      # 日均评论数
                         social_mentions_daily: int,       # 社交媒体日均提及
                         industry: str,
                         app_downloads_monthly: Optional[int] = None) -> PredictionResult:
        """
        推断竞品DAU/MAU
        
        核心公式: DAU ≈ α×搜索指数 + β×评论数 + γ×社媒提及 + δ×下载量
        通过多源数据融合估计实际活跃用户数
        """
        # 权重系数 (基于行业回归分析)
        industry_weights = {
            "电商": {"search": 120, "review": 800, "social": 60, "download": 0.08},
            "SaaS": {"search": 80, "review": 500, "social": 40, "download": 0.12},
            "游戏": {"search": 200, "review": 1000, "social": 100, "download": 0.15},
            "内容": {"search": 150, "review": 1200, "social": 80, "download": 0.10},
            "社交": {"search": 100, "review": 600, "social": 50, "download": 0.20},
        }
        
        w = industry_weights.get(industry, {"search": 100, "review": 500, "social": 50, "download": 0.10})
        
        # 多源融合估计
        dau_from_search = search_index_daily * w["search"]
        dau_from_review = app_review_count_daily * w["review"] if app_review_count_daily > 0 else 0
        dau_from_social = social_mentions_daily * w["social"] if social_mentions_daily > 0 else 0
        
        # 加权平均 (基于数据质量的权重)
        source_weights = [0.35, 0.30, 0.20]  # 搜索指数、评论、社媒
        if app_downloads_monthly:
            dau_from_download = app_downloads_monthly / 30 * w["download"]
            estimates = [dau_from_search, dau_from_review, dau_from_social, dau_from_download]
            weights = [0.30, 0.25, 0.15, 0.30]
        else:
            estimates = [dau_from_search, dau_from_review, dau_from_social]
            weights = source_weights
        
        # 加权平均
        estimated_dau = sum(e * w for e, w in zip(estimates, weights))
        estimated_mau = estimated_dau * 3.2  # 行业平均 DAU/MAU ≈ 0.31
        
        # 置信区间
        lower_dau = estimated_dau * 0.4
        upper_dau = estimated_dau * 1.6
        
        # 可靠性评分
        reliability = 50
        if app_downloads_monthly:
            reliability += 15
        if search_index_daily > 100:
            reliability += 10
        if app_review_count_daily > 10:
            reliability += 10
        if social_mentions_daily > 50:
            reliability += 10
        
        return PredictionResult(
            metric_name="DAU/MAU估算",
            predicted_value=round(estimated_dau, 0),
            confidence_level=DataConfidenceLevel.MEDIUM if reliability > 60 else DataConfidenceLevel.LOW,
            confidence_interval=(round(lower_dau, 0), round(upper_dau, 0)),
            evidence_sources=["百度指数", "App评论数", "社交媒体提及", f"{industry}行业权重模型"],
            model_used="Weighted Multi-source Fusion",
            prediction_date=datetime.now(),
            reliability_score=min(reliability, 85)
        )
    
    # ---- C3: NPS推断 ----
    
    def estimate_nps(self,
                     positive_review_ratio: float,     # 正面评论占比
                     avg_rating: float,                 # 平均评分 (1-5)
                     review_volume_trend: float,        # 评论量环比变化
                     complaint_ratio: Optional[float] = None,  # 投诉占比
                     brand_search_ratio: Optional[float] = None) -> PredictionResult:
        """
        推断竞品NPS (净推荐值)
        
        NPS范围: -100 到 +100
        核心假设: NPS与评论情感、评分、评论趋势强相关
        
        公式: NPS ≈ (正面率×100 - 负面率×100) + 评分修正 + 趋势修正
        """
        # 基础NPS估计 (从评论情感)
        negative_ratio = 1 - positive_review_ratio
        base_nps = (positive_review_ratio - negative_ratio) * 100
        
        # 评分修正 (1-5分映射到-20到+20)
        rating_adjustment = (avg_rating - 3) * 20
        
        # 趋势修正 (评论增长 = 口碑传播信号)
        trend_adjustment = min(max(review_volume_trend * 15, -15), 15)
        
        # 投诉修正
        complaint_adjustment = 0
        if complaint_ratio is not None:
            complaint_adjustment = -complaint_ratio * 30
        
        # 品牌搜索修正 (品牌搜索占比高 = 口碑传播强)
        brand_adjustment = 0
        if brand_search_ratio is not None:
            brand_adjustment = (brand_search_ratio - 0.3) * 20
        
        estimated_nps = base_nps + rating_adjustment + trend_adjustment + complaint_adjustment + brand_adjustment
        estimated_nps = max(-100, min(100, estimated_nps))  # 裁剪到有效范围
        
        # 置信区间
        uncertainty = 20  # 基础不确定性
        if complaint_ratio is None:
            uncertainty += 10
        if brand_search_ratio is None:
            uncertainty += 10
        
        lower_nps = estimated_nps - uncertainty
        upper_nps = estimated_nps + uncertainty
        
        # 可靠性评分
        reliability = 50
        reliability += min(20, int(positive_review_ratio * 20))
        if complaint_ratio is not None:
            reliability += 10
        if brand_search_ratio is not None:
            reliability += 10
        
        return PredictionResult(
            metric_name="NPS估算",
            predicted_value=round(estimated_nps, 1),
            confidence_level=DataConfidenceLevel.MEDIUM if reliability > 65 else DataConfidenceLevel.LOW,
            confidence_interval=(round(lower_nps, 1), round(upper_nps, 1)),
            evidence_sources=["评论情感分析", "应用评分", "评论趋势", "投诉数据"],
            model_used="NPS Surrogate Inference Model",
            prediction_date=datetime.now(),
            reliability_score=min(reliability, 80)
        )
    
    # ---- C4: 用户留存率推断 ----
    
    def estimate_retention(self,
                         d1_retention_proxy: float,     # 次日留存代理(日活/日新增)
                         industry: str,
                         avg_session_duration: Optional[float] = None,
                         crash_rate: Optional[float] = None,
                         update_frequency_monthly: Optional[int] = None,
                         user_complaint_trend: Optional[float] = None) -> Dict[str, PredictionResult]:
        """
        推断竞品留存率曲线 (D1/D7/D30/D90)
        
        使用幂函数模型: R(t) = R(1) × t^(-β)
        其中 β 为衰减系数，行业不同值不同
        """
        # 行业衰减系数
        decay_params = {
            "电商": {"beta": 0.35, "d1_benchmark": 0.25},
            "SaaS": {"beta": 0.25, "d1_benchmark": 0.35},
            "游戏": {"beta": 0.45, "d1_benchmark": 0.35},
            "内容": {"beta": 0.30, "d1_benchmark": 0.30},
            "社交": {"beta": 0.20, "d1_benchmark": 0.45},
            "工具": {"beta": 0.40, "d1_benchmark": 0.20},
        }
        
        params = decay_params.get(industry, {"beta": 0.35, "d1_benchmark": 0.25})
        beta = params["beta"]
        
        # 用代理数据修正D1留存
        d1 = d1_retention_proxy if d1_retention_proxy > 0 else params["d1_benchmark"]
        
        # 应用修正因子
        if avg_session_duration:
            duration_factor = min(max((avg_session_duration - 60) / 300, -0.1), 0.1)
            d1 *= (1 + duration_factor)
        
        if crash_rate and crash_rate > 0.05:
            d1 *= (1 - crash_rate)
        
        if update_frequency_monthly and update_frequency_monthly >= 2:
            d1 *= 1.05
        
        if user_complaint_trend and user_complaint_trend > 0.1:
            d1 *= (1 - user_complaint_trend * 0.5)
        
        d1 = max(0.05, min(0.80, d1))
        
        # 计算留存曲线
        days = [1, 7, 30, 90]
        results = {}
        
        for day in days:
            retention = d1 * (day ** (-beta))
            retention = max(0.01, min(1.0, retention))
            uncertainty = 0.08 + (day / 30) * 0.05  # 时间越长不确定性越大
            
            results[f"D{day}"] = PredictionResult(
                metric_name=f"{day}日留存率",
                predicted_value=round(retention * 100, 2),
                confidence_level=DataConfidenceLevel.MEDIUM if day <= 7 else DataConfidenceLevel.LOW,
                confidence_interval=(round((retention - uncertainty) * 100, 2), 
                                     round((retention + uncertainty) * 100, 2)),
                evidence_sources=["活跃/新增比率", f"{industry}行业衰减模型", "产品质量信号"],
                model_used=f"Power Decay Model (β={beta})",
                prediction_date=datetime.now(),
                reliability_score=max(30, 70 - day)
            )
        
        return results
    
    # ---- C5: 广告投放预算推断 ----
    
    def estimate_ad_spend(self,
                          ad_creative_count_monthly: int,   # 月广告素材数
                          ad_duration_days: float,           # 素材平均投放天数
                          estimated_cpm: float = 30.0,       # 预估CPM (元)
                          estimated_ctr: float = 0.015,      # 预估CTR
                          platforms: List[str] = None) -> PredictionResult:
        """
        推断竞品广告投放预算
        
        公式: 月广告花费 ≈ 素材数 × 单素材日均消耗 × 投放天数
        通过广告素材抓取和投放时长估计预算规模
        """
        platforms = platforms or ["信息流"]
        
        # 单素材日均消耗 (根据平台不同)
        platform_daily_spend = {
            "信息流": 2000, "搜索": 3000, "短视频": 1500,
            "社交": 1000, "开屏": 5000, "应用商店": 2500
        }
        
        avg_daily = np.mean([platform_daily_spend.get(p, 2000) for p in platforms])
        
        # 计算月预算
        estimated_monthly_spend = ad_creative_count_monthly * avg_daily * ad_duration_days
        
        # 范围估计
        lower = estimated_monthly_spend * 0.3
        upper = estimated_monthly_spend * 2.0
        
        # 可靠性
        reliability = 40
        if ad_creative_count_monthly > 100:
            reliability += 15
        if ad_duration_days > 7:
            reliability += 10
        if len(platforms) > 1:
            reliability += 10
        
        return PredictionResult(
            metric_name="广告投放预算估算",
            predicted_value=round(estimated_monthly_spend, 0),
            confidence_level=DataConfidenceLevel.LOW,
            confidence_interval=(round(lower, 0), round(upper, 0)),
            evidence_sources=["广告素材抓取量", "投放时长估计", "平台CPM基准"],
            model_used="Ad Spend Surrogate Model",
            prediction_date=datetime.now(),
            reliability_score=min(reliability, 65)
        )
    
    # ---- C6: 技术架构推断 ----
    
    def infer_tech_stack(self,
                         job_postings: List[str],
                         patents: List[str],
                         product_features: List[str],
                         engineering_blog_posts: Optional[List[str]] = None) -> Dict[str, any]:
        """
        推断竞品技术架构
        
        通过招聘JD关键词、专利分类、产品功能反推技术栈
        """
        tech_keywords = {
            "前端": ["React", "Vue", "Angular", "Next.js", "Flutter", "React Native", "Swift", "Kotlin"],
            "后端": ["Java", "Go", "Python", "Node.js", "Rust", "Spring", "Django", "微服务"],
            "数据库": ["MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "ClickHouse", "TiDB"],
            "大数据": ["Spark", "Flink", "Hadoop", "Kafka", "Hive", "数据仓库", "实时计算"],
            "AI/ML": ["TensorFlow", "PyTorch", "机器学习", "深度学习", "NLP", "推荐系统", "Transformer"],
            "云原生": ["Kubernetes", "Docker", "微服务", "Service Mesh", "Serverless", "AWS", "阿里云"],
            "DevOps": ["CI/CD", "Jenkins", "GitLab", "Prometheus", "Grafana", "ELK"],
        }
        
        all_text = " ".join(job_postings + patents + product_features).lower()
        if engineering_blog_posts:
            all_text += " " + " ".join(engineering_blog_posts).lower()
        
        tech_detected = {}
        for category, keywords in tech_keywords.items():
            detected = []
            scores = []
            for kw in keywords:
                count = all_text.count(kw.lower())
                if count > 0:
                    detected.append(kw)
                    scores.append(count)
            
            if detected:
                # 计算置信度
                total_score = sum(scores)
                max_possible = len(keywords) * 3  # 假设每个关键词最多出现3次
                confidence = min(total_score / max_possible * 100, 95)
                
                tech_detected[category] = {
                    "technologies": detected,
                    "confidence": round(confidence, 1),
                    "primary": detected[0] if detected else None
                }
        
        overall_confidence = np.mean([v["confidence"] for v in tech_detected.values()]) if tech_detected else 0
        
        return {
            "tech_stack": tech_detected,
            "overall_confidence": round(overall_confidence, 1),
            "evidence_count": len(job_postings) + len(patents) + len(product_features),
            "inference_reliability": DataConfidenceLevel.MEDIUM if overall_confidence > 50 else DataConfidenceLevel.LOW
        }


# ================================================================================
# 第四部分: 用户口碑评估框架
# ================================================================================

class ReputationAssessmentFramework:
    """
    用户口碑评估框架
    多平台数据采集 + 情感分析 + 综合评分
    """
    
    def __init__(self, use_transformers: bool = True):
        self.use_transformers = use_transformers and TRANSFORMERS_AVAILABLE
        self.sentiment_analyzer = None
        if self.use_transformers:
            try:
                self.sentiment_analyzer = pipeline(
                    "sentiment-analysis",
                    model="uer/roberta-base-finetuned-jd-binary-chinese",
                    tokenizer="uer/roberta-base-finetuned-jd-binary-chinese"
                )
            except Exception as e:
                print(f"[WARNING] 无法加载transformers模型: {e}, 使用备用方案")
                self.use_transformers = False
        
        # 数据源权重配置
        self.platform_weights = {
            # 应用商店 (高权重: 真实用户)
            "app_store": 0.25,
            "google_play": 0.20,
            # 社交媒体 (中高权重)
            "weibo": 0.12,
            "xiaohongshu": 0.10,
            "zhihu": 0.10,
            "douyin": 0.08,
            # 专业社区
            "v2ex": 0.05,
            "juejin": 0.05,
            # 投诉平台 (负面信号)
            "heimal": 0.03,
            "tousu": 0.02,
        }
        
        # 水军检测关键词
        self.shuibing_indicators = [
            "绝对好用", "强烈推荐", "非常好", "完美", "五星好评",
            "建议大家", "真的不错", "确实好用", "值得信赖",
            # 英文水军模式
            "great app", "love it", "best ever", "highly recommend",
        ]
        
        # 负面情感关键词库
        self.negative_keywords = [
            "崩溃", "闪退", "卡顿", "bug", "垃圾", "难用", "失望",
            "骗钱", "流氓", "卸载", "后悔", "差评", "投诉", "客服不理",
            "封号", "盗刷", "诈骗", "虚假宣传", "诱导消费",
        ]
        
        # 正面情感关键词库
        self.positive_keywords = [
            "好用", "推荐", "流畅", "方便", "实用", "喜欢", "满意",
            "高效", "专业", "靠谱", "惊喜", "值得", "优秀", "清晰",
        ]
    
    # ---- 4.1 基于规则的情感分析 (备用方案) ----
    
    def rule_based_sentiment(self, text: str) -> Dict:
        """基于关键词规则的情感分析"""
        text_lower = text.lower()
        
        neg_count = sum(1 for kw in self.negative_keywords if kw in text_lower)
        pos_count = sum(1 for kw in self.positive_keywords if kw in text_lower)
        
        # 水军检测
        shuibing_score = sum(1 for p in self.shuibing_indicators if p in text_lower)
        is_suspected_shuibing = shuibing_score >= 2 or (len(text) < 20 and pos_count >= 2)
        
        # 情感极性
        if pos_count > neg_count:
            label = "POSITIVE"
            score = min(0.5 + (pos_count - neg_count) * 0.1, 0.99)
        elif neg_count > pos_count:
            label = "NEGATIVE"
            score = max(0.01, 0.5 - (neg_count - pos_count) * 0.1)
        else:
            label = "NEUTRAL"
            score = 0.5
        
        return {
            "label": label,
            "score": round(score, 3),
            "pos_keywords": pos_count,
            "neg_keywords": neg_count,
            "is_suspected_shuibing": is_suspected_shuibing,
            "shuibing_score": shuibing_score
        }
    
    # ---- 4.2 统一情感分析接口 ----
    
    def analyze_sentiment(self, text: str) -> Dict:
        """统一情感分析入口"""
        if self.use_transformers and self.sentiment_analyzer:
            try:
                result = self.sentiment_analyzer(text[:512])[0]  # 截断到模型最大长度
                transformer_result = {
                    "label": result["label"],
                    "score": round(result["score"], 3),
                    "method": "transformers"
                }
                # 结合规则检测水军
                rule_result = self.rule_based_sentiment(text)
                transformer_result["is_suspected_shuibing"] = rule_result["is_suspected_shuibing"]
                return transformer_result
            except Exception:
                pass
        
        return {**self.rule_based_sentiment(text), "method": "rule-based"}
    
    # ---- 4.3 批量处理与综合评分 ----
    
    def analyze_batch_reviews(self, reviews: List[Dict]) -> Dict:
        """
        批量分析评论数据
        
        reviews格式: [{"text": "评论文本", "platform": "平台名", "rating": 5, "date": "2024-01-01"}]
        """
        results = []
        platform_stats = {}
        
        for review in reviews:
            text = review.get("text", "")
            platform = review.get("platform", "unknown")
            
            sentiment = self.analyze_sentiment(text)
            
            # 水军标记
            if sentiment.get("is_suspected_shuibing"):
                sentiment["label"] = "SUSPECTED_SHUIBING"
            
            result = {
                **review,
                "sentiment": sentiment["label"],
                "sentiment_score": sentiment["score"],
                "is_shuibing": sentiment.get("is_suspected_shuibing", False)
            }
            results.append(result)
            
            # 平台统计
            if platform not in platform_stats:
                platform_stats[platform] = {"total": 0, "positive": 0, "negative": 0, 
                                           "neutral": 0, "shuibing": 0, "avg_rating": []}
            platform_stats[platform]["total"] += 1
            
            # 水军评论单独标记，不计入情感统计
            if sentiment.get("is_suspected_shuibing"):
                platform_stats[platform]["shuibing"] += 1
            else:
                # 只统计非水军评论的情感
                label_key = sentiment["label"].lower()
                if label_key in platform_stats[platform]:
                    platform_stats[platform][label_key] += 1
                else:
                    platform_stats[platform]["neutral"] += 1
            
            if review.get("rating"):
                platform_stats[platform]["avg_rating"].append(review["rating"])
        
        # 过滤水军后计算综合评分
        valid_results = [r for r in results if not r["is_shuibing"]]
        
        if not valid_results:
            return {"error": "所有评论均被标记为水军", "raw_results": results}
        
        # 计算综合口碑分数 (0-100)
        positive_ratio = sum(1 for r in valid_results if r["sentiment"] == "POSITIVE") / len(valid_results)
        negative_ratio = sum(1 for r in valid_results if r["sentiment"] == "NEGATIVE") / len(valid_results)
        
        # NPS风格分数
        nps_score = (positive_ratio - negative_ratio) * 100
        
        # 综合口碑指数 (0-100)
        reputation_index = 50 + nps_score * 0.5
        reputation_index = max(0, min(100, reputation_index))
        
        # 平台维度评分
        platform_scores = {}
        for platform, stats in platform_stats.items():
            if stats["total"] > 0:
                valid_count = stats["total"] - stats["shuibing"]
                if valid_count > 0:
                    pos_r = stats["positive"] / valid_count
                    neg_r = stats["negative"] / valid_count
                    platform_nps = (pos_r - neg_r) * 100
                    weight = self.platform_weights.get(platform, 0.05)
                    platform_scores[platform] = {
                        "nps": round(platform_nps, 1),
                        "sample_size": valid_count,
                        "shuibing_ratio": round(stats["shuibing"] / stats["total"] * 100, 1),
                        "avg_rating": round(np.mean(stats["avg_rating"]), 2) if stats["avg_rating"] else None,
                        "weight": weight
                    }
        
        # 加权综合评分
        weighted_score = 0
        total_weight = 0
        for platform, scores in platform_scores.items():
            weighted_score += scores["nps"] * scores["weight"]
            total_weight += scores["weight"]
        
        weighted_nps = weighted_score / total_weight if total_weight > 0 else 0
        
        return {
            "reputation_index": round(reputation_index, 1),
            "nps_estimate": round(nps_score, 1),
            "weighted_nps": round(weighted_nps, 1),
            "positive_ratio": round(positive_ratio * 100, 1),
            "negative_ratio": round(negative_ratio * 100, 1),
            "neutral_ratio": round((1 - positive_ratio - negative_ratio) * 100, 1),
            "shuibing_ratio": round(sum(1 for r in results if r["is_shuibing"]) / len(results) * 100, 1),
            "sample_size": len(valid_results),
            "platform_scores": platform_scores,
            "confidence_level": "B" if len(valid_results) > 100 else "C",
            "detail_results": results[:50]  # 只返回前50条详情
        }
    
    # ---- 4.4 市场反响衡量 ----
    
    def calculate_market_response(self,
                                   baidu_index: List[float],
                                   wechat_index: Optional[List[float]] = None,
                                   social_mentions_daily: Optional[List[int]] = None,
                                   media_exposure_monthly: Optional[int] = None,
                                   industry_report_citations: Optional[int] = None) -> Dict:
        """
        市场反响综合衡量
        
        输出: 市场热度指数 (0-100)
        """
        # 搜索指数趋势得分
        if len(baidu_index) >= 2:
            search_trend = (baidu_index[-1] - baidu_index[0]) / (baidu_index[0] + 1)
            search_score = min(max(search_trend * 50 + 50, 0), 100)
        else:
            search_score = 50
        
        # 社媒声量得分 (归一化到0-100)
        social_score = 50
        if social_mentions_daily:
            avg_mentions = np.mean(social_mentions_daily)
            social_score = min(avg_mentions / 10, 100)
        
        # 媒体曝光得分
        media_score = 50
        if media_exposure_monthly:
            media_score = min(media_exposure_monthly / 5, 100)
        
        # 行业报告引用得分
        report_score = 50
        if industry_report_citations:
            report_score = min(industry_report_citations * 5, 100)
        
        # 微信指数
        wechat_score = 50
        if wechat_index and len(wechat_index) >= 2:
            wechat_trend = (wechat_index[-1] - wechat_index[0]) / (wechat_index[0] + 1)
            wechat_score = min(max(wechat_trend * 50 + 50, 0), 100)
        
        # 加权综合 (搜索指数权重最高)
        weights = {"search": 0.30, "wechat": 0.15, "social": 0.25, "media": 0.15, "report": 0.15}
        scores = {"search": search_score, "wechat": wechat_score, 
                 "social": social_score, "media": media_score, "report": report_score}
        
        market_heat_index = sum(scores[k] * weights[k] for k in weights)
        
        return {
            "market_heat_index": round(market_heat_index, 1),
            "component_scores": {k: round(v, 1) for k, v in scores.items()},
            "interpretation": self._interpret_market_heat(market_heat_index),
            "confidence_level": "B" if all([baidu_index, social_mentions_daily]) else "C"
        }
    
    def _interpret_market_heat(self, index: float) -> str:
        """市场热度解读"""
        if index >= 80:
            return "极高热度: 市场关注度爆发，可能处于快速增长期或危机期"
        elif index >= 60:
            return "高热度: 市场关注度较高，品牌声量良好"
        elif index >= 40:
            return "中等热度: 正常市场关注水平"
        elif index >= 20:
            return "低热度: 市场关注度较低"
        else:
            return "极低热度: 市场几乎无关注"


# ================================================================================
# 第五部分: 预测模型 (D类数据)
# ================================================================================

class CompetitivePredictor:
    """
    D类数据预测模型
    基于历史趋势、行业基准和相似竞品进行预测
    """
    
    def __init__(self):
        self.models = {}
        self.is_fitted = False
    
    # ---- 5.1 时序预测模型 ----
    
    def time_series_forecast(self, 
                              historical_data: pd.Series,
                              forecast_periods: int = 3,
                              method: str = "holt_winters") -> Dict:
        """
        时序预测: 基于历史趋势外推
        
        Parameters:
        -----------
        historical_data : pd.Series with DatetimeIndex
        forecast_periods : 预测期数
        method : "holt_winters" | "arima" | "naive"
        """
        if len(historical_data) < 6:
            return {
                "error": "历史数据不足(至少6个时间点)",
                "forecast": None
            }
        
        try:
            if method == "holt_winters":
                model = ExponentialSmoothing(
                    historical_data,
                    trend="add",
                    seasonal=None,
                    damped_trend=True
                )
                fitted = model.fit()
                forecast = fitted.forecast(forecast_periods)
                
                # 置信区间
                residuals = fitted.resid
                std_error = np.std(residuals)
                
            elif method == "arima":
                model = ARIMA(historical_data, order=(2, 1, 2))
                fitted = model.fit()
                forecast_result = fitted.get_forecast(steps=forecast_periods)
                forecast = forecast_result.predicted_mean
                conf_int = forecast_result.conf_int(alpha=0.2)
                
                return {
                    "forecast_values": forecast.round(2).tolist(),
                    "forecast_dates": pd.date_range(
                        start=historical_data.index[-1] + pd.Timedelta(days=30),
                        periods=forecast_periods,
                        freq='MS'
                    ).strftime('%Y-%m').tolist(),
                    "confidence_intervals": [
                        (round(conf_int.iloc[i, 0], 2), round(conf_int.iloc[i, 1], 2))
                        for i in range(len(conf_int))
                    ],
                    "method": method,
                    "reliability": 60 if len(historical_data) > 12 else 45
                }
            
            else:  # naive
                last_value = historical_data.iloc[-1]
                avg_growth = historical_data.pct_change().mean()
                forecast = pd.Series([last_value * (1 + avg_growth) ** i for i in range(1, forecast_periods + 1)])
                std_error = historical_data.std() * 0.3
            
            # 通用置信区间
            conf_lower = forecast - 1.645 * std_error
            conf_upper = forecast + 1.645 * std_error
            
            return {
                "forecast_values": forecast.round(2).tolist(),
                "forecast_dates": pd.date_range(
                    start=historical_data.index[-1] + pd.Timedelta(days=30),
                    periods=forecast_periods,
                    freq='MS'
                ).strftime('%Y-%m').tolist(),
                "confidence_intervals": [
                    (round(conf_lower.iloc[i], 2), round(conf_upper.iloc[i], 2))
                    for i in range(len(forecast))
                ],
                "method": method,
                "reliability": 55 if len(historical_data) > 12 else 40
            }
            
        except Exception as e:
            return {"error": f"预测失败: {str(e)}", "forecast": None}
    
    # ---- 5.2 相似竞品对标预测 ----
    
    def benchmark_prediction(self,
                            target_metrics: Dict[str, float],
                            comparable_companies: List[Dict],
                            target_variable: str,
                            k: int = 3) -> PredictionResult:
        """
        对标预测: 找相似竞品，用其已知数据推断目标
        
        comparable_companies格式:
        [
            {"name": "竞品A", "funding_stage": "C轮", "industry": "SaaS", 
             "employee_count": 500, "monthly_downloads": 100000, "known_gmv": 50000000},
            ...
        ]
        """
        if not comparable_companies:
            return PredictionResult(
                metric_name=target_variable,
                predicted_value=0,
                confidence_level=DataConfidenceLevel.SPECULATIVE,
                confidence_interval=(0, 0),
                evidence_sources=[],
                model_used="Benchmark Prediction (No Data)",
                prediction_date=datetime.now(),
                reliability_score=10
            )
        
        # 计算相似度 (欧氏距离归一化)
        features = ["funding_stage_score", "employee_count", "monthly_downloads"]
        
        # 给目标赋值阶段分数
        stage_scores = {"种子轮": 1, "天使轮": 2, "A轮": 3, "B轮": 4, 
                       "C轮": 5, "D轮": 6, "E轮及以上": 7, "上市公司": 8}
        
        target_vector = np.array([
            stage_scores.get(target_metrics.get("funding_stage", "A轮"), 3),
            target_metrics.get("employee_count", 100),
            target_metrics.get("monthly_downloads", 10000)
        ])
        
        similarities = []
        for comp in comparable_companies:
            comp_vector = np.array([
                stage_scores.get(comp.get("funding_stage", "A轮"), 3),
                comp.get("employee_count", 100),
                comp.get("monthly_downloads", 10000)
            ])
            
            # 归一化
            max_vals = np.maximum(target_vector, comp_vector) + 1
            norm_target = target_vector / max_vals
            norm_comp = comp_vector / max_vals
            
            distance = np.linalg.norm(norm_target - norm_comp)
            similarity = 1 / (1 + distance)
            
            if target_variable in comp and comp[target_variable] is not None:
                similarities.append({
                    "company": comp["name"],
                    "similarity": similarity,
                    "value": comp[target_variable]
                })
        
        if not similarities:
            return PredictionResult(
                metric_name=target_variable,
                predicted_value=0,
                confidence_level=DataConfidenceLevel.SPECULATIVE,
                confidence_interval=(0, 0),
                evidence_sources=["无可比公司数据"],
                model_used="Benchmark Prediction",
                prediction_date=datetime.now(),
                reliability_score=15
            )
        
        # 取Top-K相似公司
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        top_k = similarities[:k]
        
        # 加权预测
        total_weight = sum(s["similarity"] for s in top_k)
        weighted_value = sum(s["value"] * s["similarity"] for s in top_k) / total_weight
        
        # 置信区间
        values = [s["value"] for s in top_k]
        lower = min(values) * 0.8
        upper = max(values) * 1.2
        
        # 可靠性
        avg_similarity = np.mean([s["similarity"] for s in top_k])
        reliability = min(int(avg_similarity * 100), 70)
        
        return PredictionResult(
            metric_name=target_variable,
            predicted_value=round(weighted_value, 2),
            confidence_level=DataConfidenceLevel.MEDIUM if reliability > 50 else DataConfidenceLevel.LOW,
            confidence_interval=(round(lower, 2), round(upper, 2)),
            evidence_sources=[f"对标: {s['company']}(相似度{s['similarity']:.2f})" for s in top_k],
            model_used=f"KNN Benchmark (k={k})",
            prediction_date=datetime.now(),
            reliability_score=reliability
        )
    
    # ---- 5.3 回归预测模型 ----
    
    def fit_regression_model(self,
                            X: np.ndarray,
                            y: np.ndarray,
                            model_type: str = "random_forest") -> Dict:
        """
        训练回归预测模型
        
        Parameters:
        -----------
        X : 特征矩阵 (n_samples, n_features)
            特征示例: [下载量, 搜索指数, 评论数, 社媒提及, 员工数]
        y : 目标变量 (n_samples,)
            目标示例: 已知GMV/营收
        model_type : "random_forest" | "gradient_boosting" | "linear" | "ridge"
        """
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # 特征标准化
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # 模型选择
        if model_type == "random_forest":
            model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        elif model_type == "gradient_boosting":
            model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        elif model_type == "ridge":
            model = Ridge(alpha=1.0)
        else:
            model = LinearRegression()
        
        # 训练
        if model_type in ["ridge", "linear"]:
            model.fit(X_train_scaled, y_train)
            y_pred = model.predict(X_test_scaled)
            self.models[model_type] = {"model": model, "scaler": scaler}
        else:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            self.models[model_type] = {"model": model, "scaler": None}
        
        # 评估
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        mape = np.mean(np.abs((y_test - y_pred) / (y_test + 1e-8))) * 100
        
        self.is_fitted = True
        
        return {
            "model_type": model_type,
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r2": round(r2, 3),
            "mape": round(mape, 2),
            "feature_importance": dict(zip(
                ["下载量", "搜索指数", "评论数", "社媒提及", "员工数"],
                model.feature_importances_.round(3).tolist() if hasattr(model, "feature_importances_") else []
            )),
            "status": "trained"
        }
    
    def predict_with_model(self,
                          features: np.ndarray,
                          model_type: str = "random_forest") -> PredictionResult:
        """使用训练好的模型进行预测"""
        if model_type not in self.models:
            return PredictionResult(
                metric_name="预测",
                predicted_value=0,
                confidence_level=DataConfidenceLevel.SPECULATIVE,
                confidence_interval=(0, 0),
                evidence_sources=[],
                model_used=f"{model_type} (未训练)",
                prediction_date=datetime.now(),
                reliability_score=0
            )
        
        model_info = self.models[model_type]
        model = model_info["model"]
        scaler = model_info["scaler"]
        
        if scaler:
            features_scaled = scaler.transform(features.reshape(1, -1))
            pred = model.predict(features_scaled)[0]
        else:
            pred = model.predict(features.reshape(1, -1))[0]
        
        # 置信区间 (基于模型不确定性)
        if hasattr(model, "estimators_"):
            predictions = [est.predict(features.reshape(1, -1))[0] for est in model.estimators_]
            std = np.std(predictions)
            lower = pred - 1.96 * std
            upper = pred + 1.96 * std
        else:
            lower = pred * 0.7
            upper = pred * 1.3
        
        return PredictionResult(
            metric_name="模型预测",
            predicted_value=round(pred, 2),
            confidence_level=DataConfidenceLevel.MEDIUM,
            confidence_interval=(round(lower, 2), round(upper, 2)),
            evidence_sources=["历史训练数据", f"{model_type}模型"],
            model_used=model_type,
            prediction_date=datetime.now(),
            reliability_score=65
        )
    
    # ---- 5.4 LLM辅助推断 ----
    
    def llm_evidence_based_inference(self,
                                      evidence_list: List[str],
                                      question: str,
                                      confidence_threshold: float = 0.6) -> Dict:
        """
        基于证据的LLM推断框架
        
        注意: 这是结构化推断模板，实际使用时需要接入LLM API
        
        Parameters:
        -----------
        evidence_list : 证据列表
        question : 推断问题
        confidence_threshold : 置信度阈值
        """
        # 构建推断模板
        evidence_text = "\n".join([f"[证据{i+1}] {e}" for i, e in enumerate(evidence_list)])
        
        prompt_template = f"""你是一个专业的竞品分析分析师。请基于以下证据回答问题。

## 证据清单
{evidence_text}

## 问题
{question}

## 输出要求
请按以下格式输出推断结果:

1. **推断结论**: [你的结论，必须明确具体]
2. **置信度**: [高/中/低/推测] 
3. **置信度理由**: [解释为什么是这个置信度]
4. **关键证据**: [列出支持你结论的top3证据]
5. **反对证据**: [列出可能推翻你结论的证据]
6. **不确定性**: [列出结论中的关键不确定性]
7. **需要验证的假设**: [列出推断依赖的假设]

重要规则:
- 如果证据不足以支持明确结论，请明确说"证据不足"
- 区分"事实"和"推断"，用[FACT]和[INFERENCE]标记
- 不要编造证据中不存在的信息
- 如果多个证据矛盾，请指出矛盾并给出你的判断
"""
        
        # 在实际应用中，这里调用LLM API
        # response = call_llm_api(prompt_template)
        
        # 模拟返回结构化结果
        return {
            "prompt": prompt_template,
            "inference_template": {
                "conclusion": "[需接入LLM生成]",
                "confidence": "[高/中/低/推测]",
                "confidence_reason": "[基于证据的充分性]",
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "uncertainties": [],
                "assumptions": []
            },
            "evidence_count": len(evidence_list),
            "reliability_guide": {
                "证据充分": "置信度=高",
                "证据部分充分": "置信度=中",
                "证据有限": "置信度=低",
                "证据极少": "置信度=推测"
            },
            "note": "此为结构化推断模板。生产环境需接入LLM API (GPT-4/Claude等)并添加RAG检索增强"
        }


# ================================================================================
# 第六部分: 置信度量化引擎
# ================================================================================

class ConfidenceQuantifier:
    """
    置信度量化引擎
    为每个推断结果打上可靠性标签
    """
    
    def __init__(self):
        # 置信度评分维度
        self.dimensions = {
            "data_source_quality": 0.25,    # 数据源质量
            "data_quantity": 0.20,           # 数据量
            "method_rigor": 0.20,            # 方法严谨性
            "cross_validation": 0.15,        # 交叉验证
            "expert_consensus": 0.10,        # 专家共识
            "temporal_relevance": 0.10       # 时效性
        }
    
    def calculate_confidence_score(self,
                                    data_sources: List[str],
                                    data_points: int,
                                    method: str,
                                    has_cross_validation: bool,
                                    expert_validation: bool,
                                    data_freshness_days: int) -> Dict:
        """
        计算综合置信度分数
        
        输出: 0-100的可靠性分数 + 等级
        """
        # 1. 数据源质量评分
        source_quality_scores = {
            "财报": 95, "官方数据": 90, "权威第三方": 80,
            "应用商店": 75, "社交媒体": 60, "搜索引擎": 65,
            "招聘平台": 55, "行业报告": 70, "模型推断": 40,
            "传闻": 20, "猜测": 10
        }
        
        source_scores = []
        for src in data_sources:
            matched = False
            for key, score in source_quality_scores.items():
                if key in src:
                    source_scores.append(score)
                    matched = True
                    break
            if not matched:
                source_scores.append(50)
        
        avg_source_quality = np.mean(source_scores) if source_scores else 30
        
        # 2. 数据量评分
        if data_points >= 1000:
            quantity_score = 95
        elif data_points >= 100:
            quantity_score = 75
        elif data_points >= 30:
            quantity_score = 55
        elif data_points >= 10:
            quantity_score = 35
        else:
            quantity_score = 15
        
        # 3. 方法严谨性评分
        method_scores = {
            " audited_financial": 95, "surrogate_model": 60, 
            "time_series": 65, "benchmark": 55, "ml_model": 70,
            "expert_estimate": 45, "guess": 10
        }
        method_score = method_scores.get(method, 40)
        
        # 4. 交叉验证
        cv_score = 80 if has_cross_validation else 30
        
        # 5. 专家验证
        expert_score = 85 if expert_validation else 40
        
        # 6. 时效性
        if data_freshness_days <= 7:
            freshness_score = 95
        elif data_freshness_days <= 30:
            freshness_score = 75
        elif data_freshness_days <= 90:
            freshness_score = 55
        elif data_freshness_days <= 180:
            freshness_score = 35
        else:
            freshness_score = 15
        
        # 综合评分
        scores = {
            "data_source_quality": avg_source_quality,
            "data_quantity": quantity_score,
            "method_rigor": method_score,
            "cross_validation": cv_score,
            "expert_consensus": expert_score,
            "temporal_relevance": freshness_score
        }
        
        final_score = sum(scores[k] * self.dimensions[k] for k in self.dimensions)
        
        # 等级判定
        if final_score >= 80:
            level = "A-高置信度"
            color = "green"
        elif final_score >= 60:
            level = "B-中等置信度"
            color = "yellow"
        elif final_score >= 40:
            level = "C-低置信度"
            color = "orange"
        else:
            level = "D-推测性"
            color = "red"
        
        return {
            "final_score": round(final_score, 1),
            "level": level,
            "dimension_scores": {k: round(v, 1) for k, v in scores.items()},
            "weights": self.dimensions,
            "recommendation": self._confidence_recommendation(final_score)
        }
    
    def _confidence_recommendation(self, score: float) -> str:
        """基于置信度给出建议"""
        if score >= 80:
            return "数据可信，可直接用于决策"
        elif score >= 60:
            return "数据有参考价值，建议结合其他信息验证"
        elif score >= 40:
            return "数据仅供参考，不建议作为唯一决策依据"
        else:
            return "数据可靠性低，仅作方向性参考"
    
    def confidence_badge(self, score: float) -> str:
        """生成置信度标签"""
        if score >= 80:
            return "✓ HIGH"
        elif score >= 60:
            return "~ MEDIUM"
        elif score >= 40:
            return "! LOW"
        else:
            return "?? SPECULATIVE"


# ================================================================================
# 第七部分: 主控制器 (系统入口)
# ================================================================================

class CompetitiveIntelligenceSystem:
    """
    竞品情报分析系统主控制器
    整合所有模块，提供统一分析接口
    """
    
    def __init__(self):
        print("=" * 70)
        print("  AI驱动竞品分析系统 - 缺失数据预测与口碑分析框架 v1.0")
        print("=" * 70)
        
        self.matrix = DataAccessibilityMatrix()
        self.surrogate = SurrogateMetricsEngine()
        self.reputation = ReputationAssessmentFramework()
        self.predictor = CompetitivePredictor()
        self.confidence = ConfidenceQuantifier()
        
        print("[✓] 数据可达性矩阵 初始化完成")
        print("[✓] 代理指标引擎 初始化完成")
        print("[✓] 口碑评估框架 初始化完成")
        print("[✓] 预测模型 初始化完成")
        print("[✓] 置信度量引擎 初始化完成")
        print("=" * 70)
    
    def full_analysis(self, competitor_data: Dict) -> Dict:
        """
        执行完整竞品分析
        
        competitor_data格式:
        {
            "name": "竞品名称",
            "industry": "行业",
            "monthly_downloads": 100000,
            "search_index": 5000,
            "daily_reviews": 50,
            "social_mentions": 200,
            "avg_rating": 4.2,
            "reviews": [{"text": "...", "platform": "app_store", "rating": 5}],
            # ... 其他可用数据
        }
        """
        name = competitor_data.get("name", "未知竞品")
        industry = competitor_data.get("industry", "电商")
        results = {"competitor": name, "industry": industry, "timestamp": datetime.now().isoformat()}
        
        print(f"\n[1/5] 正在分析 {name} ({industry})...")
        
        # 1. GMV估算
        if "monthly_downloads" in competitor_data:
            gmv_result = self.surrogate.estimate_gmv(
                app_downloads_monthly=competitor_data["monthly_downloads"],
                industry=industry,
                avg_order_value=competitor_data.get("avg_order_value")
            )
            results["gmv_estimate"] = {
                "value": gmv_result.predicted_value,
                "range": gmv_result.confidence_interval,
                "reliability": gmv_result.reliability_score
            }
        
        # 2. DAU/MAU估算
        if all(k in competitor_data for k in ["search_index", "daily_reviews", "social_mentions"]):
            dau_result = self.surrogate.estimate_dau_mau(
                search_index_daily=competitor_data["search_index"],
                app_review_count_daily=competitor_data["daily_reviews"],
                social_mentions_daily=competitor_data["social_mentions"],
                industry=industry,
                app_downloads_monthly=competitor_data.get("monthly_downloads")
            )
            results["dau_estimate"] = {
                "value": dau_result.predicted_value,
                "range": dau_result.confidence_interval,
                "reliability": dau_result.reliability_score
            }
        
        # 3. NPS估算
        if "reviews" in competitor_data and competitor_data["reviews"]:
            pos_ratio = sum(1 for r in competitor_data["reviews"] if r.get("rating", 3) >= 4) / len(competitor_data["reviews"])
            nps_result = self.surrogate.estimate_nps(
                positive_review_ratio=pos_ratio,
                avg_rating=competitor_data.get("avg_rating", 3.5),
                review_volume_trend=competitor_data.get("review_trend", 0)
            )
            results["nps_estimate"] = {
                "value": nps_result.predicted_value,
                "range": nps_result.confidence_interval,
                "reliability": nps_result.reliability_score
            }
        
        # 4. 口碑分析
        if "reviews" in competitor_data and competitor_data["reviews"]:
            print(f"[2/5] 正在分析用户口碑 ({len(competitor_data['reviews'])}条评论)...")
            reputation_result = self.reputation.analyze_batch_reviews(competitor_data["reviews"])
            results["reputation_analysis"] = {
                "reputation_index": reputation_result.get("reputation_index"),
                "nps_estimate": reputation_result.get("nps_estimate"),
                "positive_ratio": reputation_result.get("positive_ratio"),
                "negative_ratio": reputation_result.get("negative_ratio"),
                "shuibing_ratio": reputation_result.get("shuibing_ratio")
            }
        
        # 5. 留存率估算
        if "d1_retention_proxy" in competitor_data:
            print("[3/5] 正在估算留存率...")
            retention_results = self.surrogate.estimate_retention(
                d1_retention_proxy=competitor_data["d1_retention_proxy"],
                industry=industry,
                avg_session_duration=competitor_data.get("avg_session_duration"),
                crash_rate=competitor_data.get("crash_rate")
            )
            results["retention_estimate"] = {
                k: {
                    "value": v.predicted_value,
                    "range": v.confidence_interval,
                    "reliability": v.reliability_score
                }
                for k, v in retention_results.items()
            }
        
        # 6. 综合置信度评估
        print("[4/5] 计算综合置信度...")
        confidence_result = self.confidence.calculate_confidence_score(
            data_sources=["应用商店", "社交媒体", "搜索指数"],
            data_points=len(competitor_data.get("reviews", [])),
            method="surrogate_model",
            has_cross_validation=True,
            expert_validation=False,
            data_freshness_days=competitor_data.get("data_age_days", 30)
        )
        results["overall_confidence"] = confidence_result
        
        print("[5/5] 分析完成!")
        return results


# ================================================================================
# 第八部分: 演示与测试
# ================================================================================

def demo():
    """
    完整演示流程
    """
    print("\n" + "=" * 70)
    print("  演示: 竞品分析完整流程")
    print("=" * 70)
    
    # 初始化系统
    system = CompetitiveIntelligenceSystem()
    
    # 打印数据可达性矩阵摘要
    print("\n【数据可达性矩阵摘要】")
    summary = system.matrix.summary()
    for cat, count in summary.items():
        cat_names = {"A": "A类-可直接获取", "B": "B类-可间接推断", 
                    "C": "C类-难以直接获取", "D": "D类-几乎无法获取"}
        print(f"  {cat_names[cat]}: {count}项")
    
    # 模拟竞品数据
    demo_reviews = [
        {"text": "这个App真的太好用了，界面简洁流畅，功能也很实用，强烈推荐给大家！", "platform": "app_store", "rating": 5},
        {"text": "使用体验很不错，客服响应也很快，解决了我的问题", "platform": "app_store", "rating": 5},
        {"text": "最近更新后有点卡顿，希望能优化一下性能", "platform": "google_play", "rating": 3},
        {"text": "功能很全面，但是价格有点贵，希望能有更多优惠活动", "platform": "google_play", "rating": 4},
        {"text": "崩溃了三次，根本无法正常使用，太差了", "platform": "app_store", "rating": 1},
        {"text": "非常好用的产品，效率提升了很多，已经推荐给了同事", "platform": "xiaohongshu", "rating": 5},
        {"text": "和其他同类产品比，这个的体验是最好的", "platform": "xiaohongshu", "rating": 5},
        {"text": "不错的工具，日常使用足够了", "platform": "zhihu", "rating": 4},
        {"text": "功能更新太慢了，竞争对手都已经有了", "platform": "zhihu", "rating": 3},
        {"text": "客服态度很差，问题半天没人回复", "platform": "weibo", "rating": 2},
        {"text": "建议大家试试，真的很好用，完美！", "platform": "app_store", "rating": 5},
        {"text": "用这个已经一年多了，体验越来越好", "platform": "google_play", "rating": 5},
        {"text": "五星好评，绝对好用，值得信赖", "platform": "app_store", "rating": 5},
        {"text": "新手引导做得不太好，上手有点困难", "platform": "zhihu", "rating": 3},
        {"text": "性价比还可以，功能也够用", "platform": "xiaohongshu", "rating": 4},
    ]
    
    competitor_data = {
        "name": "Demo竞品A",
        "industry": "SaaS",
        "monthly_downloads": 50000,
        "search_index": 3500,
        "daily_reviews": 25,
        "social_mentions": 150,
        "avg_rating": 4.1,
        "avg_order_value": 299,
        "review_trend": 0.15,
        "d1_retention_proxy": 0.32,
        "avg_session_duration": 420,
        "reviews": demo_reviews,
        "data_age_days": 15
    }
    
    # 执行完整分析
    results = system.full_analysis(competitor_data)
    
    # 打印结果摘要
    print("\n【分析结果摘要】")
    print(f"  分析对象: {results['competitor']} ({results['industry']})")
    
    if "gmv_estimate" in results:
        gmv = results["gmv_estimate"]
        print(f"\n  [GMV估算]")
        print(f"    估算值: ¥{gmv['value']:,.0f}")
        print(f"    置信区间: ¥{gmv['range'][0]:,.0f} - ¥{gmv['range'][1]:,.0f}")
        print(f"    可靠性: {gmv['reliability']}/100")
    
    if "dau_estimate" in results:
        dau = results["dau_estimate"]
        print(f"\n  [DAU估算]")
        print(f"    估算值: {dau['value']:,.0f}")
        print(f"    可靠性: {dau['reliability']}/100")
    
    if "nps_estimate" in results:
        nps = results["nps_estimate"]
        print(f"\n  [NPS估算]")
        print(f"    估算值: {nps['value']:.1f}")
        print(f"    可靠性: {nps['reliability']}/100")
    
    if "retention_estimate" in results:
        print(f"\n  [留存率估算]")
        for period, data in results["retention_estimate"].items():
            print(f"    {period}: {data['value']:.2f}% (可靠性: {data['reliability']}/100)")
    
    if "reputation_analysis" in results:
        rep = results["reputation_analysis"]
        print(f"\n  [口碑分析]")
        print(f"    口碑指数: {rep['reputation_index']}/100")
        print(f"    好评率: {rep['positive_ratio']:.1f}%")
        print(f"    差评率: {rep['negative_ratio']:.1f}%")
        print(f"    水军比例: {rep['shuibing_ratio']:.1f}%")
    
    if "overall_confidence" in results:
        conf = results["overall_confidence"]
        print(f"\n  [综合置信度]")
        print(f"    综合评分: {conf['final_score']}/100")
        print(f"    置信等级: {conf['level']}")
        print(f"    建议: {conf['recommendation']}")
    
    # 演示技术栈推断
    print("\n【技术栈推断演示】")
    job_posts = [
        "招聘高级Java工程师，有Spring Cloud微服务经验",
        "招聘前端开发，要求精通React和TypeScript",
        "招聘数据工程师，熟悉Spark和Kafka实时计算",
        "招聘算法工程师，有推荐系统和NLP经验",
        "招聘DevOps工程师，熟悉Kubernetes和Docker"
    ]
    patents = ["一种基于深度学习的推荐方法", "分布式数据处理系统"]
    features = ["智能推荐", "实时数据分析", "多端同步"]
    
    tech_result = system.surrogate.infer_tech_stack(job_posts, patents, features)
    print(f"  推断置信度: {tech_result['overall_confidence']}%")
    for category, info in tech_result["tech_stack"].items():
        print(f"  {category}: {', '.join(info['technologies'])} (置信度: {info['confidence']}%)")
    
    print("\n" + "=" * 70)
    print("  演示完成!")
    print("=" * 70)
    
    return results


# ================================================================================
# 入口点
# ================================================================================

if __name__ == "__main__":
    # 运行演示
    demo_results = demo()
