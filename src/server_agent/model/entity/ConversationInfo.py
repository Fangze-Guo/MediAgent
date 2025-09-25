from pydantic import BaseModel


class ConversationInfo(BaseModel):
    conversation_uid: str
    owner_uid: str
