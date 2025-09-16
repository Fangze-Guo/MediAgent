"""
数据库迁移工具
"""
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import aiosqlite
from .base_mapper import BaseMapper
from .paths import in_data

logger = logging.getLogger(__name__)


class Migration:
    """数据库迁移类"""
    
    def __init__(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.created_at = datetime.now()


class DatabaseMigrator:
    """数据库迁移管理器"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.migrations: List[Migration] = []
        self._register_migrations()
    
    def _register_migrations(self):
        """注册所有迁移"""
        # 迁移 1: 创建用户表
        self.migrations.append(Migration(
            version=1,
            name="create_users_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS users (
                    uid INTEGER PRIMARY KEY,
                    user_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password TEXT NOT NULL,
                    token TEXT UNIQUE,
                    created_at TEXT,
                    updated_at TEXT,
                    last_login TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(user_name);
                CREATE INDEX IF NOT EXISTS idx_users_token ON users(token);
                CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
            """,
            down_sql="DROP TABLE IF EXISTS users;"
        ))
        
        # 迁移 2: 创建迁移记录表
        self.migrations.append(Migration(
            version=2,
            name="create_migrations_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
            """,
            down_sql="DROP TABLE IF EXISTS migrations;"
        ))
    
    async def get_current_version(self) -> int:
        """获取当前数据库版本"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT MAX(version) FROM migrations") as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result[0] is not None else 0
        except Exception:
            return 0
    
    async def get_applied_migrations(self) -> List[int]:
        """获取已应用的迁移版本"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT version FROM migrations ORDER BY version") as cursor:
                    results = await cursor.fetchall()
                    return [row[0] for row in results]
        except Exception:
            return []
    
    async def apply_migration(self, migration: Migration) -> bool:
        """应用单个迁移"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("BEGIN IMMEDIATE;")
                
                # 执行迁移SQL
                for sql in migration.up_sql.split(';'):
                    sql = sql.strip()
                    if sql:
                        await db.execute(sql)
                
                # 记录迁移
                await db.execute(
                    "INSERT INTO migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (migration.version, migration.name, migration.created_at.isoformat())
                )
                
                await db.commit()
                logger.info(f"Applied migration {migration.version}: {migration.name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to apply migration {migration.version}: {e}")
            return False
    
    async def rollback_migration(self, migration: Migration) -> bool:
        """回滚单个迁移"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("BEGIN IMMEDIATE;")
                
                # 执行回滚SQL
                if migration.down_sql:
                    for sql in migration.down_sql.split(';'):
                        sql = sql.strip()
                        if sql:
                            await db.execute(sql)
                
                # 删除迁移记录
                await db.execute("DELETE FROM migrations WHERE version = ?", (migration.version,))
                
                await db.commit()
                logger.info(f"Rolled back migration {migration.version}: {migration.name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to rollback migration {migration.version}: {e}")
            return False
    
    async def migrate_to_latest(self) -> bool:
        """迁移到最新版本"""
        current_version = await self.get_current_version()
        applied_migrations = await self.get_applied_migrations()
        
        logger.info(f"Current database version: {current_version}")
        
        # 应用未应用的迁移
        for migration in self.migrations:
            if migration.version not in applied_migrations:
                logger.info(f"Applying migration {migration.version}: {migration.name}")
                if not await self.apply_migration(migration):
                    logger.error(f"Failed to apply migration {migration.version}")
                    return False
        
        logger.info("All migrations applied successfully")
        return True
    
    async def migrate_to_version(self, target_version: int) -> bool:
        """迁移到指定版本"""
        current_version = await self.get_current_version()
        applied_migrations = await self.get_applied_migrations()
        
        if target_version > current_version:
            # 向前迁移
            for migration in self.migrations:
                if migration.version > current_version and migration.version <= target_version:
                    if migration.version not in applied_migrations:
                        logger.info(f"Applying migration {migration.version}: {migration.name}")
                        if not await self.apply_migration(migration):
                            return False
        
        elif target_version < current_version:
            # 向后迁移
            for migration in reversed(self.migrations):
                if migration.version > target_version and migration.version in applied_migrations:
                    logger.info(f"Rolling back migration {migration.version}: {migration.name}")
                    if not await self.rollback_migration(migration):
                        return False
        
        logger.info(f"Migration to version {target_version} completed")
        return True
    
    async def reset_database(self) -> bool:
        """重置数据库"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("BEGIN IMMEDIATE;")
                
                # 删除所有表
                async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                    tables = await cursor.fetchall()
                    for table in tables:
                        await db.execute(f"DROP TABLE IF EXISTS {table[0]}")
                
                await db.commit()
                logger.info("Database reset successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to reset database: {e}")
            return False


async def run_migrations():
    """运行数据库迁移"""
    db_path = in_data("db", "app.sqlite3")
    migrator = DatabaseMigrator(db_path)
    
    # 确保数据库目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 迁移到最新版本
    success = await migrator.migrate_to_latest()
    
    if success:
        print("✅ Database migrations completed successfully")
    else:
        print("❌ Database migrations failed")
    
    return success


if __name__ == "__main__":
    asyncio.run(run_migrations())
