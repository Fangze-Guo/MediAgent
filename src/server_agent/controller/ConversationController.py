from typing import List, Dict, Any

from fastapi import Header, Depends

from src.server_agent.common import ResultUtils, BaseResponse
from src.server_agent.model.entity.ConversationInfo import ConversationInfo
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service import ConversationService
from src.server_agent.service.UserService import UserService
from src.server_agent.exceptions import AuthenticationError
from .base import BaseController


class ConversationController(BaseController):
    """消息控制器"""

    def __init__(self):
        super().__init__(prefix="/conversation", tags=["会话"])
        self.conversationService = ConversationService(
            database_path="src/server_new/data/db/app.sqlite3",
            conversation_root="src/server_agent/conversations"
        )
        self.user_service = UserService()
        self._register_routes()

    async def _get_current_user(self, authorization: str = Header(None)) -> UserVO:
        """根据token获取用户信息的依赖函数"""
        if not authorization:
            raise AuthenticationError(
                detail="Missing authorization header",
                context={"header": "Authorization"}
            )

        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization

        userVO: UserVO = await self.user_service.get_user_by_token(token)
        if not userVO:
            raise AuthenticationError(
                detail="Invalid token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return userVO

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
        async def getMessages(
            conversation_id: str,
            target: str,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[List[Dict[str, Any]]]:
            """
            获取对话消息，从 '消息根路径/conversationId/target'
            """
            messages = await self.conversationService.get_messages(conversation_id, target, userVO.uid)
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