# 多Agent企业级竞品情报分析系统

## 项目背景
企业在竞品分析工作中普遍存在三大核心痛点：
1. **信息分散，效率低下**：竞品信息分散在官网、新闻、社交媒体等多个渠道，人工监控更新不及时，一份完整的竞品分析报告需要2天才能完成；
2. **质量依赖个人，输出不标准**：分析质量依赖分析师的个人能力，没有标准化的输出模板，不同人做的分析报告质量参差不齐；
3. **业务赋能不足**：销售团队面对客户提问，没有统一的竞品应对话术，产品决策缺乏数据支撑。

## 产品定位
基于多Agent架构的企业级竞品情报分析平台，实现**竞品监控、深度研究、对比分析、销售战术卡生成、智能告警**的全流程自动化，大幅提升竞品分析的效率与专业性，真正把AI技术落地成可创造业务价值的产品。

## 核心功能
1. **多Agent智能分析**：6个专业Agent（Monitor/Alert/Research/Compare/Battlecard/Quality Check）协同工作，5分钟完成竞品全维度分析
![多Agent实时执行进度](docs/images/workbench_progress.png)

2. **可视化工作台**：零代码操作，业务人员可一键完成竞品分析，实时展示Agent执行进度
![可视化工作台](docs/images/workbench_initial.png)

3. **竞品库管理**：统一维护竞品信息，支持新增、编辑、删除、快速选择，无需重复输入
![快速选择已有竞品](docs/images/workbench_select_competitor.png)

4. **历史分析回溯**：沉淀分析数据，支持按竞品筛选、查看详情，对比竞品变化趋势
![历史分析回溯](docs/images/history_list.png)

5. **标准化报告导出**：一键生成Word格式的竞品分析报告，自动生成结构化内容，可直接用于业务汇报
![Word报告导出](docs/images/word_report_matrix.png)

6. **质量校验机制**：新增Quality Check Agent，对分析结果进行质量评分与反思优化，分析质量评分稳定在9分以上

## 产品架构图
![产品架构图](docs/images/architecture.png)
*架构图说明：前端采用Streamlit实现可视化工作台，后端基于FastAPI提供RESTful API，通过LangGraph编排5个专业Agent，调用通义千问大模型完成分析任务，SQLite实现数据持久化存储。*

## 界面截图
### 1. 竞品分析工作台
![竞品分析工作台](docs/images/workbench_report_matrix.png)
*核心亮点：实时展示Agent执行进度，分Tab结构化展示对比矩阵、销售战术卡等核心内容，9.2分高质量输出。*

### 2. 竞品管理页面
![竞品管理页面](docs/images/competitor_management.png)
*核心亮点：统一维护竞品信息，支持CRUD操作，分析时可快速选择，无需重复输入。*

### 3. 历史分析回溯
![历史分析回溯](docs/images/history_list.png)
*核心亮点：沉淀所有分析数据，支持按竞品筛选，对比竞品变化趋势，实现数据资产化。*

## 技术栈
| 层级 | 技术选型 |
|------|----------|
| 前端 | Streamlit |
| 后端 | FastAPI |
| Agent编排 | LangGraph + LangChain |
| 大模型 | 通义千问（Qwen） |
| 存储 | SQLite |
| 文档导出 | python-docx |

![后端标准化接口文档](docs/images/swagger_api.png)
*基于FastAPI自动生成的RESTful API接口文档，支持在线调试，接口规范清晰，便于前后端对接与后续扩展。*

## 快速启动指南
### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/你的用户名/competitive-intelligence-multi-agent.git
cd competitive-intelligence-multi-agent

# 创建虚拟环境
cd python
python -m venv venv

# 激活虚拟环境
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置大模型
在python目录下创建.env文件，配置通义千问 API Key：
API Key 需从阿里云百炼平台申请：https://dashscope.aliyun.com/

### 3. 启动服务
# 启动后端服务（终端1）
cd python
venv\Scripts\activate
uvicorn src.api.server:app --reload --port 8000

# 启动前端服务（终端2）
cd 项目根目录
python\venv\Scripts\activate
streamlit run frontend\app.py

### 4. 访问系统
打开浏览器访问：http://localhost:8501

## 个人核心贡献
1.完成国产大模型全量适配：将原项目的 OpenAI 全量替换为通义千问，解决了 datetime 序列化、中文域名解析等核心技术问题，实现项目全流程跑通；
2.设计并实现可视化产品界面：从产品视角出发，把纯技术的 API 接口封装成业务人员零代码可用的产品，大幅降低了使用门槛；
3.新增核心业务功能：深度调研企业竞品分析的全流程业务场景，新增了竞品管理、历史分析回溯、标准化报告导出等核心功能，覆盖了从竞品监控到业务赋能的全链路；
4.优化 Agent 工作流：新增质量校验与细粒度反思机制，保证了分析结果的专业性和稳定性，分析质量评分达 9.2 分。

## 项目成果
1.效率提升 90%：把竞品分析的耗时从人工 2 天缩短到 AI 5 分钟，大幅提升了分析效率；
2.分析质量标准化：通过多 Agent 协同 + 质量校验机制，分析结果的质量评分稳定在 9 分以上，实现了标准化的专业输出；
3.业务落地性强：生成的竞品对比矩阵、销售战术卡可直接用于产品决策、销售赋能，真正把 AI 技术落地成了可创造业务价值的产品。

## 演示视频
1 分钟快速演示：从新增竞品→启动分析→查看报告→导出 Word 的全流程。