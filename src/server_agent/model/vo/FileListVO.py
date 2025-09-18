from typing import List, Optional

from pydantic import BaseModel

from src.server_agent.model import FileInfo


class FileListVO(BaseModel):
    files: List[FileInfo]
    currentPath: str
    parentPath: Optional[str] = None
