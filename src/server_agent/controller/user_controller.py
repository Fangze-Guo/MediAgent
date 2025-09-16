"""
用户管理API控制器
"""
from __future__ import annotations

from typing import Optional, Dict, Any

from fastapi import Depends, Header
from pydantic import BaseModel, Field

from .base import BaseController
from src.server_agent.exceptions import (
    ValidationError, AuthenticationError, ConflictError,
    NotFoundError, ServiceError
)
from src.server_agent.service.user_service import register_user, login_user, get_user_by_token, update_user_info


# ==================== 数据模型 ====================

class RegisterIn(BaseModel):
    user_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RegisterOut(BaseModel):
    uid: int
    message: str = "registered successfully"


class LoginIn(BaseModel):
    user_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LoginOut(BaseModel):
    token: str
    message: str = "login successful"


class UserInfoOut(BaseModel):
    uid: int
    user_name: str
    message: str = "user info retrieved successfully"


class UpdateUserIn(BaseModel):
    user_name: Optional[str] = Field(None, min_length=1, max_length=64)
    password: Optional[str] = Field(None, min_length=1, max_length=256)


class UpdateUserOut(BaseModel):
    message: str


# ==================== 主控制器 ====================

class UserController(BaseController):
    """用户控制器"""

    def __init__(self):
        super().__init__(prefix="/user", tags=["用户管理"])
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.post("/register", response_model=RegisterOut, status_code=201)
        async def register(payload: RegisterIn):
            """用户注册接口"""
            res = await register_user(payload.user_name, payload.password)

            if not res["ok"]:
                if res["code"] == "USERNAME_EXISTS":
                    raise ConflictError(
                        detail="username already exists",
                        context={"username": payload.user_name}
                    )
                if res["code"] == "INVALID_INPUT":
                    raise ValidationError(
                        detail="invalid input",
                        context={"username": payload.user_name}
                    )
                # 其他错误
                raise ServiceError(
                    detail="registration failed",
                    service_name="register_user"
                )

            return {"uid": res["uid"], "message": "registered successfully"}

        @self.router.post("/login", response_model=LoginOut)
        async def login(payload: LoginIn):
            """用户登录接口"""
            res = await login_user(payload.user_name, payload.password)

            if not res["ok"]:
                if res["code"] == "USERNAME_NOT_FOUND":
                    raise NotFoundError(
                        resource_type="user",
                        resource_id=payload.user_name,
                        detail="username not found"
                    )
                if res["code"] == "BAD_PASSWORD":
                    raise AuthenticationError(
                        detail="incorrect password",
                        context={"username": payload.user_name}
                    )
                raise ServiceError(
                    detail="login failed",
                    service_name="login_user"
                )

            return {"token": res["token"], "message": "login successful"}

        @self.router.get("/info", response_model=UserInfoOut)
        async def get_user_info(current_user: Dict[str, Any] = Depends(self._get_current_user)):
            """获取用户信息接口"""
            return {
                "uid": current_user["uid"],
                "user_name": current_user["user_name"],
                "message": "user info retrieved successfully"
            }

        @self.router.put("/info", response_model=UpdateUserOut)
        async def update_user_info_endpoint(
                payload: UpdateUserIn,
                current_user: Dict[str, Any] = Depends(self._get_current_user)
        ):
            """更新用户信息接口"""
            # 检查是否提供了至少一个要更新的字段
            if not payload.user_name and not payload.password:
                raise ValidationError(
                    detail="At least one field (user_name or password) must be provided"
                )

            # 调用服务层更新用户信息
            success = await update_user_info(
                current_user["uid"],
                payload.user_name,
                payload.password
            )

            if not success:
                raise ServiceError(
                    detail="Failed to update user info",
                    service_name="update_user_info"
                )

            return {"message": "user info updated successfully"}

    # ==================== 工具方法 ====================

    async def _get_current_user(self, authorization: str = Header(None)) -> Dict[str, Any]:
        """根据token获取用户信息的依赖函数"""
        if not authorization or not authorization.startswith("Bearer "):
            raise AuthenticationError(
                detail="Invalid authorization header",
                context={"header": "Authorization"}
            )

        token = authorization[7:]  # 移除 "Bearer " 前缀
        user = await get_user_by_token(token)
        if not user:
            raise AuthenticationError(
                detail="Invalid token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return user
