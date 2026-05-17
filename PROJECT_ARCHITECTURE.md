# 多Agent竞品情报分析系统 — 项目架构文档（全量分析版）

> **文档目的**：新会话/新开发者仅需阅读本文档，即可 100% 接手本项目开发与竞品分析任务。
> **分析范围**：仅做客观梳理与总结，不修改、不补代码、不优化。
> **最后更新**：2026-05-17

---

# 阶段1：项目整体定位与竞品分析背景

## 1.1 一句话定位

**基于多Agent（LangGraph）架构的企业级竞品情报分析SaaS平台，将人工2天的竞品报告工作压缩为AI 5分钟全自动完成。**

## 1.2 产品属性

| 维度               | 属性                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------ |
| **产品类型** | B2B 企业级 SaaS 工具/平台                                                                  |
| **目标用户** | 产品经理、销售团队、战略分析部门、竞争情报分析师                                           |
| **核心价值** | 效率提升 90%（2天→5分钟）、质量标准化（评分≥9/10）、业务落地性强（销售战术卡可直接使用） |
| **商业模式** | 内部工具 / 比赛项目（字节全栈挑战赛），未商业定价                                          |

## 1.3 比赛背景

- **赛事**：字节全栈挑战赛
- **赛道方向**：AI Agent × 企业效率工具
- **核心目标**：展示"多Agent协作 + LLM驱动"在真实业务场景（竞品分析）中的落地能力
- **对标方向**：Crayon、Klue、Kompyte 等国际竞品情报SaaS产品（但本系统侧重AI Agent自动化，非人工维护看板）
- **期望产出**：可运行的全栈系统 + 可视化工作台 + 标准化报告导出

## 1.4 竞品范围

### 直接竞品（同类竞品情报平台）

| 竞品              | 差异化                                  | 来源            |
| ----------------- | --------------------------------------- | --------------- |
| **Crayon**  | 人工维护 + 看板模式，非AI自动生成       | README 隐含对标 |
| **Klue**    | 侧重销售赋能，本系统更侧重Agent自动分析 | 同类赛道        |
| **Kompyte** | 多源采集，本系统用LLM替代规则引擎       | 同类赛道        |

### 间接竞品（功能重叠领域）

| 竞品                         | 重叠领域                              |
| ---------------------------- | ------------------------------------- |
| ChatGPT/Claude + 手动 Prompt | 部分替代Research Agent功能            |
| SEMrush / SimilarWeb         | 流量/市场数据维度（本系统暂时未覆盖） |
| 钉钉/飞书 AI 助手            | 告警通知能力重叠                      |

---

# 阶段2：技术栈与架构全景

## 2.1 核心技术栈

### 前端

| 类别                 | 技术选型                                     | 版本   | 文件位置                |
| -------------------- | -------------------------------------------- | ------ | ----------------------- |
| **框架**       | Streamlit                                    | ≥1.30 | `frontend/app.py`     |
| **HTTP客户端** | requests                                     | 内置   | `frontend/app.py`     |
| **SSE客户端**  | sseclient                                    | latest | `frontend/app.py:5`   |
| **Word生成**   | python-docx                                  | latest | `frontend/app.py:7-9` |
| **状态管理**   | st.session_state（Streamlit内置）            | -      | 全局                    |
| **缓存**       | @st.cache_data (TTL=60s)                     | -      | `frontend/app.py:39`  |
| **UI布局**     | st.columns / st.tabs / st.expander / st.form | -      | 全局                    |

### 后端

| 类别                 | 技术选型                         | 版本      | 文件位置                         |
| -------------------- | -------------------------------- | --------- | -------------------------------- |
| **语言**       | Python 3.11+                     | -         | -                                |
| **Web框架**    | FastAPI                          | ≥0.115.0 | `python/src/api/server.py`     |
| **ASGI服务器** | Uvicorn                          | ≥0.32.0  | 启动命令依赖                     |
| **API风格**    | RESTful + SSE流式                | -         | `python/src/api/server.py`     |
| **CORS**       | CORSMiddleware（全放通 `*`）   | -         | `server.py:113-118`            |
| **数据校验**   | Pydantic v2                      | ≥2.9.0   | `python/src/models/schemas.py` |
| **数据存储**   | SQLite（sqlite3内置库）          | -         | `python/src/db/sqlite.py`      |
| **配置管理**   | python-dotenv + frozen dataclass | ≥1.0.0   | `python/src/config.py`         |

### Agent编排与AI

| 类别                 | 技术选型                                         | 版本                                          | 文件位置                         |
| -------------------- | ------------------------------------------------ | --------------------------------------------- | -------------------------------- |
| **工作流编排** | LangGraph (StateGraph)                           | ≥0.2.0                                       | `python/src/graph/workflow.py` |
| **LLM框架**    | LangChain (langchain-core + langchain-community) | ≥0.3.0                                       | 各Agent文件                      |
| **大模型**     | 通义千问 Qwen（ChatTongyi）                      | qwen-turbo（实际.env配置）/ qwen-plus（默认） | 各Agent文件                      |
| **LLM API**    | 阿里云百炼 DashScope                             | API Key:`sk-6f3b...`                        | `.env` / `config.py`         |

### 工具与基础设施

| 类别               | 技术选型                                  | 版本                | 文件位置                                              |
| ------------------ | ----------------------------------------- | ------------------- | ----------------------------------------------------- |
| **网页抓取** | httpx + BeautifulSoup4                    | ≥0.28.0 / ≥4.12.0 | `python/src/tools/web_scraper.py`                   |
| **重试机制** | tenacity                                  | ≥9.0.0             | `web_scraper.py` / `search_tool.py`               |
| **搜索API**  | SerpAPI（含demo fallback）                | -                   | `python/src/tools/search_tool.py`                   |
| **通知**     | Slack Webhook / 钉钉 Webhook / Email SMTP | -                   | `python/src/tools/notification.py`                  |
| **日志**     | structlog + logging                       | ≥24.4.0            | 各模块                                                |
| **消息队列** | Kafka (confluent-kafka)                   | ≥2.6.0             | 配置预留，实际未激活                                  |
| **全文检索** | Elasticsearch                             | ≥8.16.0            | 配置预留，实际未激活                                  |
| **缓存**     | Redis                                     | ≥5.2.0             | 配置预留，实际未激活                                  |
| **容器化**   | Docker + Docker Compose                   | -                   | `python/Dockerfile` / `python/docker-compose.yml` |
| **调度**     | APScheduler                               | ≥3.10.0            | 配置预留（定时监控）                                  |

## 2.2 完整目录结构（按功能分层）

```
competitive-intelligence-multi-agent/          # 项目根目录
│
├── README.md                                  # 项目介绍 + 快速启动指南
├── PROJECT_ARCHITECTURE.md                    # 【本文档】架构全景
├── requirements.txt                           # 根级依赖（与python/requirements.txt相同）
├── .env                                       # 环境变量（已在.gitignore，含真实API Key）
├── .gitignore                                 # Git忽略规则
├── LICENSE                                    # 开源协议
│
├── docs/                                      # 文档资源
│   ├── architecture.md                        # 架构设计稿（描述设计意图，部分与实现有偏差）
│   ├── deployment.md                          # 部署指南
│   └── images/                                # 界面截图
│       ├── architecture.png                   # 产品架构图
│       ├── workbench_initial.png              # 工作台初始界面
│       ├── workbench_progress.png             # Agent执行进度
│       ├── workbench_select_competitor.png     # 选择已有竞品
│       ├── workbench_report_matrix.png        # 报告矩阵Tab
│       ├── competitor_management.png          # 竞品管理页
│       ├── history_list.png                   # 历史记录列表
│       ├── swagger_api.png                    # FastAPI自动生成的Swagger文档
│       ├── word_report_battlecard.png         # Word报告-战术卡
│       └── word_report_matrix.png             # Word报告-矩阵
│
├── frontend/                                  # 【前端】Streamlit单页应用
│   └── app.py                                 # ★ 前端入口（500+行，4个页面，SSE消费端）
│
├── python/                                    # 【后端】Python项目根
│   ├── .env.example                           # 环境变量模板（OpenAI版）
│   ├── requirements.txt                       # Python依赖清单
│   ├── Dockerfile                             # Docker镜像配置
│   ├── docker-compose.yml                     # 容器编排（API + Kafka + ES + Redis + ZK）
│   ├── ci_system.db                           # SQLite数据库文件（运行时自动生成）
│   │
│   ├── src/                                   # ★ 后端源码
│   │   ├── __init__.py                        # 空文件，包标记
│   │   ├── config.py                          # ★ 全局配置中心（frozen dataclass + .env加载）
│   │   │
│   │   ├── api/                               # ★★ API层（路由入口）
│   │   │   ├── __init__.py                    # 空文件
│   │   │   └── server.py                      # ★★★ FastAPI应用工厂、所有路由定义、SSE端点
│   │   │
│   │   ├── graph/                             # ★★ 编排层（Agent工作流）
│   │   │   ├── __init__.py                    # 空文件
│   │   │   └── workflow.py                    # ★★★ LangGraph状态机定义、条件分支、Pipeline构建
│   │   │
│   │   ├── agents/                            # ★★ 业务层（6个Agent实现）
│   │   │   ├── __init__.py                    # Agent统一导出（5个Agent类）
│   │   │   ├── monitor_agent.py               # ★★ 变更监控Agent（爬取+Hash对比+LLM分析）
│   │   │   ├── alert_agent.py                 # ★★ 告警Agent（HIGH/CRITICAL阈值过滤+多渠道推送）
│   │   │   ├── research_agent.py              # ★★ 深度研究Agent（5维度分析+SerpAPI搜索）
│   │   │   ├── compare_agent.py               # ★★ 对比分析Agent（8维度0-10评分矩阵）
│   │   │   └── battlecard_agent.py            # ★★ 销售战术卡Agent（优劣势+异议处理+电梯演讲）
│   │   │
│   │   ├── models/                            # ★★ 数据层（Pydantic模型）
│   │   │   ├── __init__.py                    # 空文件
│   │   │   └── schemas.py                     # ★★★ 全部数据模型定义（枚举、Agent输入输出、Pipeline状态）
│   │   │
│   │   ├── db/                                # ★ 持久化层
│   │   │   ├── __init__.py                    # 空文件
│   │   │   └── sqlite.py                      # ★★ SQLite CRUD封装（竞品库 + 历史记录）
│   │   │
│   │   └── tools/                             # ★ 工具层（Agent调用的底层能力）
│   │       ├── __init__.py                    # 空文件
│   │       ├── web_scraper.py                 # ★★ 网页抓取（httpx+BS4、SHA-256 Hash、定价/招聘提取）
│   │       ├── search_tool.py                 # ★★ 搜索工具（SerpAPI封装 + Demo fallback）
│   │       └── notification.py                # ★★ 通知工具（Slack/钉钉/邮件，按配置优雅降级）
│   │
│   └── tests/                                 # 测试目录
│       ├── __init__.py                        # 空文件
│       └── test_pipeline.py                   # 数据模型单元测试（4个test，仅测Pydantic模型）
│
└── venv/                                      # Python虚拟环境（gitignore）
```

### 关键文件标注

| 角色                       | 文件                             | 行数      | 说明                                                 |
| -------------------------- | -------------------------------- | --------- | ---------------------------------------------------- |
| **前端入口**         | `frontend/app.py`              | ~520      | 所有UI逻辑、SSE消费、Word导出                        |
| **后端入口**         | `python/src/api/server.py`     | ~343      | FastAPI应用、全部路由、lifespan事件                  |
| **API路由中心**      | `python/src/api/server.py`     | L125-L343 | 8个端点（health/analyze/stream/competitors/records） |
| **工作流引擎**       | `python/src/graph/workflow.py` | ~191      | LangGraph DAG编排、条件分支、Pipeline单例            |
| **数据模型中心**     | `python/src/models/schemas.py` | ~133      | 全部Pydantic模型、枚举、类型定义                     |
| **全局配置**         | `python/src/config.py`         | ~71       | 环境变量加载、6个frozen dataclass                    |
| **数据库操作**       | `python/src/db/sqlite.py`      | ~233      | SQLite CRUD、自动建表                                |
| **请求封装（前端）** | 无统一封装                       | -         | 前端直接使用 `requests.get/post` 调用后端API       |
| **状态中心**         | `st.session_state`             | -         | Streamlit内置，非独立模块                            |

## 2.3 整体架构设计

### 2.3.1 分层架构（5层）

```
┌──────────────────────────────────────────────────────────┐
│                    展示层 (Presentation)                    │
│  Streamlit 单页应用  │  st.tabs/st.expander/st.columns     │
│  侧边栏导航(4页面)  │  SSE实时进度展示  │  Word报告导出    │
├──────────────────────────────────────────────────────────┤
│                     API 网关层 (API Gateway)                │
│  FastAPI  │  CORS(* 全放通)  │  lifespan事件自动初始化DB    │
│  ┌──────────────┬──────────────┬───────────────────┐      │
│  │ GET /health  │ POST /analyze│ POST /analyze/stream│     │
│  │ 竞品CRUD x5  │ 历史记录 x2  │ /competitors(legacy) │     │
│  └──────────────┴──────────────┴───────────────────┘      │
├──────────────────────────────────────────────────────────┤
│                    编排层 (Orchestration)                   │
│  LangGraph StateGraph  │  PipelineState TypedDict          │
│  Monitor → Alert+Research(并行) → Compare → Battlecard     │
│  → Quality Check → [<7 循环重试(最多3次) | ≥7 END]        │
├──────────────────────────────────────────────────────────┤
│                    业务层 (Agents)                          │
│  Monitor │ Research │ Compare │ Battlecard │ Alert        │
│  每个Agent = 独立类 + __call__(state) → dict节点接口       │
│  内置 LLM: ChatTongyi (qwen-plus/qwen-turbo)              │
├──────────────────────────────────────────────────────────┤
│                    基础设施层 (Infrastructure)              │
│  ┌─────────┬──────────┬──────────┬──────────┬────────┐   │
│  │ SQLite  │  httpx   │ SerpAPI  │  Slack/  │ Redis/ │   │
│  │(持久化) │+ BS4抓取 │ (搜索)   │ 钉钉/邮件│ Kafka/ │   │
│  │         │          │          │ (通知)   │  ES(预)│   │
│  └─────────┴──────────┴──────────┴──────────┴────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 2.3.2 核心数据流（用户操作 → 视图更新）

```
┌──────────┐    POST /analyze/stream     ┌──────────────┐
│  用户输入  │ ──────────────────────────▶ │  FastAPI      │
│ 竞品+URLs │                             │  server.py    │
└──────────┘                             └──────┬───────┘
                                                 │ PipelineState
                                                 ▼
                                        ┌───────────────┐
                                        │   LangGraph    │
                                        │   workflow.py  │
                                        └───────┬───────┘
                                                │
                    ┌───────────────────────────┼───────────────────────┐
                    ▼                           ▼                       ▼
            ┌──────────────┐          ┌──────────────┐        ┌──────────────┐
            │Monitor Agent │          │ Alert  Agent  │        │Research Agent│
            │ web_scraper  │          │ notification  │        │ search_tool  │
            │ (httpx+BS4)  │          │ Slack/钉钉    │        │ SerpAPI      │
            └──────┬───────┘          └──────┬───────┘        └──────┬───────┘
                   │                         │                       │
                   │  changes_detected       │  alerts_sent          │ research_results
                   ▼                         ▼                       ▼
            ┌──────────────────────────────────────────────────────────────┐
            │                    LangGraph 状态汇聚                          │
            └──────────────────────────────────────────────────────────────┘
                   │                         │                       │
                   ▼                         ▼                       ▼
           ┌──────────────┐         ┌──────────────┐       ┌──────────────┐
           │Compare Agent │         │Battlecard Agt│       │Quality Check │
           │8维度对比矩阵  │         │销售战术卡     │       │质量评分1-10  │
           └──────┬───────┘         └──────┬───────┘       └──────┬───────┘
                  │                        │                      │
                  ▼                        ▼                      ▼
           ┌──────────────────────────────────────────────────────────┐
           │  SSE Event Stream → 前端 st.expander/st.tabs 实时渲染    │
           │  + 自动存入 SQLite (analysis_records 表)                 │
           └──────────────────────────────────────────────────────────┘
```

### 2.3.3 Agent工作流（LangGraph DAG）

```
                     ┌──────────────┐
                     │    START     │
                     └──────┬───────┘
                            ▼
               ┌────────────────┐
               │ Monitor Agent  │  ← 监控竞品URL，检测变更
               └────────┬───────┘
                        │
               ┌────────┴───────┐
               ▼                ▼
       ┌──────────────┐  ┌───────────────┐
       │ Alert Agent  │  │ Research Agent│  ← Monitor→Alert+Research 并行
       └──────┬───────┘  └───────┬───────┘
              ▼                  ▼
         ┌──────┐       ┌─────────────────┐
         │ END  │       │ Compare Agent   │  ← 生成对比矩阵
         └──────┘       └────────┬────────┘
                                 ▼
                       ┌──────────────────┐
                       │ Battlecard Agent │  ← 生成销售战术卡
                       └────────┬─────────┘
                                ▼
                       ┌──────────────────┐
                       │ Quality Check    │  ← 质量校验（反思门）
                       └────────┬─────────┘
                         ┌──────┴──────┐
                   score < 7      score >= 7
                         │             │
                         ▼             ▼
                 ┌──────────┐    ┌─────┐
                 │ Research │    │ END │  ← 循环优化直到达标或超过最大重试次数
                 └──────────┘    └─────┘
```

### 2.3.4 关键依赖与核心能力承担

| 能力                | 承担库                    | 决策依据                                                 |
| ------------------- | ------------------------- | -------------------------------------------------------- |
| **Agent编排** | LangGraph                 | 图状态机、条件分支、checkpoint持久化、原生async支持      |
| **LLM抽象**   | LangChain ChatTongyi      | 统一消息格式（SystemMessage/HumanMessage）、通义千问适配 |
| **API服务**   | FastAPI                   | 异步原生、自动Swagger文档、SSE支持（sse-starlette）      |
| **数据校验**  | Pydantic v2               | 类型安全、自动序列化（datetime→ISO）、field_validator   |
| **网页抓取**  | httpx + BeautifulSoup4    | 异步HTTP + CSS选择器提取、SHA-256变更检测                |
| **文档导出**  | python-docx               | Word (.docx) 格式，结构化报告生成                        |
| **重试容错**  | tenacity                  | 指数退避 + 最大重试次数（网络请求）                      |
| **配置管理**  | python-dotenv + dataclass | 环境变量 → frozen dataclass，类型安全、不可变           |

---

# 阶段3：业务与竞品分析逻辑

## 3.1 竞品分析模块

### 3.1.1 竞品数据来源

| 数据来源              | 获取方式                                 | 文件位置                     | 备注                                            |
| --------------------- | ---------------------------------------- | ---------------------------- | ----------------------------------------------- |
| **用户输入URL** | 前端表单 →`monitor_urls` 字段         | `frontend/app.py:156-163`  | 支持1行1个URL，亦可从竞品库快速选择             |
| **自动生成URL** | MonitorAgent._default_urls()             | `monitor_agent.py:131-148` | 中文名→英文域名映射（字节跳动→bytedance.com） |
| **网页内容**    | httpx异步抓取 → BS4解析 → SHA-256 Hash | `tools/web_scraper.py`     | 3次重试、指数退避、30s超时                      |
| **搜索数据**    | SerpAPI（web_search + news_search）      | `tools/search_tool.py`     | 无API Key时返回Demo数据                         |
| **LLM生成**     | 通义千问 ChatTongyi                      | 各Agent文件                  | 所有分析结论均由LLM生成（非规则引擎）           |
| **历史数据**    | SQLite analysis_records 表               | `db/sqlite.py:L150-178`    | 每次分析完成后自动存入                          |

### 3.1.2 分析维度全景表

| Agent                   | 分析维度                                                                       | 评分方式                              | 输出数据结构                             |
| ----------------------- | ------------------------------------------------------------------------------ | ------------------------------------- | ---------------------------------------- |
| **Monitor**       | 定价变化、产品功能、招聘信号、新闻动态                                         | 严重程度 LOW/MEDIUM/HIGH/CRITICAL     | `CompetitorChange[]`                   |
| **Research**      | 财务信号、专利/IP、技术博客、开源贡献、战略动作                                | 置信度 0-1                            | `ResearchInsight[]`                    |
| **Compare**       | 产品功能、定价价值、用户体验、市场份额、客户评价、技术创新、生态集成、支持文档 | 0-10 分（我方 vs 竞品）               | `ComparisonMatrix` (8个DimensionScore) |
| **Battlecard**    | 优劣势、核心差异化、异议处理话术、电梯演讲                                     | 无评分（文本质量由Quality Check把关） | `Battlecard`                           |
| **Quality Check** | 完整性、准确性、可操作性                                                       | 1-10 分                               | `quality_score` (float)                |

### 3.1.3 分析结果可视化方式

| 可视化方式                   | 前端实现                                              | 数据来源                                          |
| ---------------------------- | ----------------------------------------------------- | ------------------------------------------------- |
| **对比矩阵表格**       | `st.columns` 三列布局（维度/我方/竞品）+ metric组件 | `comparison_matrix.dimensions[]`                |
| **SWOT式卡片**         | 双列布局 + 无序列表（优势/劣势 × 我方/竞品）         | `battlecard.our_strengths/weaknesses`           |
| **研究洞察可折叠列表** | `st.expander` 可展开/折叠 + bullet list             | `research_results[].topic/summary/key_findings` |
| **变更监控列表**       | 简单文本列表 + 严重程度标签                           | `changes_detected[].severity/title`             |
| **Timeline视图**       | 无时间线图（当前仅有简单文本）                        | -                                                 |
| **雷达图/折线图**      | **未实现**（当前无图表库依赖）                  | -                                                 |
| **Word报告导出**       | python-docx 生成结构化 .docx 文件                     | 汇总全部分析结果                                  |

## 3.2 核心页面/功能详解

### 3.2.1 竞品分析工作台（首页，核心页面）

- **文件位置**：`frontend/app.py:L126-324`
- **核心逻辑**：
  1. 健康检查（`GET /health`）→ 服务不可用时显示错误提示
  2. 竞品选择：支持「手动输入」或「从竞品库快速选择」（checkbox切换）
  3. 表单提交 → `POST /analyze/stream`（SSE流式请求）
  4. 实时进度：`SSEClient` 逐event消费 → `st.expander` 展示每个节点的JSON输出
  5. 最终报告：4个Tab（对比矩阵/销售战术卡/研究洞察/变更监控）+ 质量评分Metric + Word导出按钮
- **数据来源**：SSE事件流（monitor → alert/research → compare → battlecard → quality_check）
- **状态管理**：`node_results` 局部dict + 各Tab内容直接从 `final_analysis_result` 读取

### 3.2.2 竞品管理

- **文件位置**：`frontend/app.py:L329-434`
- **核心逻辑**：
  - 新增：表单（名称+URL列表）→ `POST /competitors`
  - 列表：`GET /competitors/all` → `@st.cache_data(ttl=60)` 缓存 → 按卡片展示
  - 编辑：行内表单展开（通过 `st.session_state[f"edit_comp_{id}"]` 控制）→ `PUT /competitors/{id}`
  - 删除：确认按钮 → `DELETE /competitors/{id}` → 清除缓存 + rerun
- **数据来源**：SQLite competitors 表

### 3.2.3 历史分析

- **文件位置**：`frontend/app.py:L439-515`
- **核心逻辑**：
  - 筛选：按竞品下拉选择（可选"全部"）→ `GET /analysis/records?competitor_id=X`
  - 列表：按时间倒序展示，每条显示竞品名、时间、质量评分
  - 详情：`st.session_state[f"view_record_{id}"]` 控制展开，4个Tab复用工作台展示逻辑
- **数据来源**：SQLite analysis_records 表

### 3.2.4 系统配置

- **文件位置**：`frontend/app.py:L519-521`
- **当前状态**：占位页面（"功能开发中"），未实现任何配置功能

## 3.3 编码约定与特殊逻辑

### 3.3.1 请求处理（前端）

| 特性                 | 当前状态                                              | 文件位置                                            |
| -------------------- | ----------------------------------------------------- | --------------------------------------------------- |
| **统一拦截器** | 无                                                    | 每个请求单独 `try-except` + `.status_code` 判断 |
| **Token处理**  | 无（所有接口公开）                                    | -                                                   |
| **跨域处理**   | 后端 `CORSMiddleware(allow_origins=["*"])`          | `server.py:113-118`                               |
| **错误处理**   | 前端 `try-except` 捕获异常 → `st.error()` 展示   | `app.py` 各处                                     |
| **超时处理**   | `timeout=5` 硬编码在每个请求中                      | `app.py` 各处                                     |
| **重试机制**   | 无（仅后端工具层有 tenacity 重试）                    | -                                                   |
| **请求封装**   | 无统一函数，直接调用 `requests.get/post/put/delete` | `app.py` 各处                                     |

### 3.3.2 状态管理（前端）

| 特性                   | 实现方式                                                        | 说明                      |
| ---------------------- | --------------------------------------------------------------- | ------------------------- |
| **全局状态方案** | `st.session_state`（Streamlit内置）                           | 非Redux/Zustand等独立方案 |
| **持久化**       | 无（页面刷新后丢失，除非Streamlit自动保留session）              | -                         |
| **缓存**         | `@st.cache_data(ttl=60)` 仅用于 `get_competitor_list()`     | `app.py:39`             |
| **交互状态**     | 硬编码键名模式：`f"edit_comp_{id}"` / `f"view_record_{id}"` | `app.py:392-484`        |
| **清理缓存**     | `st.cache_data.clear()` + `st.rerun()` 用于增删改后刷新     | -                         |

### 3.3.3 样式系统

| 特性                 | 实现方式                                                               |
| -------------------- | ---------------------------------------------------------------------- |
| **CSS方案**    | Streamlit 原生渲染（无自定义CSS文件、无Tailwind）                      |
| **主题**       | Streamlit 默认主题（通过 `st.set_page_config` 仅设置标题/图标/布局） |
| **复用方式**   | 无组件抽象，直接在页面内重复代码（如健康检查、竞品列表渲染）           |
| **响应式布局** | `st.columns([1,2])` / `use_container_width=True`                   |

### 3.3.4 后端特殊逻辑

| 特性                         | 实现位置                                        | 说明                                                                               |
| ---------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| **SSE流式**            | `server.py:L202-274`                          | `EventSourceResponse` + `async generator`，每个LangGraph节点产生event          |
| **datetime序列化**     | `server.py:L153-164`                          | 递归遍历 `convert_datetime()`，确保所有datetime→ISO字符串（防止JSON序列化报错） |
| **优雅降级**           | `search_tool.py` / `notification.py`        | 无API Key时返回Demo结果；未配置通知渠道时静默跳过                                  |
| **质量反思循环**       | `workflow.py:L98-143`                         | Quality Check评分 < 7 时重新执行Research（最多3次）                                |
| **重名检测**           | `db/sqlite.py:L71-72`                         | `sqlite3.IntegrityError` → `ValueError`（竞品名称唯一约束）                   |
| **LLM输出解析**        | 各Agent `_parse_*` 方法                       | 统一模式：先strip → 去```标记 → json.loads → 失败时返回默认值                   |
| **中文→英文域名映射** | `monitor_agent.py:L131-148`                   | 硬编码映射表（字节跳动→bytedance等）+ 兜底转小写去空格                            |
| **列表reduce**         | `workflow.py:L62-64`                          | `_merge_lists` reducer：追加而非替换（Annotated list字段专用）                   |
| **分析自动存库**       | `server.py:L178-196` / `server.py:L236-265` | 同步/流式分析完成后均自动存入SQLite（失败不影响主流程）                            |

### 3.3.5 配置管理

| 特性                  | 实现                                                                                                                        |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **配置来源**    | `.env` 环境变量 → `python-dotenv` 加载 → frozen dataclass                                                             |
| **配置层级**    | 6个嵌套dataclass：`LLMConfig` / `KafkaConfig` / `ESConfig` / `RedisConfig` / `NotificationConfig` / `AppConfig` |
| **单例访问**    | `config = AppConfig()`（模块级单例）                                                                                      |
| **LLM切换**     | 修改 `.env` 中 `LLM_PROVIDER` 和对应API Key即可（当前仅实现ChatTongyi）                                                 |
| **API Key安全** | `.env` 已加入 `.gitignore`，但有真实Key已提交的风险（当前 `.env` 含真实Key）                                          |

### 3.3.6 已知技术债

| 编号  | 问题                                                               | 严重程度 | 涉及文件                        |
| ----- | ------------------------------------------------------------------ | -------- | ------------------------------- |
| TD-01 | 前端单文件 >500行，无模块拆分                                      | 中       | `frontend/app.py`             |
| TD-02 | 无统一API请求封装（重复requests调用、timeout硬编码）               | 中       | `frontend/app.py`             |
| TD-03 | 无认证/鉴权机制（所有接口公开）                                    | 高       | `server.py`                   |
| TD-04 | 状态键名硬编码（`f"edit_comp_{id}"` 模式）                       | 低       | `frontend/app.py`             |
| TD-05 | 前端无单元测试                                                     | 中       | 全局                            |
| TD-06 | 后端测试仅覆盖Pydantic模型（4个test），无Agent集成测试             | 高       | `tests/test_pipeline.py`      |
| TD-07 | 无API限流/防护                                                     | 中       | `server.py`                   |
| TD-08 | 搜索/抓取无API Key时静默降级为Demo数据，可能误导用户               | 中       | `tools/search_tool.py`        |
| TD-09 | Kafka/ES/Redis仅有配置预留，未在Pipeline中激活                     | 低       | `config.py` / `workflow.py` |
| TD-10 | `docs/architecture.md` 描述的理想架构与实际代码实现存在偏差      | 低       | `docs/architecture.md`        |
| TD-11 | `.env.example` 为OpenAI配置模板，但实际使用通义千问              | 低       | `python/.env.example`         |
| TD-12 | `/competitors` 端点（非 `/competitors/all`）返回硬编码demo数据 | 低       | `server.py:L277-287`          |

---

## 3.4 API接口完整清单

| 方法   | 端点                       | 功能                             | 文件位置               |
| ------ | -------------------------- | -------------------------------- | ---------------------- |
| GET    | `/health`                | 健康检查                         | `server.py:L125-127` |
| POST   | `/analyze`               | 同步执行全流程分析               | `server.py:L130-199` |
| POST   | `/analyze/stream`        | SSE流式分析（实时进度）          | `server.py:L202-274` |
| GET    | `/competitors`           | 获取Demo竞品列表（遗留）         | `server.py:L277-287` |
| GET    | `/competitors/all`       | 获取所有竞品                     | `server.py:L291-294` |
| GET    | `/competitors/{id}`      | 获取竞品详情                     | `server.py:L296-302` |
| POST   | `/competitors`           | 新增竞品                         | `server.py:L304-310` |
| PUT    | `/competitors/{id}`      | 更新竞品                         | `server.py:L312-318` |
| DELETE | `/competitors/{id}`      | 删除竞品                         | `server.py:L320-327` |
| GET    | `/analysis/records`      | 获取历史分析记录（可按竞品筛选） | `server.py:L332-335` |
| GET    | `/analysis/records/{id}` | 获取分析记录详情                 | `server.py:L337-343` |

## 3.5 数据库Schema

### competitors（竞品库）

| 字段       | 类型    | 约束             | 说明                |
| ---------- | ------- | ---------------- | ------------------- |
| id         | INTEGER | PK AUTOINCREMENT | 主键                |
| name       | TEXT    | NOT NULL UNIQUE  | 竞品名称            |
| urls       | TEXT    | NOT NULL         | JSON数组存储URL列表 |
| created_at | TEXT    | NOT NULL         | ISO时间字符串       |
| updated_at | TEXT    | NOT NULL         | ISO时间字符串       |

### analysis_records（历史分析记录）

| 字段            | 类型    | 约束                 | 说明                    |
| --------------- | ------- | -------------------- | ----------------------- |
| id              | INTEGER | PK AUTOINCREMENT     | 主键                    |
| competitor_id   | INTEGER | FK → competitors.id | 关联竞品ID（可为NULL）  |
| competitor_name | TEXT    | NOT NULL             | 竞品名称                |
| request_urls    | TEXT    | -                    | JSON数组存储本次分析URL |
| analysis_result | TEXT    | NOT NULL             | JSON格式完整分析结果    |
| quality_score   | REAL    | DEFAULT 0.0          | 质量评分                |
| created_at      | TEXT    | NOT NULL             | ISO时间字符串           |

## 3.6 启动与运行

### 开发环境

```bash
# 后端（终端1）
cd python
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn src.api.server:app --reload --port 8000

# 前端（终端2）
cd 项目根目录
streamlit run frontend/app.py
```

### 访问地址

| 服务            | 地址                         |
| --------------- | ---------------------------- |
| 前端工作台      | http://localhost:8501        |
| API Swagger文档 | http://localhost:8000/docs   |
| 健康检查        | http://localhost:8000/health |

### Docker部署

```bash
cd python
docker-compose up -d  # 启动 API + Kafka + ZK + ES + Redis（全量基础设施）
```

> **注意**：Docker Compose 启动的是完整基础设施栈（Kafka/ES/Redis），但当前代码中这些组件仅在配置中预留，Pipeline 实际运行时并不依赖它们（SQLite 替代了 ES/Redis，Agent 间通信用 LangGraph 内存状态替代了 Kafka）。

---

## 附录：快速开发参考

### 添加新Agent的步骤

1. 在 `python/src/agents/` 新建 `xxx_agent.py`
2. 实现类：`__init__` 初始化LLM + `async def __call__(self, state: dict) -> dict`
3. 在 `python/src/agents/__init__.py` 导出
4. 在 `python/src/graph/workflow.py` 中 `build_pipeline()` 添加节点和边

### 添加新API端点的步骤

1. 在 `python/src/models/schemas.py` 定义请求/响应Pydantic模型
2. 在 `python/src/api/server.py` 添加路由函数
3. 前端在 `frontend/app.py` 添加对应的 `requests.xxx()` 调用

### 添加新前端页面的步骤

1. 在 `frontend/app.py` 侧边栏 `st.radio` 中添加页面名称
2. 添加 `elif page == "新页面":` 分支
3. 在分支开头调用 `check_health()` 检查后端状态
