# 多Agent竞品情报分析系统 — 项目架构文档（全量分析版 v3.1）

> **文档目的**：新会话/新开发者仅需阅读本文档，即可 100% 接手本项目开发与竞品分析任务。
> **分析范围**：仅做客观梳理与总结，不修改、不补代码、不优化。
> **最后更新**：2026-05-21（M6 进化引擎 + M7 Mock模式 已接入）

---

# 阶段1：项目整体定位与竞品分析背景

## 1.1 一句话定位

**基于 LangGraph 12 节点 DAG 编排 + 三节点校验闭环 + 豆包 LLM 驱动的企业级竞品情报分析 SaaS 平台，将人工 2 天的竞品报告工作压缩为 AI 5 分钟全自动完成。**

## 1.2 产品属性

| 维度 | 属性 |
|------|------|
| **产品类型** | B2B 企业级 SaaS 工具/平台 |
| **目标用户** | 产品经理、销售团队、战略分析部门、竞争情报分析师 |
| **核心价值** | 效率提升 90%（2天→5分钟）、质量标准化（评分≥9/10）、业务落地性强（销售战术卡可直接使用） |
| **商业模式** | 内部工具 / 比赛项目（字节 AI 全栈挑战赛），未商业定价 |

## 1.3 比赛背景

- **赛事**：2026 字节 AI 全栈挑战赛 · Agent 智能体赛道
- **核心目标**：展示"多Agent协作 + LLM驱动 + 全链路可观测 + 知识库RAG"在真实业务场景（竞品分析）中的落地能力
- **对标方向**：Crayon、Klue、Kompyte 等国际竞品情报 SaaS 产品
- **期望产出**：可运行的全栈系统 + 可视化工作台 + 飞书消息推送 + 标准化报告导出

## 1.4 竞品范围

| 竞品 | 差异化 | 类型 |
|------|--------|------|
| **Crayon** | 人工维护 + 看板模式，非AI自动生成 | 直接竞品 |
| **Klue** | 侧重销售赋能，本系统更侧重 Agent 自动分析 | 直接竞品 |
| **Kompyte** | 多源采集，本系统用 LLM 替代规则引擎 | 直接竞品 |
| **CompetitorLens** | 中科大参赛项目，6 Agent，MiniMax M2.7，自研 Harness 五层 | 比赛竞品 |
| ChatGPT/Claude + Prompt | 部分替代 Research Agent 功能 | 间接竞品 |
| SEMrush / SimilarWeb | 流量/市场数据维度（本系统暂时未覆盖） | 间接竞品 |

---

# 阶段2：技术栈与架构全景

## 2.1 核心技术栈（v3.0 更新版）

| 类别 | 技术选型 | 版本 | 位置 |
|------|----------|------|------|
| **语言后端** | Python 3.11+ | - | `python/` |
| **Web框架** | FastAPI | ≥0.115 | `python/src/api/server.py` |
| **ASGI** | Uvicorn | ≥0.32 | 启动命令 |
| **API网关** | CloudWeGo Hertz (Go) | v0.9.x | `gateway/` — 展示字节技术生态 |
| **Agent编排** | LangGraph StateGraph | ≥0.2 | `python/src/graph/workflow.py` |
| **LLM主Provider** | 字节豆包 Doubao (Ark SDK) | doubao-seed-1-8-251228 | `python/src/services/llm/` |
| **LLM回退Provider** | 通义千问 Qwen (ChatTongyi) | qwen-turbo | `python/src/services/llm/llm_factory.py` |
| **前端** | Streamlit | ≥1.30 | `frontend/app.py` |
| **关系存储** | SQLite (sqlite3) | 内置 | `python/src/db/sqlite.py` |
| **向量存储** | FAISS-cpu + SentenceTransformer | latest | `python/src/services/rag/` |
| **嵌入模型** | paraphrase-multilingual-MiniLM-L12-v2 | 384维 | `python/src/services/rag/retriever.py` |
| **数据校验** | Pydantic v2 | ≥2.9 | `python/src/models/schemas.py` |
| **配置管理** | python-dotenv + frozen dataclass + SQLite动态覆盖 | ≥1.0 | `python/src/config.py` |
| **飞书通知** | 自定义 Bot (HMAC-SHA256 + 交互卡片) | - | `python/src/services/feishu/` |
| **网页抓取** | httpx + BeautifulSoup4 | ≥0.28 | `python/src/tools/web_scraper.py` |
| **搜索** | SerpAPI（含 demo fallback） | - | `python/src/tools/search_tool.py` |
| **文档导出** | python-docx (Word) | latest | `frontend/app.py` |
| **容器化** | Docker + Docker Compose | - | `python/docker-compose.yml` + `gateway/Dockerfile` |

## 2.2 完整目录结构（v3.0）

```
competitive-intelligence-multi-agent/              # 项目根
│
├── README.md                                       # 项目介绍 + 快速启动
├── PROJECT_ARCHITECTURE.md                         # ★ 本文档
├── requirements.txt                                # 根级依赖（= python/requirements.txt）
├── .env                                            # ★ 环境变量(含ARK_API_KEY等，gitignore)
├── .env.example                                    # 环境变量模板
├── .gitignore
├── LICENSE
│
├── frontend/                                       # 【Streamlit 前端】单文件多页应用
│   └── app.py                                      # ★ 前端入口（7页面，~1400行）
│       # 页面: 竞品分析工作台 → 竞品管理 → 我方产品 → 历史分析
│       #       → 系统配置 → 可观测中心 → 竞品知识库
│
├── gateway/                                        # 【Go API 网关】CloudWeGo Hertz v0.9
│   ├── main.go                                     # ★ Hertz 入口 + banner
│   ├── go.mod / go.sum                             # Go 模块
│   ├── Dockerfile                                  # 多阶段构建
│   ├── config/config.go                            # 环境变量配置
│   ├── handler/                                    # 5 个处理器
│   │   ├── analysis.go                             # 分析代理 + SSE 逐块转发
│   │   ├── competitor.go                           # 竞品 CRUD 代理
│   │   ├── feishu.go                               # 飞书 Webhook 回调 + 200容错
│   │   ├── health.go                               # 双层健康检查
│   │   └── infra.go                                # 可观测性 + 报告代理
│   └── middleware/                                 # 3 个中间件
│       ├── cors.go                                 # CORS
│       ├── logging.go                              # 请求日志
│       └── ratelimit.go                            # Token Bucket 限流
│
├── python/                                         # 【Python 后端】
│   ├── .env.example                                # 环境变量模板
│   ├── requirements.txt                            # Python 依赖
│   ├── Dockerfile                                  # Python 后端镜像
│   ├── docker-compose.yml                          # 编排: API + 网关 + Kafka + ES + Redis
│   ├── ci_system.db                                # SQLite 数据库 (gitignore)
│   ├── data/rag_index/                             # FAISS 向量索引 (gitignore)
│   │
│   ├── src/                                        # ★ 后端源码
│   │   ├── __init__.py
│   │   ├── config.py                               # ★ 全局配置中心
│   │   │   # 6 个 frozen dataclass + get_effective_*() 动态加载
│   │   │   # LLMConfig / DoubaoConfig / Kafka / ES / Redis / Notification / Alert
│   │   │
│   │   ├── api/                                    # ★ API 层（路由入口）
│   │   │   ├── __init__.py
│   │   │   └── server.py                           # ★★★ FastAPI 应用（~750行，33端点）
│   │   │       # 分析: /analyze /analyze/stream
│   │   │       # 竞品CRUD: /competitors + /competitors/{id}
│   │   │       # 历史: /analysis/records + /analysis/records/{id}
│   │   │       # 系统配置: /api/config + /api/config/history/rollback/export/import
│   │   │       # 我方产品: /api/our-product
│   │   │       # 飞书: /api/v1/feishu/test /api/v1/feishu/feedback
│   │   │       # 可观测: /api/v1/infra/status/logs/events/dag/token/audit/anomalies
│   │   │       # RAG: /api/v1/rag/ingest/query/stats
│   │   │       # 系统: /api/system-info /api/config/test-notification
│   │   │
│   │   ├── graph/                                  # ★ 编排层（LangGraph 12 节点 DAG）
│   │   │   ├── __init__.py
│   │   │   └── workflow.py                         # ★★★ LangGraph 状态机
│   │   │       # DAG: monitor → alert(→END) + research → fact_check
│   │   │       #      → compare → battlecard → reviewer
│   │   │       #      → targeted_fix(loop×3) → citation → feishu_push → END
│   │   │       # instrumented_node() 包装器：自动 EventBus + 决策日志 + Token 统计
│   │   │       # PipelineState：15 字段 (含 our_product_info / fact_check_result / 等)
│   │   │
│   │   ├── agents/                                 # ★ 业务层（9 Agent）
│   │   │   ├── __init__.py                         # 统一导出
│   │   │   ├── monitor_agent.py                    # 网页变更监控 (SHA-256 + LLM 语义)
│   │   │   ├── alert_agent.py                      # 告警推送 (HIGH/CRITICAL 阈值过滤)
│   │   │   ├── research_agent.py                   # 5 维度并行研究 + RAG 注入
│   │   │   ├── factcheck_agent.py                  # ★ 交叉验证 (纯规则引擎, 0 LLM Token)
│   │   │   ├── compare_agent.py                    # 8 维度评分 + 我方产品数据 + FactCheck 降权
│   │   │   ├── battlecard_agent.py                 # 销售战术卡 + RAG 模板约束
│   │   │   ├── reviewer_agent.py                   # ★ 4 维度审查 (accuracy/completeness/citation/actionability)
│   │   │   ├── targeted_fix_agent.py               # ★ 定向修复 (精准修补 + 计数递增)
│   │   │   └── citation_agent.py                   # ★ 引用溯源 (URL 可达性 + 可信度评分)
│   │   │       # 每个 Agent 统一使用 LLMFactory.get_llm("agent_name")
│   │   │       # ResearchAgent / BattlecardAgent 额外接入 RAG 检索
│   │   │
│   │   ├── models/                                 # ★ 数据层
│   │   │   ├── __init__.py
│   │   │   └── schemas.py                          # ★★★ 全部 Pydantic 模型（~250行）
│   │   │       # 业务模型: CompetitorChange / ResearchInsight / ComparisonMatrix / Battlecard
│   │   │       # 校验模型: FactCheckResult / ReviewFeedback / CitationReport / ReviewIssue
│   │   │       # 产品模型: OurProduct
│   │   │       # 枚举: VerificationStatus / Severity / NodeStatus / EventType
│   │   │
│   │   ├── db/                                     # ★ 持久化层
│   │   │   ├── __init__.py
│   │   │   └── sqlite.py                           # ★★ SQLite CRUD（~550行，6张表）
│   │   │       # competitors / analysis_records / system_config / config_history
│   │   │       # our_product / feedback_records
│   │   │
│   │   ├── services/                               # ★ 服务层（3大模块）
│   │   │   ├── __init__.py
│   │   │   ├── llm/                                # 【M1】LLM 服务
│   │   │   │   ├── __init__.py                     # 导出 LLMFactory
│   │   │   │   ├── doubao_client.py                # DoubaoLLM — Ark SDK 封装 + ainvoke 兼容
│   │   │   │   └── llm_factory.py                  # LLMFactory — doubao/tongyi 双 Provider
│   │   │   ├── feishu/                             # 【M2】飞书服务
│   │   │   │   ├── __init__.py                     # 导出 FeishuBot
│   │   │   │   ├── bot.py                          # HMAC-SHA256 签名 + 报告卡片/告警/测试
│   │   │   │   └── card_templates.py               # 3 套交互卡片模板 (report/alert/feedback)
│   │   │   └── rag/                                # 【M6】RAG 知识库 (L1+L2 MVP)
│   │   │       ├── __init__.py                     # 导出 CompetitorRAG / DocumentLoader / Retriever / RAGEnhancedAgent
│   │   │       ├── core.py                         # CompetitorRAG 引擎 (ingest/query/batch/multi_recall)
│   │   │       ├── ingestion.py                    # L1 文档摄取 (load_dir + chunk + format)
│   │   │       ├── retriever.py                    # L2 向量索引 (FAISS + 嵌入 + 持久化 + BM25)
│   │   │       ├── rag_agent.py                    # RAGEnhancedAgent 基类 (augment_prompt + citations)
│   │   │       └── seed_kb.py                      # 知识库初始化脚本
│   │   │
│   │   │
│   │   ├── evolution/                              # 【M6】自进化引擎（反馈驱动策略调整）
│   │   │   ├── __init__.py                         # 导出 EvolutionEngine / 模板函数
│   │   │   ├── engine.py                           # EvolutionEngine 单例（分析留存+反馈+置信度调整+模板推荐）
│   │   │   ├── knowledge_base.py                   # SQLite 三层持久化（快照+反馈+模板表现）
│   │   │   └── prompt_templates.py                 # 多模板策略（4 Agent × 3 Prompt，加权随机+评分调优）
│   │   │
│   │   ├── mock/                                   # 【M7】Mock 模式（Demo 零失败保障）
│   │   │   ├── __init__.py                         # 导出 is_mock_mode / MockDataGenerator
│   │   │   ├── mode.py                             # MockContext 上下文管理器 + 运行时切换
│   │   │   ├── data.py                             # 3 个 Demo 场景完整预生成数据（直播电商/跨境电商/AI电商）
│   │   │   └── generator.py                        # MockDataGenerator（完整Pipeline+SSE事件序列生成）
│   │   ├── infrastructure/                         # 【M5】可观测性（5 组件 + 统一 Hub）
│   │   │   ├── __init__.py
│   │   │   ├── data_models.py                      # ★ 基础设施 Pydantic 模型（~300行）
│   │   │   │   # AgentDecisionLog / DAGSnapshot / BusEvent / TokenQuota / AuditAction / AlertRule
│   │   │   ├── agent_logger.py                     # Agent 决策日志 (多维筛选 + 时序回溯 + 异常检测 + 导出)
│   │   │   ├── event_bus.py                        # EventBus (事件发布 + 溯源 + SQLite 持久化 + 告警)
│   │   │   ├── token_manager.py                    # TokenManager (动态配额 + 预估 + 节流 + 趋势报告)
│   │   │   ├── audit_system.py                     # AuditSystem (操作留痕 + 合规 + ISO 27001 导出)
│   │   │   ├── dag_visualizer.py                   # DAGVisualizer (纯 HTML/SVG + 热力图 + 节点交互)
│   │   │   ├── observability.py                    # ★ ObservabilityHub 单例 (5 组件统一入口 + 事件发布)
│   │   │   └── main.py                             # FastAPI 路由 + Streamlit 嵌入 + Demo
│   │   │
│   │   └── tools/                                  # 工具层
│   │       ├── __init__.py
│   │       ├── web_scraper.py                      # 网页抓取 (httpx + BS4 + SHA-256 + tenacity)
│   │       ├── search_tool.py                      # SerpAPI 搜索 + Demo fallback
│   │       └── notification.py                     # Slack/钉钉/邮件多渠道通知
│   │
│   └── tests/                                      # 测试（110用例 / 104 pass）
│       ├── conftest.py                             # 共享 fixtures (LLMFactory Mock + DB隔离 + TestClient)
│       ├── test_pipeline.py                        # 原 Pydantic 模型测试 (4)
│       ├── test_infrastructure.py                  # 可观测性组件测试 (24) ★
│       ├── test_tools/                             # 工具层测试 (29)
│       ├── test_db/                                # 数据库测试 (13)
│       ├── test_api/                               # API 端点测试 (15)
│       ├── test_agents/                            # Agent 解析测试 (19)
│       ├── test_graph/                             # 工作流测试 (8)
│       └── test_integration/                       # 集成测试 (3, 模型激活后恢复)
│
├── docs/                                           # 文档 + 截图
│   ├── architecture.md                             # 原始设计稿
│   ├── deployment.md
│   └── images/                                     # 10+ 张截图
│
├── COMPETITIVE_ANALYSIS_REPORT.md                  # 【调研报告】竞品开源项目深度分析
├── RAG_ARCHITECTURE_REPORT.md                      # 【调研报告】RAG 四层架构可行性调研
└── 产品经理汇报报告/                                # 【业务需求】PM 产出（不在 Git 中提交）
```

## 2.3 分层架构（7 层）

```
┌──────────────────────────────────────────────────────────────┐
│  接入层 (Gateway)  ← CloudWeGo Hertz :8080 (Go)             │
│  14 路由代理 + SSE 逐块转发 + 3 中间件                        │
├──────────────────────────────────────────────────────────────┤
│  展示层 (Presentation)  ← Streamlit :8501 (Python)           │
│  7 页面单页应用 + SSE 实时进度 + Word 导出 + DAG 可视化         │
├──────────────────────────────────────────────────────────────┤
│  API 网关层 (API Gateway)  ← FastAPI :8000                  │
│  33 端点 - 分析/竞品/配置/可观测/飞书/RAG/系统               │
├──────────────────────────────────────────────────────────────┤
│  编排层 (Orchestration)  ← LangGraph StateGraph             │
│  12 节点 DAG + instrumented_node 自动埋点                   │
├──────────────────────────────────────────────────────────────┤
│  业务层 (Agents)  ← 9 Agent + RAG 增强                       │
│  LLMFactory.get_llm() 统一入口 + RAGEnhancedAgent 知识注入    │
├──────────────────────────────────────────────────────────────┤
│  服务层 (Services)  ← LLM / Feishu / RAG / Infrastructure   │
│  3 服务模块 + 5 可观测组件 + ObservabilityHub 单例             │
├──────────────────────────────────────────────────────────────┤
│  基础设施层  ← SQLite + FAISS + httpx + BS4 + SerpAPI +     │
│               python-docx + tenacity                        │
└──────────────────────────────────────────────────────────────┘
```

## 2.4 架构核心数据流

```
用户输入竞品+URLs → POST /analyze/stream (SSE)
  → FastAPI lifespan 初始加载 our_product_info
  → PipelineState{competitor, urls, our_product_info, ...}
  → LangGraph 12 节点 DAG:

  1. Monitor   — 爬取网页 → SHA-256 Hash 对比 → LLM 变更分析
  2. ══════════ 并行 ══════════
     Alert     — HIGH/CRITICAL 告警 → Slack/钉钉/飞书推送 → END
     Research  — SerpAPI 搜索 + RAG 知识库检索 → LLM 5维度分析
  3. FactCheck — 纯规则交叉验证 Monitor vs Research → verified/unverified 标记
  4. Compare   — 8维度评分 (our: 我方产品数据 / competitor: Research+FackCheck)
  5. Battlecard— 销售战术卡 (5项约束) + RAG 模板注入
  6. Reviewer  — 4维度审查 (accuracy/completeness/citation/actionability)
  7. ══════════ 循环 ══════════
     TargetedFix — score<7 → 精准修补 → 返回 Reviewer (最多3次)
  8. Citation  — URL 可达性 + 可信度评分 + 缺失引用检测
  9. FeishuPush— 飞书消息卡片推送（不影响主流程）→ END

  → SSE Event Stream → 前端 st.expander 实时渲染
  → 自动存入 SQLite analysis_records 表
  → 可观测中心自动写入决策日志 + EventBus + Token记录
```

## 2.5 API 端点全清单（49 个路由，含进化+MOCK 端点）

### 分析类（2）
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/analyze` | 同步全流程分析（不推荐，耗时较长） |
| POST | `/analyze/stream` | ★ SSE 流式分析（推荐，实时进度） |

### 竞品 CRUD（4）
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/competitors/all` | 竞品列表 |
| POST | `/competitors` | 新增竞品 |
| PUT | `/competitors/{id}` | 更新竞品（已知Bug: 缺 created_at） |
| DELETE | `/competitors/{id}` | 删除竞品 |
| GET | `/competitors` | 遗留 Demo 端点 |

### 历史分析（2）
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/analysis/records` | 历史列表（可按 competitor_id 筛选） |
| GET | `/analysis/records/{id}` | 分析报告详情 |

### 系统配置（8）
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取所有配置（含默认值） |
| PUT | `/api/config` | 批量保存配置（alert/notif/llm/pipeline） |
| POST | `/api/config/test-notification` | 测试通知渠道 |
| POST | `/api/config/reset-llm` | 重置 LLM 为默认值 |
| GET | `/api/config/history` | 版本历史（按 key 筛选） |
| POST | `/api/config/rollback` | 回滚到指定版本 |
| GET | `/api/config/export` | 导出配置 JSON |
| POST | `/api/config/import` | 从 JSON 导入配置 |

### 我方产品（2）
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/our-product` | 获取我方产品信息 |
| PUT | `/api/our-product` | 更新我方产品（compare_agent 基于此评分） |

### 飞书 Bot（3）
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/feishu/test` | 测试飞书推送卡片 |
| POST | `/api/v1/feishu/feedback` | 飞书卡片按钮回调（confirm/correct） |
| GET | `/api/v1/feishu/feedback` | 获取反馈记录 |

### 可观测性 & 基础设施（11）
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/infra/status` | 系统整体状态（DAG/Token/Agents/Events） |
| GET | `/api/v1/infra/decision-logs` | 决策日志（agent/phase/anomaly 筛选） |
| GET | `/api/v1/infra/decision-logs/timeline` | 时序回溯 |
| GET | `/api/v1/infra/token-usage` | Token 用量（按 Agent 统计） |
| GET | `/api/v1/infra/token-quota` | Token 配额状态 |
| GET | `/api/v1/infra/events` | 事件总线列表（type/source 筛选） |
| GET | `/api/v1/infra/events/{id}/trace` | 事件溯源链路 |
| GET | `/api/v1/infra/dag-snapshot` | DAG 快照 JSON |
| GET | `/api/v1/infra/dag-svg` | DAG HTML/SVG（可嵌入式） |
| GET | `/api/v1/infra/audit-logs` | 审计日志（action/operator 筛选） |
| GET | `/api/v1/infra/anomalies` | 异常检测报告（Agent+审计+Token） |

### RAG 知识库（3）
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/rag/ingest` | 手动重建知识库索引 |
| POST | `/api/v1/rag/query` | RAG 检索（industry/doc_type 过滤） |
| GET | `/api/v1/rag/stats` | 知识库统计 |

### 系统自进化（4，M6 反馈驱动策略调整）
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/evolution/feedback` | 提交人类反馈（确认正确/标记错误） |
| GET | `/api/v1/evolution/stats` | 进化统计：快照数/验证率/准确率趋势/模板排行 |
| GET | `/api/v1/evolution/snapshots` | 分析快照历史（?competitor=&dimension=&agent_name=） |
| GET | `/api/v1/evolution/templates` | 模板性能排行（按 performance_score 降序） |

### Mock 模式（2，M7 Demo 零失败保障）
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/mock/status` | 当前 Mock 状态 + 可用场景列表 |
| POST | `/api/v1/mock/toggle` | 运行时切换 Mock 模式 {enabled, scenario} |

### 系统信息（1）
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/system-info` | Python/平台/内存/CPU/DB 统计 |

---

# 阶段3：业务与竞品分析逻辑

## 3.1 竞品分析模块

### 3.1.1 竞品数据来源

| 来源 | 获取方式 | 绑定 Agent |
|------|----------|------------|
| **用户输入 URL** | 前端表单 → `monitor_urls` 字段 | Monitor Agent |
| **自动生成 URL** | 中文名→英文域名映射 + pricing/blog/careers 子页面 | Monitor Agent |
| **网页抓取** | httpx + BS4 → SHA-256 Hash → LLM 语义分析（tenacity 3次重试） | Monitor Agent |
| **搜索** | SerpAPI (web_search + news_search) + Demo fallback | Research Agent |
| **RAG 知识库** | FAISS 向量检索 → Top-K 行业知识 + 评分锚定 → 注入 Prompt | Research / Battlecard |
| **我方产品** | SQLite our_product 表 → PipelineState.our_product_info | Compare Agent |
| **LLM 生成** | 豆包 Doubao (Ark SDK) / 通义千问 (ChatTongyi 回退) | 全部 Agent |
| **历史数据** | SQLite analysis_records 表 | 历史分析页面 |

### 3.1.2 12 节点 DAG 分析维度全景表

| 节点 | 分析维度 | 评分方式 | 输出 |
|------|----------|----------|------|
| **Monitor** | 定价变化/产品功能/招聘信号/新闻动态 | 严重程度 LOW→CRITICAL | `CompetitorChange[]` |
| **Alert** | HIGH/CRITICAL 阈值过滤 | 多渠道推送 | `Alert[]`→Slack/钉钉/飞书 |
| **Research** | 财务/专利/技术博客/开源/战略 (5维度并行) | 置信度 0-1 + RAG 知识增强 | `ResearchInsight[]` |
| **FactCheck** | ★ Monitor vs Research 交叉验证 | verified/unverified (纯规则) | `FactCheckResult` |
| **Compare** | 产品功能/定价/UX/市场/评价/技术/生态/支持 | 0-10 分 (我方产品数据 + FactCheck降权) | `ComparisonMatrix` |
| **Battlecard** | 优劣势/差异化/异议处理/电梯演讲 | RAG 模板约束 (精确5+3 items) | `Battlecard` |
| **Reviewer** | ★ accuracy / completeness / citation / actionability | 4 维度评分 + Fix指令 | `ReviewFeedback` |
| **TargetedFix** | ★ 精准修补（仅修改问题字段） | 自动计数 `targeted_fix_count` | 修补后的 `Battlecard` |
| **Citation** | ★ URL 可达性 + 可信度评分 | 域名评分 (官网 1.0 → 论坛 0.3) | `CitationReport` |
| **FeishuPush** | ★ 飞书消息卡片推送 | 不阻塞主流程 | `feishu_push_status` |

### 3.1.3 RAG 知识库四层架构

| 层级 | 名称 | 存储内容 | 状态 |
|------|------|----------|------|
| **L1** | 基础事实层 | 网页爬取快照 / 搜索结果缓存 | 已设计，待实现 |
| **L2** | 行业知识层 | ★ 电商 4 子行业 KB (23文档→139 chunks) | ✅ MVP 已实现 |
| **L3** | 分析方法论层 | 评分锚定 / SWOT 框架 / 战术卡模板 | 已设计，待实现 |
| **L4** | 报告生成层 | 5 类报告模板 / 术语表 | 已设计，待实现 |

### 3.1.4 分析结果可视化

| 可视化方式 | 前端实现 | 说明 |
|------------|----------|------|
| **对比矩阵** | `st.columns` 三列布局 + metric 组件 | 8 维度 × (我方/竞品) |
| **SWOT 式卡片** | 双列布局 + 无序列表 | Battlecard Tab |
| **研究洞察** | `st.expander` 可折叠 + bullet list | 按 topic 分组 |
| **变更监控** | 文本列表 + 严重程度标签 | severity 颜色标注 |
| **质量审查报告** | **新增 Tab** 4 维度评分卡片 + issue 展开 | 精确到字段路径 |
| **引用溯源报告** | **新增 Tab** 可信度进度条 + 缺失引用列表 | Citation 验证结果 |
| **Word 报告导出** | python-docx 结构化 .docx | 含全部 Tab 内容 |
| **DAG 实时可视化** | 纯 HTML/CSS/JS SVG 嵌入 st.components.v1.html | 12 节点 + 热力图 |
| **知识库检索** | 搜索框 + 置信度排序 + 来源展示 | RAG 知识库页面 |

---

## 阶段4：编码约定与开发规范

### 4.1 新增 Agent 的标准写法

```python
# 1. 文件: python/src/agents/new_agent.py
from ..services.llm import LLMFactory          # ★ 统一 LLM 入口
from ..services.rag.rag_agent import RAGEnhancedAgent  # 如需 RAG

class NewAgent:
    def _get_llm(self):
        return LLMFactory.get_llm("new_agent")  # ★ agent_name 唯一标识

    async def __call__(self, state: dict) -> dict:
        """LangGraph node — 固定签名 state:dict → dict"""
        ...
        return {"output_key": output_data}

# 2. 注册到 agents/__init__.py
from .new_agent import NewAgent

# 3. 注册到 workflow.py
from ..agents.new_agent import NewAgent
new_agent = NewAgent()
graph.add_node("new_agent", instrumented_node("new_agent", new_agent))
```

### 4.2 新增 API 端点的标准写法

```python
# 在 server.py 中
class NewRequest(BaseModel):
    """请求体 — Pydantic v2"""
    field1: str = Field(default="")
    field2: int = Field(default=0, ge=0)

@app.post("/api/v1/new-endpoint", summary="功能简述")
async def api_new_endpoint(req: NewRequest):
    """详细说明。异常返回 HTTPException。"""
    try:
        result = some_function(req.field1, req.field2)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
```

### 4.3 新增前端页面的标准写法

```python
# 1. 侧边栏注册（~L76）
page = st.radio("功能导航", ["现有页面1", ..., "新页面名称"])

# 2. 页面代码（末尾追加）
elif page == "新页面名称":
    st.header("📌 页面标题")
    st.caption("页面描述")

    service_online = check_health()
    if not service_online:
        st.error("❌ 后端服务未启动")
        st.stop()

    @st.cache_data(ttl=10)
    def fetch_page_data():
        try:
            resp = requests.get(f"{API_BASE_URL}/api/xxx", timeout=5)
            return resp.json() if resp.status_code == 200 else {}
        except:
            return {}

    data = fetch_page_data()
    # ... 渲染逻辑 ...
```

### 4.4 新增数据库表的步骤

```python
# 1. 在 sqlite.py 的 init_db() 中 CREATE TABLE IF NOT EXISTS
# 2. 追加 CRUD 函数（命名: create_xxx / get_all_xxx / update_xxx / delete_xxx）
# 3. JSON 字段使用 json.loads/dumps 序列化
# 4. 使用 check_same_thread=False 避免 FastAPI 线程阻塞
```

### 4.5 LLM 调用规范

```python
# ★ 所有 Agent 统一通过 LLMFactory 获取 LLM（不要直接 import ChatTongyi）
from ..services.llm import LLMFactory

llm = LLMFactory.get_llm("agent_name")  # provider = doubao(主) / tongyi(回退)
response = await llm.ainvoke([SystemMessage(content=prompt), HumanMessage(content=user_msg)])
# llm.ainvoke 是 LangChain 兼容接口，DoubaoLLM 内部做了适配
```

### 4.6 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| Python 文件 | snake_case | `compare_agent.py` |
| Go 文件 | snake_case | `ratelimit.go` |
| Python 类 | PascalCase | `CompareAgent` |
| Go 类型/函数 | PascalCase / camelCase | `RateLimiter()` / `getEnv()` |
| Python 函数/变量 | snake_case | `get_effective_llm_config()` |
| URL 路由 | kebab-case RESTful | `/api/v1/infra/decision-logs` |
| Agent 名称 | snake_case 字符串 | `"targeted_fix"` |
| 数据库表 | snake_case 复数 | `analysis_records` |
| Pydantic 模型 | PascalCase | `AgentDecisionLog` |
| 环境变量 | UPPER_SNAKE | `ARK_API_KEY` |
| Commit | `type: 中文描述` | `feat: 豆包LLM迁移+飞书Bot推送` |

### 4.7 前端状态管理

| 特性 | 实现方式 |
|------|----------|
| **全局状态方案** | `st.session_state`（Streamlit 内置） |
| **持久化** | 无（页面刷新后丢失） |
| **缓存** | `@st.cache_data(ttl=N)` — 竞品列表 ttl=60s, 配置 ttl=5s, 可观测 ttl=3s |
| **交互状态** | 硬编码键名模式：`f"edit_comp_{id}"` / `f"view_record_{id}"` |
| **清理缓存** | `st.cache_data.clear()` + `st.rerun()` |

### 4.8 前端请求封装

| 特性 | 当前状态 |
|------|----------|
| **统一拦截器** | 无 — 每个请求单独 `try-except` |
| **Token 处理** | 无（所有接口公开） |
| **跨域处理** | 后端 `CORSMiddleware(allow_origins=["*"])` + Hertz CORS 中间件 |
| **超时控制** | `timeout=5` 普通请求 / `timeout=(5, 300)` SSE流式 / `timeout=10` 测试 |
| **错误处理** | `try-except` → `st.error()` 或 `st.warning()` |

---

## 阶段5：本次变更说明（2026-05-20）

### M1 豆包 LLM 迁移
- 新增 `services/llm/` — DoubaoLLM (Ark SDK) + LLMFactory (doubao/tongyi 双Provider)
- 6 个 Agent 全部从 `ChatTongyi` 迁移到 `LLMFactory.get_llm()`
- config.py 新增 `DoubaoConfig` dataclass + `ark_api_key` / `doubao_model_id` 字段
- 默认 provider 改为 `doubao`，保留 `tongyi` 回退

### M2 飞书 Bot 推送
- 新增 `services/feishu/` — FeishuBot + HMAC-SHA256 签名 + 3 套交互卡片
- workflow 新增 `feishu_push` 节点（12 节点 DAG）
- 前端通知配置新增飞书 Webhook/Secret 字段 + 测试按钮
- 数据库新增 `feedback_records` 表（M6 自进化数据源）

### M1-B Hertz API 网关
- 新增 `gateway/` — Go 项目，14 代理路由 + 3 中间件 + Docker 多阶段构建
- SSE 端点逐块转发（`Flush()` 禁用缓冲）
- 飞书 Webhook 200 容错
- docker-compose 新增 gateway 服务

### M5 可观测性基础设施接线
- 新增 `observability.py` — ObservabilityHub 单例，统一接入 5 组件
- `instrumented_node()` 工作流包装器 → 每个 Agent 自动埋点
- 11 个可观测性 API 端点 + 前端"可观测中心"页面
- 顶部 5 指标卡 + DAG SVG 嵌入 + 决策日志时间线 + Token 柱状图

### M6 RAG 知识库 MVP
- 新增 `services/rag/` — 四层架构 L1+L2（FAISS + SentenceTransformer）
- `seed_kb.py` 索引 23 文档 → 139 chunks, 覆盖 5 个电商子行业
- ResearchAgent / BattlecardAgent 接入 RAG 检索（`augment_prompt`）
- 3 个 RAG API 端点 + 前端"竞品知识库"页面
- 嵌入模型自动回退：bge-large-zh-v1.5 → MiniLM-L12-v2

### 我方产品管理
- 新增 `our_product` 表 + `OurProduct` 模型 + API + 前端页面
- CompareAgent 基于真实产品数据评分（非 LLM 凭空生成）

### 系统配置页面
- 5-Tab 完整配置页（告警/通知/LLM/系统信息/导入导出）
- 动态配置层：DB 覆盖 + 版本历史 + 回滚 + JSON 导入导出

### 三节点全局校验架构
- 新增 FactCheck / Reviewer / TargetedFix / Citation 4 个 Agent
- 10 → 12 节点 DAG 升级（含 feishu_push）
- 全链路校验闭环：交叉验证 → 定向修复 ×3 → 引用溯源

### Docker 部署
- docker-compose 新增 gateway 服务
- gateway/Dockerfile 多阶段构建（golang:1.21 → alpine:3.19）

### BUG-01 修复
- `update_competitor` 现在先查询 `created_at` 再更新，返回完整 `CompetitorResponse`
- 测试从 `xfail` 变为 `xpass` 确认修复

---

## 阶段7：本次变更说明（2026-05-21）

### M6 自进化引擎
- 新建 `python/src/services/evolution/` — EvolutionEngine 单例 + 3 层 SQLite 持久化
- **多模板策略**：4 个 Agent（research/compare/battlecard/reviewer）各 3 份 Prompt 模板
- **加权随机选择**：模板 performance_score 越高被选中概率越大
- **反馈闭环**：确认正确 → +0.1 / 标记错误 → -0.2，置信度调整系数 0.5~1.5
- **进化统计**：总快照数 / 人类验证率 / 准确率趋势（按日）/ 模板评分排行
- 数据库新增 3 张表：`analysis_snapshots` / `evolution_feedback` / `template_performance`
- workflow.py 新增 `extract_evolution_snapshots()` + `save_evolution_snapshots()` — pipeline 执行后自动保存 8 个 Agent 维度的快照
- server.py 新增 4 个进化 API 端点（feedback/stats/snapshots/templates）
- 前端可观测中心页新增「系统进化」面板（指标卡+覆盖率进度环+准确率趋势线+模板排行柱状图+快照列表）

### M7 Mock 模式（Demo 零失败保障）
- 新建 `python/src/mock/` — `is_mock_mode()` / `MockContext` / `MockDataGenerator`
- **3 个 Demo 场景**完整预生成数据：
  - 场景1「直播电商三巨头」：抖音电商 vs 快手电商（字节主场，答辩默认）
  - 场景2「跨境电商出海」：SHEIN vs Temu
  - 场景3「AI电商未来」：各大平台 AI 能力对比
- 每个场景含：监控结果+研究洞察+交叉验证+8维对比矩阵+战术卡+审查反馈+引用溯源+决策日志
- **DAG 模拟**：9 节点逐个执行（各 200-600ms），可观测性 EventBus 正常触发，总耗时 3-5 秒
- **运行时切换**：环境变量 `MOCK_MODE=true` 或 `POST /api/v1/mock/toggle`
- server.py 的 `/analyze` 和 `/analyze/stream` 自动检测 Mock 模式分流
- 前端侧边栏新增 Mock 模式开关 + Demo 场景选择器 + 全局黄色横幅提示
- 新增 2 个 Mock API 端点（status/toggle）

### 数据库扩展
- analysis_snapshots（分析快照：竞品+维度+Agent+置信度+模板ID）
- evolution_feedback（进化反馈：快照关联+操作+置信度变化）
- template_performance（模板表现：评分+使用次数+成功率）
- BUG-01 修复：update_competitor 返回完整 created_at

### 前端增强
- 可观测中心新增「系统进化」面板
- 侧边栏新增 Mock 模式开关 toggle + Demo 场景选择器
- Mock 模式启用时全局黄色横幅提示

---

## 阶段6：已知问题与改进建议

### 🔴 P0 — 比赛前必须修复

| 编号 | 问题 | 位置 | 影响 |
|------|------|------|------|
| ~~BUG-01~~ | ~~`db/sqlite.py:update_competitor` 返回值缺少 `created_at`~~ → **已于 v3.1 修复** | `sqlite.py` | ✅ 测试从 xfail 变 xpass |
| BUG-02 | 豆包模型 `doubao-seed-1-8-251228` 未激活 — API Key 有效但模型服务未开通 | Ark Console | 全部分析无法运行 |
| TODO-01 | 前端单文件 ~1400 行 — 需拆分为 `pages/`、`components/`、`services/` 目录 | `frontend/app.py` | 维护性差 |

### 🟡 P1 — 本周内修复

| 编号 | 问题 | 位置 | 建议 |
|------|------|------|------|
| TD-03 | 无认证/鉴权机制（所有接口公开） | `server.py` | 比赛 Demo 可接受，生产必须加 |
| TD-06 | 后端测试仅覆盖解析/工具/DB 层，Agent 集成测试需 LLM API 可用的环境 | `tests/` | 模型激活后取消 skip |
| TD-07 | `api_token_usage` 使用 `hub.token_manager._get_used()` (私有方法) | `server.py` | TokenManager 应暴露公共方法 |
| TD-12 | `/competitors` 端点返回硬编码 Demo 数据 | `server.py` | 清理或标记为遗留 |
| PERF-01 | TargetedFix→Reviewer 循环每次调用 LLM，最坏情况 3×2=6 次 LLM 调用 | `workflow.py` | 考虑 Reviewer 缓存上次评分 |
| PERF-02 | RAG 嵌入模型为 MiniLM (384维)，bge-large-zh (1024维) 模型太大未下载 | `retriever.py` | 生产环境应下载 bge 模型获得更好效果 |

### 🟢 P2 — 后续优化

| 编号 | 问题 | 位置 | 建议 |
|------|------|------|------|
| TD-01 | Go 网关未安装 Go 环境，代码未编译验证 | `gateway/` | 安装 Go 1.21+ 执行 `go build` |
| TD-09 | Kafka/ES/Redis 仅在 config/docker-compose 中定义，Pipeline 不依赖 | - | 可移除或激活 |
| ARCH-01 | `compare_agent._parse_matrix` 缩进/结构需代码审查 | `compare_agent.py` | try-except 嵌套较深 |
| PERF-03 | 前端每个页面独立 `check_health()` 调用，可优化为全局状态 | `app.py` | 用 `st.session_state` 缓存 |
| UX-01 | RAG 知识库搜索只在点击按钮时触发，不支持回车键 | `app.py` | 改为 `st.form` 或 `on_change` 回调 |

---

## 附录：开发快速参考

### 启动命令

```bash
# 终端 1 — 后端 (Python)
cd python
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 — 前端 (Streamlit)
streamlit run frontend/app.py --server.port 8501

# 终端 3 — 网关 (Go, 可选)
cd gateway
HERTZ_PORT=8080 BACKEND_URL=http://localhost:8000 go run main.go

# Docker Compose 一键启动
cd python
docker-compose up -d
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端工作台 | http://localhost:8501 |
| API Swagger 文档 | http://localhost:8000/docs |
| Hertz 网关 | http://localhost:8080 |
| 网关路由表 | http://localhost:8080/routes |

### 测试命令

```bash
cd python
python -m pytest tests/ -v                     # 全部测试 (104 pass, 6 skip)
python -m pytest tests/ -v --tb=long           # 详细错误
python -m pytest tests/test_agents/ -v          # 仅 Agent 测试
python -m pytest tests/test_infrastructure.py -v # 可观测性测试
```

### RAG 知识库索引

```bash
cd python
RAG_KB_PATH="/d/.../ecommerce_kb" python -m src.services.rag.seed_kb
```

### LLM Provider 切换

修改 `.env` 中 `LLM_PROVIDER` 字段：
- `doubao` → 豆包 (Ark SDK)，需激活模型服务
- `tongyi` → 通义千问 (DashScope)，保留用于回退和开发调试
