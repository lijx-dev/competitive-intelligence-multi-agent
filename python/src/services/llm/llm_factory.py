"""
LLM 工厂 — 根据配置动态创建 LLM 实例，支持豆包/通义千问双 Provider。

所有 Agent 通过 LLMFactory.get_llm(agent_name) 获取统一 LLM 接口，
不再直接依赖 langchain_community.chat_models.ChatTongyi。

Provider 切换策略:
    - provider="doubao" → DoubaoLLM（默认，比赛指定模型）
    - provider="tongyi" → ChatTongyi（回退兼容）
"""

from __future__ import annotations

import logging
from typing import Any

from ...config import get_effective_llm_config

logger = logging.getLogger(__name__)

# 延迟导入避免循环依赖
_DOUBAO_IMPORTED = False


def _get_doubao_llm(agent_name: str = "default") -> Any:
    """创建豆包 LLM 实例"""
    global _DOUBAO_IMPORTED
    if not _DOUBAO_IMPORTED:
        from .doubao_client import DoubaoLLM
        _DOUBAO_IMPORTED = True

    cfg = get_effective_llm_config()
    from .doubao_client import DoubaoLLM

    return DoubaoLLM(
        model_id=getattr(cfg, "doubao_model_id", None) or cfg.model or "doubao-seed-2.0-lite",  # 官方提供模型
        api_key=getattr(cfg, "ark_api_key", None) or cfg.api_key or "",
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        # 可根据 agent 类型调整 context_editing
        context_editing={
            "enabled": True,
            "max_context_tokens": 64000 if agent_name == "research" else 32000,
            "truncation_strategy": "tail",
        },
    )


def _get_tongyi_llm() -> Any:
    """创建通义千问 LLM 实例（回退兼容）"""
    from langchain_community.chat_models import ChatTongyi
    cfg = get_effective_llm_config()
    return ChatTongyi(
        model=cfg.model,
        api_key=cfg.api_key,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )


class LLMFactory:
    """LLM 工厂 — 根据 provider 配置创建对应 LLM 实例。

    使用示例:
        from src.services.llm import LLMFactory
        llm = LLMFactory.get_llm("research")
        response = await llm.ainvoke([SystemMessage(...), HumanMessage(...)])
    """

    @staticmethod
    def get_llm(agent_name: str = "default") -> Any:
        """获取 LLM 实例。

        Args:
            agent_name: Agent 名称（如 "research"/"compare"），用于差异化配置

        Returns:
            DoubaoLLM（provider=doubao）或 ChatTongyi（provider=tongyi）
        """
        cfg = get_effective_llm_config()
        provider = getattr(cfg, "provider", "doubao")

        logger.debug("LLMFactory: agent=%s, provider=%s, model=%s", agent_name, provider, cfg.model)

        if provider == "tongyi":
            logger.info("使用通义千问 Provider（回退模式）")
            return _get_tongyi_llm()

        # 默认：豆包（2026 字节 AI 全栈挑战赛指定模型）
        logger.info("使用豆包 Provider: agent=%s, model=%s", agent_name, cfg.model)
        return _get_doubao_llm(agent_name)

    @staticmethod
    def get_multimodal_llm(agent_name: str = "multimodal_analysis") -> Any:
        """获取多模态 LLM 实例，优先豆包自动降级通义。

        豆包 DoubaoLLM 的 ainvoke_multimodal() 内部已包含 fallback 逻辑。
        通义模式下动态 monkey-patch 兼容的 ainvoke_multimodal 占位方法。
        """
        cfg = get_effective_llm_config()
        provider = getattr(cfg, "provider", "doubao")
        if provider == "doubao":
            return _get_doubao_llm(agent_name)
        else:
            logger.info("多模态使用通义回退模式")
            tongyi_llm = _get_tongyi_llm()
            # 动态绑定多模态兼容方法
            async def _dummy_tongyi_multimodal(
                self, image_path_or_url: str = "", prompt_text: str = ""
            ) -> str:
                logger.warning(
                    "当前provider=tongyi，多模态能力请切换provider=doubao获得完整体验"
                )
                return ""
            setattr(
                tongyi_llm,
                "ainvoke_multimodal",
                _dummy_tongyi_multimodal.__get__(tongyi_llm, type(tongyi_llm)),
            )
            return tongyi_llm

    @staticmethod
    def get_provider_info() -> dict:
        """获取当前 Provider 信息（供系统信息 API 使用）"""
        cfg = get_effective_llm_config()
        return {
            "provider": getattr(cfg, "provider", "doubao"),
            "model": cfg.model,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
