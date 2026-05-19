from pydantic import BaseModel
from typing import Optional


class KbDocumentInfo(BaseModel):
    """知识库文档实体"""
    id: Optional[int] = None
    kb_id: int
    file_name: str
    file_path: str
    file_size: int
    content_type: str
    status: str = "pending"
    chunk_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
