# conversation_manager.py
from __future__ import annotations

import asyncio
import json
import secrets
import string
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite


class ConversationManager:
    """
    最小可用对话管理器（异步）：
    - __init__(database_path, conversation_root)
    - create_conversation(owner_uid) -> 创建对话（校验用户 -> 生成唯一对话UID -> 建目录/JSON -> 落库）
    - add_message_to_main(conversation_uid, content) -> 向 main_chat.json 追加一条消息

    说明：
    - 使用 aiosqlite 避免阻塞事件循环
    - 针对同一 conversation_uid 的文件写入使用 asyncio.Lock 串行化，防止并发破坏 JSON
    """

    def __init__(self, database_path: str, conversation_root: str):
        """
        :param database_path: SQLite 数据库文件路径（如: src/server_new/data/db/app.sqlite3）
        :param conversation_root: 对话文件根目录（如: src/server_new/conversations）
        """
        self.database_path = Path(database_path)
        self.conversation_root = Path(conversation_root)
        self.conversation_root.mkdir(parents=True, exist_ok=True)

        # 同一对话的写入锁：conversation_uid -> asyncio.Lock
        self._locks: Dict[str, asyncio.Lock] = {}

    # ---------------------- 基础工具 ----------------------

    async def _user_exists(self, uid: str) -> bool:
        """检查用户是否存在：users(uid)"""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute("SELECT 1 FROM users WHERE uid=? LIMIT 1", (uid,)) as cur:
                return (await cur.fetchone()) is not None

    async def _conversation_uid_exists(self, conversation_uid: str) -> bool:
        """检查对话UID是否已存在：conversations(conversation_uid)"""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute(
                "SELECT 1 FROM conversations WHERE conversation_uid=? LIMIT 1",
                (conversation_uid,),
            ) as cur:
                return (await cur.fetchone()) is not None

    def _generate_conversation_uid(self) -> str:
        """生成 10 位 [a-zA-Z0-9] 的随机对话UID"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(10))

    def _get_lock(self, conversation_uid: str) -> asyncio.Lock:
        """获取（或创建）该对话的写入锁"""
        lock = self._locks.get(conversation_uid)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[conversation_uid] = lock
        return lock

    # ---------------------- 对外功能 ----------------------

    async def create_conversation(self, owner_uid: str) -> Dict[str, Any]:
        """
        创建新对话：
          1) 校验用户是否存在
          2) 生成唯一对话UID（10位字母数字）
          3) 在 CONVERSATION_FILE_ROOT/<UID>/main_chat.json 初始化
          4) 向 conversations 表插入记录 (conversation_uid, owner_uid)

        返回：
          {"ok": bool, "message": str, "conversation_uid": Optional[str]}
        """
        # 1) 用户存在性
        if not await self._user_exists(owner_uid):
            return {"ok": False, "message": "发出请求的用户不存在", "conversation_uid": None}

        # 2) 生成唯一对话UID
        while True:
            conversation_uid = self._generate_conversation_uid()
            if not await self._conversation_uid_exists(conversation_uid):
                break

        # 3) 创建目录与 main_chat.json
        conv_dir = self.conversation_root / conversation_uid
        conv_dir.mkdir(parents=True, exist_ok=False)
        main_chat_file = conv_dir / "main_chat.json"

        init_payload = {"conversation_uid": conversation_uid, "messages": []}
        # 使用 to_thread 避免大文件写阻塞事件循环
        text = json.dumps(init_payload, ensure_ascii=False, indent=2)
        await asyncio.to_thread(main_chat_file.write_text, text, "utf-8")

        # 4) 插入数据库
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                "INSERT INTO conversations (conversation_uid, owner_uid) VALUES (?, ?)",
                (conversation_uid, owner_uid),
            )
            await db.commit()

        return {"ok": True, "message": "对话创建成功", "conversation_uid": conversation_uid}

    async def add_message_to_main(self, conversation_uid: str, content: str) -> Dict[str, Any]:
        """
        向主对话流（main_chat.json）追加一条消息。
        入参：
          - conversation_uid: 对话UID
          - content: 要插入的内容（字符串）
        返回：
          - {"ok": True, "message": "添加消息成功"} 或错误信息
        """
        # 先确认对话UID存在（复用 _conversation_uid_exists）
        if not await self._conversation_uid_exists(conversation_uid):
            return {"ok": False, "message": "该对话ID不存在"}

        conv_dir = self.conversation_root / conversation_uid
        main_chat_file = conv_dir / "main_chat.json"

        lock = self._get_lock(conversation_uid)
        async with lock:
            try:
                if not main_chat_file.exists():
                    # 你指定：失败统一报“未知错误”
                    return {"ok": False, "message": "未知错误"}

                # 读 -> 改 -> 写 （读写都放到线程池，避免阻塞事件循环）
                raw = await asyncio.to_thread(main_chat_file.read_text, "utf-8")
                data = json.loads(raw)

                messages = data.get("messages")
                if not isinstance(messages, list):
                    return {"ok": False, "message": "未知错误"}

                messages.append({"content": content})
                data["messages"] = messages

                new_text = json.dumps(data, ensure_ascii=False, indent=2)
                await asyncio.to_thread(main_chat_file.write_text, new_text, "utf-8")

                return {"ok": True, "message": "添加消息成功"}

            except Exception:
                return {"ok": False, "message": "未知错误"}
