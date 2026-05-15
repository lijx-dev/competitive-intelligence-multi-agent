# 多Agent竞品情报分析系统 - 项目架构文档

## 1. 项目概述

本项目是一个基于多Agent架构的企业级竞品情报分析平台，实现竞品监控、深度研究、对比分析、销售战术卡生成、智能告警的全流程自动化。

### 核心价值
- **效率提升90%**：竞品分析耗时从人工2天缩短到AI 5分钟
- **质量标准化**：分析质量评分稳定在9分以上
- **业务赋能**：生成的竞品对比矩阵、销售战术卡可直接用于产品决策和销售赋能

---

## 2. 技术栈概览

| 层级 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| **前端框架** | Streamlit | >=1.30 | 可视化工作台，零代码操作界面 |
| **后端框架** | FastAPI | >=0.115 | 高性能RESTful API服务 |
| **Agent编排** | LangGraph | >=0.2.0 | 多Agent协作工作流编排 |
| **大模型框架** | LangChain | >=0.3.0 | LLM调用封装 |
| **大模型** | 通义千问（Qwen） | qwen-plus | 阿里云百炼平台 |
| **数据库** | SQLite | 内置 | 竞品库和历史分析记录持久化 |
| **流式通信** | sse-starlette | >=2.1.0 | Server-Sent Events |
| **文档导出** | python-docx | latest | Word格式报告生成 |

---

## 3. 目录结构

```
competitive-intelligence-multi-agent/
├── docs/                    # 项目文档
│   ├── code-walkthrough/    # 各语言代码示例
│   ├── images/              # 界面截图和架构图
│   └── interview/           # 面试相关资料
├── frontend/                # 前端应用（Streamlit）
│   └── app.py               # 前端入口文件（单页应用）
├── python/                  # 后端代码（Python）
│   ├── src/
│   │   ├── agents/          # Agent实现（核心业务逻辑）
│   │   │   ├── __init__.py
│   │   │   ├── alert_agent.py      # 告警Agent：发送通知
│   │   │   ├── battlecard_agent.py # 销售战术卡Agent
│   │   │   ├── compare_agent.py    # 对比分析Agent
│   │   │   ├── monitor_agent.py    # 变更监控Agent
│   │   │   └── research_agent.py   # 深度研究Agent
│   │   ├── api/             # RESTful API服务
│   │   │   ├── __init__.py
│   │   │   └── server.py    # FastAPI入口，路由定义
│   │   ├── db/              # 数据库操作
│   │   │   ├── __init__.py
│   │   │   └── sqlite.py    # SQLite CRUD封装
│   │   ├── graph/           # 工作流编排
│   │   │   ├── __init__.py
│   │   │   └── workflow.py  # LangGraph状态机定义
│   │   ├── models/          # 数据模型
│   │   │   ├── __init__.py
│   │   │   └── schemas.py   # Pydantic模型定义
│   │   ├── tools/           # 工具函数
│   │   │   ├── __init__.py
│   │   │   ├── notification.py     # 通知工具（Slack/DingTalk/邮件）
│   │   │   ├── search_tool.py      # 搜索工具
│   │   │   └── web_scraper.py      # 网页抓取工具
│   │   ├── config.py        # 全局配置管理（环境变量）
│   │   └── __init__.py
│   ├── tests/               # 测试代码
│   │   ├── __init__.py
│   │   └── test_pipeline.py # 工作流测试
│   ├── .env.example         # 环境变量示例模板
│   ├── Dockerfile           # Docker镜像配置
│   ├── docker-compose.yml   # 容器编排配置
│   └── requirements.txt     # Python依赖清单
├── PROJECT_ARCHITECTURE.md  # 本文件
├── .gitignore
├── LICENSE
└── README.md
```

---

## 4. 核心架构设计

### 4.1 Agent工作流架构

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
      │ Alert Agent  │  │ Research Agent│  ← 并行执行
      └──────────────┘  └───────┬───────┘
                                ▼
                      ┌─────────────────┐
                      │ Compare Agent   │  ← 生成对比矩阵
                      └────────┬────────┘
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
               │ Research │    │ END │  ← 循环优化直到达标
               └──────────┘    └─────┘
```

### 4.2 Agent职责说明

| Agent名称 | 职责描述 | 输入 | 输出 |
|-----------|----------|------|------|
| **Monitor** | 监控竞品URL内容变化 | 竞品名称、监控URL列表 | 变更检测列表 |
| **Alert** | 发送告警通知 | 变更检测结果 | 告警发送记录 |
| **Research** | 深度研究竞品信息 | 竞品名称、变更信息 | 研究洞察列表 |
| **Compare** | 生成竞品对比矩阵 | 研究结果 | 对比维度矩阵 |
| **Battlecard** | 生成销售战术卡 | 对比矩阵 | 战术卡（优势/劣势/话术） |
| **Quality Check** | 质量评分与反思 | 战术卡、对比矩阵 | 质量分数 |

### 4.3 数据流

```
用户输入 → API层 → LangGraph → Agent执行 → 结果存储 → 返回前端
              ↓                ↓
           SQLite           LLM调用
```

---

## 5. 核心开发规范

### 5.1 如何添加新页面（前端）

当前前端为单文件Streamlit应用，页面通过侧边栏导航切换：

```python
# 1. 在侧边栏添加新页面选项
page = st.radio("功能导航", ["竞品分析工作台", "竞品管理", "历史分析", "新页面"])

# 2. 添加页面逻辑
elif page == "新页面":
    st.header("新页面标题")
    # 添加页面内容...
```

**页面开发约定**：
- 每个页面使用 `elif page == "页面名称"` 结构
- 页面开头必须包含健康检查
- 复杂逻辑抽取为独立函数
- 使用 `st.session_state` 管理交互状态

### 5.2 如何调用后端接口

#### 5.2.1 基础请求模式

```python
import requests

API_BASE_URL = "http://localhost:8000"

# GET请求
res = requests.get(f"{API_BASE_URL}/endpoint", params={"key": "value"}, timeout=5)
if res.status_code == 200:
    data = res.json()

# POST请求
res = requests.post(f"{API_BASE_URL}/endpoint", json={"key": "value"}, timeout=5)

# PUT请求
res = requests.put(f"{API_BASE_URL}/endpoint/{id}", json={"key": "value"}, timeout=5)

# DELETE请求
res = requests.delete(f"{API_BASE_URL}/endpoint/{id}", timeout=5)
```

#### 5.2.2 SSE流式请求（实时进度）

```python
from sseclient import SSEClient
import json

response = requests.post(
    f"{API_BASE_URL}/analyze/stream",
    json=request_body,
    stream=True,
    headers={"Accept": "text/event-stream"}
)
client = SSEClient(response)

for event in client.events():
    if event.event == "error":
        # 处理错误
        break
    node_data = json.loads(event.data)
    # 处理节点数据...
```

### 5.3 如何添加新Agent

```python
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatTongyi
from ..config import config

class NewAgent:
    def __init__(self):
        self.llm = ChatTongyi(
            model=config.llm.model,
            api_key=config.llm.api_key,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
    
    async def analyze(self, input_data):
        """核心业务逻辑"""
        response = await self.llm.ainvoke([
            SystemMessage(content="系统提示词"),
            HumanMessage(content=f"用户输入：{input_data}"),
        ])
        return response.content
    
    async def __call__(self, state: dict) -> dict:
        """LangGraph节点接口"""
        input_data = state.get("input_key", "")
        result = await self.analyze(input_data)
        return {"output_key": result}
```

然后在 `workflow.py` 中注册：

```python
new_agent = NewAgent()

graph.add_node("new_node", new_agent)
graph.add_edge("previous_node", "new_node")
```

### 5.4 如何添加新API端点

```python
# 在 python/src/api/server.py 中添加

# 1. 定义请求/响应模型（如果需要）
class NewRequest(BaseModel):
    param1: str
    param2: int = 0

class NewResponse(BaseModel):
    result: str
    status: str = "success"

# 2. 添加路由
@app.post("/new-endpoint", response_model=NewResponse)
async def new_endpoint(req: NewRequest):
    """端点描述"""
    # 业务逻辑...
    return {"result": "success"}
```

---

## 6. 数据库设计

### 6.1 竞品库表（competitors）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 主键 |
| name | TEXT | NOT NULL UNIQUE | 竞品名称（唯一） |
| urls | TEXT | NOT NULL | 监控URL列表（JSON数组） |
| created_at | TEXT | NOT NULL | 创建时间（ISO格式） |
| updated_at | TEXT | NOT NULL | 更新时间（ISO格式） |

### 6.2 历史分析记录表（analysis_records）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 主键 |
| competitor_id | INTEGER | FOREIGN KEY | 关联竞品ID（可选） |
| competitor_name | TEXT | NOT NULL | 竞品名称 |
| request_urls | TEXT | - | 本次分析的URL（JSON数组） |
| analysis_result | TEXT | NOT NULL | 完整分析结果（JSON） |
| quality_score | REAL | DEFAULT 0.0 | 质量评分 |
| created_at | TEXT | NOT NULL | 创建时间 |

---

## 7. API接口规范

### 7.1 健康检查

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/health` | 服务健康检查 |

### 7.2 分析接口

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/analyze` | 同步执行完整分析流程 |
| POST | `/analyze/stream` | SSE流式分析（实时进度） |

**请求体**：
```json
{
  "competitor": "竞品名称",
  "urls": ["https://example.com"]
}
```

**响应体**：
```json
{
  "competitor": "竞品名称",
  "changes_detected": [],
  "research_results": [],
  "comparison_matrix": {},
  "battlecard": {},
  "alerts_sent": [],
  "quality_score": 9.2
}
```

### 7.3 竞品管理接口

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/competitors/all` | 获取所有竞品列表 |
| GET | `/competitors/{id}` | 获取竞品详情 |
| POST | `/competitors` | 新增竞品 |
| PUT | `/competitors/{id}` | 更新竞品信息 |
| DELETE | `/competitors/{id}` | 删除竞品 |

### 7.4 历史记录接口

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/analysis/records` | 获取历史分析记录（可按竞品筛选） |
| GET | `/analysis/records/{id}` | 获取分析记录详情 |

---

## 8. 配置管理

### 8.1 环境变量配置

创建 `python/.env` 文件：

```env
# LLM配置
LLM_PROVIDER=tongyi
LLM_MODEL=qwen-plus
DASHSCOPE_API_KEY=your-api-key

# 应用配置
MONITOR_INTERVAL_MINUTES=60
QUALITY_THRESHOLD=7.0
MAX_REFLEXION_RETRIES=3

# Kafka配置（可选）
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# 通知配置（可选）
SLACK_WEBHOOK_URL=
DINGTALK_WEBHOOK_URL=
```

### 8.2 配置读取

```python
# python/src/config.py 已封装
from ..config import config

# 使用示例
llm_api_key = config.llm.api_key
quality_threshold = config.quality_threshold
```

---

## 9. 部署与运行

### 9.1 开发环境启动

```bash
# 1. 进入python目录
cd python

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动后端服务
uvicorn src.api.server:app --reload --port 8000

# 6. 启动前端服务（新终端）
cd 项目根目录
streamlit run frontend/app.py
```

### 9.2 访问地址

- 前端：http://localhost:8501
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

---

## 10. 代码质量规范

### 10.1 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 文件/目录 | 小写蛇形 | `research_agent.py` |
| 类名 | PascalCase | `ResearchAgent` |
| 函数/方法 | 小写蛇形 | `analyze_competitor()` |
| 变量 | 小写蛇形 | `competitor_name` |
| 常量 | 大写蛇形 | `API_BASE_URL` |

### 10.2 代码风格

- 使用 Python 3.10+ 类型注解
- 函数/方法必须有文档字符串
- 行长度不超过120字符
- 使用 `black` 进行代码格式化
- 使用 `flake8` 进行代码检查

### 10.3 错误处理

- API层使用 `try-except` 捕获异常
- 数据库操作必须有异常处理
- 敏感信息禁止打印到日志
- 使用 `logging` 模块记录日志

---

## 11. 注意事项

### 11.1 当前技术债

1. **前端单文件过大**：`app.py` 超过500行，建议模块化拆分
2. **无统一API封装**：重复的requests调用，建议抽取工具函数
3. **缺乏认证机制**：所有接口公开访问，生产环境需添加认证
4. **状态键名硬编码**：`st.session_state[f"edit_comp_{id}"]` 易出错
5. **测试覆盖不足**：前端无单元测试

### 11.2 扩展建议

1. 添加用户认证模块（JWT/OAuth）
2. 前端按功能拆分组件
3. 增加接口请求超时和重试机制
4. 添加接口限流
5. 完善测试覆盖

---

## 12. 联系方式

项目维护者：
- 文档版本：v1.0
- 最后更新：2026-05-15