from pydantic import BaseModel
from typing import Optional


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateKnowledgeBaseRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
