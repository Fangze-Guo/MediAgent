"""
任务数据访问层 - 处理任务相关的数据库操作
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from src.server_agent.mapper.BaseMapper import BaseMapper
from src.server_agent.mapper.paths import in_data

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """任务数据模型"""
    task_uid: str
    total_steps: int
    status: str
    current_step_number: Optional[int] = None
    current_step_uid: Optional[str] = None
    last_completed_step: Optional[int] = None
    failed_step_number: Optional[int] = None
    request_json: str = ""
    user_uid: Optional[int] = None
    failed_step_uid: Optional[str] = None
    task_name: Optional[str] = None
    create_time: Optional[str] = None
    update_time: Optional[str] = None


class TaskMapper(BaseMapper):
    """任务数据访问层"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = in_data("db", "app.sqlite3")
        super().__init__(db_path)

    async def find_task_by_uid(self, task_uid: str) -> Optional[Task]:
        """
        根据任务UID查找任务
        
        Args:
            task_uid: 任务UID
            
        Returns:
            Task 对象或 None
        """
        query = """
                SELECT task_uid, total_steps, status, current_step_number, 
                       current_step_uid, last_completed_step, failed_step_number,
                       request_json, user_uid, failed_step_uid, task_name, 
                       create_time, update_time
                FROM tasks
                WHERE task_uid = ?
                LIMIT 1
                """
        result = await self.execute_query(query, (task_uid,), fetch_one=True)

        if result:
            return Task(
                task_uid=result['task_uid'],
                total_steps=result['total_steps'],
                status=result['status'],
                current_step_number=result['current_step_number'],
                current_step_uid=result['current_step_uid'],
                last_completed_step=result['last_completed_step'],
                failed_step_number=result['failed_step_number'],
                request_json=result['request_json'],
                user_uid=result['user_uid'],
                failed_step_uid=result['failed_step_uid'],
                task_name=result['task_name'] if 'task_name' in result.keys() else None,
                create_time=result['create_time'] if 'create_time' in result.keys() else None,
                update_time=result['update_time'] if 'update_time' in result.keys() else None
            )
        return None

    async def find_tasks_by_user(self, user_uid: int, limit: int = 100, offset: int = 0) -> List[Task]:
        """
        根据用户UID查找所有任务
        
        Args:
            user_uid: 用户UID
            limit: 返回记录数限制
            offset: 偏移量
            
        Returns:
            Task 对象列表
        """
        query = """
                SELECT task_uid, total_steps, status, current_step_number, 
                       current_step_uid, last_completed_step, failed_step_number,
                       request_json, user_uid, failed_step_uid, task_name, 
                       create_time, update_time
                FROM tasks
                WHERE user_uid = ?
                ORDER BY create_time DESC
                LIMIT ? OFFSET ?
                """
        results = await self.execute_query(query, (user_uid, limit, offset), fetch_all=True)

        tasks = []
        for result in results:
            tasks.append(Task(
                task_uid=result['task_uid'],
                total_steps=result['total_steps'],
                status=result['status'],
                current_step_number=result['current_step_number'],
                current_step_uid=result['current_step_uid'],
                last_completed_step=result['last_completed_step'],
                failed_step_number=result['failed_step_number'],
                request_json=result['request_json'],
                user_uid=result['user_uid'],
                failed_step_uid=result['failed_step_uid'],
                task_name=result['task_name'] if 'task_name' in result.keys() else None,
                create_time=result['create_time'] if 'create_time' in result.keys() else None,
                update_time=result['update_time'] if 'update_time' in result.keys() else None
            ))
        
        return tasks

    async def count_tasks_by_user(self, user_uid: int) -> int:
        """
        统计用户的任务总数
        
        Args:
            user_uid: 用户UID
            
        Returns:
            任务总数
        """
        query = "SELECT COUNT(*) as count FROM tasks WHERE user_uid = ?"
        result = await self.execute_query(query, (user_uid,), fetch_one=True)
        return result['count'] if result else 0

    async def find_tasks_by_status(self, user_uid: int, status: str, limit: int = 100) -> List[Task]:
        """
        根据用户UID和状态查找任务
        
        Args:
            user_uid: 用户UID
            status: 任务状态
            limit: 返回记录数限制
            
        Returns:
            Task 对象列表
        """
        query = """
                SELECT task_uid, total_steps, status, current_step_number, 
                       current_step_uid, last_completed_step, failed_step_number,
                       request_json, user_uid, failed_step_uid, task_name, 
                       create_time, update_time
                FROM tasks
                WHERE user_uid = ? AND status = ?
                ORDER BY create_time DESC
                LIMIT ?
                """
        results = await self.execute_query(query, (user_uid, status, limit), fetch_all=True)

        tasks = []
        for result in results:
            tasks.append(Task(
                task_uid=result['task_uid'],
                total_steps=result['total_steps'],
                status=result['status'],
                current_step_number=result['current_step_number'],
                current_step_uid=result['current_step_uid'],
                last_completed_step=result['last_completed_step'],
                failed_step_number=result['failed_step_number'],
                request_json=result['request_json'],
                user_uid=result['user_uid'],
                failed_step_uid=result['failed_step_uid'],
                task_name=result['task_name'] if 'task_name' in result.keys() else None,
                create_time=result['create_time'] if 'create_time' in result.keys() else None,
                update_time=result['update_time'] if 'update_time' in result.keys() else None
            ))
        
        return tasks

    async def search_tasks(
        self, 
        user_uid: int, 
        keyword: str, 
        status: Optional[str] = None, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[Task]:
        """
        根据关键词搜索任务（在task_name中搜索）
        
        Args:
            user_uid: 用户UID
            keyword: 搜索关键词
            status: 任务状态过滤（可选）
            limit: 返回记录数限制
            offset: 偏移量
            
        Returns:
            Task 对象列表
        """
        # 构建基础查询，在 task_name 中搜索
        query = """
                SELECT task_uid, total_steps, status, current_step_number, 
                       current_step_uid, last_completed_step, failed_step_number,
                       request_json, user_uid, failed_step_uid, task_name, 
                       create_time, update_time
                FROM tasks
                WHERE user_uid = ? AND (task_name LIKE ? OR task_uid LIKE ?)
                """
        
        params = [user_uid, f'%{keyword}%', f'%{keyword}%']
        
        # 如果有状态过滤，添加状态条件
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY create_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        results = await self.execute_query(query, tuple(params), fetch_all=True)

        tasks = []
        for result in results:
            tasks.append(Task(
                task_uid=result['task_uid'],
                total_steps=result['total_steps'],
                status=result['status'],
                current_step_number=result['current_step_number'],
                current_step_uid=result['current_step_uid'],
                last_completed_step=result['last_completed_step'],
                failed_step_number=result['failed_step_number'],
                request_json=result['request_json'],
                user_uid=result['user_uid'],
                failed_step_uid=result['failed_step_uid'],
                task_name=result['task_name'] if 'task_name' in result.keys() else None,
                create_time=result['create_time'] if 'create_time' in result.keys() else None,
                update_time=result['update_time'] if 'update_time' in result.keys() else None
            ))
        
        return tasks

    async def update_task_name(self, task_uid: str, task_name: str) -> bool:
        """
        更新任务名称
        
        Args:
            task_uid: 任务UID
            task_name: 新的任务名称
            
        Returns:
            是否更新成功
        """
        try:
            query = """
                    UPDATE tasks 
                    SET task_name = ?, update_time = datetime('now', 'localtime')
                    WHERE task_uid = ?
                    """
            operations = [
                {
                    'query': query,
                    'params': (task_name, task_uid)
                }
            ]
            result = await self.execute_transaction(operations)
            
            if result:
                logger.info(f"Successfully updated task name: {task_uid} -> {task_name}")
            return result
        except Exception as e:
            logger.error(f"Failed to update task name {task_uid}: {e}")
            return False

    async def delete_task(self, task_uid: str) -> bool:
        """
        删除任务（包括相关的步骤记录）
        
        Args:
            task_uid: 任务UID
            
        Returns:
            是否删除成功
        """
        try:
            # 删除任务记录（如果有外键约束，相关的步骤记录会自动删除）
            operations = [
                {
                    'query': "DELETE FROM tasks WHERE task_uid = ?",
                    'params': (task_uid,)
                }
            ]
            result = await self.execute_transaction(operations)
            
            if result:
                logger.info(f"Successfully deleted task: {task_uid}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete task {task_uid}: {e}")
            return False

