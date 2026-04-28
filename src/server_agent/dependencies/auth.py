"""
认证依赖模块
提供统一的用户认证和授权依赖
"""
from typing import Optional
from fastapi import Header, Depends

from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.exceptions import AuthenticationError, AuthorizationError


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserVO:
    """
    获取当前登录用户的依赖函数
    
    Args:
        authorization: Authorization header，格式为 "Bearer {token}" 或直接 "{token}"
        
    Returns:
        UserVO: 当前用户信息
        
    Raises:
        AuthenticationError: 认证失败时抛出
    """
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

    # 延迟导入避免循环依赖
    from src.server_agent.service.UserService import UserService
    
    user_service = UserService()
    user = await user_service.get_user_by_token(token)
    
    if not user:
        raise AuthenticationError(
            detail="Invalid or expired token",
            context={"token": token[:10] + "..." if len(token) > 10 else token}
        )
    
    return user


async def get_current_admin_user(
    current_user: UserVO = Depends(get_current_user)
) -> UserVO:
    """
    获取当前管理员用户的依赖函数
    
    Args:
        current_user: 当前登录用户（通过 get_current_user 依赖注入）
        
    Returns:
        UserVO: 当前管理员用户信息
        
    Raises:
        AuthorizationError: 非管理员用户访问时抛出
    """
    if current_user.role != 'admin':
        raise AuthorizationError(
            detail="Admin access required",
            context={
                "user_id": current_user.uid,
                "user_role": current_user.role,
                "required_role": "admin"
            }
        )
    
    return current_user


# 可选的 token 认证（不强制要求登录）
async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[UserVO]:
    """
    可选的用户认证依赖（不强制要求登录）
    
    Args:
        authorization: Authorization header
        
    Returns:
        Optional[UserVO]: 用户信息，如果未登录则返回 None
    """
    if not authorization:
        return None
    
    try:
        return await get_current_user(authorization)
    except AuthenticationError:
        return None
