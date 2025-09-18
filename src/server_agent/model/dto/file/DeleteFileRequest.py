from pydantic import BaseModel


class DeleteFileRequest(BaseModel):
    fileId: str
