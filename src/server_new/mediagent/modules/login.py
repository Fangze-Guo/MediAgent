# src/server_new/mediagent/modules/login.py
from __future__ import annotations

import string
import secrets
from pathlib import Path
from typing import TypedDict, Optional

import aiosqlite


def _resolve_db_path() -> Path:
    """定位到 server_new/data/db/app.sqlite3（优先用你的 paths 模块）"""
    try:
        from ..paths import in_data  # 若已实现
        return in_data("db", "app.sqlite3")
    except Exception:
        return Path(__file__).resolve().parents[2] / "data" / "db" / "app.sqlite3"


DB_PATH: Path = _resolve_db_path()
_ALPHABET = string.ascii_letters + string.digits  # a-zA-Z0-9


class LoginResult(TypedDict):
    ok: bool
    code: str
    message: str
    token: Optional[str]


async def _username_row(db: aiosqlite.Connection, user_name: str) -> Optional[tuple[int, str]]:
    """按用户名(不区分大小写)查找用户，返回 (uid, password) 或 None"""
    async with db.execute(
        "SELECT uid, password FROM users WHERE user_name = ? COLLATE NOCASE LIMIT 1;",
        (user_name,),
    ) as cur:
        return await cur.fetchone()


async def _token_exists(db: aiosqlite.Connection, token: str) -> bool:
    async with db.execute("SELECT 1 FROM users WHERE token = ? LIMIT 1;", (token,)) as cur:
        return (await cur.fetchone()) is not None


def _gen_token(n: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


async def _gen_unique_token(db: aiosqlite.Connection, n: int = 10) -> str:
    # 10位字母数字，直到不与现有 token 冲突为止
    while True:
        t = _gen_token(n)
        if not await _token_exists(db, t):
            return t


async def login_user(user_name: str, password: str) -> LoginResult:
    """
    登录（明文密码，仅 demo）：
    - 用户名不存在 → USERNAME_NOT_FOUND
    - 密码不匹配 → BAD_PASSWORD
    - 成功 → 生成10位字母数字token，写回 users.token，返回 token
    """
    if not user_name or not password:
        return {"ok": False, "code": "INVALID_INPUT", "message": "username/password required", "token": None}

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")

            # 读用户信息
            row = await _username_row(db, user_name)
            if row is None:
                return {"ok": False, "code": "USERNAME_NOT_FOUND", "message": "username not found", "token": None}

            uid, stored_password = row
            if password != stored_password:  # 明文比对；仅用于 demo
                return {"ok": False, "code": "BAD_PASSWORD", "message": "incorrect password", "token": None}

            # 生成唯一 token，更新到该用户
            await db.execute("BEGIN IMMEDIATE;")  # 降低并发竞态
            token = await _gen_unique_token(db, 10)
            await db.execute("UPDATE users SET token = ? WHERE uid = ?;", (token, uid))
            await db.commit()

            return {"ok": True, "code": "LOGGED_IN", "message": "login successful", "token": token}

    except aiosqlite.IntegrityError as e:
        # 万一并发下 token 唯一约束撞了，给出兜底错误
        return {"ok": False, "code": "INTEGRITY_ERROR", "message": f"integrity error: {e}", "token": None}
    except Exception as e:
        return {"ok": False, "code": "UNKNOWN_ERROR", "message": f"unknown error: {e}", "token": None}
