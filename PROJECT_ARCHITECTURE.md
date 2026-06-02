# 多Agent竞品情报分析系统 — 项目架构文档 v4.0

> **文档目的**：新会话 / 新开发者仅需阅读本文档，即可 100% 接手本项目开发与竞品分析任务。
> **分析范围**：仅做客观梳理与总结，不修改、不补代码、不优化。
> **最后更新**：2026-06-01（ci-agent-final 合并完成，170+ 测试全通过）

---

# 阶段1：项目整体定位与竞品分析背景

## 1.1 一句话概括

**基于 LangGraph 12 节点 DAG 编排 + 三节点校验闭环（Reviewer → TargetedFix → Reviewer）+ 豆包 LLM 驱动的企业级竞品情报分析 SaaS 平台，将人工 2 天的竞品报告工作压缩为 AI 5 分钟全自动完成。**

## 1.2 产品属性

| 维度 | 属性 |
| --- | --- |
| **产品类型** | B2B 企业级 SaaS 工具 / 平台 |
| **目标用户** | 产品经理、销售团队、战略分析部门、竞争情报分析师 |
| **核心价值** | 效率提升 90%（2 天 → 5 分钟）、质量标准化（评分 ≥ 9/10）、业务落地性强（销售战术卡可直接使用） |
| **商业模式** | 内部工具 / 比赛项目（2026 字节 AI 全栈挑战赛 · Agent 智能体赛道），未商业定价 |

## 1.3 比赛背景

- **赛事**：2026 字节 AI 全栈挑战赛 · Agent 智能体赛道
- **核心目标**：展示"多 Agent 协作 + LLM 驱动 + 多模态分析 + Palantir Ontology 知识图谱 + 全链路可观测 + 知识库 RAG"在真实业务场景（竞品分析）中的落地能力
- **对标方向**：Crayon、Klue、Kompyte 等国际竞品情报 SaaS 产品
- **期望产出**：可运行的全栈系统 + React 可视化工作台 + 飞书消息推送 + 标准化报告导出 + 竞品关系图谱
- **当前评分**：86.5-88+ 分，A 级一等奖候选（满分 100）

## 1.4 竞品范围

| 竞品 | 差异化 | 类型 |
| --- | --- | --- |
| **Crayon** | 人工维护 + 看板模式，非 AI 自动生成 | 直接竞品 |
| **Klue** | 侧重销售赋能，本系统更侧重 Agent 自动分析 | 直接竞品 |
| **Kompyte** | 多源采集，本系统用 LLM 替代规则引擎 | 直接竞品 |
| **CompetitorLens** | 中科大参赛项目，6 Agent，MiniMax M2.7，自研 Harness 五层 | 比赛竞品 |
| ChatGPT / Claude + Prompt | 部分替代 Research Agent 功能 | 间接竞品 |
| SEMrush / SimilarWeb | 流量 / 市场数据维度（本系统暂未覆盖） | 间接竞品 |

---

# 阶段2：技术栈与架构全景

## 2.1 核心技术栈

| 类别 | 技术选型 | 版本 | 位置 |
| --- | --- | --- | --- |
| **语言后端** | Python 3.11+ | - | `python/` |
| **Web 框架** | FastAPI | ≥ 0.115 | `python/src/api/server.py` |
| **ASGI** | Uvicorn | ≥ 0.32 | 启动命令 |
| **API 网关** | CloudWeGo Hertz (Go) | v0.9.x | `gateway-hertz/` — 展示字节技术生态 |
| **Agent 编排** | LangGraph StateGraph | ≥ 0.2 | `python/src/graph/workflow.py` |
| **LLM 主 Provider** | 字节豆包 Doubao (Ark SDK) | doubao-seed-2.0-lite | `python/src/services/llm/` |
| **LLM 回退 Provider** | 通义千问 Qwen (ChatTongyi) | qwen-turbo | `python/src/services/llm/llm_factory.py` |
| **多模态视觉** | 豆包 VL API + 通义 VL (fallback) | - | `python/src/services/multimodal/doubao_vl_service.py` |
| **OCR（本地免费）** | PaddleOCR | ≥ 2.7.0 | `python/src/services/multimodal/ocr_service.py` |
| **音频转录（本地免费）** | OpenAI Whisper | ≥ 20240930 | `python/src/services/multimodal/whisper_audio_service.py` |
| **视频帧提取（本地免费）** | FFmpeg | - | `python/src/services/multimodal/video_frame_service.py` |
| **截图对比（本地免费）** | pixelmatch / diffimg | ≥ 0.3.0 | `python/src/services/multimodal/screenshot_diff_service.py` |
| **前端（主力）** | React 18 + Vite | latest | `frontend-react/` |
| **前端（备用）** | Streamlit | ≥ 1.30 | `frontend-streamlit/app.py` |
| **关系存储** | SQLite (sqlite3) | 内置 | `python/src/db/sqlite.py` |
| **向量存储** | FAISS-cpu + SentenceTransformer | latest | `python/src/services/rag/` |
| **嵌入模型** | paraphrase-multilingual-MiniLM-L12-v2 | 384 维 | `python/src/services/rag/retriever.py` |
| **数据校验** | Pydantic v2 | ≥ 2.9 | `python/src/models/schemas.py` |
| **配置管理** | python-dotenv + frozen dataclass + SQLite 动态覆盖 | ≥ 1.0 | `python/src/config.py` |
| **飞书通知** | 自定义 Bot (HMAC-SHA256 + 交互卡片) | - | `python/src/services/feishu/` |
| **网页抓取** | httpx + BeautifulSoup4 | ≥ 0.28 | `python/src/tools/web_scraper.py` |
| **搜索** | SerpAPI（含 demo fallback） | - | `python/src/tools/search_tool.py` |
| **文档导出** | python-docx (Word) | latest | `frontend-streamlit/app.py` |
| **容器化** | Docker + Docker Compose | - | `python/docker-compose.yml` + `gateway-hertz/Dockerfile` |

## 2.2 完整目录结构

```
competitive-intelligence-multi-agent/              # 项目根
│
├── README.md                                       # 项目介绍 + 快速启动
├── PROJECT_ARCHITECTURE.md                         # ★ 本文档（唯一入口文档）
├── .env.example                                    # 环境变量脱敏模板
├── .gitignore                                      # 分层忽略规则（密钥/运行时产物/归档）
├── LICENSE
├── requirements.txt                                # 根级依赖（= python/requirements.txt）
│
├── frontend-react/                                 # 【React 前端】主力前端，6 页面 SPA
│   ├── index.html                                  # ★ Vite 入口 HTML
│   ├── package.json                                # npm 依赖声明
│   ├── vite.config.js                              # Vite 构建配置
│   ├── Dockerfile                                  # 前端容器化
│   └── src/
│       ├── main.jsx                                # ★ React 入口
│       ├── App.jsx                                 # ★ 根组件（认证 → Landing → SystemShell）
│       ├── api/client.js                           # ★ API 客户端（JWT + 拦截器 + 认证）
│       ├── data/agentFlow.js                       # Agent 流配置数据
│       ├── styles/global.css                       # 全局样式
│       ├── pages/
│       │   ├── LandingPage.jsx                     # 登录页
│       │   ├── AgentWorkspace.jsx                  # ★ 竞品分析工作台（核心页面）
│       │   ├── SystemDashboard.jsx                 # 系统仪表盘
│       │   ├── KnowledgeBasePage.jsx               # 竞品知识库管理
│       │   ├── FeishuIntegrationPage.jsx           # 飞书集成配置
│       │   └── TraceabilityPage.jsx                # ★ 溯源追踪页（一键跳转原始数据源）
│       ├── components/
│       │   ├── system/SystemShell.jsx              # 系统外壳（侧边栏 + 路由）
│       │   ├── auth/AuthPanel.jsx                  # 认证面板
│       │   ├── agent/
│       │   │   ├── AgentDAG.jsx                    # DAG 可视化组件
│       │   │   ├── AgentOutputCard.jsx             # Agent 输出卡片
│       │   │   ├── AgentStreamPanel.jsx            # SSE 实时流面板
│       │   │   ├── AnalysisReport.jsx              # 分析报告渲染
│       │   │   └── SourceCitation.jsx              # 来源引用展示
│       │   └── common/
│       │       ├── MarkdownText.jsx                # Markdown 渲染
│       │       ├── MetricCard.jsx                  # 指标卡片
│       │       ├── ProgressBar.jsx                 # 进度条
│       │       ├── SectionHeader.jsx               # 区块标题
│       │       └── HighlightText.jsx               # 高亮文本
│       └── utils/agentMarkdown.js                  # Agent Markdown 工具
│
├── frontend-streamlit/                             # 【Streamlit 前端】备用单文件多页应用
│   └── app.py                                      # ★ 前端入口（7 页面，~1400 行）
│
├── frontend/                                       # 【Streamlit 前端】旧版（保留兼容）
│   └── app.py
│
├── gateway-hertz/                                  # 【Go API 网关】CloudWeGo Hertz v0.9（主力）
│   ├── main.go                                     # ★ Hertz 入口 + banner + 路由注册
│   ├── go.mod / go.sum                             # Go 模块
│   ├── Dockerfile                                  # 多阶段构建
│   ├── config/config.go                            # 环境变量配置
│   ├── handler/
│   │   ├── analysis.go                             # 分析代理 + SSE 逐块转发
│   │   ├── competitor.go                           # 竞品 CRUD 代理
│   │   ├── feishu.go                               # 飞书 Webhook 回调 + 200 容错
│   │   ├── health.go                               # 双层健康检查
│   │   └── infra.go                                # ★ GenericAPIProxy 全路由透传 + 可观测性代理
│   └── middleware/
│       ├── cors.go                                 # CORS
│       ├── logging.go                              # 请求日志
│       └── ratelimit.go                            # Token Bucket 限流
│
├── gateway/                                        # 【Go 网关】旧版 gin（保留兼容）
│   └── ...
│
├── python/                                         # 【Python 后端】核心引擎
│   ├── .env.example                                # 环境变量模板
│   ├── requirements.txt                            # Python 依赖（含多模态）
│   ├── Dockerfile                                  # Python 后端镜像
│   ├── docker-compose.yml                          # 编排: API + 网关 + Kafka + ES + Redis
│   ├── verify_merge_complete.py                    # ★ 12 项全量验证脚本
│   ├── verify_full_pipeline.py                     # 完整流水线验证
│   │
│   ├── src/                                        # ★ 后端源码
│   │   ├── config.py                               # ★ 全局配置中心
│   │   │   # 7 个 frozen dataclass + get_effective_*() 动态加载
│   │   │   # LLMConfig / DoubaoConfig / Kafka / ES / Redis / Notification / Alert / AppConfig
│   │   │
│   │   ├── api/server.py                           # ★★★ FastAPI 应用（~750 行，33+ 端点）
│   │   │   # 分析: /analyze /analyze/stream
│   │   │   # 竞品 CRUD: /competitors /competitors/{id}
│   │   │   # 历史: /analysis/records /analysis/records/{id}
│   │   │   # 系统配置: /api/config + /api/config/history/rollback/export/import
│   │   │   # 我方产品: /api/our-product
│   │   │   # 飞书: /api/v1/feishu/test /api/v1/feishu/feedback /api/v1/feishu/report-callback
│   │   │   # 可观测: /api/v1/infra/status/logs/events/dag/token/audit/anomalies
│   │   │   # RAG: /api/v1/rag/ingest/query/stats
│   │   │   # 系统: /api/system-info /api/config/test-notification
│   │   │   # ⚠ 安全: 限流 60 请求/分钟 + 请求体 50MB + 日志脱敏 + URL 白名单 + 超时 60s
│   │   │
│   │   ├── graph/workflow.py                       # ★★★ LangGraph 12 节点 DAG 状态机
│   │   │   # DAG: Monitor → Alert(→END) + Research(5维并行) → Multimodal
│   │   │   #      → FactCheck → Compare → Battlecard → Review
│   │   │   #      → [score<7: TargetedFix→Reviewer(loop×3)] → [partial_completion]
│   │   │   #      → Citation → Ontology → FeishuPush → END
│   │   │   # instrumented_node() 包装器：自动 EventBus + 决策日志 + Token 统计
│   │   │   # PipelineState：20+ 字段（含 ontology_graph / multimodal_data / fix_history）
│   │   │
│   │   ├── agents/                                 # ★ 业务层（9 Agent）
│   │   │   ├── monitor_agent.py                    # 网页变更监控 (SHA-256 + LLM 语义)
│   │   │   ├── alert_agent.py                      # 告警推送 (HIGH/CRITICAL 阈值过滤)
│   │   │   ├── research_agent.py                   # 5 维度并行研究 + RAG 注入
│   │   │   ├── factcheck_agent.py                  # ★ 交叉验证 (纯规则引擎, 0 LLM Token)
│   │   │   ├── compare_agent.py                    # 8 维度评分 + 我方产品数据 + FactCheck 降权
│   │   │   ├── battlecard_agent.py                 # 销售战术卡 + RAG 模板约束
│   │   │   ├── reviewer_agent.py                   # ★ 4 维度审查 (accuracy/completeness/citation/actionability)
│   │   │   ├── targeted_fix_agent.py               # ★ 定向修复 (精准修补 + 计数递增 + fix_history)
│   │   │   └── citation_agent.py                   # ★ 引用溯源 (URL 可达性 + 可信度评分)
│   │   │
│   │   ├── models/                                 # ★ 数据层
│   │   │   ├── schemas.py                          # ★★★ 全部 Pydantic 模型（~250 行）
│   │   │   │   # 业务模型: CompetitorChange / ResearchInsight / ComparisonMatrix / Battlecard
│   │   │   │   # 校验模型: FactCheckResult / ReviewFeedback / CitationReport / ReviewIssue
│   │   │   │   # 产品模型: OurProduct / FixEffectiveness
│   │   │   │   # 枚举: VerificationStatus / Severity / NodeStatus / EventType
│   │   │   └── ontology_schema.py                  # ★★★ Palantir Ontology 五层 Schema（~350 行）
│   │   │       # L1: OntologyCompetitor / OntologyProduct / OntologyBrand
│   │   │       # L2: OntologyFeature / OntologyArchitecture / OntologyPricing
│   │   │       # L3: OntologyMarketEvent / OntologyUserFeedback / OntologySentimentSignal
│   │   │       # L4: OntologyComparisonReport / OntologyScoreCard / OntologyInsight
│   │   │       # L5: OntologyAlertRule / OntologyMonitorTask / OntologyResponseAction
│   │   │       # 媒体: OntologyMultimodalAsset (image/video/audio/pdf)
│   │   │
│   │   ├── core/                                   # ★ 核心引擎
│   │   │   └── ontology_relation_graph.py          # ★ 20+ 种关系类型 + D3 图数据结构
│   │   │       # RelationType 枚举 (20 种语义关系)
│   │   │       # OntologyNode / OntologyRelation / OntologyGraph
│   │   │       # LAYER_COLORS 五色映射 + build_demo_graph()
│   │   │
│   │   ├── db/sqlite.py                            # ★★ SQLite CRUD（~550 行，6 张表）
│   │   │   # competitors / analysis_records / system_config / config_history
│   │   │   # our_product / feedback_records / analysis_snapshots / template_ranking
│   │   │
│   │   ├── services/                               # ★ 服务层（4 大模块）
│   │   │   ├── llm/                                # 【M1】LLM 服务
│   │   │   │   ├── doubao_client.py                # DoubaoLLM — Ark SDK 封装 + ainvoke 兼容
│   │   │   │   └── llm_factory.py                  # LLMFactory — doubao/tongyi 双 Provider + get_multimodal_llm()
│   │   │   ├── multimodal/                         # 【M2】多模态服务（6 大免费方案）
│   │   │   │   ├── doubao_vl_service.py            # 豆包多模态视觉分析（海报/截图/VL 理解）
│   │   │   │   ├── ocr_service.py                  # PaddleOCR 本地中文识别
│   │   │   │   ├── screenshot_diff_service.py      # 像素级 UI 改版差异检测
│   │   │   │   ├── video_frame_service.py          # FFmpeg 关键帧采样提取
│   │   │   │   ├── whisper_audio_service.py        # 本地 Whisper 音频转录 + 时间戳
│   │   │   │   ├── path_security.py                # 路径穿越攻击防护
│   │   │   │   └── image_preprocess.py             # 大图自动压缩（减少 LLM Token 消耗）
│   │   │   ├── feishu/                             # 【M3】飞书服务
│   │   │   │   ├── bot.py                          # HMAC-SHA256 签名 + 报告卡片/告警/测试
│   │   │   │   └── card_templates.py               # 3 套交互卡片模板 (report/alert/feedback)
│   │   │   └── rag/                                # 【M4】RAG 知识库
│   │   │       ├── core.py                         # CompetitorRAG 引擎 (ingest/query/batch/multi_recall)
│   │   │       ├── ingestion.py                    # L1 文档摄取 (load_dir + chunk + format)
│   │   │       ├── retriever.py                    # L2 向量索引 (FAISS + 嵌入 + 持久化 + BM25)
│   │   │       ├── rag_agent.py                    # RAGEnhancedAgent 基类 (augment_prompt + citations)
│   │   │       ├── report_builder.py               # 报告构建器
│   │   │       └── seed_kb.py                      # 知识库初始化脚本
│   │   │
│   │   ├── competitive_intelligence_framework.py   # 【M5】缺失数据预测与口碑分析框架
│   │   │   # 代理指标计算 + 预测模型 (RandomForest/GradientBoosting) + 口碑评估
│   │   │   # C/D 类竞品数据补全，降级到简化实现（无 sklearn 时）
│   │   │
│   │   ├── weight_fusion_engine.py                 # 【M6】多平台数据源权重融合引擎
│   │   │   # 4 个梯队分级 (官方/行业媒体/社交/UGC)
│   │   │   # 5 种冲突处理策略 (权威优先/多数投票/时效优先/加权平均/标记存疑)
│   │   │   # 贝叶斯可信度更新 + 时间衰减 + 多源一致性评分
│   │   │
│   │   ├── services/evolution/                     # 【M7】自进化引擎
│   │   │   ├── engine.py                           # EvolutionEngine 单例
│   │   │   ├── knowledge_base.py                   # SQLite 三层持久化
│   │   │   └── prompt_templates.py                 # 多模板策略 (4 Agent × 3 Prompt)
│   │   │
│   │   ├── mock/                                   # 【M8】Mock 模式（Demo 零失败保障）
│   │   │   ├── mode.py                             # MockContext 上下文管理器 + 运行时切换
│   │   │   ├── data.py                             # 3 个 Demo 场景完整预生成数据
│   │   │   └── generator.py                        # MockDataGenerator（完整 Pipeline + SSE 事件序列）
│   │   │
│   │   ├── infrastructure/                         # 【M9】可观测性（5 组件 + 统一 Hub）
│   │   │   ├── observability.py                    # ★ ObservabilityHub 单例 (5 组件统一入口)
│   │   │   ├── agent_logger.py                     # Agent 决策日志 (多维筛选 + 时序回溯 + 异常检测)
│   │   │   ├── event_bus.py                        # EventBus (事件发布 + 溯源 + SQLite 持久化)
│   │   │   ├── token_manager.py                    # TokenManager (动态配额 + 预估 + 节流)
│   │   │   ├── audit_system.py                     # AuditSystem (操作留痕 + ISO 27001 合规)
│   │   │   ├── dag_visualizer.py                   # DAGVisualizer (纯 HTML/SVG + 热力图)
│   │   │   ├── data_models.py                      # 基础设施 Pydantic 模型（~300 行）
│   │   │   └── main.py                             # FastAPI 路由 + Streamlit 嵌入 + Demo
│   │   │
│   │   ├── utils/                                  # ★ 安全防护工具
│   │   │   ├── log_mask.py                         # 敏感字段日志脱敏（API Key / Token 等自动打码）
│   │   │   └── url_security.py                     # URL 白名单校验（防 SSRF 攻击）
│   │   │
│   │   └── tools/                                  # 工具层
│   │       ├── web_scraper.py                      # 网页抓取 (httpx + BS4 + SHA-256 + tenacity)
│   │       ├── search_tool.py                      # SerpAPI 搜索 + Demo fallback
│   │       └── notification.py                     # Slack/钉钉/邮件多渠道通知
│   │
│   └── tests/                                      # ★ 测试（170+ 用例，全量通过）
│       ├── conftest.py                             # 共享 fixtures (LLMFactory Mock + DB 隔离 + TestClient)
│       ├── test_pipeline.py                        # Pydantic 模型测试
│       ├── test_core_paths.py                      # 核心路径测试
│       ├── test_infrastructure.py                  # 可观测性组件测试
│       ├── test_ontology.py                        # ★ Ontology 五层 Schema 测试
│       ├── test_security.py                        # ★ 5 层安全防护测试
│       ├── test_agents/                            # Agent 解析测试 (5 文件)
│       ├── test_api/test_server.py                 # API 端点测试
│       ├── test_db/test_sqlite.py                  # 数据库测试
│       ├── test_graph/test_workflow.py             # 工作流测试
│       ├── test_tools/                             # 工具层测试 (3 文件)
│       ├── test_integration/test_full_pipeline.py  # 集成测试
│       ├── test_feishu/test_bot.py                 # 飞书机器人测试
│       └── test_multimodal/test_path_security.py   # 多模态安全测试
│
├── knowledge-base-public/                          # ★ 公开知识库（13 个结构化 JSON 素材）
│   ├── README.md
│   ├── demo/demo_scenarios.json                    # Demo 场景数据
│   ├── rubrics/ecommerce_8dimensions_rubric.json    # 8 维度评分标准
│   ├── schemas/                                    # Schema 定义
│   │   ├── comparison_dimensions.json
│   │   └── product_schema.json
│   ├── industries/                                 # 行业知识
│   │   ├── livestream_ecommerce.json               # 直播电商
│   │   ├── crossborder_ecommerce.json              # 跨境电商
│   │   ├── social_ecommerce.json                   # 社交电商
│   │   └── instant_retail.json                     # 即时零售
│   ├── templates/                                  # 分析模板
│   │   ├── report_templates.json
│   │   ├── porter_five_forces.json                 # 波特五力模型
│   │   └── swot_ecommerce.json                     # SWOT 电商模板
│   ├── tactics/sales_tactics.json                  # 销售战术
│   └── terms/ecommerce_glossary.json               # 行业术语
│
├── docs/                                           # 文档 + 截图
│   ├── architecture.md                             # 原始设计稿
│   ├── deployment.md                               # 部署文档
│   └── images/                                     # 10+ 张截图
│
└── archive/                                        # 🚫 历史打包存档（不纳入 Git）
    ├── archive-20260601-ci-engineer-25-patches/     # 后端工程师 25+ 文件改进包
    └── archive-20260528-react-full-migration/       # 前端工程师 React 完整迁移包
```

## 2.3 分层架构（7 层）

```
┌──────────────────────────────────────────────────────────────────┐
│  接入层 (Gateway)  ← CloudWeGo Hertz :8080 (Go)                 │
│  14 路由显式代理 + GenericAPIProxy 全路由透传 + 3 中间件          │
│  GenericAPIProxy: h.Any("/api/v1/*path", ...) 兜底所有新路由      │
├──────────────────────────────────────────────────────────────────┤
│  展示层 (Presentation)  ← React 18 :5173 + Streamlit :8501      │
│  React 6 页面: 工作台/仪表盘/知识库/飞书/溯源/登录               │
│  Streamlit 7 页面: 备用单文件应用                                 │
├──────────────────────────────────────────────────────────────────┤
│  API 层 (Server)  ← FastAPI :8000 (Python)                      │
│  33+ REST 端点 + SSE 流式 + 5 层安全防护中间件                    │
├──────────────────────────────────────────────────────────────────┤
│  编排层 (Orchestration)  ← LangGraph StateGraph                 │
│  12 节点 DAG 并行编排 + 条件路由 + 反馈闭环                       │
├──────────────────────────────────────────────────────────────────┤
│  业务层 (Agents)  ← 9 个专业 Agent                              │
│  每个 Agent 统一使用 LLMFactory.get_llm("agent_name")           │
│  ResearchAgent / BattlecardAgent 额外接入 RAG 检索               │
│  CompareAgent 接入 03 方案口碑分析 + 权重融合引擎                 │
├──────────────────────────────────────────────────────────────────┤
│  服务层 (Services)  ← 4 大模块 + 多模态 + 03 方案               │
│  LLM/多模态/飞书/RAG/进化/融合/预测                              │
├──────────────────────────────────────────────────────────────────┤
│  数据层 (Data)  ← SQLite + FAISS + Pydantic                    │
│  6 张业务表 + 向量索引 + 完整 Schema 体系                        │
└──────────────────────────────────────────────────────────────────┘
```

## 2.4 数据流：完整请求链路

```
用户操作 → React 前端 (SSE 连接)
          → Hertz 网关 (:8080) GenericAPIProxy
          → FastAPI (:8000) /api/v1/analysis/stream
          → LangGraph 12 节点 DAG 编排
          → 9 Agent 顺序 + 并行执行
          → 各 Agent 调用 LLMFactory → Doubao ARK API
          → 结果经 FactCheck → Compare → Battlecard
          → Reviewer → TargetedFix ×3 闭环
          → Citation → Ontology → FeishuPush
          → SSE 逐节点实时推送 → React 前端渲染
```

## 2.5 关键依赖关系

| 核心能力 | 依赖库 | 位置 |
| --- | --- | --- |
| Agent 编排 | langgraph | workflow.py |
| LLM 调用 | volcengine-python-sdk (豆包 ARK) | doubao_client.py |
| 多模态 OCR | paddleocr + paddlepaddle | ocr_service.py |
| 音频转录 | openai-whisper | whisper_audio_service.py |
| 截图对比 | pixelmatch + diffimg | screenshot_diff_service.py |
| 向量检索 | faiss-cpu + sentence-transformers | retriever.py |
| 网页抓取 | httpx + beautifulsoup4 | web_scraper.py |
| 预测模型 | scikit-learn + statsmodels (可选) | competitive_intelligence_framework.py |
| 权重融合 | numpy + pandas | weight_fusion_engine.py |
| 飞书通知 | HMAC-SHA256 (标准库) | bot.py |

---

# 阶段3：业务与竞品分析逻辑

## 3.1 竞品分析模块

### 3.1.1 竞品数据来源

| 来源 | 说明 | 实现 |
| --- | --- | --- |
| **SerpAPI 实时搜索** | 5 维度并行搜索（财务/专利/技术/开源/战略） | `search_tool.py` |
| **网页抓取** | 竞品官网/新闻/社交媒体页面 | `web_scraper.py` |
| **RAG 知识库** | 13 个结构化 JSON 行业知识素材 | `knowledge-base-public/` |
| **多模态素材** | 本地截图/海报/视频帧/音频 | `multimodal/` 目录 |
| **Mock 数据** | 3 个 Demo 场景预生成数据 | `mock/data.py` |
| **用户手动录入** | 我方产品信息 / 竞品基础信息 | SQLite CRUD |

### 3.1.2 支持的分析维度

| 维度 | Agent | 方法 |
| --- | --- | --- |
| **功能对比** | CompareAgent | 8 维度评分矩阵 + 我方产品数据 |
| **市场情报** | ResearchAgent | 5 子维度并行搜索（财务/专利/技术/开源/战略） |
| **口碑分析** | ReputationAssessmentFramework | NPS 估算 + 情感趋势 + 痛点提取 |
| **定价对比** | OntologyPricing | 入口/中级/企业三级定价对比 |
| **技术架构** | OntologyArchitecture | 技术栈/云服务商/开源采用度 |
| **SWOT 分析** | BattlecardAgent | 优势/劣势/机会/威胁 |
| **销售战术** | BattlecardAgent | 杀手级问题 + 反驳话术 + 差异化亮点 |
| **视觉分析** | doubao_vl_service | 海报/截图 UI 模式识别 + 功能检测 |
| **数据可信度** | weight_fusion_engine | 4 梯队权重 + 贝叶斯更新 + 多源冲突检测 |

### 3.1.3 对比结果可视化

| 可视化形式 | 前端实现 | 数据来源 |
| --- | --- | --- |
| **对比矩阵表格** | AgentWorkspace.jsx | comparison_matrix |
| **SWOT 四象限** | AnalysisReport.jsx | battlecard.swot |
| **Ontology 关系图谱** | AgentDAG.jsx (D3/AntV) | ontology_graph |
| **Agent 执行 DAG 图** | AgentDAG.jsx | workflow 实时状态 |
| **SSE 实时进度条** | AgentStreamPanel.jsx | SSE 事件流 |
| **引用溯源列表** | SourceCitation.jsx | citation_report |
| **Word 报告导出** | Streamlit 备用 | python-docx 生成 |

## 3.2 核心页面 / 功能

### React 前端（主力，6 页面）

| 页面 | 路由 | 核心逻辑 | 数据来源 |
| --- | --- | --- | --- |
| **LandingPage** | `/` | JWT 登录认证，token 持久化 localStorage | `api/client.js` → FastAPI |
| **AgentWorkspace** | `/workspace` | ★ 核心分析页：选择竞品 → 启动分析 → SSE 实时进度 → 结果展示 | POST `/api/v1/analysis/stream` |
| **SystemDashboard** | `/dashboard` | 系统仪表盘：Token 用量/事件日志/决策记录 | GET `/api/v1/infra/*` |
| **KnowledgeBasePage** | `/knowledge` | RAG 知识库管理：上传/检索/统计 | POST `/api/v1/rag/ingest` |
| **FeishuIntegrationPage** | `/feishu` | 飞书集成：Webhook 配置/测试/反馈 | POST `/api/v1/feishu/test` |
| **TraceabilityPage** | `/traceability` | ★ 溯源追踪：分析报告 ID → 一键跳转原始数据源 | GET `/analysis/records/:id` |

### Streamlit 前端（备用，7 页面）

- 竞品分析工作台 → 竞品管理 → 我方产品 → 历史分析 → 系统配置 → 可观测中心 → 竞品知识库

## 3.3 编码约定与特殊逻辑

### 3.3.1 请求规范

| 规范项 | 实现 |
| --- | --- |
| **API 鉴权** | 可选 X-API-Key 中间件（环境变量 `ALLOWED_API_KEYS` 控制，未配置时跳过） |
| **跨域 CORS** | 环境变量 `CORS_ALLOWED_ORIGINS` 控制，默认 `*` |
| **限流** | 内存滑动窗口，每 IP 60 请求/分钟 |
| **请求体限制** | 50MB 上限（`content-length` 头校验） |
| **超时** | 全局 60 秒（`asyncio.wait_for`） |
| **错误处理** | 统一 JSON `{"ok": false, "error": "..."}` 格式，不泄露栈信息 |
| **SSE 流式** | `sse-starlette` EventSourceResponse，逐节点推送 |

### 3.3.2 状态管理

| 规范项 | 实现 |
| --- | --- |
| **React 全局状态** | localStorage JWT token + user + `useState` / `useEffect` |
| **Python 配置状态** | frozen dataclass（默认值）+ SQLite 动态覆盖 + `get_effective_*()` 合并 |
| **Agent 执行状态** | LangGraph PipelineState TypedDict，20+ 字段贯穿全链路 |
| **持久化** | SQLite 6 张表 + FAISS 向量索引 + 飞书反馈记录 |

### 3.3.3 样式方案

| 规范项 | 实现 |
| --- | --- |
| **React 样式** | 纯 CSS（`global.css`），无第三方 UI 库 |
| **Streamlit 样式** | Streamlit 原生组件 + 自定义 CSS |
| **主题** | 深色 / 浅色（CSS 变量控制） |

### 3.3.4 特殊逻辑

| 逻辑 | 位置 | 说明 |
| --- | --- | --- |
| **防伪闭环** | workflow.py `_after_review()` | Reviewer → TargetedFix 循环最多 3 次，3 次后标记 `partial_completion` 继续流程 |
| **并行研究** | workflow.py `research_node()` | `asyncio.gather()` 5 维度并行，单维度失败不影响其他 |
| **多模态降级** | multimodal/ | 豆包 VL → 通义 VL fallback，本地 OCR/Whisper 零 API 依赖 |
| **安全防护** | server.py + utils/ | 限流/脱敏/URL 白名单/大小限制/超时 5 层全链路 |
| **Mock 模式** | mock/mode.py | `MockContext` 上下文管理器，零外部依赖 3 秒生成全量 SSE 事件 |
| **自进化** | services/evolution/ | 反馈驱动 Prompt 模板评分 + 置信度调整 |
| **权重融合** | weight_fusion_engine.py | 4 梯队数据源 + 贝叶斯可信度 + 时间衰减 + 冲突检测 |
| **Ontology 图谱** | workflow.py `ontology_builder_node()` | 分析结果自动构建五层关系图谱，失败不阻塞主流程 |
| **飞书推送** | workflow.py `feishu_push_node()` | Citation 完成后自动推送，失败不阻塞主流程 |
| **Python 3.9+ 兼容** | 全局 | 所有 `str \| None` 改为 `Optional[str]`，无 3.10+ 独有语法 |

## 3.4 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/lijx-dev/competitive-intelligence-multi-agent.git
cd competitive-intelligence-multi-agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 ARK_API_KEY（豆包）和 DASHSCOPE_API_KEY（通义千问 fallback）

# 3. 安装 Python 依赖
cd python
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 4. 启动后端
uvicorn src.api.server:app --reload --port 8000

# 5. 启动 React 前端（新终端）
cd frontend-react
npm install
npm run dev                     # 访问 http://localhost:5173

# 6. 启动 Go 网关（可选，新终端）
cd gateway-hertz
go run main.go                  # 访问 http://localhost:8080

# 7. 运行全量验证
cd python
python verify_merge_complete.py
```

## 3.5 测试基线

| 指标 | 数值 |
| --- | --- |
| **测试用例总数** | 170+ |
| **通过率** | 100%（0 failed） |
| **Python 兼容性** | 3.9 / 3.10 / 3.11 / 3.12 全版本 |
| **覆盖模块** | 配置层 / 数据模型 / Ontology / DAG / 多模态 / LLM / 安全 / API / 数据库 / 工作流 / 集成 / 飞书 |
| **项目评分** | 86.5-88+ 分，A 级一等奖候选 |

---

> **文档结束** — 新会话直接读此文档即可 100% 接手本项目。