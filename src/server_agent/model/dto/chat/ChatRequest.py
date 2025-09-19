from typing import List, Any, Dict, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from src.server_agent.model.entity import FileInfo


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    history: List[Dict[str, Any]] = []
    files: List["FileInfo"] = []
    assistant_type: str = "general"  # 助手类型：medical, data, document, general

    model_config = {"arbitrary_types_allowed": True}