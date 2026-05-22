"""
AgentMapper - 临床智能体 & 全局技能仓库的数据访问层
使用与 CodeAgentMapper 相同的 asyncpg + PostgreSQL 模式
"""
import logging
from typing import List, Optional

import asyncpg

from src.server_agent.configs.pg_config import get_pg_config

logger = logging.getLogger(__name__)


class AgentMapper:

    def __init__(self):
        self._config = get_pg_config()
        self._pool: Optional[asyncpg.Pool] = None

    async def init(self) -> None:
        await self._get_pool()
        await self._ensure_tables()
        logger.info("[AgentMapper] Initialized")

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
                min_size=1,
                max_size=5,
            )
        return self._pool

    async def _ensure_tables(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS global_skills (
                    id           SERIAL PRIMARY KEY,
                    slug         VARCHAR(255) UNIQUE NOT NULL,
                    name         VARCHAR(255) NOT NULL,
                    description  TEXT DEFAULT '',
                    type         VARCHAR(100) DEFAULT 'user-invocable',
                    version      VARCHAR(50)  DEFAULT '1.0.0',
                    author       VARCHAR(255) DEFAULT '',
                    storage_path VARCHAR(500) NOT NULL,
                    user_id      BIGINT,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS clinical_agents (
                    agent_id      VARCHAR(100) PRIMARY KEY,
                    name          VARCHAR(255) NOT NULL,
                    description   TEXT DEFAULT '',
                    system_prompt TEXT DEFAULT '',
                    base_dir      VARCHAR(500) NOT NULL,
                    user_id       BIGINT,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # ------------------------------------------------------------------ #
    # global_skills CRUD
    # ------------------------------------------------------------------ #

    async def upsert_skill(
        self,
        slug: str,
        name: str,
        description: str,
        type_: str,
        version: str,
        author: str,
        storage_path: str,
        user_id: Optional[int] = None,
    ) -> dict:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO global_skills
                    (slug, name, description, type, version, author, storage_path, user_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (slug) DO UPDATE SET
                    name         = EXCLUDED.name,
                    description  = EXCLUDED.description,
                    type         = EXCLUDED.type,
                    version      = EXCLUDED.version,
                    author       = EXCLUDED.author,
                    storage_path = EXCLUDED.storage_path
                RETURNING *
                """,
                slug, name, description, type_, version, author, storage_path, user_id,
            )
        return dict(row)

    async def list_skills(self) -> List[dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM global_skills ORDER BY name")
        return [dict(r) for r in rows]

    async def get_skill_by_slug(self, slug: str) -> Optional[dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM global_skills WHERE slug = $1", slug
            )
        return dict(row) if row else None

    async def delete_skill(self, slug: str) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM global_skills WHERE slug = $1", slug
            )
        return int(result.split()[-1]) > 0

    # ------------------------------------------------------------------ #
    # clinical_agents CRUD
    # ------------------------------------------------------------------ #

    async def create_agent(
        self,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        base_dir: str,
        user_id: Optional[int] = None,
    ) -> dict:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO clinical_agents
                    (agent_id, name, description, system_prompt, base_dir, user_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                agent_id, name, description, system_prompt, base_dir, user_id,
            )
        return dict(row)

    async def list_agents(self, user_id: Optional[int] = None) -> List[dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if user_id is not None:
                rows = await conn.fetch(
                    "SELECT * FROM clinical_agents WHERE user_id = $1 ORDER BY created_at DESC",
                    user_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM clinical_agents ORDER BY created_at DESC"
                )
        return [dict(r) for r in rows]

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM clinical_agents WHERE agent_id = $1", agent_id
            )
        return dict(row) if row else None

    async def update_agent(
        self,
        agent_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[dict]:
        fields, params = [], []
        i = 1
        for col, val in [
            ("name", name),
            ("description", description),
            ("system_prompt", system_prompt),
        ]:
            if val is not None:
                fields.append(f"{col} = ${i}")
                params.append(val)
                i += 1
        if not fields:
            return await self.get_agent(agent_id)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(agent_id)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"UPDATE clinical_agents SET {', '.join(fields)} WHERE agent_id = ${i} RETURNING *",
                *params,
            )
        return dict(row) if row else None

    async def delete_agent(self, agent_id: str) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM clinical_agents WHERE agent_id = $1", agent_id
            )
        return int(result.split()[-1]) > 0

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
