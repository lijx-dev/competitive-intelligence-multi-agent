"""
豆包大模型客户端 — 基于火山引擎 Ark SDK 封装。

统一的 generate() / generate_stream() 接口，
屏蔽底层 API 差异，供 LLMFactory 和所有 Agent 调用。

豆包特有参数（context_editing 等）在此集中管理。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

from volcenginesdkarkruntime import Ark

logger = logging.getLogger(__name__)

# ── 豆包推荐的默认上下文编辑参数 ──
DEFAULT_CONTEXT_EDITING = {
    "enabled": True,
    "max_context_tokens": 32000,  # 豆包长上下文窗口
    "truncation_strategy": "tail",  # 尾部截断
}


class DoubaoLLM:
    """豆包（Doubao）大模型统一调用客户端。

    封装火山引擎 Ark SDK，提供与 LangChain 兼容的接口风格。

    使用示例:
        client = DoubaoLLM(api_key="ark-xxx")
        result = await client.generate("分析竞品", system_prompt="你是分析师")
        print(result["content"])
    """

    def __init__(
        self,
        model_id: str = "doubao-seed-1-8-251228",
        api_key: str = "",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        context_editing: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_editing = context_editing or DEFAULT_CONTEXT_EDITING

        # 初始化 Ark 客户端
        self._client = Ark(
            api_key=api_key,
            base_url=base_url,
        )
        logger.info("豆包客户端初始化完成: model=%s", model_id)

    # ── 同步生成（核心接口） ────────────────────────────────

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """生成补全 — 统一返回 {"content", "usage", "model"}

        Args:
            prompt: 用户消息
            system_prompt: 系统提示词（可选）
            temperature: 覆盖实例温度
            max_tokens: 覆盖实例 max_tokens
            tools: function_calling 工具定义列表（可选）
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 构建请求参数
        request_params: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        # 豆包特有: context_editing 参数
        if self.context_editing.get("enabled"):
            request_params["extra_body"] = {
                "context_editing": {
                    "max_context_tokens": self.context_editing.get("max_context_tokens", 32000),
                    "truncation_strategy": self.context_editing.get("truncation_strategy", "tail"),
                }
            }

        # 透传 function_calling tools
        if tools:
            request_params["tools"] = tools

        # 透传额外参数
        request_params.update(kwargs)

        try:
            response = self._client.chat.completions.create(**request_params)
            choice = response.choices[0]

            # 处理 tool_calls 场景
            if choice.message.tool_calls:
                content = ""
                for tc in choice.message.tool_calls:
                    content += f"[tool_call: {tc.function.name}({tc.function.arguments})]"
            else:
                content = choice.message.content or ""

            return {
                "content": content,
                "usage": {
                    "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "output_tokens": response.usage.completion_tokens if response.usage else 0,
                },
                "model": response.model,
            }
        except Exception as e:
            logger.error("豆包 API 调用失败: %s", str(e))
            raise

    # ── 流式生成（SSE 场景） ─────────────────────────────────

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成 — 逐步 yield 文本片段"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = self._client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("豆包流式调用失败: %s", str(e))
            raise

    # ── LangChain 兼容接口 ───────────────────────────────────

    async def ainvoke(
        self,
        messages: list,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """LangChain 兼容接口：接收 Message 列表，返回类 AIMessage 对象。

        兼容现有 Agent 中 `await self.llm.ainvoke([SystemMessage(...), HumanMessage(...)])` 模式。
        """
        system_prompt = None
        user_prompt = ""

        for msg in messages:
            # LangChain Message 对象的 type 属性
            msg_type = getattr(msg, "type", "")
            if msg_type == "system":
                system_prompt = msg.content
            elif msg_type == "human":
                user_prompt = msg.content
            elif msg_type == "ai":
                continue  # 跳过历史 AI 消息
            else:
                # 兜底：按 role 属性判断
                role = getattr(msg, "role", "")
                if role == "system":
                    system_prompt = msg.content
                elif role in ("user", "human"):
                    user_prompt = msg.content

        result = await self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )

        # 构造类 AIMessage 对象（兼容 response.content 访问）
        return _FakeAIMessage(
            content=result["content"],
            usage=result["usage"],
        )

    # ── 统计 ─────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """返回模型基本信息（供 M5 可观测性使用）"""
        return {
            "provider": "doubao",
            "model": self.model_id,
            "base_url": self._client.base_url,
        }


class _FakeAIMessage:
    """模拟 LangChain AIMessage，兼容 response.content 和 response.usage_metadata"""

    def __init__(self, content: str, usage: dict):
        self.content = content
        self.usage_metadata = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        }
