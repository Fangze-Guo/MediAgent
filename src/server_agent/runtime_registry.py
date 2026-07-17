import logging
import os
from typing import Optional

from src.server_agent.agent.conversation_agent import AgentConfig, ConversationAgent
from src.server_agent.agent.react_agent import ReActAgent
from src.server_agent.configs.config_provider import ConfigProvider, ModelSnapshot
from src.server_agent.exceptions import ValidationError

logger = logging.getLogger(__name__)


class RuntimeRegistry:
    """根据请求模型创建隔离的 Agent，避免用户之间共享可变 LLM 状态。"""

    def __init__(self, provider: ConfigProvider) -> None:
        self._provider = provider

    def _resolve_snapshot(self, model_id: Optional[str]) -> ModelSnapshot:
        selected_model_id = model_id or self._provider.get_default_model_id()
        if not selected_model_id:
            fallback_model = os.getenv("MODEL", "qwen3-30b-a3b")
            return ModelSnapshot(
                current_model_id=fallback_model,
                model=fallback_model,
                api_key=os.getenv("MODEL_API_KEY"),
                base_url=os.getenv("MODEL_URL"),
            )
        snapshot = self._provider.get_model_snapshot(selected_model_id)
        if snapshot is None:
            raise ValidationError(
                detail=f"模型 '{selected_model_id}' 不存在或未启用",
                field="model_id",
                context={"model_id": selected_model_id},
            )
        return snapshot

    @staticmethod
    def _to_agent_config(snapshot: ModelSnapshot) -> AgentConfig:
        return AgentConfig(
            model=snapshot.model,
            api_key=snapshot.api_key,
            base_url=snapshot.base_url,
            temperature=snapshot.temperature,
        )

    def get_agent(self, model_id: Optional[str] = None) -> ConversationAgent:
        snapshot = self._resolve_snapshot(model_id)
        logger.info("Creating request-scoped ConversationAgent — model=%s", snapshot.current_model_id)
        return ConversationAgent(self._to_agent_config(snapshot))

    def get_react_agent(self, model_id: Optional[str] = None) -> ReActAgent:
        snapshot = self._resolve_snapshot(model_id)
        logger.info("Creating request-scoped ReActAgent — model=%s", snapshot.current_model_id)
        return ReActAgent(self._to_agent_config(snapshot))
