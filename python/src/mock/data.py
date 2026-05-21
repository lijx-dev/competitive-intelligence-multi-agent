"""
Mock 预生成数据 — 3 个 Demo 场景的完整竞品分析结果。

场景1「直播电商三巨头」：抖音电商 vs 快手电商（字节主场，默认场景）
场景2「跨境电商出海」：SHEIN vs Temu
场景3「AI电商未来」：各大平台 AI 能力对比

数据特点：
  - 全部中文内容，符合答辩场景
  - 质量评分 ≥ 8.5/10（展示系统审查能力）
  - 每条结论带来源 URL 和置信度
  - 通过 Pydantic Schema 校验
"""

from __future__ import annotations

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ======================================================================
# SCENARIO 1: 直播电商三巨头 — 抖音电商 vs 快手电商
# ======================================================================

SCENARIO1_COMPETITOR = "快手电商"

SCENARIO1_MONITOR_RESULTS = {
    "changes_detected": [
        {
            "title": "快手电商上线「全站推广」智能投放工具",
            "summary": "快手电商于2026年Q1推出全站推广工具，整合信息流广告、搜索广告和直播推广，利用AI算法实现跨场景智能投放。该功能直接对标抖音千川的全站推广能力，表明快手在广告投放智能化方面加速追赶。",
            "severity": "HIGH",
            "source_url": "https://www.kuaishou.com/news/2026-q1",
            "detected_at": _now(),
        },
        {
            "title": "快手商城改版：强化货架电商入口",
            "summary": "快手APP首页新增「商城」一级入口，页面布局向传统货架电商靠拢。新增品牌旗舰店专区、限时秒杀、品类导航等模块，标志着快手从纯直播电商向「直播+货架」双轮驱动转型。",
            "severity": "MEDIUM",
            "source_url": "https://about.kuaishou.com",
            "detected_at": _now(),
        },
        {
            "title": "快手电商2025年GMV突破1.2万亿",
            "summary": "快手2025年报显示电商GMV达1.2万亿元，同比增长28%。品牌商家数量突破50万，月活跃买家达1.2亿。其中泛货架电商GMV占比从5%提升至15%。",
            "severity": "MEDIUM",
            "source_url": "https://ir.kuaishou.com/financials",
            "detected_at": _now(),
        },
    ]
}

SCENARIO1_RESEARCH_INSIGHTS = {
    "research_results": [
        {
            "topic": "[financial] 快手电商营收与增长分析",
            "summary": "快手2025年全年电商GMV达1.2万亿元，同比增长28%。电商业务收入（含佣金+广告）约680亿元，占集团总营收的45%。经调整净利润率提升至8.2%，主要得益于高毛利电商广告占比提升。公司指引2026年GMV目标1.5-1.6万亿元，增速预期25-30%。",
            "key_findings": [
                "GMV 1.2万亿，同比增长28%，增速连续3年超25%",
                "电商收入680亿元，占总营收45%，成为第一大收入来源",
                "月活买家1.2亿，渗透率达30%（MAU 4亿）",
                "品牌商家50万+，同比增长40%",
                "2026年GMV目标1.5-1.6万亿"
            ],
            "confidence": 0.85,
            "sources": ["快手2025年报", "艾瑞咨询直播电商报告2026"],
        },
        {
            "topic": "[strategic_moves] 快手电商战略转型分析",
            "summary": "快手电商正经历从「信任电商」到「信任+货架双轮驱动」的战略转型。核心动作包括：1）首页新增商城一级入口，强化搜索和浏览购物心智；2）推出全站推广工具，对标抖音千川；3）加码品牌自播，引入雅诗兰黛、耐克等国际品牌；4）布局本地生活电商，与美团合作「快手团购」。战略重心从GMV规模增长转向「用户购物心智培养」。",
            "key_findings": [
                "从信任电商转向「信任+货架」双轮驱动",
                "全站推广工具直接对标抖音千川",
                "引入国际品牌，品牌化率从20%提升至35%",
                "本地生活电商为差异化方向"
            ],
            "confidence": 0.80,
            "sources": ["晚点LatePost", "36氪快手战略分析", "快手官方公告"],
        },
        {
            "topic": "[tech_blog] 快手AI技术能力评估",
            "summary": "快手在AI领域的投入主要集中在三个方面：1）推荐算法——快手长期以来在短视频推荐上有技术积累，其多模态内容理解模型Kuaishou-LLM（130B参数）在中文多模态理解评测中排名前三；2）AI创作工具——「快影」AI剪辑、「可灵」AI视频生成（对标字节即梦）；3）电商AI——智能客服、AI主播、智能选品等应用已落地。整体技术实力位于国内第二梯队（次于字节、百度）。",
            "key_findings": [
                "Kuaishou-LLM 130B参数，多模态理解能力国内前三",
                "可灵AI视频生成日活创作者超100万",
                "AI主播覆盖30%直播间，降低商家开播门槛",
                "技术投入约80亿元/年，占营收8%"
            ],
            "confidence": 0.75,
            "sources": ["快手技术博客", "机器之心评测", "各公司年报"],
        },
        {
            "topic": "[patent_ip] 快手电商相关专利布局",
            "summary": "快手在电商领域已申请专利超过2000项，主要集中在：直播交互技术（35%）、推荐算法（25%）、支付与交易安全（15%）、AI内容生成（15%）、物流与供应链（10%）。与抖音相比，快手在AI内容生成和推荐算法专利数量约为抖音的60%，但在直播交互技术上持平。",
            "key_findings": [
                "电商相关专利2000+项",
                "直播交互技术占比最高（35%）",
                "专利总量约为抖音的60%",
                "近两年AI专利增速超100%"
            ],
            "confidence": 0.70,
            "sources": ["国家知识产权局", "智慧芽", "各公司专利数据库"],
        },
        {
            "topic": "[oss_community] 快手开源生态与开发者社区",
            "summary": "快手开源项目主要集中在大前端和AI推理方向：Kui（React Native替代方案，GitHub 8k stars）、Y-tech（视频处理SDK）、Kwai-LLM（部分模型权重开源）。开发者社区规模较小，GitHub总Star数约2.5万，远低于字节的15万+。但快手在AI模型开源上有加速趋势，2025年开源了3个多模态模型。",
            "key_findings": [
                "GitHub总Star约2.5万，字节15万+",
                "Kui框架8k stars，前端方向有一定影响力",
                "2025年加速AI模型开源，发布3个多模态模型",
                "开发者社区活跃度低于字节、阿里"
            ],
            "confidence": 0.75,
            "sources": ["GitHub", "开源中国", "各公司开源官网"],
        },
    ]
}

SCENARIO1_FACTCHECK_RESULTS = {
    "fact_check_result": {
        "verified_count": 12,
        "unverified_count": 1,
        "conflicts": [],
        "overall_confidence": 0.88,
        "verification_summary": "12/13条核心结论验证通过。快手GMV 1.2万亿数据与年报一致。全站推广工具已通过官方公告确认。「可灵AI日活100万」数据来自行业估算，置信度标记为中等。",
        "status": "verified",
    }
}

SCENARIO1_COMPARISON_MATRIX = {
    "comparison_matrix": {
        "competitor": "快手电商",
        "dimensions": [
            {
                "dimension": "产品功能",
                "our_score": 8.5,
                "competitor_score": 7.0,
                "notes": "我方（抖音电商）产品功能更全面：千川投放系统成熟度高于快手全站推广，抖店后台功能丰富度领先。快手商城刚完成改版，货架电商能力仍在建设中。差距主要体现在数据看板、智能诊断等商家工具深度上。",
                "evidence": [{"source": "产品体验对比", "url": "", "confidence": 0.90}],
            },
            {
                "dimension": "定价与价值",
                "our_score": 7.5,
                "competitor_score": 8.0,
                "notes": "快手电商佣金率（2-5%）低于抖音（3-8%），对中小商家更有吸引力。但快手整体ROI低于抖音（因流量规模差距）。品牌商更看重抖音的流量规模和人群质量。",
                "evidence": [{"source": "公开定价页面", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "用户体验",
                "our_score": 8.0,
                "competitor_score": 7.5,
                "notes": "抖音电商的用户体验在内容丰富度、推荐精准度和支付流畅度上均领先快手。快手「信任电商」模式在复购率上有优势（粉丝复购率比抖音高15%），适合社区型商家。",
                "evidence": [{"source": "用户调研报告", "url": "", "confidence": 0.80}],
            },
            {
                "dimension": "市场份额",
                "our_score": 9.0,
                "competitor_score": 6.5,
                "notes": "抖音电商2025年GMV约3.5万亿，市占率约45%（直播电商赛道），快手约1.2万亿，市占率15%。抖音在品牌商家数量（100万+）、日活用户（7亿+）上都有显著优势。",
                "evidence": [{"source": "艾瑞咨询2026", "url": "", "confidence": 0.90}],
            },
            {
                "dimension": "用户评价与口碑",
                "our_score": 7.5,
                "competitor_score": 7.5,
                "notes": "双方用户NPS均在30-40区间。抖音因流量分发算法争议受到部分商家抱怨（「流量太贵」），快手因社区黏性强获得中小商家好评。快手「老铁经济」模式在低线城市口碑更好。",
                "evidence": [{"source": "NPS调研", "url": "", "confidence": 0.75}],
            },
            {
                "dimension": "技术与创新",
                "our_score": 9.0,
                "competitor_score": 6.5,
                "notes": "字节AI技术积累显著领先：豆包大模型、推荐算法、AIGC工具（即梦、豆包）均为行业第一梯队。快手虽有可灵AI，但整体AI投入（80亿/年）仅为字节（500亿+/年）的16%。",
                "evidence": [{"source": "各公司年报/技术博客", "url": "", "confidence": 0.90}],
            },
            {
                "dimension": "生态与平台效应",
                "our_score": 9.0,
                "competitor_score": 6.0,
                "notes": "抖音已形成「内容-电商-本地生活-支付」超级App生态，飞书、火山引擎提供企业服务闭环。快手生态以短视频+直播为核心，本地生活依赖美团合作，缺少自有企业服务能力。",
                "evidence": [{"source": "产品矩阵分析", "url": "", "confidence": 0.90}],
            },
            {
                "dimension": "支持与服务",
                "our_score": 8.0,
                "competitor_score": 7.0,
                "notes": "抖音电商有完善的商家大学、服务商体系和API开放平台。快手商家服务起步较晚，服务商网络密度约为抖音的50%。但快手「小二」人工服务在中小商家中口碑较好。",
                "evidence": [{"source": "商家调研", "url": "", "confidence": 0.80}],
            },
        ],
        "overall_assessment": "综合8维度对比，抖音电商（我方）在市场份额(9.0 vs 6.5)、技术创新(9.0 vs 6.5)、生态效应(9.0 vs 6.0)三个维度上显著领先快手电商。快手在定价友好度(7.5 vs 8.0)上有微弱优势。整体竞争优势明显，但需要警惕快手在「信任电商」差异化定位和AI能力上的加速追赶。",
        "our_overall_score": 8.3,
        "competitor_overall_score": 7.0,
    }
}

SCENARIO1_BATTLECARD = {
    "battlecard": {
        "our_strengths": [
            "流量规模碾压：抖音DAU 7亿+ vs 快手4亿，品牌曝光量级差距3-5倍",
            "AI技术代差：豆包大模型+推荐算法+即梦AI工具形成技术护城河",
            "超级App生态：内容-电商-本地生活-企业服务（飞书）完整闭环",
            "品牌商家生态：100万+品牌入驻，覆盖头部国际品牌到新锐国货",
            "数据驱动能力：千川广告系统的精准定向和ROI优化领先行业"
        ],
        "our_weaknesses": [
            "流量成本攀升：商家获客成本年均上涨20%，中小商家流失风险增加",
            "社区黏性不足：粉丝复购率低于快手15%，更依赖算法推荐而非社交关系链",
            "下沉市场渗透不足：三四线城市用户占比低于快手10个百分点"
        ],
        "competitor_strengths": [
            "信任电商模式：老铁经济带来高复购和高转化，粉丝复购率高于抖音15%",
            "低佣金策略：2-5%佣金率吸引价格敏感型中小商家",
            "差异化AI工具：可灵AI视频生成在创作者中口碑优秀",
            "下沉市场壁垒：三四线城市渗透率领先，用户黏性更强"
        ],
        "competitor_weaknesses": [
            "流量天花板：DAU 4亿，增速放缓至5%以下",
            "品牌化不足：国际品牌入驻率低，客单价受限于用户消费力",
            "技术投入差距：AI投入仅为字节16%，长期竞争力存疑",
            "生态单一：缺少企业服务、本地生活等协同业务"
        ],
        "key_differentiators": [
            "流量规模：抖音7亿DAU vs 快手4亿 → 品牌曝光3-5倍差距",
            "AI技术：豆包大模型体系 vs 快手单点AI → 系统性代差",
            "生态闭环：抖音「内容+电商+飞书+火山引擎」vs 快手「短视频+直播」→ 维度差距",
            "品牌生态：100万+品牌 vs 50万+品牌 → 商家资源2倍差距",
            "广告系统：千川成熟度 vs 全站推广（新上线）→ 3年先发优势"
        ],
        "objection_handling": {
            "客户说快手佣金更低，想去试试？": "理解您对成本的关注。但需要关注综合ROI而非单一佣金率——抖音虽然佣金高2-3个点，但流量规模大3-5倍，品牌曝光和转化总额远超快手。我们帮您算一笔账：假设同样1万元广告预算，抖音预期GMV约3-5万（ROI 3-5），快手约1.5-2.5万（ROI 1.5-2.5）。算上佣金差，抖音的净利润仍然更高。建议先在抖音做大，再用快手做增量。",
            "快手老铁经济复购率高，是不是更适合我们这种品类？": "社区黏性确实是快手的优势，但需要评估您的目标客群规模。如果您的品类在三四线城市有主力消费群，快手值得作为补充渠道。但抖音的一二线城市覆盖和中高消费力人群规模（约3亿）是快手无法替代的。建议「抖音做规模、快手做黏性」双平台策略。",
            "抖音流量越来越贵，小商家怎么活下去？": "这是个真实挑战，我们建议三个策略：1）从「买流量」转向「做内容」——优质短视频内容获取免费流量，我们的数据表明自然流量GMV占比可达30-50%；2）利用千川的智能定向，把每一分钱花在精准人群上；3）关注抖音的「中小商家扶持计划」，新商家有流量券和佣金减免。"
        },
        "elevator_pitch": "抖音电商是品牌规模化的主阵地——7亿DAU、3.5万亿GMV、AI驱动的精准匹配，是品牌从0到100的最短路径。快手适合作为社区渗透的补充渠道。核心策略：抖音做规模+品牌，快手做黏性+下沉，双平台协同而非二选一。"
    }
}

SCENARIO1_REVIEW_FEEDBACK = {
    "review_feedback": {
        "overall_score": 8.7,
        "accuracy_score": 9.0,
        "completeness_score": 8.5,
        "citation_score": 8.5,
        "actionability_score": 8.8,
        "approved": True,
        "issues": [],
        "revision_instructions": "报告质量优秀，8维度对比数据翔实，引用来源可靠。建议在答辩时重点强调AI技术差距和生态闭环两个差异化优势。战术卡异议处理话术内容丰富，实战价值高。",
    }
}

SCENARIO1_CITATION_REPORT = {
    "citation_report": {
        "total_sources": 15,
        "verified_sources": 13,
        "broken_links": 0,
        "unreachable_sources": 2,
        "overall_reliability_score": 0.87,
        "missing_citations": [],
        "reliability_distribution": {
            "high": 8,
            "medium": 5,
            "low": 2,
        },
        "source_list": [
            {"url": "https://ir.kuaishou.com/financials", "domain_score": 1.0, "status": "verified"},
            {"url": "https://www.kuaishou.com/news/2026-q1", "domain_score": 1.0, "status": "verified"},
            {"url": "https://about.kuaishou.com", "domain_score": 1.0, "status": "verified"},
        ],
    }
}

SCENARIO1_AGENT_DECISION_LOGS = [
    {
        "agent_name": "monitor", "agent_role": "监控Agent", "phase": "execution",
        "step_number": 1, "reasoning": "爬取快手官网+财报页面，SHA-256哈希对比检测到3处变更：全站推广上线(HIGH)、商城改版(MEDIUM)、GMV突破1.2万亿(MEDIUM)。LLM语义分析确认重大变更。",
        "input_tokens": 420, "output_tokens": 180, "duration_ms": 820, "status": "completed",
    },
    {
        "agent_name": "research", "agent_role": "研究Agent", "phase": "execution",
        "step_number": 2, "reasoning": "执行5维度并行研究：财务维度通过财报获取GMV 1.2万亿数据；战略维度分析晚点/36氪报道；技术维度评估Kuaishou-LLM和可灵AI；专利维度检索2000+专利布局；开源维度统计GitHub 2.5万Star。全部通过SerpAPI+网页抓取完成。",
        "input_tokens": 1100, "output_tokens": 650, "duration_ms": 1850, "status": "completed",
    },
    {
        "agent_name": "fact_check", "agent_role": "交叉验证Agent", "phase": "execution",
        "step_number": 3, "reasoning": "纯规则引擎交叉验证Monitor vs Research结果：13条结论中12条验证通过。1条'可灵AI日活100万'来自行业估算，标记为unverified。无矛盾发现。",
        "input_tokens": 0, "output_tokens": 0, "duration_ms": 45, "status": "completed",
    },
    {
        "agent_name": "compare", "agent_role": "对比Agent", "phase": "execution",
        "step_number": 4, "reasoning": "基于我方产品数据+Research洞察+FactCheck结果，完成8维度对比评分。我方综合8.3 vs 竞品7.0，在市场份额(9.0 vs 6.5)、技术创新(9.0 vs 6.5)、生态(9.0 vs 6.0)三维显著领先。",
        "input_tokens": 1500, "output_tokens": 900, "duration_ms": 2100, "status": "completed",
    },
    {
        "agent_name": "battlecard", "agent_role": "战术卡Agent", "phase": "execution",
        "step_number": 5, "reasoning": "生成销售战术卡：5项优势、3项劣势、5项核心差异化、3套异议处理话术、1段电梯演讲。RAG知识库注入电商战术模板约束。",
        "input_tokens": 800, "output_tokens": 550, "duration_ms": 1600, "status": "completed",
    },
    {
        "agent_name": "reviewer", "agent_role": "审查Agent", "phase": "execution",
        "step_number": 6, "reasoning": "4维度审查：准确度9.0/10（数据来源可验证），完整度8.5/10（8维度全部覆盖），引用可追溯性8.5/10（13/15来源已验证），可操作性8.8/10（异议处理话术实战价值高）。综合8.7分，审查通过，无需修复。",
        "input_tokens": 600, "output_tokens": 280, "duration_ms": 1200, "status": "completed",
    },
    {
        "agent_name": "citation", "agent_role": "溯源Agent", "phase": "execution",
        "step_number": 7, "reasoning": "验证15个引用来源的URL可达性：13个可达、2个不可达（行业报告链接过期）。总体可信度87%，来源分布：8个高可信（官网/年报）、5个中可信（媒体/咨询）、2个低可信（估算数据）。",
        "input_tokens": 300, "output_tokens": 200, "duration_ms": 550, "status": "completed",
    },
]

# ======================================================================
# SCENARIO 2: 跨境电商出海 — SHEIN vs Temu
# ======================================================================

SCENARIO2_COMPETITOR = "Temu"

SCENARIO2_MONITOR_RESULTS = {
    "changes_detected": [
        {
            "title": "Temu 2025年GMV突破500亿美元，增速超预期",
            "summary": "拼多多旗下Temu 2025年全球GMV达520亿美元，同比增长200%+，超越SHEIN成为全球增速最快的跨境电商平台。已进入78个国家和地区，美国市场贡献约40%GMV。",
            "severity": "HIGH",
            "source_url": "https://investor.pddholdings.com",
            "detected_at": _now(),
        },
        {
            "title": "Temu推出「半托管」模式，吸引品牌商家",
            "summary": "Temu从全托管向半托管模式扩展，允许商家自主管理部分物流和定价。首批在美、英、德、日四国上线，吸引安克创新、小米生态链等品牌入驻。这一模式直接对标SHEIN的第三方开放平台。",
            "severity": "HIGH",
            "source_url": "https://www.temu.com/business",
            "detected_at": _now(),
        },
    ]
}

SCENARIO2_RESEARCH_INSIGHTS = {
    "research_results": [
        {
            "topic": "[financial] Temu全球营收与增长分析",
            "summary": "Temu 2025年全球GMV约520亿美元，同比增长超200%。美国市场GMV约210亿美元，占比40%。平台月活买家突破2亿。拼多多集团2025年总收入约4500亿元，其中Temu贡献约1200亿元（含广告和佣金）。",
            "key_findings": [
                "GMV 520亿美元，增速200%+",
                "进入78个国家，月活买家2亿+",
                "美国市场占比40%，欧洲30%，亚洲及其他30%",
                "年亏损约300亿元（用于补贴和市场扩张）"
            ],
            "confidence": 0.85,
            "sources": ["拼多多2025年报", "SimilarWeb", "SensorTower"],
        },
        {
            "topic": "[strategic_moves] Temu战略定位与竞争策略",
            "summary": "Temu核心策略为「极致低价+社交裂变+全托管」。2025年战略升级：1）从全托管扩展到半托管，吸引品牌商家；2）从美国单核扩展到全球多点布局；3）从日用消费品扩展到电子、家居等高客单价品类；4）加强本地仓储建设（美国已建5个仓库）。",
            "key_findings": [
                "半托管模式上线，对标SHEIN第三方平台",
                "从纯低价策略转向「低价+品质」双轮",
                "美国5仓布局，物流时效从15天缩短至5-7天",
                "品牌化转型是最大变量"
            ],
            "confidence": 0.80,
            "sources": ["晚点LatePost", "亿邦动力", "拼多多官方"],
        },
        {
            "topic": "[tech_blog] Temu技术架构与数据能力",
            "summary": "Temu继承了拼多多的技术基因：分布式推荐系统、C2M反向定制、社交裂变算法。技术优势在于供应链效率极致化——通过数据驱动实现「消费者需要什么，工厂生产什么」。AI应用覆盖选品、定价、物流调度全链路。但在AI基础研究上投入有限，主要做应用层优化。",
            "key_findings": [
                "C2M反向定制：消费者数据直达工厂，库存周转15天",
                "社交裂变算法：用户获取成本仅为SHEIN的30%",
                "AI定价系统：实时调整数千万SKU价格",
                "推荐系统日处理100亿+请求"
            ],
            "confidence": 0.75,
            "sources": ["拼多多技术博客", "InfoQ报道", "技术会议演讲"],
        },
        {
            "topic": "[market] Temu vs SHEIN 差异化定位",
            "summary": "Temu和SHEIN虽然都是中国背景的跨境电商，但定位差异明显：Temu是全品类低价平台（Amazon的拼多多版），SHEIN是快时尚品牌（Zara的线上版）。Temu优势在品类广度和性价比，SHEIN优势在时尚供应链速度和品牌认知。预计2026年两者直接竞争将加剧。",
            "key_findings": [
                "Temu=全品类低价平台，SHEIN=快时尚品牌",
                "Temu品类数1000万+ SKU vs SHEIN 100万+ SKU",
                "SHEIN品牌溢价10-15% vs Temu纯性价比定位",
                "2026年直接竞争加剧：SHEIN开放第三方 vs Temu推半托管"
            ],
            "confidence": 0.80,
            "sources": ["CB Insights", "亿欧智库", "各公司数据"],
        },
        {
            "topic": "[risk] Temu面临的监管与合规风险",
            "summary": "Temu面临三大合规挑战：1）美国数据隐私审查——TikTok禁令的溢出效应；2）欧盟数字服务法（DSA）合规——低价商品的环保和消费者保护标准；3）关税政策不确定性——美国可能取消800美元以下包裹免税政策。任何一个风险都可能对Temu的商业模式产生重大冲击。",
            "key_findings": [
                "美国数据隐私审查：TikTok禁令可能波及其他中国App",
                "欧盟DSA：Temu已列为「超大型在线平台」(VLOP)",
                "de minimis关税豁免若取消，Temu的物流成本可能上涨20-30%",
                "多国对低价中国电商的限制政策在加速推进"
            ],
            "confidence": 0.85,
            "sources": ["Reuters", "EU Commission", "美国国会听证会记录"],
        },
    ]
}

SCENARIO2_FACTCHECK_RESULTS = {
    "fact_check_result": {
        "verified_count": 10,
        "unverified_count": 1,
        "conflicts": [],
        "overall_confidence": 0.90,
        "verification_summary": "10/11条核心结论验证通过。GMV 520亿美元数据引自拼多多年报。欧盟DSA VLOP认定已确认。监管风险分析引用多重权威来源。",
        "status": "verified",
    }
}

SCENARIO2_COMPARISON_MATRIX = {
    "comparison_matrix": {
        "competitor": "Temu",
        "dimensions": [
            {
                "dimension": "产品功能",
                "our_score": 8.0, "competitor_score": 7.5,
                "notes": "SHEIN App在时尚浏览体验上更优（个性化推荐+虚拟试穿），Temu在品类搜索和比价功能上更强。SHEIN品牌页面的视觉呈现质量更高。",
                "evidence": [{"source": "产品体验对比", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "定价与价值",
                "our_score": 7.5, "competitor_score": 9.0,
                "notes": "Temu的定价策略极为激进（同类商品价格低于SHEIN 10-30%），加上大量补贴和优惠券，性价比在跨境电商中无人能及。SHEIN在时尚品类上有品牌溢价能力（高10-15%），但在日用消费品上难以与Temu竞争。",
                "evidence": [{"source": "第三方比价数据", "url": "", "confidence": 0.90}],
            },
            {
                "dimension": "用户体验",
                "our_score": 8.5, "competitor_score": 7.0,
                "notes": "SHEIN的App体验在时尚电商中一流：个性化推荐精准、物流可追踪、退换货流程友好。Temu的购物体验较弱（物流变数大、商品质量不稳定、App界面略显杂乱）。",
                "evidence": [{"source": "App Store评分", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "市场份额",
                "our_score": 7.5, "competitor_score": 8.5,
                "notes": "Temu GMV 520亿 vs SHEIN约450亿（2025年估算），Temu已超越SHEIN成为全球GMV最大的跨境电商平台。Temu在78个国家运营 vs SHEIN约150个国家，但SHEIN单国家渗透率更高。",
                "evidence": [{"source": "各公司年报/估算", "url": "", "confidence": 0.80}],
            },
            {
                "dimension": "用户评价与口碑",
                "our_score": 8.0, "competitor_score": 6.0,
                "notes": "SHEIN在TrustPilot评分4.2 vs Temu 3.5，SHEIN在商品质量和购物体验上口碑显著更好。Temu的低价策略带来「廉价感」标签，社交媒体上质量问题吐槽较多。",
                "evidence": [{"source": "TrustPilot/Social Media", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "技术与创新",
                "our_score": 8.0, "competitor_score": 7.5,
                "notes": "SHEIN在时尚供应链数字化（需求预测+小单快反）上全球领先，AI设计辅助工具降低设计成本70%。Temu继承拼多多技术基因，在推荐算法和AI定价上更强。各有所长。",
                "evidence": [{"source": "技术分析报告", "url": "", "confidence": 0.80}],
            },
            {
                "dimension": "生态与平台效应",
                "our_score": 7.5, "competitor_score": 6.0,
                "notes": "SHEIN已形成「自有品牌+第三方+供应链SaaS」的小生态。Temu目前仅是交易平台，生态协同能力弱。但拼多多集团生态（C2M工厂网络）为Temu提供了供应链支撑。",
                "evidence": [{"source": "生态分析", "url": "", "confidence": 0.75}],
            },
            {
                "dimension": "支持与服务",
                "our_score": 7.0, "competitor_score": 5.5,
                "notes": "SHEIN的商家支持和物流服务相对成熟（海外仓覆盖30+国家）。Temu全托管模式下商家几乎无运营负担，但商家话语权极弱，对平台依赖度高。",
                "evidence": [{"source": "商家调研", "url": "", "confidence": 0.80}],
            },
        ],
        "overall_assessment": "SHEIN（我方）与Temu的竞争是「品牌+时尚」vs「低价+全品类」两种模式的较量。SHEIN在用户体验(8.5 vs 7.0)、品牌口碑(8.0 vs 6.0)上领先；Temu在定价(7.5 vs 9.0)和规模增速上领先。核心策略应是守住时尚品类护城河，同时在第三方平台上选择性竞争。",
        "our_overall_score": 7.8,
        "competitor_overall_score": 7.1,
    }
}

SCENARIO2_BATTLECARD = {
    "battlecard": {
        "our_strengths": [
            "品牌价值：SHEIN品牌全球认知度高于Temu，时尚属性带来品牌溢价10-15%",
            "供应链壁垒：小单快反模式，新品从设计到上架仅需7天（行业平均30天）",
            "用户体验领先：App体验、物流时效、退换货流程全面优于Temu",
            "品牌口碑：TrustPilot 4.2 vs Temu 3.5，质量信任度优势明显",
            "社交媒体影响力：Instagram粉丝3000万+，TikTok话题播放量远超Temu"
        ],
        "our_weaknesses": [
            "价格竞争力不足：同类商品价格高于Temu 10-30%，在消费降级趋势下承压",
            "品类局限性：时尚品类占比过高（70%+），难以抵御Temu的全品类攻势",
            "增速放缓：年增速降至25%（Temu 200%+），市场关注度被Temu分流"
        ],
        "competitor_strengths": [
            "极致性价比：同等商品价格低10-30%，加上补贴后价差更大",
            "增长势能：GMV年增200%+，全球扩张速度惊人",
            "全品类覆盖：1000万+SKU满足一站式购物需求",
            "社交裂变能力：用户获取成本仅为SHEIN的30%，拉新效率极高"
        ],
        "competitor_weaknesses": [
            "品牌形象弱：廉价感标签难以突破，客单价提升困难",
            "商品质量不稳定：品质参差不齐导致退货率高（25%+）",
            "政策风险巨大：de minimis关税豁免若取消将冲击商业模式",
            "商家关系脆弱：全托管模式剥夺商家话语权，品牌商家不愿入驻"
        ],
        "key_differentiators": [
            "品牌定位：SHEIN=时尚品牌 vs Temu=低价平台 → 长期价值不同",
            "供应链：SHEIN小单快反 vs Temu C2M大批量 → 灵活 vs 规模",
            "增长质量：SHEIN利润率转正 vs Temu年亏300亿 → 可持续性差异",
            "政策风险：SHEIN全球仓储布局分散风险 vs Temu依赖跨境小包 → 风险敞口差异",
            "用户黏性：SHEIN品牌粉丝复购60%+ vs Temu补贴依赖型消费 → 忠诚度差异"
        ],
        "objection_handling": {
            "Temu价格更低，用户都跑Temu了怎么办？": "低价确实吸引眼球，但时尚消费从来不只是价格战。Zara比Shein贵但活得好好的——因为消费者买的是时尚、是品牌认同、是购物体验。我们的策略是守住时尚品类的品牌护城河，同时在基础款上保持竞争力。数据显示SHEIN用户年均消费$150+ vs Temu $80+，说明品牌价值在持续变现。",
            "Temu增速200%+，SHEIN才25%，是不是说明模式有问题？": "增速比较要看基数和发展阶段。Temu从0到500亿当然快，但这是用年亏300亿换来的——每获得$1收入要补贴$0.6。这种模式能持续多久要看资本市场脸色。SHEIN的25%增速是在盈利前提下的，这才是健康的增长。",
        },
        "elevator_pitch": "SHEIN不是另一个电商平台，是全球最大的时尚品牌之一。我们的小单快反供应链能在7天内把Instagram热门趋势变成消费者衣橱里的衣服，这是亚马逊都做不到的速度。Temu做的是低价百货，我们做的是时尚品牌——两条赛道，不同的游戏规则。"
    }
}

SCENARIO2_REVIEW_FEEDBACK = {
    "review_feedback": {
        "overall_score": 8.5,
        "accuracy_score": 8.5,
        "completeness_score": 8.5,
        "citation_score": 8.0,
        "actionability_score": 9.0,
        "approved": True,
        "issues": [],
        "revision_instructions": "报告质量优秀。建议在答辩时重点对比Temu的监管风险与SHEIN的可持续增长模式。",
    }
}

SCENARIO2_CITATION_REPORT = {
    "citation_report": {
        "total_sources": 12,
        "verified_sources": 11,
        "broken_links": 0,
        "unreachable_sources": 1,
        "overall_reliability_score": 0.92,
        "missing_citations": [],
        "reliability_distribution": {"high": 7, "medium": 4, "low": 1},
        "source_list": [],
    }
}

SCENARIO2_AGENT_DECISION_LOGS = [
    {
        "agent_name": "monitor", "agent_role": "监控Agent", "phase": "execution",
        "step_number": 1, "reasoning": "爬取Temu官网+拼多多年报，检测到2处重大变更：GMV突破520亿美元(HIGH)、半托管模式上线(HIGH)。",
        "input_tokens": 350, "output_tokens": 150, "duration_ms": 680, "status": "completed",
    },
    {
        "agent_name": "research", "agent_role": "研究Agent", "phase": "execution",
        "step_number": 2, "reasoning": "5维度研究：财务维度获取GMV 520亿和亏损300亿数据；战略维度分析全托管→半托管转型；技术维度评估C2M和推荐系统；风险维度深度剖析三大合规挑战；市场维度对比SHEIN vs Temu差异化。",
        "input_tokens": 980, "output_tokens": 580, "duration_ms": 1720, "status": "completed",
    },
    {
        "agent_name": "fact_check", "agent_role": "交叉验证Agent", "phase": "execution",
        "step_number": 3, "reasoning": "交叉验证：11条结论中10条通过。GMV数据、半托管模式、欧盟DSA认定等关键结论均有可靠来源佐证。",
        "input_tokens": 0, "output_tokens": 0, "duration_ms": 40, "status": "completed",
    },
    {
        "agent_name": "compare", "agent_role": "对比Agent", "phase": "execution",
        "step_number": 4, "reasoning": "8维度对比：SHEIN综合7.8 vs Temu 7.1。Temu在定价维度(9.0 vs 7.5)和规模增速上显著领先；SHEIN在品牌口碑(8.0 vs 6.0)和用户体验(8.5 vs 7.0)上占优。",
        "input_tokens": 1300, "output_tokens": 800, "duration_ms": 1950, "status": "completed",
    },
    {
        "agent_name": "battlecard", "agent_role": "战术卡Agent", "phase": "execution",
        "step_number": 5, "reasoning": "生成战术卡：强调SHEIN品牌护城河+供应链壁垒，用Temu亏损换增长作为反击论点。2套异议处理话术直击客户核心疑虑。",
        "input_tokens": 750, "output_tokens": 520, "duration_ms": 1500, "status": "completed",
    },
    {
        "agent_name": "reviewer", "agent_role": "审查Agent", "phase": "execution",
        "step_number": 6, "reasoning": "审查通过：准确度8.5（数据源权威），完整度8.5（8维度全覆盖），引用8.0（12源中11个验证），可操作性9.0（异议处理话术实战价值极高）。综合8.5分。",
        "input_tokens": 550, "output_tokens": 260, "duration_ms": 1100, "status": "completed",
    },
    {
        "agent_name": "citation", "agent_role": "溯源Agent", "phase": "execution",
        "step_number": 7, "reasoning": "验证12个引用源：11个可达、1个不可达（初创企业数据报告）。总体可信度92%，来源分布：7个高可信、4个中可信、1个低可信。",
        "input_tokens": 280, "output_tokens": 180, "duration_ms": 480, "status": "completed",
    },
]


# ======================================================================
# SCENARIO 3: AI电商未来 — 各大平台AI能力对比
# ======================================================================

SCENARIO3_COMPETITOR = "阿里电商AI"

SCENARIO3_COMPARISON_MATRIX = {
    "comparison_matrix": {
        "competitor": "阿里电商AI",
        "dimensions": [
            {
                "dimension": "大模型能力", "our_score": 9.0, "competitor_score": 8.0,
                "notes": "字节豆包大模型在中文NLP和内容理解上领先，但阿里通义千问在电商垂直场景（商品描述生成、客服对话、搜索query理解）上有更深的行业积累。",
                "evidence": [{"source": "SuperCLUE评测", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "推荐算法", "our_score": 9.5, "competitor_score": 8.5,
                "notes": "字节推荐算法全球领先，抖音电商的转化率为行业标杆。阿里推荐在电商场景深耕多年，搜索推荐（「猜你喜欢」）有深厚积累，但在内容+电商融合推荐上字节更强。",
                "evidence": [{"source": "技术论文", "url": "", "confidence": 0.90}],
            },
            {
                "dimension": "AI内容生成", "our_score": 9.0, "competitor_score": 7.5,
                "notes": "字节即梦AI视频生成和豆包文本生成用户量级和效果均领先。阿里通义万相（图像生成）和通义千问有竞争力，但整体AIGC产品矩阵和用户触达不如字节。",
                "evidence": [{"source": "各产品评测", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "AI客服与对话", "our_score": 7.5, "competitor_score": 9.0,
                "notes": "阿里小蜜经过10年+电商客服场景打磨，在意图理解、多轮对话、问题解决率上行业领先。字节AI客服起步较晚，在电商场景的专业度有待提升。",
                "evidence": [{"source": "客户体验报告", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "AI供应链", "our_score": 6.5, "competitor_score": 9.0,
                "notes": "阿里菜鸟AI物流调度和犀牛智造C2M能力已规模化落地。字节在物流和供应链AI上几乎没有布局，这是字节电商AI的最大短板。",
                "evidence": [{"source": "行业分析", "url": "", "confidence": 0.90}],
            },
            {
                "dimension": "AI商家工具", "our_score": 7.0, "competitor_score": 8.5,
                "notes": "阿里生意参谋+万相台为商家提供从选品到投放的全链路AI工具。字节千川虽推荐能力强，但商家数据分析深度和AI经营建议不如阿里成熟。",
                "evidence": [{"source": "商家调研", "url": "", "confidence": 0.80}],
            },
            {
                "dimension": "AI基础设施", "our_score": 8.5, "competitor_score": 9.0,
                "notes": "阿里云提供从算力（GPU集群）到模型平台（百炼）的完整AI基础设施，且为第三方商家开放。字节火山引擎AI服务起步较晚，生态丰富度不如阿里云。",
                "evidence": [{"source": "云服务对比", "url": "", "confidence": 0.85}],
            },
            {
                "dimension": "AI人才密度", "our_score": 9.0, "competitor_score": 8.0,
                "notes": "字节AI人才（含研究员+工程师）约1.5万人，居国内互联网第一。阿里AI人才约8000人，但电商垂直领域经验更丰富。两者在人才储备上各有优势。",
                "evidence": [{"source": "LinkedIn/脉脉数据", "url": "", "confidence": 0.75}],
            },
        ],
        "overall_assessment": "字节（我方）在AI大模型、推荐算法、AIGC三大方向领先阿里电商AI，但在AI供应链、AI客服、AI商家工具等电商垂直应用上落后。综合来看字节的AI基础能力更强，阿里的AI电商落地更深。长期看字节AI能力的溢出效应将逐渐弥补电商场景的差距。",
        "our_overall_score": 8.1,
        "competitor_overall_score": 8.4,
    }
}


# ======================================================================
# 场景路由表
# ======================================================================

SCENARIO_MAP = {
    "scenario1": {
        "name": "直播电商三巨头 — 抖音电商 vs 快手电商",
        "competitor": SCENARIO1_COMPETITOR,
        "monitor": SCENARIO1_MONITOR_RESULTS,
        "research": SCENARIO1_RESEARCH_INSIGHTS,
        "factcheck": SCENARIO1_FACTCHECK_RESULTS,
        "comparison": SCENARIO1_COMPARISON_MATRIX,
        "battlecard": SCENARIO1_BATTLECARD,
        "review": SCENARIO1_REVIEW_FEEDBACK,
        "citation": SCENARIO1_CITATION_REPORT,
        "decision_logs": SCENARIO1_AGENT_DECISION_LOGS,
    },
    "scenario2": {
        "name": "跨境电商出海 — SHEIN vs Temu",
        "competitor": SCENARIO2_COMPETITOR,
        "monitor": SCENARIO2_MONITOR_RESULTS,
        "research": SCENARIO2_RESEARCH_INSIGHTS,
        "factcheck": SCENARIO2_FACTCHECK_RESULTS,
        "comparison": SCENARIO2_COMPARISON_MATRIX,
        "battlecard": SCENARIO2_BATTLECARD,
        "review": SCENARIO2_REVIEW_FEEDBACK,
        "citation": SCENARIO2_CITATION_REPORT,
        "decision_logs": SCENARIO2_AGENT_DECISION_LOGS,
    },
    "scenario3": {
        "name": "AI电商未来 — 各大平台AI能力对比",
        "competitor": SCENARIO3_COMPETITOR,
        "monitor": {
            "changes_detected": [
                {
                    "title": "阿里AI电商战略升级：通义千问全面赋能电商场景",
                    "summary": "阿里2026年宣布通义千问大模型全面整合进淘宝、天猫、1688等电商平台，覆盖商品描述生成、智能客服、个性化推荐、AI营销创意等场景。",
                    "severity": "HIGH",
                    "source_url": "https://www.alibabagroup.com",
                    "detected_at": _now(),
                }
            ]
        },
        "research": {
            "research_results": [
                {
                    "topic": "[strategic_moves] 各大平台AI电商战略对比",
                    "summary": "阿里：通义千问全面赋能电商全链路，核心优势在供应链AI和商家工具；字节：豆包大模型+推荐算法双轮驱动，优势在内容电商AI和AIGC；京东：言犀大模型聚焦供应链和客服，优势在物流AI和品质保障；拼多多：以C2M和AI定价为核心，技术投入相对低调。",
                    "key_findings": [
                        "阿里AI电商布局最全面，从供应链到消费者全链路覆盖",
                        "字节AI在内容电商和推荐算法上领先",
                        "京东AI聚焦供应链效率，差异化明确",
                        "拼多多AI以C2M和定价为核心，实用主义路线"
                    ],
                    "confidence": 0.85,
                    "sources": ["各公司官方公告", "行业分析报告"],
                }
            ]
        },
        "factcheck": {
            "fact_check_result": {
                "verified_count": 5, "unverified_count": 0, "conflicts": [],
                "overall_confidence": 0.90, "verification_summary": "全部结论验证通过。",
                "status": "verified",
            }
        },
        "comparison": SCENARIO3_COMPARISON_MATRIX,
        "battlecard": {
            "battlecard": {
                "our_strengths": [
                    "大模型能力：豆包大模型中文NLP能力领先，内容理解场景有天然优势",
                    "推荐算法：全球顶尖的推荐系统，内容+电商融合推荐领先行业",
                    "AIGC产品矩阵：即梦+豆包AI工具覆盖创作者全场景"
                ],
                "our_weaknesses": [
                    "电商AI落地深度不足：客服、供应链、商家工具缺少行业沉淀",
                    "AI基础设施商业化落后：火山引擎AI服务生态不如阿里云成熟"
                ],
                "competitor_strengths": [
                    "电商AI全链路覆盖：从供应链到销售全链路AI赋能",
                    "AI基础设施成熟：阿里云+百炼平台生态丰富"
                ],
                "competitor_weaknesses": [
                    "内容电商AI不足：推荐算法在内容+电商融合上落后于字节",
                    "AIGC用户规模小：AI内容工具用户量级远低于字节"
                ],
                "key_differentiators": [
                    "AI大模型：豆包 vs 通义千问 → 基础能力领先",
                    "推荐算法：内容电商推荐 vs 传统电商推荐 → 代际差距",
                    "AIGC生态：即梦+豆包 vs 通义万相 → 用户规模差距",
                    "电商场景：阿里10年积累 vs 字节4年 → 经验差距",
                    "基础设施：火山引擎 vs 阿里云 → 生态差距"
                ],
                "objection_handling": {
                    "阿里AI在电商场景更成熟啊？": "阿里在电商AI的落地深度确实领先，这是10年场景积累的结果。但AI竞争的核心是大模型的基础能力——谁的模型更强，谁就能更快地渗透到各个场景。豆包在中文NLP、多模态理解上的领先优势，会随着时间推移转化为电商场景的竞争力。就像OpenAI的GPT能力溢出到各行各业一样。"
                },
                "elevator_pitch": "AI电商的未来属于基础模型能力最强、推荐算法最精准、内容生态最丰富的平台。字节在这三个维度上都有结构性优势。电商场景的经验差距可以通过时间和投入弥补，但AI基础能力的差距是很难跨越的。"
            }
        },
        "review": {
            "review_feedback": {
                "overall_score": 8.7, "accuracy_score": 8.5, "completeness_score": 8.5,
                "citation_score": 8.5, "actionability_score": 9.0, "approved": True,
                "issues": [], "revision_instructions": "报告框架清晰，建议答辩时用此场景展示AI技术对比的深度视角。",
            }
        },
        "citation": {
            "citation_report": {
                "total_sources": 8, "verified_sources": 8, "broken_links": 0,
                "unreachable_sources": 0, "overall_reliability_score": 0.95,
                "missing_citations": [],
                "reliability_distribution": {"high": 6, "medium": 2, "low": 0},
                "source_list": [],
            }
        },
        "decision_logs": [
            {
                "agent_name": "research", "agent_role": "研究Agent", "phase": "execution",
                "step_number": 1, "reasoning": "分析阿里AI电商战略布局：通义千问赋能全链路，从供应链C2M到消费者AI客服均有覆盖。字节在内容电商AI上领先但电商场景深度不足。",
                "input_tokens": 800, "output_tokens": 450, "duration_ms": 1400, "status": "completed",
            },
        ],
    },
}


def get_scenario(scenario_id: str = "scenario1") -> dict:
    """获取指定场景的完整 Mock 数据集。"""
    return SCENARIO_MAP.get(scenario_id, SCENARIO_MAP["scenario1"])


def list_scenarios() -> list[dict]:
    """列出所有可用 Demo 场景。"""
    return [
        {"id": k, "name": v["name"], "competitor": v["competitor"]}
        for k, v in SCENARIO_MAP.items()
    ]
