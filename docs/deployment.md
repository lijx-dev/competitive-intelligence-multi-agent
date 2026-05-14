# 部署指南

## 快速开始

### 前置条件

- Docker & Docker Compose
- OpenAI API Key（或兼容的LLM API）

### 一键启动（Python版）

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/competitive-intelligence-multi-agent.git
cd competitive-intelligence-multi-agent/python

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY

# 3. 启动所有服务
docker-compose up -d

# 4. 验证服务健康
curl http://localhost:8000/health

# 5. 运行一次竞品分析
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"competitor": "Stripe"}'
```

### 本地开发运行（不需要Docker）

```bash
cd python

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env

# 启动服务
uvicorn src.api.server:app --reload --port 8000
```

> 注意：本地开发模式下，Kafka/ES/Redis相关功能会优雅降级（跳过或使用内存替代）。


---

## API 使用说明

### 健康检查

```bash
GET /health

# 响应
{"status": "ok", "timestamp": "2026-04-06T12:00:00"}
```

### 同步分析

```bash
POST /analyze
Content-Type: application/json

{
  "competitor": "Stripe",
  "urls": [
    "https://stripe.com",
    "https://stripe.com/pricing",
    "https://stripe.com/jobs"
  ]
}

# urls 可选，不传则自动生成默认URL
```

### SSE 流式分析（Python版）

```bash
POST /analyze/stream
Content-Type: application/json

{"competitor": "Stripe"}

# SSE事件流响应
event: monitor
data: {"changes_detected": [...]}

event: alert
data: {"alerts_sent": [...]}

event: research
data: {"research_results": [...]}

event: compare
data: {"comparison_matrix": {...}}

event: battlecard
data: {"battlecard": {...}}
```

---

## 环境变量说明

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| OPENAI_API_KEY | 是 | - | OpenAI API密钥 |
| LLM_MODEL | 否 | gpt-4o | LLM模型名称 |
| LLM_TEMPERATURE | 否 | 0.3 | 生成温度 |
| KAFKA_BOOTSTRAP_SERVERS | 否 | localhost:9092 | Kafka地址 |
| ES_URL | 否 | http://localhost:9200 | ES地址 |
| REDIS_URL | 否 | redis://localhost:6379/0 | Redis地址 |
| SLACK_WEBHOOK_URL | 否 | - | Slack通知Webhook |
| DINGTALK_WEBHOOK_URL | 否 | - | 钉钉通知Webhook |
| QUALITY_THRESHOLD | 否 | 7.0 | Reflexion质量阈值 |
| MAX_REFLEXION_RETRIES | 否 | 3 | 最大重试次数 |

---

## 生产部署建议

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ci-agent-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ci-agent
  template:
    spec:
      containers:
        - name: api
          image: ci-agent:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: ci-agent-secrets
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

### 监控

- Prometheus: 采集API指标
- Grafana: Dashboard展示
- LangSmith: LLM调用链追踪
- ELK: 日志聚合分析
