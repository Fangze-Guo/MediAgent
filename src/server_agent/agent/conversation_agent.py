"""
LangChain-based conversation agent for MediAgent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
你是一个医疗工具助手，负责与用户直接对话，提供专业的医学信息与智能分析支持。

【语言规则】
- 若用户使用中文，全程中文回复。
- 若用户使用英文，全程英文回复。
- 不混用语言。\
"""

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.2
    request_timeout: float = 60.0
    max_retries: int = 2


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class ConversationAgent:
    """
    Stateless LangChain conversation agent.

    History is passed in on every call; the agent holds only LLM config.
    Call `update_config()` for hot-reload when model settings change.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._build_llm()

    def _build_llm(self) -> None:
        self._llm = ChatOpenAI(
            model=self.config.model,
            api_key=self.config.api_key or "lm-studio",
            base_url=self.config.base_url or "http://127.0.0.1:1234/v1",
            temperature=self.config.temperature,
            timeout=self.config.request_timeout,
            max_retries=self.config.max_retries,
        )

    def update_config(
        self,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> None:
        """Hot-reload LLM settings."""
        self.config.model = model
        self.config.api_key = api_key
        self.config.base_url = base_url
        self._build_llm()
        logger.info("ConversationAgent: LLM config reloaded — model=%s", model)

    def _build_messages(
        self, user_input: str, history: List[Dict[str, str]]
    ) -> List[BaseMessage]:
        messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=user_input))
        return messages

    async def converse(
        self,
        user_input: str,
        history: List[Dict[str, str]],
    ) -> str:
        """Single-turn: wait for full reply and return it."""
        try:
            response: AIMessage = await self._llm.ainvoke(
                self._build_messages(user_input, history)
            )
            return (response.content or "").strip() or "（空回复）"
        except Exception as exc:
            logger.error("LLM call failed: %s", exc, exc_info=True)
            return f"抱歉，与语言模型通信失败：{exc}"

    async def stream(
        self,
        user_input: str,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Streaming: yield text tokens progressively via astream."""
        try:
            async for chunk in self._llm.astream(
                self._build_messages(user_input, history)
            ):
                token: str = chunk.content or ""
                if token:
                    yield token
        except Exception as exc:
            logger.error("LLM stream failed: %s", exc, exc_info=True)
            yield f"\n\n抱歉，与语言模型通信失败：{exc}"
