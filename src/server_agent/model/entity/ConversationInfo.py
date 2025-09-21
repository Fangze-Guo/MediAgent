from pydantic import BaseModel


class ConversationInfo(BaseModel):
    conversation_id: str
    message: str
