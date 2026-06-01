# 多Agent竞品情报分析系统 — 项目全景总览文档

> **文档定位**：新AI助手/开发者打开此文档，只读这一篇就能100%接手本项目所有开发、维护、竞品分析任务，完全不需要翻其他零散代码。
> **最后更新**：2026-06-01 版本v4.0 合并25+改进提交

---

## 阶段1：项目整体定位与竞品分析背景

### 1.1 一句话概括
**基于LangGraph 12节点DAG编排 + Palantir Ontology五层语义网络 + 字节豆包多模态深度融合的企业级竞品情报分析SaaS平台**，将人工2天的竞品分析工作压缩为AI 5分钟全自动完成。

- 产品类型：**B2B企业级SaaS工具/平台**
- 核心用户群：产品经理、销售团队、战略分析部门、竞争情报分析师
- 核心价值：效率提升90%（人工2天→AI 5分钟）、质量标准化（评分稳定≥9分）、业务落地性强（销售战术卡直接可用）

### 1.2 字节全栈挑战赛 项目定位
- 赛事赛道：Agent智能体赛道
- 核心目标：展示"多Agent协作 + LLM驱动 + 全链路可观测 + 知识库RAG"在真实竞品分析业务场景中的落地能力
- 对标方向：Crayon、Klue、Kompyte等国际竞品情报SaaS产品
- 期望产出：可运行的全栈系统 + 可视化工作台 + 飞书消息推送闭环 + 标准化Word报告导出 + 多模态图像/视频分析 + Ontology语义图谱

### 1.3 竞品范围
| 竞品类型 | 产品列表 | 差异化说明 |
|---|---|---|
| 直接竞品 | Crayon / Klue / Kompyte | 人工维护看板模式，非AI自动生成 |
| 直接竞品 | CompetitorLens（中科大参赛项目6Agent） | 我们12节点DAG+三层校验闭环深度更强 |
| 间接竞品 | ChatGPT/Claude + Prompt 人工协作 | 普通单大模型，无结构化DAG编排 |
| 间接竞品 | SEMrush / SimilarWeb | 仅流量/市场数据维度，我们覆盖全维度语义分析 |

---

## 阶段2：技术栈与架构全景

### 2.1 核心技术栈总表
| 层级 | 技术选型 | 版本/说明 |
|---|---|---|
| **前端框架** | Streamlit + React双版本 | Streamlit快速原型 / React 6页面正式版 |
| **UI库** | 自定义Component + AntV X6/D3图谱 | 组件化Agent面板/溯源页面 |
| **构建工具** | Vite + npm | React项目构建 |
| **后端语言** | Python 3.9+ | 全栈核心 |
| **Web后端框架** | FastAPI ≥0.115 | ASGI高性能，自动生成Swagger |
| **ASGI服务器** | Uvicorn | 生产级部署 |
| **API网关** | CloudWeGo Hertz (Go) v0.9 | 字节跳动开源生态，全路由GenericAPIProxy兜底透传 |
| **Agent编排** | LangGraph StateGraph ≥0.2 | 12节点完整DAG编排 |
| **LLM主Provider** | 字节豆包 Doubao ARK | doubao-seed-2.0-lite 256K超长上下文 |
| **LLM回退Provider** | 通义千问 Qwen VL-Plus | 多模态视觉分析安全fallback |
| **数据存储** | SQLite3 | 轻量高性能，全量数据持久化 |
| **向量存储** | FAISS-cpu + SentenceTransformer | 本地无依赖轻量向量检索 |
| **数据校验** | Pydantic v2 | 全项目统一BaseSchema自动序列化datetime ISO字符串 |
| **图片OCR** | PaddleOCR | 本地中文识别>95%准确率完全免费 |
| **视频处理** | FFmpeg | 关键帧提取完全免费 |
| **音频转录** | OpenAI Whisper tiny/base | 本地运行中文识别>95%完全免费 |
| **多模态LLM** | 豆包多模态 → 通义VL-Plus fallback | 海报图片/视频帧结构化分析 |
| **SDK集成** | lark-cli v1.0.40 官方26个预置技能 | 飞书Bot/多维表格/云文档 深度打通 |
| **文档导出** | python-docx | 标准Word报告自动生成 |

### 2.2 完整目录结构树
```
competitive-intelligence-multi-agent/
│
├── frontend-react/                          # 【正式React前端】
│   ├── src/
│   │   ├── api/client.js                    # API统一请求封装
│   │   ├── components/                      # 通用/业务组件
│   │   │   ├── agent/                      # Agent专属组件（DAG可视化/输出卡片/溯源面板）
│   │   │   ├── common/                      # 全局通用组件（进度条/指标卡片）
│   │   │   └── system/                      # 系统仪表盘组件
│   │   ├── pages/                           # 6核心页面
│   │   │   ├── AgentWorkspace.jsx            # 竞品分析主工作台
│   │   │   ├── TraceabilityPage.jsx          # 信息溯源一键跳转页面
│   │   │   ├── FeishuIntegrationPage.jsx     # 飞书集成配置页
│   │   │   ├── KnowledgeBasePage.jsx         # 竞品RAG知识库页
│   │   │   ├── SystemDashboard.jsx            # 系统可观测性仪表盘
│   │   │   └── LandingPage.jsx               # 首页着陆页
│   │   ├── styles/global.css                 # 全局样式
│   │   └── utils/                           # 工具函数
│   ├── package.json                         # React依赖声明
│   └── vite.config.js                       # Vite构建配置
│
├── frontend-streamlit/                       # 【快速原型Streamlit前端】
│   └── app.py                               # 单文件7页面快速演示
│
├── gateway-hertz/                            # 【Go Hertz API网关】
│   ├── main.go                               # Hertz入口 + Banner
│   ├── go.mod / go.sum                       # Go模块
│   ├── Dockerfile                            # 多阶段构建
│   ├── config/config.go                      # 环境变量配置
│   ├── handler/
│   │   ├── analysis.go                       # 分析代理
│   │   ├── competitor.go                     # 竞品CRUD代理
│   │   ├── feishu.go                         # 飞书Webhook回调
│   │   ├── health.go                         # 双层健康检查
│   │   └── infra.go                          # 全路由GenericAPIProxy兜底透传
│   └── middleware/
│       ├── cors.go                           # CORS跨域
│       ├── logging.go                        # 请求日志
│       └── ratelimit.go                       # TokenBucket限流
│
├── python/                                    # 【Python 后端核心】
│   ├── requirements.txt                      # Python全量依赖
│   ├── Dockerfile                            # 后端镜像
│   ├── docker-compose.yml                    # 编排配置
│   ├── ci_system.db                          # SQLite主库
│   ├── data/rag_index/                       # FAISS向量索引
│   ├── src/
│   │   ├── config.py                          # ★ 全局配置中心 6frozen dataclass
│   │   ├── api/server.py                      # ★ FastAPI应用 33+端点
│   │   ├── graph/workflow.py                  # ★ LangGraph 12节点DAG编排
│   │   ├── agents/                            # 9业务Agent目录
│   │   │   ├── monitor_agent.py
│   │   │   ├── alert_agent.py
│   │   │   ├── research_agent.py
│   │   │   ├── factcheck_agent.py
│   │   │   ├── compare_agent.py
│   │   │   ├── battlecard_agent.py
│   │   │   ├── reviewer_agent.py
│   │   │   ├── targeted_fix_agent.py
│   │   │   ├── citation_agent.py
│   │   │   └── (新增) multimodal_agent.py      # 多模态分析Agent
│   │   ├── models/
│   │   │   └── schemas.py                     # Pydantic v2全量模型 + 新增FixEffectiveness
│   │   ├── models/ontology_schema.py           # ★ Palantir Ontology五层15+实体类
│   │   ├── core/ontology_relation_graph.py      # Ontology关系图谱D3兼容生成
│   │   ├── db/sqlite.py                       # SQLite CRUD 9张表
│   │   ├── infrastructure/                    # 5组件可观测性Hub
│   │   │   ├── observability.py               # 统一Hub入口
│   │   │   ├── event_bus.py                   # 事件总线
│   │   │   ├── agent_logger.py                # Agent决策日志
│   │   │   ├── audit_system.py                # 审计系统
│   │   │   ├── token_manager.py               # Token配额管理
│   │   │   └── dag_visualizer.py              # DAG热力图可视化
│   │   ├── services/
│   │   │   ├── llm/                           # 双Provider LLM工厂
│   │   │   ├── feishu/                        # 飞书Bot服务
│   │   │   ├── rag/                           # RAG知识库
│   │   │   ├── evolution/                     # 自进化引擎
│   │   │   ├── multimodal/                     # ★ 多模态免费6大服务
│   │   │   │   ├── ocr_service.py             # PaddleOCR本地中文OCR
│   │   │   │   ├── doubao_vl_service.py       # 豆包多模态分析
│   │   │   │   ├── screenshot_diff_service.py  # 像素级差异检测
│   │   │   │   ├── video_frame_service.py      # FFmpeg关键帧提取
│   │   │   │   ├── whisper_audio_service.py   # Whisper本地音频转录
│   │   │   │   └── path_security.py           # 路径安全白名单
│   │   │   └── competitive_intelligence_framework.py + weight_fusion_engine.py # 03方案AHP权重融合
│   │   ├── tools/                             # 工具层 网页抓取/搜索/通知
│   │   ├── utils/
│   │   │   ├── log_mask.py                     # 日志脱敏
│   │   │   └── url_security.py                 # URL白名单校验
│   │   └── mock/                               # Mock演示零依赖模式
│   └── tests/                                 # 170+测试用例 7大模块全覆盖
│
├── knowledge-base-public/                     # 【公开电商行业RAG知识库13JSON素材】
│
├── archive/                                    # 历史成员打包存档目录 Gitignore排除
│   ├── archive-20260528-react-full-migration/
│   └── archive-20260601-ci-engineer-25-patches/
│
├── .gitignore                                  # 专业级分层黑白名单零敏感泄露
├── .env.example                                # 脱敏环境变量模板 无真实密钥
├── README.md                                   # 项目总览介绍
└── PROJECT_ARCHITECTURE.md                    # 【本文件】新AI助手100%接手总览
```

### 2.3 分层架构模式
```
┌─────────────────────────────────────────────────────────────┐
│  接入层 (Hertz Go)  :8080 全路由GenericAPIProxy兜底透传     │
│  CORS / 限流 / 请求日志                                     │
├─────────────────────────────────────────────────────────────┤
│  展示层 (React / Streamlit) 双版本  8501/5173              │
│  6页面工作台 / SSE实时进度 / Word导出 / DAG可视化            │
├─────────────────────────────────────────────────────────────┤
│  API路由层 (FastAPI)  :8000  33+端点                      │
│  限流中间件 / 大小限制50MB / CORS / 错误脱敏               │
├─────────────────────────────────────────────────────────────┤
│  编排层 (LangGraph 12节点DAG)                              │
│  Monitor→Alert→Research→Multimodal→FactCheck→Compare→      │
│  Battlecard→Reviewer→TargetedFix→Citation→Ontology→Feishu   │
├─────────────────────────────────────────────────────────────┤
│  业务Agent层 (9专职Agent)                                  │
│  Monitor/Research/FactCheck/Compare/Battlecard/Reviewer/   │
│  TargetedFix/Citation/Alert 职责边界零重叠                 │
├─────────────────────────────────────────────────────────────┤
│  服务层 (LLM/飞书/RAG/多模态/自进化)                        │
├─────────────────────────────────────────────────────────────┤
│  持久化层 (SQLite + FAISS)                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 阶段3：业务与竞品分析逻辑

### 3.1 竞品分析模块
| 维度 | 说明 |
|---|---|
| 竞品数据来源 | 1. Mock演示预生成数据 2. 公开网页网页抓取 3. 飞书多维表格同步录入 4. RAG知识库历史沉淀 |
| 支持分析维度 | 1.产品功能 2.定价策略 3.目标用户 4.技术架构 5.市场定位 6.用户体验 7.内容营销 8.生态策略 + 3新增多模态维度（视觉传达力/设计成熟度/信息可视化） |
| 对比结果可视化 | 8维度评分矩阵表格 / SWOT四象限战术卡 / 关系图谱D3渲染 / 趋势折线图 |

### 3.2 核心页面/功能
| 页面名 | 核心逻辑 | 数据来源 |
|---|---|---|
| 竞品分析主工作台 | 选择竞品 → 启动分析 → SSE实时看12节点进度 → 查看报告 | LangGraph DAG流式输出 |
| 溯源一键跳转页面 | 每条结论绿红点展示可达性 → 点击target="_blank"直接打开原始数据源 | CitationAgent输出source_urls |
| 飞书集成页面 | 配置Webhook → 测试推送 → 查看历史推送记录 | FeishuBot + lark-cli |
| 系统仪表盘 | Agent决策日志 / Token用量趋势 / DAG实时快照 | ObservabilityHub统一输出 |

### 3.3 编码约定与特殊逻辑
| 分类 | 规范说明 |
|---|---|
| 请求约定 | 统一拦截所有detail=str(e)错误脱敏 → 通用提示不泄露后端栈信息 |
| 限流约定 | 60请求/分钟/IP，防止爬虫DOS |
| 路径安全约定 | 本地路径白名单 + 后缀检查 + URL schema白名单防SSRF |
| 状态约定 | PipelineState TypedDict 15字段 Annotated自动合并，不用自己写merge逻辑 |
| 特殊创新点 | 1. 三层递进质量校验闭环 2. PartialCompletion分支3次修复后继续流程 3. Ontology五层语义网络 4. 全本地多模态零云API依赖 |

---

## 关键入口速查清单
| 目标 | 文件路径 |
|---|---|
| 修改DAG编排 | `python/src/graph/workflow.py` |
| 新增Agent | `python/src/agents/` |
| 修改API接口 | `python/src/api/server.py` |
| 看数据模型 | `python/src/models/schemas.py` |
| 多模态服务 | `python/src/services/multimodal/` |
| Ontology图谱 | `python/src/core/ontology_relation_graph.py` |
| React首页 | `frontend-react/src/pages/AgentWorkspace.jsx` |
