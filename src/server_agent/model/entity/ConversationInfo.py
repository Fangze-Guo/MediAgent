from pydantic import BaseModel

class ConversationInfo(BaseModel):
    conversation_id: str
    answer: result["content"],
    tool_calls: result["tool_calls"]