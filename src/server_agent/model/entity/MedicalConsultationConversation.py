"""
医学咨询实体模型
定义医学咨询相关的数据库实体
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MedicalConversation:
    """医学咨询会话实体"""
    id: int
    conversation_id: str
    user_id: int
    title: Optional[str] = None
    patient_name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class MedicalMessage:
    """医学咨询消息实体"""
    id: int
    message_id: str
    conversation_id: str
    role: str  # 'user' 或 'assistant'
    content: str
    created_at: Optional[datetime] = None


@dataclass
class ConversationDetail:
    """会话详情（包含消息列表）"""
    conversation: MedicalConversation
    messages: list[MedicalMessage]


@dataclass
class ConversationInfo:
    """会话信息（用于列表展示）"""
    conversation_id: str
    user_id: int
    title: Optional[str] = None
    patient_name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message: Optional[str] = None
