# conversation_manager.py
import asyncio
import aiosqlite
import secrets
import string
import json
from pathlib import Path
from typing import Optional, Dict, Any


class ConversationManager:
    def __init__(self, database_path: str, conversation_root: str):
        """
        :param database_path: SQLite 数据库文件路径
        :param conversation_root: 对话文件根目录
        """
        self.database_path = Path(database_path)
        self.conversation_root = Path(conversation_root)
        self.conversation_root.mkdir(parents=True, exist_ok=True)

    async def _user_exists(self, uid: str) -> bool:
        """检查用户 UID 是否存在"""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute("SELECT 1 FROM users WHERE uid=? LIMIT 1", (uid,)) as cur:
                row = await cur.fetchone()
                return row is not None

    async def _conversation_uid_exists(self, conversation_uid: str) -> bool:
        """检查对话 UID 是否已存在"""
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute(
                "SELECT 1 FROM conversations WHERE conversation_uid=? LIMIT 1",
                (conversation_uid,),
            ) as cur:
                row = await cur.fetchone()
                return row is not None

    def _generate_conversation_uid(self) -> str:
        """生成一个 10 位字母+数字的随机 UID"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(10))

    async def create_conversation(self, owner_uid: str) -> Dict[str, Any]:
        """
        创建新对话
        :param owner_uid: 发起请求的用户 UID
        :return: {"ok": bool, "message": str, "conversation_uid": Optional[str]}
        """
        # 1. 检查用户是否存在
        if not await self._user_exists(owner_uid):
            return {"ok": False, "message": "发出请求的用户不存在", "conversation_uid": None}

        # 2. 生成唯一对话 UID
        while True:
            conversation_uid = self._generate_conversation_uid()
            if not await self._conversation_uid_exists(conversation_uid):
                break

        # 3. 创建文件夹和 main_chat.json
        conv_dir = self.conversation_root / conversation_uid
        conv_dir.mkdir(parents=True, exist_ok=False)
        main_chat_file = conv_dir / "main_chat.json"
        async with await asyncio.to_thread(open, main_chat_file, "w", encoding="utf-8") as f:
            # asyncio.to_thread 确保文件写入不阻塞事件循环
            json.dump(
                {"conversation_uid": conversation_uid, "messages": []},
                f,
                ensure_ascii=False,
                indent=2,
            )

        # 4. 插入数据库
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                "INSERT INTO conversations (conversation_uid, owner_uid) VALUES (?, ?)",
                (conversation_uid, owner_uid),
            )
            await db.commit()

        return {"ok": True, "message": "对话创建成功", "conversation_uid": conversation_uid}
