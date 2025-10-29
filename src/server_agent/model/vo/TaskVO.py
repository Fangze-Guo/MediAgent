from pydantic import BaseModel
from typing import Optional


class TaskVO(BaseModel):
    """任务视图对象"""
    task_uid: str
    total_steps: int
    status: str  # queued, running, succeeded, failed
    current_step_number: Optional[int] = None
    current_step_uid: Optional[str] = None
    last_completed_step: Optional[int] = None
    failed_step_number: Optional[int] = None
    failed_step_uid: Optional[str] = None
    user_uid: int
    request_json: str
    task_name: Optional[str] = None
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    
    # 计算属性
    progress_percentage: float = 0.0  # 进度百分比
    status_text: str = ""  # 状态文本
    status_color: str = ""  # 状态颜色
    
    @classmethod
    def from_task_info(cls, task_info) -> "TaskVO":
        """从TaskInfo创建TaskVO"""
        # 计算进度百分比
        progress = 0.0
        if task_info.total_steps > 0:
            completed_steps = task_info.last_completed_step or 0
            progress = (completed_steps / task_info.total_steps) * 100
        
        # 状态映射（与 TaskManager 实际使用的状态保持一致）
        status_map = {
            "queued": {"text": "排队中", "color": "default"},
            "running": {"text": "执行中", "color": "processing"},
            "succeeded": {"text": "已完成", "color": "success"},
            "failed": {"text": "已失败", "color": "error"}
        }
        
        status_info = status_map.get(task_info.status, {"text": "未知", "color": "default"})
        
        return cls(
            task_uid=task_info.task_uid,
            total_steps=task_info.total_steps,
            status=task_info.status,
            current_step_number=task_info.current_step_number,
            current_step_uid=task_info.current_step_uid,
            last_completed_step=task_info.last_completed_step,
            failed_step_number=task_info.failed_step_number,
            failed_step_uid=task_info.failed_step_uid,
            user_uid=task_info.user_uid,
            request_json=task_info.request_json,
            task_name=task_info.task_name,
            create_time=task_info.create_time,
            update_time=task_info.update_time,
            progress_percentage=round(progress, 2),
            status_text=status_info["text"],
            status_color=status_info["color"]
        )

