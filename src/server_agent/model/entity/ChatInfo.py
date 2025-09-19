from typing import List, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from src.server_agent.model.entity import ToolCallInfo


class ChatInfo(BaseModel):
    role: str
    content: str
    tool_calls: List["ToolCallInfo"]

    model_config = {"arbitrary_types_allowed": True}
