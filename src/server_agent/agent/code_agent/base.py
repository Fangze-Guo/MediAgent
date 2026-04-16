"""
Code Agent 基础接口
定义 Code Agent 的抽象接口，具体实现由 Qwen 或 Claude 完成
"""
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class BaseCodeAgent(ABC):
    """Code Agent 基类"""

    def __init__(self, agent_type: str = "unknown"):
        """
        初始化基础 Code Agent

        Args:
            agent_type: Agent 类型标识 (qwen/claude)
        """
        self.agent_type = agent_type
        self.timeout = 120

    @abstractmethod
    async def stream_chat(
        self,
        current_message: str,
        session_id: Optional[str] = None,
        is_file: bool = False,
        use_stream_json: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        流式对话方法

        Args:
            current_message: 当前用户消息（如果是is_file=True，则为文件路径）
            session_id: 会话ID，用于管理历史对话
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Yields:
            每个输出片段的JSON字符串（SSE格式）
        """
        yield ""

    @abstractmethod
    async def chat(
        self,
        current_message: str,
        session_id: Optional[str] = None,
        is_file: bool = False,
        use_stream_json: bool = True
    ) -> str:
        """
        同步对话方法（非流式）

        Args:
            current_message: 当前用户消息（如果是is_file=True，则为文件路径）
            session_id: 会话ID，用于管理历史对话
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Returns:
            AI的完整回复
        """
        pass

    async def close_session(self, session_id: str):
        """
        关闭指定会话

        Args:
            session_id: 会话ID
        """
        logger.info(f"[{self.agent_type}] 会话已关闭: {session_id}")

    async def close_all_sessions(self):
        """关闭所有会话"""
        logger.info(f"[{self.agent_type}] 所有会话已关闭")