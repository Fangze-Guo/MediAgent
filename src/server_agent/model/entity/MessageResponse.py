"""
CodeAgent 消息响应模型

从 CodeAgentController 中提取，供 Controller / Service / message_parser 共用，
避免循环依赖。
"""
from typing import Dict, List, Optional

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    role: Optional[str] = None  # None 表示非消息事件（如 skill_call）
    content: Optional[str] = None
    thinking: Optional[str] = None
    created_at: Optional[str] = None
    # Skill call 字段
    event_type: Optional[str] = None  # "skill_call" | "todo" | None
    skill_name: Optional[str] = None
    skill_arguments: Optional[str] = None
    # Todo 事件字段
    todo_list: Optional[List[dict]] = None
