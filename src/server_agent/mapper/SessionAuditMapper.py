"""
会话审计数据访问层 - PostgreSQL实现
处理 user_session_audit 表的数据库操作
维护 conversation_id <-> session_id 的映射关系
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

import asyncpg

from src.server_agent.configs.pg_config import get_pg_config

logger = logging.getLogger(__name__)


@dataclass
class SessionAudit:
    """会话审计实体"""
    id: int
    user_id: int
    status: str
    created_at: datetime
    session_id: Optional[str]  # Qwen 的 session_id，可能为 NULL
    closed_at: Optional[datetime]
    conversation_id: Optional[str] = None
    extra: Optional[dict] = None


class SessionAuditMapper:
    """会话审计数据访问层"""

    def __init__(self):
        self._config = get_pg_config()
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """获取连接池（懒加载）"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
                min_size=1,
                max_size=10
            )
        return self._pool

    async def _ensure_tables(self) -> None:
        """确保数据库表存在"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # 检查表是否存在
            tables_exist = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'user_session_audit'
                )
            """)

            if tables_exist:
                logger.info("Session audit table already exists")
                return

            # 创建审计表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_session_audit (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    conversation_id UUID UNIQUE NOT NULL,
                    session_id UUID,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'closed')),
                    extra JSONB
                )
            """)

            # 创建索引
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_session_audit_user_id
                ON user_session_audit(user_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_session_audit_conversation_id
                ON user_session_audit(conversation_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_session_audit_session_id
                ON user_session_audit(session_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_session_audit_status
                ON user_session_audit(status)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_session_audit_created_at
                ON user_session_audit(created_at DESC)
            """)

    async def create_conversation_audit(
        self,
        user_id: int,
        conversation_id: Optional[str] = None,
        extra: Optional[dict] = None
    ) -> SessionAudit:
        """
        创建新会话审计记录（第一次对话前）

        Args:
            user_id: 用户ID
            conversation_id: 会话ID（UUID格式）
            extra: 额外元数据

        Returns:
            创建的会话审计对象
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        # 转换 extra 为 JSON 字符串（如果存在）
        extra_json = json.dumps(extra) if extra else None

        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                INSERT INTO user_session_audit (user_id, conversation_id, extra)
                VALUES ($1, $2, $3::jsonb)
                RETURNING id, user_id, conversation_id, session_id, created_at, closed_at, status, extra
            """, user_id, conversation_id, extra_json)

        # 解析 extra JSON 字符串为字典
        extra_dict = json.loads(record['extra']) if record['extra'] else None

        return SessionAudit(
            id=record['id'],
            user_id=record['user_id'],
            conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
            session_id=str(record['session_id']) if record['session_id'] else None,
            created_at=record['created_at'],
            closed_at=record['closed_at'],
            status=record['status'],
            extra=extra_dict
        )

    async def update_session_id(self, conversation_id: str, session_id: str) -> bool:
        """
        更新会话的 session_id（第一次对话后调用）

        Args:
            conversation_id: 会话ID
            session_id: Qwen 的 session_id

        Returns:
            是否更新成功
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_session_audit
                SET session_id = $2
                WHERE conversation_id = $1
            """, conversation_id, session_id)

            rows_updated = int(result.split()[-1])
            return rows_updated > 0

    async def get_by_conversation_id(self, conversation_id: str) -> Optional[SessionAudit]:
        """
        根据 conversation_id 获取会话审计记录

        Args:
            conversation_id: 会话ID

        Returns:
            会话审计对象或None
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                SELECT id, user_id, conversation_id, session_id, created_at, closed_at, status, extra
                FROM user_session_audit
                WHERE conversation_id = $1
            """, conversation_id)

        if record:
            # 解析 extra JSON 字符串为字典
            extra_dict = json.loads(record['extra']) if record['extra'] else None
            return SessionAudit(
                id=record['id'],
                user_id=record['user_id'],
                conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
                session_id=str(record['session_id']) if record['session_id'] else None,
                created_at=record['created_at'],
                closed_at=record['closed_at'],
                status=record['status'],
                extra=extra_dict
            )
        return None

    async def get_by_session_id(self, session_id: str) -> Optional[SessionAudit]:
        """
        根据 Qwen 的 session_id 获取会话审计记录

        Args:
            session_id: Qwen 的 session_id

        Returns:
            会话审计对象或None
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                SELECT id, user_id, conversation_id, session_id, created_at, closed_at, status, extra
                FROM user_session_audit
                WHERE session_id = $1
            """, session_id)

        if record:
            # 解析 extra JSON 字符串为字典
            extra_dict = json.loads(record['extra']) if record['extra'] else None
            return SessionAudit(
                id=record['id'],
                user_id=record['user_id'],
                conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
                session_id=str(record['session_id']) if record['session_id'] else None,
                created_at=record['created_at'],
                closed_at=record['closed_at'],
                status=record['status'],
                extra=extra_dict
            )
        return None

    async def get_user_conversations(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SessionAudit]:
        """
        获取用户的会话列表

        Args:
            user_id: 用户ID
            status: 状态过滤（可选：'active', 'closed'）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            会话审计对象列表
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch("""
                    SELECT id, user_id, conversation_id, session_id, created_at, closed_at, status, extra
                    FROM user_session_audit
                    WHERE user_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    LIMIT $3 OFFSET $4
                """, user_id, status, limit, offset)
            else:
                rows = await conn.fetch("""
                    SELECT id, user_id, conversation_id, session_id, created_at, closed_at, status, extra
                    FROM user_session_audit
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """, user_id, limit, offset)

        return [
            SessionAudit(
                id=row['id'],
                user_id=row['user_id'],
                conversation_id=str(row['conversation_id']) if row['conversation_id'] else None,
                session_id=str(row['session_id']) if row['session_id'] else None,
                created_at=row['created_at'],
                closed_at=row['closed_at'],
                status=row['status'],
                extra=json.loads(row['extra']) if row['extra'] else None
            )
            for row in rows
        ]

    async def close_session(self, conversation_id: str) -> bool:
        """
        关闭会话

        Args:
            conversation_id: 会话ID

        Returns:
            是否关闭成功
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_session_audit
                SET status = 'closed', closed_at = CURRENT_TIMESTAMP
                WHERE conversation_id = $1 AND status = 'active'
            """, conversation_id)

            rows_updated = int(result.split()[-1])
            return rows_updated > 0

    async def delete_session(self, conversation_id: str) -> bool:
        """
        删除会话（级联删除）

        Args:
            conversation_id: 会话ID

        Returns:
            是否删除成功
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM user_session_audit
                WHERE conversation_id = $1
            """, conversation_id)

            rows_deleted = int(result.split()[-1])
            return rows_deleted > 0

    async def update_extra(self, conversation_id: str, extra: dict) -> bool:
        """
        更新会话的额外元数据

        Args:
            conversation_id: 会话ID
            extra: 新的额外元数据

        Returns:
            是否更新成功
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        # 转换 extra 为 JSON 字符串
        extra_json = json.dumps(extra)

        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_session_audit
                SET extra = $2::jsonb
                WHERE conversation_id = $1
            """, conversation_id, extra_json)

            rows_updated = int(result.split()[-1])
            return rows_updated > 0

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
