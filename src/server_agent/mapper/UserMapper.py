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

from src.server_agent.mapper.base_mapper import BaseMapper
from src.server_agent.mapper.paths import in_data

logger = logging.getLogger(__name__)


@dataclass
class User:
    """用户数据模型"""
    uid: int
    user_name: str
    password: str
    token: Optional[str] = None


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
            SELECT uid, user_name, password, token
            FROM users 
            WHERE user_name = ? COLLATE NOCASE 
            LIMIT 1
        """
        result = await self.execute_query(query, (user_name,), fetch_one=True)
        
        if result:
            return User(
                uid=result['uid'],
                user_name=result['user_name'],
                password=result['password'],
                token=result['token']
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
            SELECT uid, user_name, password, token
            FROM users 
            WHERE token = ? 
            LIMIT 1
        """
        result = await self.execute_query(query, (token,), fetch_one=True)
        
        if result:
            return User(
                uid=result['uid'],
                user_name=result['user_name'],
                password=result['password'],
                token=result['token']
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
            SELECT uid, user_name, password, token
            FROM users 
            WHERE uid = ? 
            LIMIT 1
        """
        result = await self.execute_query(query, (uid,), fetch_one=True)
        
        if result:
            return User(
                uid=result['uid'],
                user_name=result['user_name'],
                password=result['password'],
                token=result['token']
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
        
        operations = [
            {
                'query': """
                    INSERT INTO users (uid, user_name, password, token) 
                    VALUES (?, ?, ?, NULL)
                """,
                'params': (uid, user_name, password_hash)
            }
        ]
        
        await self.execute_transaction(operations)
        
        return User(
            uid=uid,
            user_name=user_name,
            password=password_hash,
            token=None
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
        operations = [
            {
                'query': "UPDATE users SET token = ? WHERE uid = ?",
                'params': (token, uid)
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
        
        if user_name:
            # 检查新用户名是否已存在
            if await self.check_username_exists(user_name):
                # 检查是否是当前用户
                current_user = await self.find_user_by_uid(uid)
                if not current_user or current_user.user_name.lower() != user_name.lower():
                    return False  # 用户名已存在
            
            operations.append({
                'query': "UPDATE users SET user_name = ? WHERE uid = ?",
                'params': (user_name, uid)
            })
        
        if password:
            password_hash = self._hash_password(password)
            operations.append({
                'query': "UPDATE users SET password = ? WHERE uid = ?",
                'params': (password_hash, uid)
            })
        
        if not operations:
            return False
        
        try:
            await self.execute_transaction(operations)
            return True
        except Exception as e:
            logger.error(f"Failed to update user info: {e}")
            return False
    
    async def verify_password(self, user: User, password: str) -> bool:
        """验证密码"""
        return user.password == self._hash_password(password)
