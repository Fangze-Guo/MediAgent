from typing import List, Dict, Any

from common import ResultUtils, BaseResponse
from model.entity.ConversationInfo import ConversationInfo
from src.server_agent.service import ConversationService
from .base import BaseController


class ConversationController(BaseController):
    """消息控制器"""

    def __init__(self):
        super().__init__(prefix="/conversation", tags=["会话"])
        self.conversationService = ConversationService(
            database_path="src/server_new/data/db/app.sqlite3",
            conversation_root="src/server_agent/conversations"
        )
        self._register_routes()

    def _register_routes(self):
        """注册路由"""

        @self.router.post("/create")
        async def createConversation(user_id: str) -> BaseResponse[ConversationInfo]:
            """
            根据用户 id 创建对话
            """
            conversation_uid = await self.conversationService.create_conversation(user_id)
            messageInfo = ConversationInfo(conversation_uid=conversation_uid, owner_uid=user_id)
            return ResultUtils.success(messageInfo)

        from fastapi import Request as _FastRequest
        @self.router.post("/add")
        async def addMessageToAgent(request: _FastRequest, conversation_id: str, content: str) -> BaseResponse[str]:
            """
            向AgentA添加消息并获取响应
            """
            response = await self.conversationService.add_message_to_agentA(request, conversation_id, content)
            return ResultUtils.success(response)

        @self.router.get("")
        async def getMessages(conversation_id: str, target: str) -> BaseResponse[List[Dict[str, Any]]]:
            """
            获取对话消息，从 '消息根路径/conversationId/target'
            """
            messages = await self.conversationService.get_messages(conversation_id, target)
            return ResultUtils.success(messages)

        @self.router.get("/user/{user_id}")
        async def getUserConversations(user_id: str) -> BaseResponse[List[str]]:
            """
            根据用户ID获取其所有会话ID列表
            """
            conversation_uids = await self.conversationService.get_user_conversation_uids(user_id)
            return ResultUtils.success(conversation_uids)

        @self.router.delete("/{conversation_id}")
        async def deleteConversation(conversation_id: str) -> BaseResponse[bool]:
            """
            根据会话ID删除会话
            """
            result = await self.conversationService.delete_conversation(conversation_id)
            return ResultUtils.success(result)