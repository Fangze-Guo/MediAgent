from pydantic import BaseModel
from typing import Optional, List


class KbDocumentVO(BaseModel):
    """知识库文档视图对象"""
    id: int
    file_name: str
    file_path: str
    file_size: int
    content_type: str
    knowledge_base_id: int
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    processing_tasks: List[dict] = []

    class Config:
        from_attributes = True


class KnowledgeBaseVO(BaseModel):
    """知识库视图对象"""
    id: int
    name: str
    description: Optional[str] = None
    documents: List[KbDocumentVO] = []
    document_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
