import logging
from typing import Optional

from src.server_agent.agent.conversation_agent import AgentConfig, ConversationAgent
from src.server_agent.agent.react_agent import ReActAgent
from src.server_agent.configs.config_provider import ModelSnapshot

logger = logging.getLogger(__name__)


class RuntimeRegistry:
    """管理当前运行态的 ConversationAgent 与 ReActAgent 实例。"""

    def __init__(self, agent: ConversationAgent, react_agent: ReActAgent) -> None:
        self._agent = agent
        self._react_agent = react_agent

    def refresh_runtime(self, snapshot: Optional[ModelSnapshot]) -> None:
        """根据新的模型快照热更新两个 agent 的配置。"""
        if snapshot is None:
            return
        self._agent.update_config(
            model=snapshot.current_model_id,
            api_key=snapshot.api_key,
            base_url=snapshot.base_url,
        )
        self._react_agent.update_config(
            model=snapshot.current_model_id,
            api_key=snapshot.api_key,
            base_url=snapshot.base_url,
        )
        logger.info("RuntimeRegistry: agent config refreshed — model=%s", snapshot.current_model_id)

    def get_agent(self) -> ConversationAgent:
        return self._agent

    def get_react_agent(self) -> ReActAgent:
        return self._react_agent
