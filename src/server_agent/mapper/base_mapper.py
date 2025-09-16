"""
基础 Mapper 类 - 提供通用的数据库操作功能
"""
import asyncio
import logging
from abc import ABC
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, List, Union

import aiosqlite

from src.server_agent.exceptions import DatabaseError, handle_mapper_exception

logger = logging.getLogger(__name__)


class BaseMapper(ABC):
    """基础 Mapper 类"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_db_directory()
        self._connection_pool = asyncio.Queue(maxsize=10)
        self._pool_size = 0
        self._max_pool_size = 10

    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def _create_connection(self) -> aiosqlite.Connection:
        """创建新的数据库连接"""
        try:
            db = await aiosqlite.connect(
                self.db_path,
                timeout=30.0,  # 30秒超时
                isolation_level=None  # 自动提交模式
            )

            # 设置 SQLite 优化参数
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")
            await db.execute("PRAGMA busy_timeout = 30000;")
            await db.execute("PRAGMA cache_size = 10000;")
            await db.execute("PRAGMA temp_store = MEMORY;")

            return db
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise DatabaseError(
                detail="Failed to create database connection",
                operation="create_connection",
                context={"db_path": str(self.db_path), "error": str(e)}
            )

    async def _get_connection(self) -> aiosqlite.Connection:
        """获取数据库连接（从连接池或创建新连接）"""
        try:
            # 尝试从连接池获取连接
            if not self._connection_pool.empty():
                return self._connection_pool.get_nowait()

            # 如果连接池为空且未达到最大连接数，创建新连接
            if self._pool_size < self._max_pool_size:
                self._pool_size += 1
                return await self._create_connection()

            # 等待连接池中的连接
            return await self._connection_pool.get()

        except asyncio.QueueEmpty:
            # 连接池为空，创建新连接
            self._pool_size += 1
            return await self._create_connection()

    async def _return_connection(self, conn: aiosqlite.Connection):
        """归还连接到连接池"""
        try:
            if self._connection_pool.qsize() < self._max_pool_size:
                self._connection_pool.put_nowait(conn)
            else:
                await conn.close()
                self._pool_size -= 1
        except Exception as e:
            logger.warning(f"Failed to return connection to pool: {e}")
            await conn.close()
            self._pool_size -= 1

    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = await self._get_connection()
        try:
            yield conn
        finally:
            await self._return_connection(conn)

    @handle_mapper_exception
    async def execute_query(self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> \
    Union[None, aiosqlite.Row, List[aiosqlite.Row]]:
        """
        执行查询语句
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            fetch_one: 是否只获取一行
            fetch_all: 是否获取所有行
            
        Returns:
            查询结果（支持对象属性访问）
        """
        async with self.get_connection() as db:
            # 设置 row_factory 为 Row 对象，支持属性访问
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                if fetch_one:
                    return await cursor.fetchone()
                elif fetch_all:
                    return await cursor.fetchall()
                else:
                    return None

    @handle_mapper_exception
    async def execute_transaction(self, operations: List[Dict[str, Any]]) -> bool:
        """
        执行事务操作
        
        Args:
            operations: 操作列表，每个操作包含 'query' 和 'params'
            
        Returns:
            事务是否成功
        """
        async with self.get_connection() as db:
            try:
                await db.execute("BEGIN IMMEDIATE;")

                for operation in operations:
                    await db.execute(operation['query'], operation['params'])

                await db.commit()
                return True

            except Exception as e:
                await db.rollback()
                logger.error(f"Transaction failed: {e}")
                raise DatabaseError(
                    detail="Transaction failed",
                    operation="execute_transaction",
                    context={"operations_count": len(operations), "error": str(e)}
                )

    @handle_mapper_exception
    async def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """
        批量执行操作
        
        Args:
            query: SQL 语句
            params_list: 参数列表
            
        Returns:
            影响的行数
        """
        async with self.get_connection() as db:
            try:
                await db.execute("BEGIN IMMEDIATE;")

                await db.executemany(query, params_list)

                await db.commit()
                return len(params_list)

            except Exception as e:
                await db.rollback()
                logger.error(f"Batch operation failed: {e}")
                raise DatabaseError(
                    detail="Batch operation failed",
                    operation="execute_batch",
                    context={"query": query, "params_count": len(params_list), "error": str(e)}
                )

    async def close_all_connections(self):
        """关闭所有连接"""
        while not self._connection_pool.empty():
            try:
                conn = self._connection_pool.get_nowait()
                await conn.close()
                self._pool_size -= 1
            except asyncio.QueueEmpty:
                break

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_all_connections()
