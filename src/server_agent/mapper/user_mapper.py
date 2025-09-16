"""
改进的用户数据访问层 - 处理用户相关的数据库操作
"""
from __future__ import annotations

import string
import secrets
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timezone

from src.server_agent.mapper.base_mapper import BaseMapper
from src.server_agent.mapper.paths import in_data

logger = logging.getLogger(__name__)


@dataclass
class User:
    """用户数据模型"""
    uid: int
    user_name: str
    password_hash: str
    token: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class UserMapper(BaseMapper):
    """改进的用户数据访问层"""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = in_data("db", "app.sqlite3")
        super().__init__(db_path)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """确保用户表存在"""
        # 这里可以添加表创建逻辑
        pass
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _generate_token(self, length: int = 32) -> str:
        """生成随机token"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))
    
    def _generate_uid(self) -> int:
        """生成随机用户ID"""
        return secrets.randbelow(9_000_000_000) + 1_000_000_000
    
    async def find_user_by_name(self, user_name: str) -> Optional[User]:
        """
        按用户名查找用户
        
        Args:
            user_name: 用户名
            
        Returns:
            User 对象或 None
        """
        query = """
            SELECT uid, user_name, password, token, created_at, updated_at, last_login 
            FROM users 
            WHERE user_name = ? COLLATE NOCASE 
            LIMIT 1
        """
        result = await self.execute_query(query, (user_name,), fetch_one=True)
        
        if result:
            return User(
                uid=result[0],
                user_name=result[1],
                password_hash=result[2],
                token=result[3],
                created_at=datetime.fromisoformat(result[4]) if result[4] else None,
                updated_at=datetime.fromisoformat(result[5]) if result[5] else None,
                last_login=datetime.fromisoformat(result[6]) if result[6] else None
            )
        return None
    
    async def find_user_by_token(self, token: str) -> Optional[User]:
        """
        根据token查找用户
        
        Args:
            token: 用户token
            
        Returns:
            User 对象或 None
        """
        query = """
            SELECT uid, user_name, password, token, created_at, updated_at, last_login 
            FROM users 
            WHERE token = ? 
            LIMIT 1
        """
        result = await self.execute_query(query, (token,), fetch_one=True)
        
        if result:
            return User(
                uid=result[0],
                user_name=result[1],
                password_hash=result[2],
                token=result[3],
                created_at=datetime.fromisoformat(result[4]) if result[4] else None,
                updated_at=datetime.fromisoformat(result[5]) if result[5] else None,
                last_login=datetime.fromisoformat(result[6]) if result[6] else None
            )
        return None
    
    async def find_user_by_uid(self, uid: int) -> Optional[User]:
        """
        根据UID查找用户
        
        Args:
            uid: 用户ID
            
        Returns:
            User 对象或 None
        """
        query = """
            SELECT uid, user_name, password, token, created_at, updated_at, last_login 
            FROM users 
            WHERE uid = ? 
            LIMIT 1
        """
        result = await self.execute_query(query, (uid,), fetch_one=True)
        
        if result:
            return User(
                uid=result[0],
                user_name=result[1],
                password_hash=result[2],
                token=result[3],
                created_at=datetime.fromisoformat(result[4]) if result[4] else None,
                updated_at=datetime.fromisoformat(result[5]) if result[5] else None,
                last_login=datetime.fromisoformat(result[6]) if result[6] else None
            )
        return None
    
    async def check_username_exists(self, user_name: str) -> bool:
        """检查用户名是否已存在"""
        query = "SELECT 1 FROM users WHERE user_name = ? COLLATE NOCASE LIMIT 1"
        result = await self.execute_query(query, (user_name,), fetch_one=True)
        return result is not None
    
    async def check_token_exists(self, token: str) -> bool:
        """检查token是否已存在"""
        query = "SELECT 1 FROM users WHERE token = ? LIMIT 1"
        result = await self.execute_query(query, (token,), fetch_one=True)
        return result is not None
    
    async def check_uid_exists(self, uid: int) -> bool:
        """检查用户ID是否已存在"""
        query = "SELECT 1 FROM users WHERE uid = ? LIMIT 1"
        result = await self.execute_query(query, (uid,), fetch_one=True)
        return result is not None
    
    async def generate_unique_token(self, length: int = 32) -> str:
        """生成唯一的token"""
        max_attempts = 100
        for _ in range(max_attempts):
            token = self._generate_token(length)
            if not await self.check_token_exists(token):
                return token
        
        raise RuntimeError(f"Failed to generate unique token after {max_attempts} attempts")
    
    async def generate_unique_uid(self) -> int:
        """生成唯一的用户ID"""
        max_attempts = 100
        for _ in range(max_attempts):
            uid = self._generate_uid()
            if not await self.check_uid_exists(uid):
                return uid
        
        raise RuntimeError(f"Failed to generate unique UID after {max_attempts} attempts")
    
    async def create_user(self, user_name: str, password: str) -> User:
        """
        创建新用户
        
        Args:
            user_name: 用户名
            password: 密码
            
        Returns:
            创建的 User 对象
        """
        uid = await self.generate_unique_uid()
        password_hash = self._hash_password(password)
        now = datetime.now(timezone.utc).isoformat()
        
        operations = [
            {
                'query': """
                    INSERT INTO users (uid, user_name, password, token, created_at, updated_at) 
                    VALUES (?, ?, ?, NULL, ?, ?)
                """,
                'params': (uid, user_name, password_hash, now, now)
            }
        ]
        
        await self.execute_transaction(operations)
        
        return User(
            uid=uid,
            user_name=user_name,
            password_hash=password_hash,
            token=None,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now)
        )
    
    async def update_user_token(self, uid: int, token: str) -> bool:
        """
        更新用户token
        
        Args:
            uid: 用户ID
            token: 新token
            
        Returns:
            更新是否成功
        """
        now = datetime.now(timezone.utc).isoformat()
        
        operations = [
            {
                'query': "UPDATE users SET token = ?, updated_at = ? WHERE uid = ?",
                'params': (token, now, uid)
            }
        ]
        
        try:
            await self.execute_transaction(operations)
            return True
        except Exception as e:
            logger.error(f"Failed to update user token: {e}")
            return False
    
    async def update_user_info(self, uid: int, user_name: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        更新用户信息
        
        Args:
            uid: 用户ID
            user_name: 新用户名（可选）
            password: 新密码（可选）
            
        Returns:
            更新是否成功
        """
        if not user_name and not password:
            return False
        
        operations = []
        now = datetime.now(timezone.utc).isoformat()
        
        if user_name:
            # 检查新用户名是否已存在
            if await self.check_username_exists(user_name):
                # 检查是否是当前用户
                current_user = await self.find_user_by_uid(uid)
                if not current_user or current_user.user_name.lower() != user_name.lower():
                    return False  # 用户名已存在
            
            operations.append({
                'query': "UPDATE users SET user_name = ?, updated_at = ? WHERE uid = ?",
                'params': (user_name, now, uid)
            })
        
        if password:
            password_hash = self._hash_password(password)
            operations.append({
                'query': "UPDATE users SET password = ?, updated_at = ? WHERE uid = ?",
                'params': (password_hash, now, uid)
            })
        
        if not operations:
            return False
        
        try:
            await self.execute_transaction(operations)
            return True
        except Exception as e:
            logger.error(f"Failed to update user info: {e}")
            return False
    
    async def update_last_login(self, uid: int) -> bool:
        """更新最后登录时间"""
        now = datetime.now(timezone.utc).isoformat()
        
        operations = [
            {
                'query': "UPDATE users SET last_login = ?, updated_at = ? WHERE uid = ?",
                'params': (now, now, uid)
            }
        ]
        
        try:
            await self.execute_transaction(operations)
            return True
        except Exception as e:
            logger.error(f"Failed to update last login: {e}")
            return False
    
    async def delete_user(self, uid: int) -> bool:
        """删除用户"""
        operations = [
            {
                'query': "DELETE FROM users WHERE uid = ?",
                'params': (uid,)
            }
        ]
        
        try:
            await self.execute_transaction(operations)
            return True
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            return False
    
    async def get_user_count(self) -> int:
        """获取用户总数"""
        query = "SELECT COUNT(*) FROM users"
        result = await self.execute_query(query, fetch_one=True)
        return result[0] if result else 0
    
    async def get_users_paginated(self, offset: int = 0, limit: int = 100) -> List[User]:
        """分页获取用户列表"""
        query = """
            SELECT uid, user_name, password, token, created_at, updated_at, last_login 
            FROM users 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """
        results = await self.execute_query(query, (limit, offset), fetch_all=True)
        
        users = []
        for result in results:
            users.append(User(
                uid=result[0],
                user_name=result[1],
                password_hash=result[2],
                token=result[3],
                created_at=datetime.fromisoformat(result[4]) if result[4] else None,
                updated_at=datetime.fromisoformat(result[5]) if result[5] else None,
                last_login=datetime.fromisoformat(result[6]) if result[6] else None
            ))
        
        return users
    
    async def verify_password(self, user: User, password: str) -> bool:
        """验证密码"""
        return user.password_hash == self._hash_password(password)


# 全局实例
user_mapper = UserMapper()
