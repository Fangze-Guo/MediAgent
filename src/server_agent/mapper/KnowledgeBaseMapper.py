"""
知识库 Mapper - PostgreSQL 实现
处理知识库及文档的数据库操作
"""
import logging
from typing import List, Optional

import asyncpg

from ..configs.pg_config import get_pg_config
from ..model.entity.KnowledgeBaseInfo import KnowledgeBaseInfo
from ..model.entity.KbDocumentInfo import KbDocumentInfo

logger = logging.getLogger(__name__)


class KnowledgeBaseMapper:
    """知识库数据库操作类（PostgreSQL）"""

    def __init__(self):
        self._config = get_pg_config()
        self._pool: Optional[asyncpg.Pool] = None

    async def init(self) -> None:
        """初始化连接池并建表（启动时调用一次）"""
        await self._get_pool()
        await self._ensure_tables()
        logger.info("[KnowledgeBaseMapper] Initialized")

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
                max_size=10,
            )
        return self._pool

    async def _ensure_tables(self) -> None:
        """确保知识库相关表存在"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id          SERIAL PRIMARY KEY,
                    name        VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    created_by  BIGINT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_documents (
                    id           SERIAL PRIMARY KEY,
                    kb_id        INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
                    file_name    VARCHAR(500) NOT NULL,
                    file_path    TEXT NOT NULL,
                    file_size    BIGINT NOT NULL DEFAULT 0,
                    content_type VARCHAR(255) NOT NULL,
                    status       VARCHAR(50) NOT NULL DEFAULT 'pending',
                    chunk_count  INTEGER NOT NULL DEFAULT 0,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_documents_kb_id ON kb_documents(kb_id)
            """)
            await conn.execute("""
                ALTER TABLE kb_documents
                ADD COLUMN IF NOT EXISTS chunk_count INTEGER NOT NULL DEFAULT 0
            """)
        logger.info("Knowledge base tables ready")

    # ==================== 知识库 CRUD ====================

    async def create_kb(self, kb: KnowledgeBaseInfo) -> int:
        """创建知识库，返回新 id"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_bases (name, description, created_by)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                kb.name, kb.description, kb.created_by,
            )
            return row["id"]

    async def get_kb_by_id(self, kb_id: int) -> Optional[KnowledgeBaseInfo]:
        """根据 id 获取知识库"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM knowledge_bases WHERE id = $1", kb_id
            )
        return self._row_to_kb(row) if row else None

    async def get_kb_by_name(self, name: str) -> Optional[KnowledgeBaseInfo]:
        """根据名称获取知识库"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM knowledge_bases WHERE name = $1", name
            )
        return self._row_to_kb(row) if row else None

    async def get_all_kbs(self) -> List[KnowledgeBaseInfo]:
        """获取所有知识库"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM knowledge_bases ORDER BY id DESC"
            )
        return [self._row_to_kb(r) for r in rows]

    async def update_kb(self, kb_id: int, update_data: dict) -> bool:
        """更新知识库信息"""
        allowed = {k: v for k, v in update_data.items()
                   if k not in ("id", "created_by", "created_at") and v is not None}
        if not allowed:
            return False
        pool = await self._get_pool()
        idx = 1
        sets = []
        vals = []
        for key, val in allowed.items():
            sets.append(f"{key} = ${idx}")
            vals.append(val)
            idx += 1
        sets.append(f"updated_at = CURRENT_TIMESTAMP")
        vals.append(kb_id)
        query = f"UPDATE knowledge_bases SET {', '.join(sets)} WHERE id = ${idx}"
        async with pool.acquire() as conn:
            await conn.execute(query, *vals)
        return True

    async def delete_kb(self, kb_id: int) -> bool:
        """删除知识库（级联删除文档记录）"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM knowledge_bases WHERE id = $1", kb_id)
        return True

    # ==================== 文档 CRUD ====================

    async def create_document(self, doc: KbDocumentInfo) -> int:
        """创建文档记录，返回新 id"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO kb_documents (kb_id, file_name, file_path, file_size, content_type, status)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                doc.kb_id, doc.file_name, doc.file_path,
                doc.file_size, doc.content_type, doc.status,
            )
            return row["id"]

    async def get_document_by_id(self, doc_id: int) -> Optional[KbDocumentInfo]:
        """根据 id 获取文档"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kb_documents WHERE id = $1", doc_id
            )
        return self._row_to_doc(row) if row else None

    async def get_documents_by_kb(self, kb_id: int) -> List[KbDocumentInfo]:
        """获取知识库下所有文档"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM kb_documents WHERE kb_id = $1 ORDER BY id ASC", kb_id
            )
        return [self._row_to_doc(r) for r in rows]

    async def delete_document(self, doc_id: int) -> bool:
        """删除文档记录"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM kb_documents WHERE id = $1", doc_id)
        return True

    async def delete_documents_by_kb(self, kb_id: int) -> bool:
        """删除知识库下所有文档记录"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM kb_documents WHERE kb_id = $1", kb_id)
        return True

    async def update_document_status(self, doc_id: int, status: str) -> None:
        """更新文档处理状态"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE kb_documents SET status = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                status, doc_id,
            )

    async def update_document_chunk_count(self, doc_id: int, chunk_count: int) -> None:
        """更新文档 chunk 数量"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE kb_documents SET chunk_count = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                chunk_count, doc_id,
            )

    async def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ==================== 内部工具 ====================

    @staticmethod
    def _row_to_kb(row) -> KnowledgeBaseInfo:
        return KnowledgeBaseInfo(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_by=row["created_by"],
            created_at=str(row["created_at"]) if row["created_at"] else None,
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        )

    @staticmethod
    def _row_to_doc(row) -> KbDocumentInfo:
        return KbDocumentInfo(
            id=row["id"],
            kb_id=row["kb_id"],
            file_name=row["file_name"],
            file_path=row["file_path"],
            file_size=row["file_size"],
            content_type=row["content_type"],
            status=row["status"],
            chunk_count=row["chunk_count"] if "chunk_count" in row.keys() else 0,
            created_at=str(row["created_at"]) if row["created_at"] else None,
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        )
