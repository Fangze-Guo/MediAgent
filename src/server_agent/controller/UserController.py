"""
用户管理API控制器
"""
from __future__ import annotations

from fastapi import Depends

from src.server_agent.common import ResultUtils, BaseResponse
from src.server_agent.model.dto.user.UserLoginRequest import UserLoginRequest
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.model.dto.user.UserRegisterRequest import UserRegisterRequest
from src.server_agent.model.dto.user.UpdateUserProfileRequest import UpdateUserProfileRequest
from src.server_agent.service.UserService import UserService
from src.server_agent.dependencies import get_current_user, get_user_service
from .base import BaseController


class UserController(BaseController):
    """用户控制器 - 使用依赖注入"""

    def __init__(self):
        super().__init__(prefix="/user", tags=["用户管理"])
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.post("/register")
        async def register(
            request: UserRegisterRequest,
            user_service: UserService = Depends(get_user_service)
        ) -> BaseResponse[dict]:
            """用户注册接口"""
            uid: int = await user_service.register_user(request.user_name, request.password)
            return ResultUtils.success({
                "uid": uid,
                "user_name": request.user_name,
                "message": f"用户 {request.user_name} 注册成功！"
            })

        @self.router.post("/login")
        async def login(
            request: UserLoginRequest,
            user_service: UserService = Depends(get_user_service)
        ) -> BaseResponse[dict[str, str]]:
            """用户登录接口"""
            token: str = await user_service.login_user(request.user_name, request.password)
            return ResultUtils.success({"token": token})

        @self.router.get("/info")
        async def get_user_info(
            current_user: UserVO = Depends(get_current_user)
        ) -> BaseResponse[UserVO]:
            """获取用户信息接口"""
            return ResultUtils.success(current_user)

        @self.router.put("/profile")
        async def update_user_profile(
            request: UpdateUserProfileRequest,
            current_user: UserVO = Depends(get_current_user),
            user_service: UserService = Depends(get_user_service)
        ) -> BaseResponse[UserVO]:
            """更新用户信息接口"""
            updated_user = await user_service.update_user_profile(
                current_user.uid,
                request.user_name,
                request.avatar
            )
            return ResultUtils.success(updated_user)
