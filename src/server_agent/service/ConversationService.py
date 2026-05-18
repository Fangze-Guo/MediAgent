from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from src.server_agent.agent.conversation_agent import ConversationAgent
from src.server_agent.exceptions import NotFoundError, AuthorizationError, handle_service_exception
from src.server_agent.mapper.ConversationMapper import ConversationMapper

logger = logging.getLogger(__name__)


class ConversationService:
    """会话服务类（PostgreSQL 版本，无本地文件 I/O）"""

    def __init__(self) -> None:
        pass

    # ---------------------- 私有：从 app.state 获取依赖 ----------------------

    def _get_mapper(self, request) -> ConversationMapper:
        return request.app.state.conv_mapper

    def _get_agent(self, request) -> ConversationAgent:
        return request.app.state.runtime_registry.get_agent()

    # ---------------------- 对话管理 ----------------------

    @handle_service_exception
    async def create_conversation(self, request, owner_uid: str) -> str:
        """创建新对话，返回 uid"""
        mapper = self._get_mapper(request)
        uid = await mapper.create_conversation(owner_uid)
        logger.info("对话创建成功: %s", uid)
        return uid

    @handle_service_exception
    async def get_messages(
        self,
        request,
        conversation_uid: str,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取对话全量消息；可选校验所有权"""
        mapper = self._get_mapper(request)

        if not await mapper.conversation_exists(conversation_uid):
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_uid,
                detail="该对话不存在",
            )

        if user_id and not await mapper.user_owns_conversation(conversation_uid, user_id):
            raise AuthorizationError(
                detail="无权访问该会话",
                context={"conversation_uid": conversation_uid, "user_id": user_id},
            )

        return await mapper.get_messages(conversation_uid)

    @handle_service_exception
    async def get_user_conversation_uids(self, request, user_id: str) -> List[str]:
        """获取用户所有对话 uid 列表"""
        mapper = self._get_mapper(request)
        return await mapper.get_conversations_by_owner(user_id)

    @handle_service_exception
    async def delete_conversation(self, request, conversation_uid: str) -> bool:
        """删除对话（消息随 ON DELETE CASCADE 一并删除）"""
        mapper = self._get_mapper(request)

        if not await mapper.conversation_exists(conversation_uid):
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_uid,
                detail="该会话不存在",
            )

        deleted = await mapper.delete_conversation(conversation_uid)
        logger.info("会话删除成功: %s", conversation_uid)
        return deleted

    # ---------------------- 消息发送 ----------------------

    @handle_service_exception
    async def send_message(
        self, request, conversation_uid: str, content: str
    ) -> str:
        """同步发送：等待完整回复后返回"""
        mapper = self._get_mapper(request)
        agent = self._get_agent(request)

        history = await mapper.get_messages(conversation_uid)
        reply = await agent.converse(content, history)

        await mapper.add_message(conversation_uid, "user", content)
        await mapper.add_message(conversation_uid, "assistant", reply)

        return reply

    async def stream_message(
        self, request, conversation_uid: str, content: str
    ) -> AsyncGenerator[str, None]:
        """流式发送：逐 token yield，完成后持久化完整回复"""
        mapper = self._get_mapper(request)
        agent = self._get_agent(request)

        history = await mapper.get_messages(conversation_uid)

        await mapper.add_message(conversation_uid, "user", content)

        full_reply: List[str] = []
        async for token in agent.stream(content, history):
            full_reply.append(token)
            yield token

        await mapper.add_message(conversation_uid, "assistant", "".join(full_reply))