"""
用户管理API控制器
"""
from __future__ import annotations

from fastapi import Depends, Header

from common import ResultUtils, BaseResponse
from model.dto.user.UserLoginRequest import UserLoginRequest
from model.vo.UserVO import UserVO
from src.server_agent.exceptions import (
    AuthenticationError
)
from src.server_agent.model.dto.user.UserRegisterRequest import UserRegisterRequest
from src.server_agent.service import UserService
from .base import BaseController


# ==================== 主控制器 ====================

class UserController(BaseController):
    """用户控制器"""

    def __init__(self):
        super().__init__(prefix="/user", tags=["用户管理"])
        self.userService = UserService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.post("/register")
        async def register(request: UserRegisterRequest) -> BaseResponse[dict[str, int]]:
            """用户注册接口"""
            res: int = await self.userService.register_user(request.user_name, request.password)
            return ResultUtils.success({"uid": res})

        @self.router.post("/login")
        async def login(request: UserLoginRequest) -> BaseResponse[dict[str, str]]:
            """用户登录接口"""
            res: str = await self.userService.login_user(request.user_name, request.password)
            return ResultUtils.success({"token": res})

        @self.router.get("/info")
        async def get_user_info(userVO: UserVO = Depends(self._get_current_user)) -> BaseResponse[UserVO]:
            """获取用户信息接口"""
            return ResultUtils.success(userVO)

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
