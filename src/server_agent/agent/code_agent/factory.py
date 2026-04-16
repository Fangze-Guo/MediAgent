"""
Code Agent 工厂类
根据配置选择使用 Qwen 或 Claude 作为后端
"""
import logging
import os
from typing import Optional

from src.server_agent.agent.code_agent.base import BaseCodeAgent
from src.server_agent.agent.code_agent.qwen.qwen_agent import QwenAgent
from src.server_agent.agent.code_agent.claude.claude_agent import ClaudeAgent

logger = logging.getLogger(__name__)


class AgentType:
    """Agent 类型常量"""
    QWEN = "qwen"
    CLAUDE = "claude"


class AgentFactory:
    """Code Agent 工厂类"""

    _instance: Optional['AgentFactory'] = None
    _agent: Optional[BaseCodeAgent] = None
    _agent_type: str = AgentType.QWEN

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化工厂"""
        if AgentFactory._agent_type is None or AgentFactory._agent_type == AgentType.QWEN:
            AgentFactory._agent_type = self._detect_agent_type()
            logger.info(f"[AgentFactory] 检测到 Agent 类型: {AgentFactory._agent_type}")

    @staticmethod
    def _detect_agent_type() -> str:
        """
        检测应该使用的 Agent 类型

        Returns:
            Agent 类型标识符 (qwen/claude)
        """
        # 优先使用环境变量 CODE_AGENT_TYPE
        agent_type = os.getenv("CODE_AGENT_TYPE", "").lower()
        if agent_type in (AgentType.QWEN, AgentType.CLAUDE):
            logger.info(f"[AgentFactory] 使用 CODE_AGENT_TYPE 环境变量: {agent_type}")
            return agent_type

        # 如果没有设置，默认为 qwen
        logger.info(f"[AgentFactory] CODE_AGENT_TYPE 未设置，默认为 qwen")
        return AgentType.QWEN

    def get_agent(self) -> BaseCodeAgent:
        """
        获取 Agent 实例（单例）

        Returns:
            BaseCodeAgent 实例 (QwenAgent 或 ClaudeAgent)
        """
        if self._agent is None:
            if self._agent_type == AgentType.CLAUDE:
                logger.info("[AgentFactory] 正在创建 ClaudeAgent 实例")
                self._agent = ClaudeAgent()
            else:
                logger.info("[AgentFactory] 正在创建 QwenAgent 实例")
                self._agent = QwenAgent()

        return self._agent

    @property
    def agent_type(self) -> str:
        """
        获取当前 Agent 类型

        Returns:
            Agent 类型标识符
        """
        return self._agent_type

    def create_agent(self) -> BaseCodeAgent:
        """
        创建新的 Agent 实例（每次调用都创建新实例）

        Returns:
            BaseCodeAgent 实例
        """
        if self._agent_type == AgentType.CLAUDE:
            logger.info("[AgentFactory] 正在创建新的 ClaudeAgent 实例")
            return ClaudeAgent()
        else:
            logger.info("[AgentFactory] 正在创建新的 QwenAgent 实例")
            return QwenAgent()

    def switch_agent_type(self, agent_type: str) -> BaseCodeAgent:
        """
        切换 Agent 类型并返回新实例

        Args:
            agent_type: 新的 Agent 类型 (qwen/claude)

        Returns:
            新的 BaseCodeAgent 实例
        """
        if agent_type not in (AgentType.QWEN, AgentType.CLAUDE):
            raise ValueError(f"无效的 Agent 类型: {agent_type}")

        self._agent_type = agent_type
        self._agent = None  # 重置单例，下次 get_agent 会创建新实例
        logger.info(f"[AgentFactory] 已切换到 Agent 类型: {agent_type}")
        return self.get_agent()


# 全局工厂实例
_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """
    获取 Agent 工厂实例

    Returns:
        AgentFactory 实例
    """
    global _factory
    if _factory is None:
        _factory = AgentFactory()
    return _factory


def get_code_agent() -> BaseCodeAgent:
    """
    获取 Code Agent 实例的便捷函数

    Returns:
        BaseCodeAgent 实例
    """
    return get_agent_factory().get_agent()


def get_agent_type() -> str:
    """
    获取当前 Agent 类型

    Returns:
        Agent 类型标识符 (qwen/claude)
    """
    return get_agent_factory().agent_type
