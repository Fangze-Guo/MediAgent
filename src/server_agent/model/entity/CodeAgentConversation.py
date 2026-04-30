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
    user_id: int
    conversation_id: Optional[str] = None  # UUID 格式的会话ID（前端生成）
    session_id: Optional[str] = None  # SDK 真实的 session_id
    project_id: Optional[str] = None  # 项目标识，如 "bc", "spine"
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CodeAgentMessage:
    """Code智能体消息实体"""
    id: int
    role: str  # 'user' 或 'assistant'
    content: str
    message_id: Optional[str] = None  # UUID 格式的消息ID
    conversation_id: Optional[str] = None  # UUID 格式的会话ID
    thinking: Optional[str] = None  # 思考过程内容
    created_at: Optional[datetime] = None


@dataclass
class ConversationDetail:
    """会话详情（包含消息列表）"""
    conversation: CodeAgentConversation
    messages: list[CodeAgentMessage]


@dataclass
class ConversationInfo:
    """会话信息（用于列表展示）"""
    user_id: int
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None  # SDK 真实的 session_id
    project_id: Optional[str] = None  # 项目标识
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message: Optional[str] = None
