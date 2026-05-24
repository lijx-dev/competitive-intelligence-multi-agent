"""配置管理 —— 默认值来自 .env，运行时可通过 DB 动态覆盖，即时生效。

分层架构：
    .env 环境变量 (frozen dataclass)  ← 系统默认值，不可变
    SQLite system_config 表           ← 用户运行时覆盖
    get_effective_*() 合并函数        ← Agent / 工具统一入口
"""

import os
import json
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

logger = logging.getLogger(__name__)

# ============================================================
# 默认值定义（来自 .env，不可变）
# ============================================================

@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置 — 兼容豆包 / 通义千问双 Provider"""
    provider: str = os.getenv("LLM_PROVIDER", "doubao")                        # doubao / tongyi
    model: str = os.getenv("LLM_MODEL", os.getenv("DOUBAO_MODEL_ID", "doubao-seed-2.0-lite"))  # 官方提供模型
    api_key: str = os.getenv("DASHSCOPE_API_KEY", "")                           # 通义千问（回退）
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # 豆包特有字段
    ark_api_key: str = os.getenv("ARK_API_KEY", "")                             # 火山引擎 Ark API Key
    doubao_model_id: str = os.getenv("DOUBAO_MODEL_ID", "doubao-seed-2.0-lite")  # 官方提供模型


@dataclass(frozen=True)
class DoubaoConfig:
    """豆包大模型特有参数"""
    context_editing_enabled: bool = True
    max_context_tokens: int = int(os.getenv("DOUBAO_MAX_CONTEXT_TOKENS", "32000"))
    truncation_strategy: str = os.getenv("DOUBAO_TRUNCATION_STRATEGY", "tail")
    base_url: str = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")


@dataclass(frozen=True)
class KafkaConfig:
    bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    group_id: str = os.getenv("KAFKA_GROUP_ID", "ci-agents")
    topics: dict = field(default_factory=lambda: {
        "changes": os.getenv("KAFKA_TOPIC_CHANGES", "ci.changes"),
        "analysis": os.getenv("KAFKA_TOPIC_ANALYSIS", "ci.analysis"),
        "comparison": os.getenv("KAFKA_TOPIC_COMPARISON", "ci.comparison"),
        "battlecard": os.getenv("KAFKA_TOPIC_BATTLECARD", "ci.battlecard"),
        "alerts": os.getenv("KAFKA_TOPIC_ALERTS", "ci.alerts"),
    })


@dataclass(frozen=True)
class ElasticsearchConfig:
    url: str = os.getenv("ES_URL", "http://localhost:9200")
    index_prefix: str = os.getenv("ES_INDEX_PREFIX", "ci-")
    api_key: str = os.getenv("ES_API_KEY", "")


@dataclass(frozen=True)
class RedisConfig:
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@dataclass(frozen=True)
class NotificationConfig:
    slack_webhook: str = os.getenv("SLACK_WEBHOOK_URL", "")
    slack_enabled: bool = False
    dingtalk_webhook: str = os.getenv("DINGTALK_WEBHOOK_URL", "")
    dingtalk_enabled: bool = False
    feishu_webhook_url: str = os.getenv("FEISHU_WEBHOOK_URL", "")
    feishu_webhook_secret: str = os.getenv("FEISHU_WEBHOOK_SECRET", "")
    feishu_enabled: bool = False
    email_smtp_host: str = os.getenv("EMAIL_SMTP_HOST", "")
    email_smtp_port: int = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")
    email_to: str = ""
    email_enabled: bool = False


@dataclass(frozen=True)
class AlertConfig:
    severity_threshold: str = "high"
    rate_limit_per_hour: int = 10
    silence_minutes: int = 60


@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    doubao: DoubaoConfig = field(default_factory=DoubaoConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    elasticsearch: ElasticsearchConfig = field(default_factory=ElasticsearchConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)

    monitor_interval_minutes: int = int(os.getenv("MONITOR_INTERVAL_MINUTES", "60"))
    quality_threshold: float = float(os.getenv("QUALITY_THRESHOLD", "7.0"))
    max_reflexion_retries: int = int(os.getenv("MAX_REFLEXION_RETRIES", "3"))

    # 自进化参数
    evolution_enabled: bool = os.getenv("EVOLUTION_ENABLED", "true").lower() == "true"
    evolution_auto_commit_threshold: float = float(os.getenv("EVOLUTION_AUTO_COMMIT_THRESHOLD", "0.8"))
    evolution_confidence_boost: float = float(os.getenv("EVOLUTION_CONFIDENCE_BOOST", "0.10"))
    evolution_confidence_penalty: float = float(os.getenv("EVOLUTION_CONFIDENCE_PENALTY", "0.20"))
    evolution_kb_path: str = os.getenv("EVOLUTION_KB_PATH", "")


# 模块级默认配置单例（不可变默认值）
_defaults = AppConfig()


# ============================================================
# 动态配置加载（运行时从 DB 覆盖默认值）
# ============================================================

def _db_get_config():
    """延迟加载 DB 配置（避免循环导入）"""
    try:
        from .db.sqlite import get_all_config
        return get_all_config()
    except Exception:
        return {}


def get_effective_llm_config() -> LLMConfig:
    """返回合并了 DB 覆盖的 LLM 配置（API Key 始终从 .env 读取）"""
    overrides = {}
    try:
        db = _db_get_config()
        llm_db = db.get("llm", {}).get("value", {})
        if isinstance(llm_db, dict):
            overrides = llm_db
    except Exception:
        pass

    return LLMConfig(
        provider=overrides.get("provider", _defaults.llm.provider),
        model=overrides.get("model", _defaults.llm.model),
        api_key=_defaults.llm.api_key,
        temperature=float(overrides.get("temperature", _defaults.llm.temperature)),
        max_tokens=int(overrides.get("max_tokens", _defaults.llm.max_tokens)),
        ark_api_key=_defaults.llm.ark_api_key or _defaults.llm.api_key,
        doubao_model_id=overrides.get("model", _defaults.llm.doubao_model_id),
    )


def get_effective_notification_config() -> NotificationConfig:
    """返回合并了 DB 覆盖的通知配置"""
    overrides = {}
    try:
        db = _db_get_config()
        notif_db = db.get("notification", {}).get("value", {})
        if isinstance(notif_db, dict):
            overrides = notif_db
    except Exception:
        pass

    return NotificationConfig(
        slack_webhook=overrides.get("slack_webhook", _defaults.notification.slack_webhook),
        slack_enabled=bool(overrides.get("slack_enabled", _defaults.notification.slack_enabled)),
        dingtalk_webhook=overrides.get("dingtalk_webhook", _defaults.notification.dingtalk_webhook),
        dingtalk_enabled=bool(overrides.get("dingtalk_enabled", _defaults.notification.dingtalk_enabled)),
        feishu_webhook_url=overrides.get("feishu_webhook_url", _defaults.notification.feishu_webhook_url),
        feishu_webhook_secret=overrides.get("feishu_webhook_secret", _defaults.notification.feishu_webhook_secret),
        feishu_enabled=bool(overrides.get("feishu_enabled", _defaults.notification.feishu_enabled)),
        email_smtp_host=overrides.get("email_smtp_host", _defaults.notification.email_smtp_host),
        email_smtp_port=int(overrides.get("email_smtp_port", _defaults.notification.email_smtp_port)),
        email_from=overrides.get("email_from", _defaults.notification.email_from),
        email_password=overrides.get("email_password", _defaults.notification.email_password),
        email_to=overrides.get("email_to", _defaults.notification.email_to),
        email_enabled=bool(overrides.get("email_enabled", _defaults.notification.email_enabled)),
    )


def get_effective_alert_config() -> AlertConfig:
    """返回合并了 DB 覆盖的告警配置"""
    overrides = {}
    try:
        db = _db_get_config()
        alert_db = db.get("alert", {}).get("value", {})
        if isinstance(alert_db, dict):
            overrides = alert_db
    except Exception:
        pass

    return AlertConfig(
        severity_threshold=overrides.get("severity_threshold", _defaults.alert.severity_threshold),
        rate_limit_per_hour=int(overrides.get("rate_limit_per_hour", _defaults.alert.rate_limit_per_hour)),
        silence_minutes=int(overrides.get("silence_minutes", _defaults.alert.silence_minutes)),
    )


def get_effective_quality_threshold() -> float:
    try:
        db = _db_get_config()
        pipeline_db = db.get("pipeline", {}).get("value", {})
        if isinstance(pipeline_db, dict) and "quality_threshold" in pipeline_db:
            return float(pipeline_db["quality_threshold"])
    except Exception:
        pass
    return _defaults.quality_threshold


def get_effective_max_reflexion_retries() -> int:
    try:
        db = _db_get_config()
        pipeline_db = db.get("pipeline", {}).get("value", {})
        if isinstance(pipeline_db, dict) and "max_reflexion_retries" in pipeline_db:
            return int(pipeline_db["max_reflexion_retries"])
    except Exception:
        pass
    return _defaults.max_reflexion_retries


def get_all_defaults() -> dict:
    """导出所有默认配置（供前端展示默认值和恢复默认使用）"""
    return {
        "llm": {
            "provider": _defaults.llm.provider,
            "model": _defaults.llm.model,
            "temperature": _defaults.llm.temperature,
            "max_tokens": _defaults.llm.max_tokens,
            "doubao_model_id": _defaults.llm.doubao_model_id,
        },
        "notification": {
            "slack_webhook": _defaults.notification.slack_webhook,
            "slack_enabled": _defaults.notification.slack_enabled,
            "dingtalk_webhook": _defaults.notification.dingtalk_webhook,
            "dingtalk_enabled": _defaults.notification.dingtalk_enabled,
            "feishu_webhook_url": _defaults.notification.feishu_webhook_url,
            "feishu_webhook_secret": _defaults.notification.feishu_webhook_secret,
            "feishu_enabled": _defaults.notification.feishu_enabled,
            "email_smtp_host": _defaults.notification.email_smtp_host,
            "email_smtp_port": _defaults.notification.email_smtp_port,
            "email_from": _defaults.notification.email_from,
            "email_password": _defaults.notification.email_password,
            "email_to": _defaults.notification.email_to,
            "email_enabled": _defaults.notification.email_enabled,
        },
        "alert": {
            "severity_threshold": _defaults.alert.severity_threshold,
            "rate_limit_per_hour": _defaults.alert.rate_limit_per_hour,
            "silence_minutes": _defaults.alert.silence_minutes,
        },
        "pipeline": {
            "quality_threshold": _defaults.quality_threshold,
            "max_reflexion_retries": _defaults.max_reflexion_retries,
        },
    }


# 保持向后兼容的模块级 config 引用（仅用于不需要动态覆盖的场景）
config = _defaults
