"""
任务服务层 - 处理任务相关的业务逻辑
"""
import logging
from typing import List, Optional

from src.server_agent.mapper.TaskMapper import TaskMapper, Task
from src.server_agent.model.vo.TaskVO import TaskVO
from src.server_agent.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class TaskService:
    """任务服务"""

    def __init__(self):
        self.taskMapper = TaskMapper()

    async def get_task_by_id(self, task_uid: str, user_uid: int) -> TaskVO:
        """
        根据任务ID获取任务详情
        
        Args:
            task_uid: 任务UID
            user_uid: 用户UID（用于权限验证）
            
        Returns:
            TaskVO 对象
            
        Raises:
            NotFoundError: 任务不存在或无权访问
        """
        task = await self.taskMapper.find_task_by_uid(task_uid)
        
        if not task:
            raise NotFoundError(detail=f"任务 {task_uid} 不存在")
        
        # 验证任务是否属于当前用户
        if task.user_uid != user_uid:
            raise NotFoundError(detail="无权访问此任务")
        
        return TaskVO.from_task_info(task)

    async def get_user_tasks(
        self, 
        user_uid: int, 
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TaskVO]:
        """
        获取用户的所有任务
        
        Args:
            user_uid: 用户UID
            status: 任务状态过滤（可选）
            limit: 返回记录数限制
            offset: 偏移量
            
        Returns:
            TaskVO 对象列表
        """
        if status:
            tasks = await self.taskMapper.find_tasks_by_status(user_uid, status, limit)
        else:
            tasks = await self.taskMapper.find_tasks_by_user(user_uid, limit, offset)
        
        return [TaskVO.from_task_info(task) for task in tasks]

    async def get_user_task_count(self, user_uid: int) -> int:
        """
        获取用户的任务总数
        
        Args:
            user_uid: 用户UID
            
        Returns:
            任务总数
        """
        return await self.taskMapper.count_tasks_by_user(user_uid)

    async def get_task_statistics(self, user_uid: int) -> dict:
        """
        获取用户任务统计信息
        
        Args:
            user_uid: 用户UID
            
        Returns:
            统计信息字典
        """
        total = await self.taskMapper.count_tasks_by_user(user_uid)
        
        # 获取各状态的任务数（使用与 TaskManager 一致的状态值）
        queued_tasks = await self.taskMapper.find_tasks_by_status(user_uid, "queued")
        running_tasks = await self.taskMapper.find_tasks_by_status(user_uid, "running")
        succeeded_tasks = await self.taskMapper.find_tasks_by_status(user_uid, "succeeded")
        failed_tasks = await self.taskMapper.find_tasks_by_status(user_uid, "failed")
        
        return {
            "total": total,
            "queued": len(queued_tasks),
            "running": len(running_tasks),
            "succeeded": len(succeeded_tasks),
            "failed": len(failed_tasks)
        }

    async def delete_task(self, task_uid: str, user_uid: int) -> bool:
        """
        删除任务（需要权限验证）
        
        Args:
            task_uid: 任务UID
            user_uid: 用户UID（用于权限验证）
            
        Returns:
            是否删除成功
            
        Raises:
            NotFoundError: 任务不存在或无权删除
        """
        # 先查询任务确认存在并验证权限
        task = await self.taskMapper.find_task_by_uid(task_uid)
        
        if not task:
            raise NotFoundError(detail=f"任务 {task_uid} 不存在")
        
        # 验证任务是否属于当前用户
        if task.user_uid != user_uid:
            raise NotFoundError(detail="无权删除此任务")
        
        # 禁止删除正在运行的任务
        if task.status == "running":
            raise ValueError("无法删除正在运行的任务")
        
        # 执行删除
        return await self.taskMapper.delete_task(task_uid)

