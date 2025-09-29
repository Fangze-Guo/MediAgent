# conversation_manager.py
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import string
from pathlib import Path
from typing import Any, Dict, List

import aiosqlite

from mediagent.modules.conversation_manager import ConversationManager
from src.server_agent.exceptions import NotFoundError, ServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class ConversationService:
    """会话服务类"""

    def __init__(self, database_path: str, conversation_root: str):
        """
        :param database_path: SQLite 数据库文件路径（如: src/server_new/data/db/app.sqlite3）
        :param conversation_root: 对话文件根目录（如: src/server_new/data/conversations）
        """
        self.database_path = Path(database_path)
        self.conversation_root = Path(conversation_root)
        self.conversation_root.mkdir(parents=True, exist_ok=True)
        self.conversationManager = ConversationManager(database_path, conversation_root)
        
        # 延迟导入以避免循环导入
        self._dialogueAgentA = None

        # 同一对话的文件级锁：conversation_uid -> asyncio.Lock
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_dialogue_agent(self):
        """延迟初始化DialogueAgentA以避免循环导入"""
        if self._dialogueAgentA is None:
            from mediagent.agents.chat_plan_agent import DialogueAgentA
            from src.server_agent.service import executor, cfg_a, cm, STREAM_ID, tm, OWNER_UID
            
            self._dialogueAgentA = DialogueAgentA(
                executor, cfg_a,
                cm=cm,
                stream_id=STREAM_ID,
                task_manager=tm,
                db_path=str(self.database_path),
                default_user_uid=OWNER_UID
            )
        return self._dialogueAgentA

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
        """获取（或创建）该对话的文件锁"""
        lock = self._locks.get(conversation_uid)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[conversation_uid] = lock
        return lock

    # ---------------------- 对外功能 ----------------------

    @handle_service_exception
    async def create_conversation(self, owner_uid: str) -> str:
        """
        创建新对话：
          1) 校验用户是否存在
          2) 生成唯一对话UID（10位字母数字）
          3) 在 CONVERSATION_FILE_ROOT/<UID>/main_chat.json 初始化
          4) 向 conversations 表插入记录 (conversation_uid, owner_uid)

        Returns:
            conversation_uid: 对话UID
        """
        # 1) 用户存在性
        if not await self._user_exists(owner_uid):
            raise NotFoundError(
                resource_type="user",
                resource_id=owner_uid,
                detail="用户不存在"
            )

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
        text = json.dumps(init_payload, ensure_ascii=False, indent=2)
        await asyncio.to_thread(main_chat_file.write_text, text, "utf-8")

        # 4) 插入数据库
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                "INSERT INTO conversations (conversation_uid, owner_uid) VALUES (?, ?)",
                (conversation_uid, owner_uid),
            )
            await db.commit()

        logger.info(f"对话创建成功: {conversation_uid}")
        return conversation_uid

    @handle_service_exception
    async def add_message_to_agentA(self, conversation_uid: str, content: str) -> str:
        """向AgentA添加消息并获取响应"""
        dialogue_agent = self._get_dialogue_agent()
        return await dialogue_agent.converse(conversation_uid, content)

    @handle_service_exception
    async def get_messages(self, conversation_uid: str, target: str) -> List[Dict[str, Any]]:
        """
        获取目标消息流（target.json）的 messages 内容。
        
        Returns:
            messages: 消息列表
        """
        if not await self._conversation_uid_exists(conversation_uid):
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_uid,
                detail="该对话UID不存在"
            )

        conv_dir = self.conversation_root / conversation_uid
        target_file = conv_dir / f"{target}.json"

        lock = self._get_lock(conversation_uid)
        async with lock:
            if not target_file.exists():
                raise NotFoundError(
                    resource_type="message_flow",
                    resource_id=target,
                    detail="该对话不存在该目标消息流"
                )

            try:
                raw = await asyncio.to_thread(target_file.read_text, "utf-8")
                data = json.loads(raw)
                messages = data.get("messages")
                if not isinstance(messages, list):
                    raise ServiceError(
                        detail="消息流格式错误",
                        service_name="conversation_service",
                        context={"conversation_uid": conversation_uid, "target": target}
                    )

                return messages

            except json.JSONDecodeError as e:
                raise ServiceError(
                    detail="消息流JSON格式错误",
                    service_name="conversation_service",
                    context={"conversation_uid": conversation_uid, "target": target, "error": str(e)}
                )
            except Exception as e:
                raise ServiceError(
                    detail="获取消息失败",
                    service_name="conversation_service",
                    context={"conversation_uid": conversation_uid, "target": target, "error": str(e)}
                )

    @handle_service_exception
    async def get_user_conversation_uids(self, user_id: str) -> List[str]:
        """
        获取用户的所有会话ID列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[str]: 会话ID列表
        """
        # 验证用户是否存在
        if not await self._user_exists(user_id):
            raise NotFoundError(
                resource_type="user",
                resource_id=user_id,
                detail="用户不存在"
            )

        try:
            async with aiosqlite.connect(self.database_path) as db:
                async with db.execute(
                    "SELECT conversation_uid FROM conversations WHERE owner_uid=? ORDER BY conversation_uid",
                    (user_id,)
                ) as cur:
                    rows = await cur.fetchall()
                    conversation_uids = [row[0] for row in rows]
                    return conversation_uids
        except Exception as e:
            raise ServiceError(
                detail="获取用户会话列表失败",
                service_name="conversation_service",
                context={"user_id": user_id, "error": str(e)}
            )

    @handle_service_exception
    async def delete_conversation(self, conversation_uid: str) -> bool:
        """
        删除会话：
          1) 验证会话是否存在
          2) 删除会话文件目录
          3) 删除数据库记录
        
        Args:
            conversation_uid: 会话ID
            
        Returns:
            bool: 删除成功返回True
        """
        # 验证会话是否存在
        if not await self._conversation_uid_exists(conversation_uid):
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_uid,
                detail="该会话不存在"
            )

        try:
            # 1) 删除文件目录
            conv_dir = self.conversation_root / conversation_uid
            if conv_dir.exists():
                import shutil
                await asyncio.to_thread(shutil.rmtree, conv_dir)
                logger.info(f"已删除会话文件目录: {conv_dir}")

            # 2) 删除数据库记录
            async with aiosqlite.connect(self.database_path) as db:
                cursor = await db.execute(
                    "DELETE FROM conversations WHERE conversation_uid=?",
                    (conversation_uid,)
                )
                await db.commit()
                
                if cursor.rowcount == 0:
                    raise NotFoundError(
                        resource_type="conversation",
                        resource_id=conversation_uid,
                        detail="会话记录不存在"
                    )

            logger.info(f"会话删除成功: {conversation_uid}")
            return True

        except Exception as e:
            raise ServiceError(
                detail="删除会话失败",
                service_name="conversation_service",
                context={"conversation_uid": conversation_uid, "error": str(e)}
            )