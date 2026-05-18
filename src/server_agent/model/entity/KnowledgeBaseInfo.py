from pydantic import BaseModel
from typing import Optional


class KnowledgeBaseInfo(BaseModel):
    """知识库实体"""
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
