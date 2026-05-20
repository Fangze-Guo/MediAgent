"""
Conversation Mapper - PostgreSQL implementation.
Handles persistence for conversations and messages.
"""
import logging
import secrets
import string
from typing import Any, Dict, List, Optional

import asyncpg

from ..configs.pg_config import get_pg_config

logger = logging.getLogger(__name__)


class ConversationMapper:
    """对话及消息的数据库操作类（PostgreSQL）"""

    def __init__(self) -> None:
        self._config = get_pg_config()
        self._pool: Optional[asyncpg.Pool] = None

    async def init(self) -> None:
        """初始化连接池并建表（启动时调用一次）"""
        await self._get_pool()
        await self._ensure_tables()
        logger.info("[ConversationMapper] Initialized")

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
                min_size=2,
                max_size=10,
            )
        return self._pool

    async def _ensure_tables(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id          BIGSERIAL PRIMARY KEY,
                    uid         TEXT UNIQUE NOT NULL,
                    owner_uid   TEXT NOT NULL,
                    title       TEXT,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_owner_uid
                ON conversations(owner_uid)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id               BIGSERIAL PRIMARY KEY,
                    conversation_uid TEXT NOT NULL REFERENCES conversations(uid) ON DELETE CASCADE,
                    role             TEXT NOT NULL,
                    content          TEXT NOT NULL,
                    attachments      JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at       TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # 兼容旧表：若 attachments 列不存在则追加
            await conn.execute("""
                ALTER TABLE messages
                ADD COLUMN IF NOT EXISTS attachments JSONB NOT NULL DEFAULT '[]'::jsonb
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_uid
                ON messages(conversation_uid, id)
            """)
        logger.info("Conversation tables ready")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ==================== Conversation ====================

    @staticmethod
    def _generate_uid() -> str:
        """生成 10 位字母数字随机 UID"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(10))

    async def create_conversation(self, owner_uid: str, title: Optional[str] = None) -> str:
        """创建对话，返回新 uid"""
        owner_uid = str(owner_uid)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            while True:
                uid = self._generate_uid()
                exists = await conn.fetchval(
                    "SELECT 1 FROM conversations WHERE uid=$1", uid
                )
                if not exists:
                    break
            await conn.execute(
                "INSERT INTO conversations (uid, owner_uid, title) VALUES ($1, $2, $3)",
                uid, owner_uid, title,
            )
        logger.info("Conversation created: %s", uid)
        return uid

    async def conversation_exists(self, uid: str) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchval("SELECT 1 FROM conversations WHERE uid=$1", uid)
            return row is not None

    async def get_conversations_by_owner(self, owner_uid: str) -> List[str]:
        """返回用户所有对话 uid 列表（按最新更新排序）"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT uid FROM conversations WHERE owner_uid=$1 ORDER BY updated_at DESC",
                str(owner_uid),
            )
            return [r["uid"] for r in rows]

    async def delete_conversation(self, uid: str) -> bool:
        """删除对话（消息随 ON DELETE CASCADE 一并删除）"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM conversations WHERE uid=$1", uid)
            deleted = int(result.split()[-1])
            return deleted > 0

    async def user_owns_conversation(self, uid: str, owner_uid: str) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT 1 FROM conversations WHERE uid=$1 AND owner_uid=$2",
                uid, str(owner_uid),
            )
            return row is not None

    # ==================== Messages ====================

    async def add_message(
        self,
        conversation_uid: str,
        role: str,
        content: str,
        attachments: list | None = None,
    ) -> None:
        """追加一条消息，并更新 conversation.updated_at"""
        import json
        attachments_json = json.dumps(attachments or [])
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO messages (conversation_uid, role, content, attachments) VALUES ($1, $2, $3, $4::jsonb)",
                    conversation_uid, role, content, attachments_json,
                )
                await conn.execute(
                    "UPDATE conversations SET updated_at=NOW() WHERE uid=$1",
                    conversation_uid,
                )

    async def get_messages(self, conversation_uid: str) -> List[Dict]:
        """获取对话全量消息，按 id 升序"""
        import json
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content, attachments FROM messages WHERE conversation_uid=$1 ORDER BY id ASC",
                conversation_uid,
            )
            result = []
            for r in rows:
                raw = r["attachments"]
                if isinstance(raw, str):
                    attachments = json.loads(raw)
                elif raw is None:
                    attachments = []
                else:
                    attachments = list(raw)
                result.append({
                    "role": r["role"],
                    "content": r["content"],
                    "attachments": attachments,
                })
            return result
