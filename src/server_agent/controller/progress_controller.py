"""
进度控制器
处理任务进度相关的API接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import time
from datetime import datetime

router = APIRouter(prefix="/api/progress", tags=["progress"])

# 全局进度存储
progress_storage: Dict[str, Dict[str, Any]] = {}

class ProgressUpdate(BaseModel):
    """进度更新请求"""
    task_id: str
    progress: int  # 0-100
    status: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class ProgressResponse(BaseModel):
    """进度响应"""
    task_id: str
    progress: int
    status: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    completed: bool = False

@router.post("/update")
async def update_progress(update: ProgressUpdate):
    """更新任务进度"""
    try:
        progress_data = {
            "task_id": update.task_id,
            "progress": update.progress,
            "status": update.status,
            "message": update.message,
            "details": update.details or {},
            "timestamp": datetime.now(),
            "completed": update.progress >= 100
        }
        
        progress_storage[update.task_id] = progress_data
        
        return {
            "success": True,
            "message": "进度更新成功",
            "data": progress_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新进度失败: {str(e)}")

@router.get("/{task_id}")
async def get_progress(task_id: str):
    """获取任务进度"""
    try:
        if task_id not in progress_storage:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "success": True,
            "data": progress_storage[task_id]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取进度失败: {str(e)}")

@router.delete("/{task_id}")
async def clear_progress(task_id: str):
    """清除任务进度"""
    try:
        if task_id in progress_storage:
            del progress_storage[task_id]
        
        return {
            "success": True,
            "message": "进度已清除"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除进度失败: {str(e)}")

@router.get("/")
async def list_progress():
    """列出所有任务进度"""
    try:
        return {
            "success": True,
            "data": list(progress_storage.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取进度列表失败: {str(e)}")

# 工具函数
def create_progress_task(task_id: str, initial_status: str = "开始处理") -> str:
    """创建新的进度任务"""
    progress_data = {
        "task_id": task_id,
        "progress": 0,
        "status": initial_status,
        "message": None,
        "details": {},
        "timestamp": datetime.now(),
        "completed": False
    }
    progress_storage[task_id] = progress_data
    return task_id

def update_task_progress(task_id: str, progress: int, status: str, message: str = None, details: Dict[str, Any] = None):
    """更新任务进度（同步版本）"""
    if task_id in progress_storage:
        progress_storage[task_id].update({
            "progress": progress,
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(),
            "completed": progress >= 100
        })

async def simulate_progress(task_id: str, total_steps: int = 5, step_duration: float = 1.0):
    """模拟进度更新（用于测试）"""
    for i in range(total_steps + 1):
        progress = int((i / total_steps) * 100)
        status = f"步骤 {i}/{total_steps}"
        
        if i == total_steps:
            status = "完成"
            message = "任务已成功完成"
        else:
            message = f"正在执行第 {i+1} 步"
        
        update_task_progress(task_id, progress, status, message, {
            "current_step": i,
            "total_steps": total_steps,
            "step_details": f"执行步骤 {i+1}"
        })
        
        if i < total_steps:
            await asyncio.sleep(step_duration)
    
    return progress_storage[task_id]
