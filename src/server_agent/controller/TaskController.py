"""
任务管理API控制器
"""

from typing import List, Optional

from fastapi import Depends, Query, Header

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.model.vo.TaskVO import TaskVO
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service.TaskService import TaskService
from src.server_agent.service.UserService import UserService
from src.server_agent.exceptions import AuthenticationError
from .base import BaseController


class TaskController(BaseController):
    """任务控制器 - 管理任务查询操作"""

    def __init__(self):
        super().__init__(prefix="/tasks", tags=["任务管理"])
        self.taskService = TaskService()
        self.userService = UserService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.get("/list")
        async def getUserTasks(
            status: Optional[str] = Query(None, description="任务状态过滤"),
            limit: int = Query(100, ge=1, le=500, description="返回记录数"),
            offset: int = Query(0, ge=0, description="偏移量"),
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[List[TaskVO]]:
            """获取当前用户的任务列表"""
            tasks = await self.taskService.get_user_tasks(
                userVO.uid, 
                status=status, 
                limit=limit, 
                offset=offset
            )
            return ResultUtils.success(tasks)

        @self.router.get("/detail/{task_uid}")
        async def getTaskDetail(
            task_uid: str,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[TaskVO]:
            """获取任务详情"""
            task = await self.taskService.get_task_by_id(task_uid, userVO.uid)
            return ResultUtils.success(task)

        @self.router.get("/statistics")
        async def getTaskStatistics(
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            """获取任务统计信息"""
            stats = await self.taskService.get_task_statistics(userVO.uid)
            return ResultUtils.success(stats)

        @self.router.delete("/delete/{task_uid}")
        async def deleteTask(
            task_uid: str,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            """删除任务"""
            try:
                result = await self.taskService.delete_task(task_uid, userVO.uid)
                if result:
                    return ResultUtils.success(True)
                else:
                    return ResultUtils.error(500, "任务删除失败")
            except ValueError as e:
                return ResultUtils.error(400, str(e))
            except Exception as e:
                return ResultUtils.error(500, f"删除任务失败: {str(e)}")

    # ==================== 工具方法 ====================

    async def _get_current_user(self, authorization: str = Header(None)) -> UserVO:
        """根据token获取用户信息的依赖函数"""
        if not authorization:
            raise AuthenticationError(
                detail="Missing authorization header",
                context={"header": "Authorization"}
            )

        # 支持多种格式：Bearer token 或直接 token
        if authorization.startswith("Bearer "):
            token = authorization[7:]  # 移除 "Bearer " 前缀
        else:
            token = authorization  # 直接使用 token

        userVO: UserVO = await self.userService.get_user_by_token(token)
        if not userVO:
            raise AuthenticationError(
                detail="Invalid token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return userVO

