from pydantic import BaseModel


class RenameFileRequest(BaseModel):
    fileId: str
    newName: str
