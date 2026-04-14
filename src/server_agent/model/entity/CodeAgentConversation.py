"""
Code智能体实体模型
Code智能体相关的数据库实体
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CodeAgentConversation:
    """Code智能体会话实体"""
    id: int
    conversation_id: str  # UUID 格式的会话ID
    user_id: int
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CodeAgentMessage:
    """Code智能体消息实体"""
    id: int
    message_id: str  # UUID 格式的消息ID
    conversation_id: str  # UUID 格式的会话ID
    role: str  # 'user' 或 'assistant'
    content: str
    created_at: Optional[datetime] = None


@dataclass
class ConversationDetail:
    """会话详情（包含消息列表）"""
    conversation: CodeAgentConversation
    messages: list[CodeAgentMessage]


@dataclass
class ConversationInfo:
    """会话信息（用于列表展示）"""
    conversation_id: str
    user_id: int
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message: Optional[str] = None
