"""
用户服务层 - 处理用户相关的业务逻辑
"""
from __future__ import annotations

from typing import TypedDict, Optional, Dict, Any

from src.server_agent.exceptions import (
    ValidationError, ConflictError, NotFoundError,
    AuthenticationError, DatabaseError, handle_service_exception
)
from src.server_agent.mapper.user_mapper import user_mapper


# ==================== 数据模型 ====================

class LoginResult(TypedDict):
    ok: bool
    code: str
    message: str
    token: Optional[str]


class RegisterResult(TypedDict):
    ok: bool
    code: str
    message: str
    uid: Optional[int]


class UserInfo(TypedDict):
    uid: int
    user_name: str
    token: Optional[str]


# ==================== 私有辅助函数 ====================

# 所有数据库操作已移至 mapper 层，这里不再需要私有辅助函数


# ==================== 公共服务函数 ====================

@handle_service_exception
async def register_user(user_name: str, password: str) -> RegisterResult:
    """
    用户注册服务
    
    Args:
        user_name: 用户名
        password: 密码
        
    Returns:
        RegisterResult: 注册结果
    """
    if not user_name or not password:
        raise ValidationError(
            detail="username/password required",
            context={"username": user_name}
        )

    # 1) 用户名查重（大小写不敏感）
    if await user_mapper.check_username_exists(user_name):
        raise ConflictError(
            detail="username already exists",
            context={"username": user_name}
        )

    # 2) 创建用户（内部会自动生成 UID）
    user = await user_mapper.create_user(user_name, password)
    if not user:
        raise DatabaseError(
            detail="failed to create user",
            operation="create_user",
            context={"username": user_name}
        )

    return {"ok": True, "code": "REGISTERED", "message": "registered successfully", "uid": user.uid}


@handle_service_exception
async def login_user(user_name: str, password: str) -> LoginResult:
    """
    用户登录服务
    
    Args:
        user_name: 用户名
        password: 密码
        
    Returns:
        LoginResult: 登录结果
    """
    if not user_name or not password:
        raise ValidationError(
            detail="username/password required",
            context={"username": user_name}
        )

    # 读用户信息
    user_row = await user_mapper.find_user_by_name(user_name)
    if user_row is None:
        raise NotFoundError(
            resource_type="user",
            resource_id=user_name,
            detail="username not found"
        )

    # 验证密码
    if not await user_mapper.verify_password(user_row, password):
        raise AuthenticationError(
            detail="incorrect password",
            context={"username": user_name}
        )

    # 生成唯一 token，更新到该用户
    token = await user_mapper.generate_unique_token(10)
    success = await user_mapper.update_user_token(user_row.uid, token)
    if not success:
        raise DatabaseError(
            detail="failed to update token",
            operation="update_user_token",
            context={"uid": user_row.uid}
        )

    return {"ok": True, "code": "LOGGED_IN", "message": "login successful", "token": token}


@handle_service_exception
async def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """
    根据token获取用户信息
    
    Args:
        token: 用户token
        
    Returns:
        Optional[Dict[str, Any]]: 用户信息字典，如果token无效则返回None
    """
    if not token:
        return None

    user_row = await user_mapper.find_user_by_token(token)
    if user_row:
        return {
            "uid": user_row.uid,
            "user_name": user_row.user_name,
            "token": user_row.token
        }
    return None


@handle_service_exception
async def update_user_info(uid: int, user_name: Optional[str] = None, password: Optional[str] = None) -> bool:
    """
    更新用户信息
    
    Args:
        uid: 用户ID
        user_name: 新用户名（可选）
        password: 新密码（可选）
        
    Returns:
        bool: 更新是否成功
    """
    if not user_name and not password:
        raise ValidationError(
            detail="At least one field (user_name or password) must be provided",
            context={"uid": uid}
        )

    return await user_mapper.update_user_info(uid, user_name, password)
