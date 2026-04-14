"""
医学咨询数据访问层 - PostgreSQL实现
处理医学咨询相关的数据库操作
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Optional

import asyncpg

from src.server_agent.configs.pg_config import get_pg_config
from src.server_agent.model.entity.CodeAgentConversation import (
    ConversationDetail,
    ConversationInfo,
    CodeAgentConversation,
    CodeAgentMessage
)

logger = logging.getLogger(__name__)


class CodeAgentMapper:
    """医学咨询数据访问层"""

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
                    WHERE table_name = 'medical_conversations'
                )
            """)

            if tables_exist:
                logger.info("Medical consultations tables already exist")
                return

            # 创建会话表 - 使用 UUID 作为 conversation_id
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS medical_conversations (
                    id SERIAL PRIMARY KEY,
                    conversation_id UUID UNIQUE NOT NULL,
                    user_id BIGINT NOT NULL,
                    title VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建消息表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS medical_messages (
                    id SERIAL PRIMARY KEY,
                    message_id UUID UNIQUE NOT NULL,
                    conversation_id UUID NOT NULL,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES medical_conversations(conversation_id) ON DELETE CASCADE
                )
            """)

            # 创建索引
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                ON medical_conversations(user_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                ON medical_messages(conversation_id)
            """)

    def _generate_conversation_id(self) -> str:
        """生成会话ID（UUID格式）"""
        return str(uuid.uuid4())

    def _generate_message_id(self) -> str:
        """生成消息ID（UUID格式）"""
        return str(uuid.uuid4())

    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None
    ) -> CodeAgentConversation:
        """
        创建新会话

        Args:
            user_id: 用户ID
            title: 会话标题（可选）

        Returns:
            创建的会话对象
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        conversation_id = self._generate_conversation_id()

        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                INSERT INTO medical_conversations
                (conversation_id, user_id, title)
                VALUES ($1, $2, $3)
                RETURNING id, conversation_id, user_id, title, created_at, updated_at
            """, conversation_id, user_id, title)

        return CodeAgentConversation(
            id=record['id'],
            conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
            user_id=record['user_id'],
            title=record['title'],
            created_at=record['created_at'],
            updated_at=record['updated_at']
        )

    async def get_conversations_by_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[ConversationInfo]:
        """
        获取用户的会话列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            会话信息列表
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 获取会话基本信息
            rows = await conn.fetch("""
                SELECT
                    c.id, c.conversation_id, c.user_id, c.title,
                    c.created_at, c.updated_at,
                    COUNT(m.id) as message_count,
                    (
                        SELECT m2.content
                        FROM medical_messages m2
                        WHERE m2.conversation_id = c.conversation_id
                        ORDER BY m2.created_at DESC
                        LIMIT 1
                    ) as last_message
                FROM medical_conversations c
                LEFT JOIN medical_messages m ON c.conversation_id = m.conversation_id
                WHERE c.user_id = $1
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT $2 OFFSET $3
            """, user_id, limit, offset)

        return [
            ConversationInfo(
                conversation_id=str(row['conversation_id']) if row['conversation_id'] else None,
                user_id=row['user_id'],
                title=row['title'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                message_count=row['message_count'],
                last_message=row['last_message']
            )
            for row in rows
        ]

    async def get_conversation_by_id(
        self,
        conversation_id: str
    ) -> Optional[CodeAgentConversation]:
        """
        根据会话ID获取会话

        Args:
            conversation_id: 会话ID

        Returns:
            会话对象或None
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                SELECT id, conversation_id, user_id, title,
                       created_at, updated_at
                FROM medical_conversations
                WHERE conversation_id = $1
            """, conversation_id)

        if record:
            return CodeAgentConversation(
                id=record['id'],
                conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
                user_id=record['user_id'],
                title=record['title'],
                created_at=record['created_at'],
                updated_at=record['updated_at']
            )
        return None

    async def get_conversation_detail(
        self,
        conversation_id: str
    ) -> Optional[ConversationDetail]:
        """
        获取会话详情（包含消息）

        Args:
            conversation_id: 会话ID

        Returns:
            会话详情或None
        """
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            return None

        messages = await self.get_messages_by_conversation(conversation_id)

        return ConversationDetail(
            conversation=conversation,
            messages=messages
        )

    async def get_messages_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[CodeAgentMessage]:
        """
        获取会话的消息列表

        Args:
            conversation_id: 会话ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            消息列表
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, message_id, conversation_id, role, content, created_at
                FROM medical_messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                LIMIT $2 OFFSET $3
            """, conversation_id, limit, offset)

        return [
            CodeAgentMessage(
                id=row['id'],
                message_id=str(row['message_id']) if row['message_id'] else None,
                conversation_id=str(row['conversation_id']) if row['conversation_id'] else None,
                role=row['role'],
                content=row['content'],
                created_at=row['created_at']
            )
            for row in rows
        ]

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> CodeAgentMessage:
        """
        添加消息到会话

        Args:
            conversation_id: 会话ID
            role: 角色（'user' 或 'assistant'）
            content: 消息内容

        Returns:
            创建的消息对象
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        message_id = self._generate_message_id()

        async with pool.acquire() as conn:
            # 插入消息
            record = await conn.fetchrow("""
                INSERT INTO medical_messages (message_id, conversation_id, role, content)
                VALUES ($1, $2, $3, $4)
                RETURNING id, message_id, conversation_id, role, content, created_at
            """, message_id, conversation_id, role, content)

            # 更新会话的更新时间
            await conn.execute("""
                UPDATE medical_conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = $1
            """, conversation_id)

        return CodeAgentMessage(
            id=record['id'],
            message_id=str(record['message_id']) if record['message_id'] else None,
            conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
            role=record['role'],
            content=record['content'],
            created_at=record['created_at']
        )

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除会话（级联删除消息）

        Args:
            conversation_id: 会话ID

        Returns:
            是否删除成功
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM medical_conversations
                WHERE conversation_id = $1
            """, conversation_id)

            # 删除的行数在 result 中
            rows_deleted = int(result.split()[-1])
            return rows_deleted > 0

    async def update_conversation_info(
        self,
        conversation_id: str,
        title: Optional[str] = None
    ) -> bool:
        """
        更新会话信息

        Args:
            conversation_id: 会话ID
            title: 新标题（可选）

        Returns:
            是否更新成功
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        # 构建更新语句
        update_fields = []
        params = []
        param_index = 1

        if title is not None:
            update_fields.append(f"title = ${param_index}")
            params.append(title)
            param_index += 1

        if not update_fields:
            return False

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(conversation_id)

        query = f"""
            UPDATE medical_conversations
            SET {', '.join(update_fields)}
            WHERE conversation_id = ${param_index}
        """

        async with pool.acquire() as conn:
            result = await conn.execute(query, *params)
            rows_updated = int(result.split()[-1])
            return rows_updated > 0

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
