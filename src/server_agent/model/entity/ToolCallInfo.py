from typing import List, Dict, Any

from pydantic import BaseModel


class ToolCallInfo(BaseModel):
    conversation_id: str
    answer: str
    tool_calls: List[Dict[str, Any]]
