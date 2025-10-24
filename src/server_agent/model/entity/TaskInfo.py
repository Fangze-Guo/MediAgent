from pydantic import BaseModel
from typing import Optional


class TaskInfo(BaseModel):
    task_uid: str
    total_steps: int
    status: str  # queued, running, succeeded, failed
    current_step_number: Optional[int] = None
    current_step_uid: Optional[str] = None
    last_completed_step: Optional[int] = None
    failed_step_number: Optional[int] = None
    request_json: str
    user_uid: int
    failed_step_uid: Optional[str] = None

