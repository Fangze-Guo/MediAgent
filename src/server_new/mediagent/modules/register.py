# src/server_new/mediagent/modules/register.py
from __future__ import annotations

import secrets
from pathlib import Path
from typing import TypedDict, Optional

import aiosqlite

def _resolve_db_path() -> Path:
    """定位到 server_new/data/db/app.sqlite3（优先用你的 paths 模块）"""
    try:
        from ..paths import in_data  # 若你已实现
        return in_data("db", "app.sqlite3")
    except Exception:
        return Path(__file__).resolve().parents[2] / "data" / "db" / "app.sqlite3"

DB_PATH: Path = _resolve_db_path()

class RegisterResult(TypedDict):
    ok: bool
    code: str
    message: str
    uid: Optional[int]

async def _username_exists(db: aiosqlite.Connection, user_name: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM users WHERE user_name = ? COLLATE NOCASE LIMIT 1;",
        (user_name,),
    ) as cur:
        row = await cur.fetchone()
        return row is not None

async def _generate_unique_uid(db: aiosqlite.Connection) -> int:
    # 10 位数字：1000000000..9999999999，直到不撞库
    while True:
        uid = secrets.randbelow(9_000_000_000) + 1_000_000_000
        async with db.execute("SELECT 1 FROM users WHERE uid = ? LIMIT 1;", (uid,)) as cur:
            if await cur.fetchone() is None:
                return uid

async def register_user(user_name: str, password: str) -> RegisterResult:
    """
    异步注册（明文密码，仅 demo）：
    - 用户名大小写不敏感查重
    - 生成 10 位数字 UID（避免与现有冲突）
    - 插入 users(uid, user_name, password, token=NULL)
    """
    if not user_name or not password:
        return {"ok": False, "code": "INVALID_INPUT", "message": "username/password required", "uid": None}

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # 基本设置：外键/WAL 更稳健
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")

            # 尽量减少竞争：开启事务
            await db.execute("BEGIN IMMEDIATE;")

            # 1) 用户名查重（大小写不敏感）
            if await _username_exists(db, user_name):
                await db.rollback()
                return {"ok": False, "code": "USERNAME_EXISTS", "message": "username already exists", "uid": None}

            # 2) 生成唯一 10 位 UID
            uid = await _generate_unique_uid(db)

            # 3) 插入（明文密码；token 先置 NULL）
            await db.execute(
                "INSERT INTO users (uid, user_name, password, token) VALUES (?, ?, ?, NULL);",
                (uid, user_name, password),
            )
            await db.commit()

            return {"ok": True, "code": "REGISTERED", "message": "registered successfully", "uid": uid}

    # 唯一约束/其它完整性问题（即使前面查重了，也可能有并发写入导致竞态）
    except aiosqlite.IntegrityError as e:
        return {"ok": False, "code": "INTEGRITY_ERROR", "message": f"integrity error: {e}", "uid": None}
    except Exception as e:
        return {"ok": False, "code": "UNKNOWN_ERROR", "message": f"unknown error: {e}", "uid": None}
