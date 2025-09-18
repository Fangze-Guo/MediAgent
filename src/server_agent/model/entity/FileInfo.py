from pydantic import BaseModel

class FileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str
    path: str
    modifiedTime: str
    isDirectory: bool