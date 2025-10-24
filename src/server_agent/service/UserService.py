"""
用户服务层 - 处理用户相关的业务逻辑
"""
from __future__ import annotations

import pathlib
import logging
from typing import Optional

from src.server_agent.exceptions import (
    ValidationError, ConflictError, NotFoundError,
    AuthenticationError, DatabaseError, handle_service_exception
)
from src.server_agent.mapper import UserMapper
from src.server_agent.model.vo.UserVO import UserVO
from constants.CommonConstants import DATASET_PATH

logger = logging.getLogger(__name__)


class UserService:
    """用户服务类"""

    def __init__(self):
        self.userMapper = UserMapper()

    @handle_service_exception
    async def register_user(self, user_name: str, password: str) -> int:
        """
        用户注册服务

        Args:
            user_name: 用户名
            password: 密码

        Returns:
            用户 id
        """
        if not user_name or not password:
            raise ValidationError(
                detail="username/password required",
                context={"username": user_name}
            )

        # 1) 用户名查重（大小写不敏感）
        if await self.userMapper.check_username_exists(user_name):
            raise ConflictError(
                detail="username already exists",
                context={"username": user_name}
            )

        # 2) 创建用户（内部会自动生成 UID）
        user = await self.userMapper.create_user(user_name, password)
        if not user:
            raise DatabaseError(
                detail="failed to create user",
                operation="create_user",
                context={"username": user_name}
            )

        # 3) 自动创建用户私有文件夹 private/{uid}
        try:
            dataset_root = pathlib.Path(DATASET_PATH)
            user_private_folder = dataset_root / "private" / str(user.uid)
            user_private_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"为用户 {user_name}(uid={user.uid}) 创建私有文件夹: {user_private_folder}")
        except Exception as e:
            logger.error(f"创建用户私有文件夹失败: {e}")
            # 不影响注册流程，只记录错误

        return user.uid

    @handle_service_exception
    async def login_user(self, user_name: str, password: str) -> str:
        """
        用户登录服务

        Args:
            user_name: 用户名
            password: 密码

        Returns:
            token
        """
        if not user_name or not password:
            raise ValidationError(
                detail="username/password required",
                context={"username": user_name}
            )

        # 读用户信息
        user_row = await self.userMapper.find_user_by_name(user_name)
        if user_row is None:
            raise NotFoundError(
                resource_type="user",
                resource_id=user_name,
                detail="username not found"
            )

        # 验证密码
        if not await self.userMapper.verify_password(user_row, password):
            raise AuthenticationError(
                detail="incorrect password",
                context={"username": user_name}
            )

        # 生成唯一 token，更新到该用户
        token = await self.userMapper.generate_unique_token(10)
        success = await self.userMapper.update_user_token(user_row.uid, token)
        if not success:
            raise DatabaseError(
                detail="failed to update token",
                operation="update_user_token",
                context={"uid": user_row.uid}
            )
        return token

    @handle_service_exception
    async def get_user_by_token(self, token: str) -> UserVO:
        """
        根据token获取用户信息

        Args:
            token: 用户token

        Returns:
            UserVO: 封装的用户
        """
        if not token:
            return None

        user_row = await self.userMapper.find_user_by_token(token)
        if user_row:
            # 确保role字段不为None
            role_value = getattr(user_row, 'role', 'user')
            if role_value is None:
                role_value = 'user'
                
            return UserVO(
                uid=user_row.uid,
                user_name=user_row.user_name,
                token=user_row.token,
                role=role_value,
                avatar=getattr(user_row, 'avatar', None)
            )
        return None

    @handle_service_exception
    async def update_user_info(self, uid: int, user_name: Optional[str] = None, password: Optional[str] = None) -> bool:
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

        return await self.userMapper.update_user_info(uid, user_name, password)

    @handle_service_exception
    async def update_user_profile(self, uid: int, user_name: str, avatar: Optional[str] = None) -> UserVO:
        """
        更新用户个人信息（用户名和头像）

        Args:
            uid: 用户ID
            user_name: 新用户名
            avatar: 新头像（Base64格式，可选）

        Returns:
            UserVO: 更新后的用户信息
        """
        if not user_name:
            raise ValidationError(
                detail="user_name is required",
                context={"uid": uid}
            )

        # 检查用户名是否已被其他用户使用
        existing_user = await self.userMapper.find_user_by_name(user_name)
        if existing_user and existing_user.uid != uid:
            raise ConflictError(
                detail="username already exists",
                context={"username": user_name, "uid": uid}
            )

        # 更新用户信息
        success = await self.userMapper.update_user_profile(uid, user_name, avatar)
        if not success:
            raise DatabaseError(
                detail="failed to update user profile",
                operation="update_user_profile",
                context={"uid": uid, "user_name": user_name}
            )

        # 获取更新后的用户信息
        updated_user = await self.userMapper.find_user_by_uid(uid)
        if not updated_user:
            raise NotFoundError(
                resource_type="user",
                resource_id=str(uid),
                detail="user not found after update"
            )

        # 确保role字段不为None
        role_value = getattr(updated_user, 'role', 'user')
        if role_value is None:
            role_value = 'user'

        return UserVO(
            uid=updated_user.uid,
            user_name=updated_user.user_name,
            token=updated_user.token,
            role=role_value,
            avatar=getattr(updated_user, 'avatar', None)
        )
