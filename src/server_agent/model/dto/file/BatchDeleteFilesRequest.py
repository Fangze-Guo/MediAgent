from typing import List

from pydantic import BaseModel


class BatchDeleteFilesRequest(BaseModel):
    fileIds: List[str]
