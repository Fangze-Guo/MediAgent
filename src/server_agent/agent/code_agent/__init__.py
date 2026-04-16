"""
Code Agent 模块
提供统一的 Code Agent 接口，支持 Qwen 和 Claude 两种后端

Usage:
    from src.server_agent.agent.code_agent import get_code_agent, get_agent_type

    # 获取当前 Agent
    agent = get_code_agent()

    # 根据配置自动选择 Qwen 或 Claude
    async for chunk in agent.stream_chat(message, session_id):
        ...

    # 查看当前使用的 Agent 类型
    print(get_agent_type())  # "qwen" 或 "claude"
"""
from src.server_agent.agent.code_agent.base import BaseCodeAgent
from src.server_agent.agent.code_agent.qwen.qwen_agent import QwenAgent
from src.server_agent.agent.code_agent.claude.claude_agent import ClaudeAgent
from src.server_agent.agent.code_agent.factory import (
    AgentFactory,
    AgentType,
    get_agent_factory,
    get_code_agent,
    get_agent_type
)
from src.server_agent.agent.code_agent.session_manager import BaseSessionManager
from src.server_agent.agent.code_agent.qwen.qwen_session_manager import QwenSessionManager
from src.server_agent.agent.code_agent.claude.claude_session_manager import ClaudeSessionManager
from src.server_agent.agent.code_agent.stream_parser import (
    StreamParser,
    StreamEvent,
    SystemEvent,
    MessageStartEvent,
    ContentBlockDeltaEvent,
    ContentBlockStopEvent,
    MessageStopEvent,
    AssistantEvent,
    ResultEvent,
    parse_stream
)

__all__ = [
    # 基础接口
    "BaseCodeAgent",
    "BaseSessionManager",

    # 具体实现
    "QwenAgent",
    "ClaudeAgent",
    "QwenSessionManager",
    "ClaudeSessionManager",

    # 工厂
    "AgentFactory",
    "AgentType",
    "get_agent_factory",
    "get_code_agent",
    "get_agent_type",

    # 流式解析器
    "StreamParser",
    "StreamEvent",
    "SystemEvent",
    "MessageStartEvent",
    "ContentBlockDeltaEvent",
    "ContentBlockStopEvent",
    "MessageStopEvent",
    "AssistantEvent",
    "ResultEvent",
    "parse_stream",
]