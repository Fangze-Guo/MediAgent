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
    """CodeAgent数据访问层"""

    def __init__(self):
        self._config = get_pg_config()
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def init(self) -> None:
        """初始化数据库连接池和表结构（仅调用一次）"""
        await self._ensure_database()
        await self._get_pool()
        await self._ensure_tables()
        logger.info("[CodeAgentMapper] Initialized")

    async def _ensure_database(self) -> None:
        """检查目标数据库是否存在，不存在则自动创建"""
        conn = None
        try:
            # 先连接到默认的 postgres 数据库来检查/创建目标数据库
            conn = await asyncpg.connect(
                host=self._config.host,
                port=self._config.port,
                database="postgres",
                user=self._config.user,
                password=self._config.password,
            )
            db_exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", self._config.database
            )
            if not db_exists:
                logger.info(f"Database '{self._config.database}' not found, creating...")
                await conn.execute(f'CREATE DATABASE "{self._config.database}"')
                logger.info(f"Database '{self._config.database}' created successfully")
        except Exception as e:
            logger.warning(f"Failed to auto-create database: {e}, continuing anyway...")
        finally:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:
                    pass

    async def _get_pool(self) -> asyncpg.Pool:
        """获取连接池"""
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
            tables_exist = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'medical_conversations'
                )
            """)

            if tables_exist:
                logger.info("Medical consultations tables already exist")
                # 增量迁移：为已有表添加 project_id 列
                await conn.execute("""
                    ALTER TABLE medical_conversations
                    ADD COLUMN IF NOT EXISTS project_id VARCHAR(50)
                """)
            else:
                # 创建会话表 - 使用 UUID 作为 conversation_id
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS medical_conversations (
                        id SERIAL PRIMARY KEY,
                        conversation_id UUID UNIQUE NOT NULL,
                        session_id VARCHAR(255),
                        user_id BIGINT NOT NULL,
                        project_id VARCHAR(50),
                        title VARCHAR(500),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 消息表已迁移到 JSONL 文件，不再需要数据库表

            # 创建索引
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                ON medical_conversations(user_id)
            """)

            # skill_tasks 持久化表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_tasks (
                    task_id     VARCHAR(64) PRIMARY KEY,
                    skill_name  VARCHAR(255) NOT NULL,
                    params      TEXT NOT NULL DEFAULT '{}',
                    conversation_id VARCHAR(64) NOT NULL,
                    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
                    progress    INT NOT NULL DEFAULT 0,
                    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    started_at  TIMESTAMP,
                    finished_at TIMESTAMP,
                    error       TEXT,
                    output      TEXT,
                    cancelled   BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_skill_tasks_conversation_id
                ON skill_tasks(conversation_id)
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
        title: Optional[str] = None,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> CodeAgentConversation:
        """
        创建新会话

        Args:
            user_id: 用户ID
            title: 会话标题（可选）
            conversation_id: 前端生成的会话ID（可选，默认自动生成）
            session_id: SDK 真实的 session_id（可选）
            project_id: 项目标识，如 "bc", "spine"（可选）

        Returns:
            创建的会话对象
        """
        pool = await self._get_pool()

        if not conversation_id:
            conversation_id = self._generate_conversation_id()

        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                INSERT INTO medical_conversations
                (conversation_id, session_id, user_id, project_id, title)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, conversation_id, session_id, user_id, project_id, title, created_at, updated_at
            """, conversation_id, session_id, user_id, project_id, title)

        return CodeAgentConversation(
            id=record['id'],
            conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
            session_id=record['session_id'],
            user_id=record['user_id'],
            project_id=record['project_id'],
            title=record['title'],
            created_at=record['created_at'],
            updated_at=record['updated_at']
        )

    async def get_conversations_by_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        project_id: Optional[str] = None
    ) -> List[ConversationInfo]:
        """
        获取用户的会话列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            project_id: 项目标识（可选），传入后只返回该项目的会话

        Returns:
            会话信息列表
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 获取会话基本信息
            if project_id:
                rows = await conn.fetch("""
                    SELECT
                        c.id, c.conversation_id, c.session_id, c.user_id,
                        c.project_id, c.title, c.created_at, c.updated_at
                    FROM medical_conversations c
                    WHERE c.user_id = $1 AND c.project_id = $2
                    ORDER BY c.updated_at DESC
                    LIMIT $3 OFFSET $4
                """, user_id, project_id, limit, offset)
            else:
                rows = await conn.fetch("""
                    SELECT
                        c.id, c.conversation_id, c.session_id, c.user_id,
                        c.project_id, c.title, c.created_at, c.updated_at
                    FROM medical_conversations c
                    WHERE c.user_id = $1
                    ORDER BY c.updated_at DESC
                    LIMIT $2 OFFSET $3
                """, user_id, limit, offset)

        return [
            ConversationInfo(
                conversation_id=str(row['conversation_id']) if row['conversation_id'] else None,
                session_id=row['session_id'],
                user_id=row['user_id'],
                project_id=row['project_id'],
                title=row['title'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                message_count=0,
                last_message=None
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
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                SELECT id, conversation_id, session_id, user_id, project_id,
                       title, created_at, updated_at
                FROM medical_conversations
                WHERE conversation_id = $1
            """, conversation_id)

        if record:
            return CodeAgentConversation(
                id=record['id'],
                conversation_id=str(record['conversation_id']) if record['conversation_id'] else None,
                session_id=record['session_id'],
                user_id=record['user_id'],
                project_id=record['project_id'],
                title=record['title'],
                created_at=record['created_at'],
                updated_at=record['updated_at']
            )
        return None

    async def get_conversation_ids_by_user(self, user_id: int) -> List[str]:
        """返回指定用户拥有的全部 code-agent 会话 ID。"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT conversation_id
                FROM medical_conversations
                WHERE user_id = $1
            """, user_id)
        return [str(row["conversation_id"]) for row in rows if row["conversation_id"]]

    async def get_conversation_detail(
        self,
        conversation_id: str
    ) -> Optional[ConversationDetail]:
        """
        获取会话详情（包含消息）

        注意：消息现在从 JSONL 读取，不再从数据库读取
        此方法仅返回会话元数据，消息列表为空

        Args:
            conversation_id: 会话ID

        Returns:
            会话详情或None
        """
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            return None

        # 消息从 JSONL 读取，这里返回空列表
        return ConversationDetail(
            conversation=conversation,
            messages=[]
        )

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除会话（级联删除关联的 skill_tasks）

        Args:
            conversation_id: 会话ID

        Returns:
            是否删除成功
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 先删关联的 skill_tasks
            await conn.execute("""
                DELETE FROM skill_tasks
                WHERE conversation_id = $1
            """, conversation_id)

            result = await conn.execute("""
                DELETE FROM medical_conversations
                WHERE conversation_id = $1
            """, conversation_id)

            # 删除的行数在 result 中
            rows_deleted = int(result.split()[-1])
            return rows_deleted > 0

    async def update_conversation_session_id(
        self,
        conversation_id: str,
        session_id: str
    ) -> bool:
        """
        更新会话的 session_id

        Args:
            conversation_id: 会话ID
            session_id: SDK 真实的 session_id

        Returns:
            是否更新成功
        """
        await self._ensure_tables()
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE medical_conversations
                SET session_id = $2, updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = $1
            """, conversation_id, session_id)

            rows_updated = int(result.split()[-1])
            return rows_updated > 0

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

    # ------------------------------------------------------------------ #
    #  skill_tasks 持久化 CRUD
    # ------------------------------------------------------------------ #

    async def upsert_skill_task(self, task: dict) -> None:
        """插入或更新一条 skill_task 记录（以 task_id 为主键）"""
        import json as _json
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skill_tasks
                    (task_id, skill_name, params, conversation_id, status,
                     progress, created_at, started_at, finished_at,
                     error, output, cancelled)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                ON CONFLICT (task_id) DO UPDATE SET
                    status      = EXCLUDED.status,
                    progress    = EXCLUDED.progress,
                    started_at  = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    error       = EXCLUDED.error,
                    output      = EXCLUDED.output,
                    cancelled   = EXCLUDED.cancelled
            """,
                task["task_id"],
                task["skill_name"],
                _json.dumps(task.get("params", {}), ensure_ascii=False),
                task["conversation_id"],
                task["status"],
                task.get("progress", 0),
                task["created_at"],
                task.get("started_at"),
                task.get("finished_at"),
                task.get("error"),
                _json.dumps(task.get("output"), ensure_ascii=False) if task.get("output") is not None else None,
                task.get("cancelled", False),
            )

    async def delete_skill_task(self, task_id: str) -> bool:
        """删除单条 skill_task 记录"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM skill_tasks WHERE task_id = $1", task_id
            )
            return int(result.split()[-1]) > 0

    async def list_skill_tasks(self, conversation_id: Optional[str] = None) -> list:
        """查询 skill_task 列表，可按 conversation_id 过滤"""
        import json as _json
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if conversation_id:
                rows = await conn.fetch(
                    "SELECT * FROM skill_tasks WHERE conversation_id = $1 ORDER BY created_at DESC",
                    conversation_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM skill_tasks ORDER BY created_at DESC"
                )
        result = []
        for row in rows:
            d = dict(row)
            d["params"] = _json.loads(d["params"]) if d["params"] else {}
            d["output"] = _json.loads(d["output"]) if d["output"] else None
            result.append(d)
        return result

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            logger.info("[CodeAgentMapper] Closing connection pool")
            await self._pool.close()
            self._pool = None
            logger.info("[CodeAgentMapper] Connection pool closed")
        else:
            logger.info("[CodeAgentMapper] Connection pool already closed")
