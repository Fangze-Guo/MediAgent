from typing import List, Dict, Any

from common import ResultUtils, BaseResponse
from model.entity.ConversationInfo import ConversationInfo
from src.server_agent.exceptions import ErrorCode
from src.server_new.mediagent.modules.conversation_manager import ConversationManager
from .base import BaseController


class ConversationController(BaseController):
    """消息控制器"""

    def __init__(self):
        super().__init__(prefix="/conversation", tags=["会话"])
        self.conversationService = ConversationManager(
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
            result = await self.conversationService.create_conversation(user_id)
            ok = result["ok"]
            message = result["message"]
            conversation_uid = result["conversation_uid"]

            messageInfo = ConversationInfo(conversation_id=conversation_uid, message=message)

            if ok:
                return ResultUtils.success(messageInfo)
            else:
                return ResultUtils.error(ErrorCode.USER_NOT_FOUND)

        @self.router.post("/add")
        async def addMessageToMain(conversation_id: str, content: str) -> BaseResponse[None]:
            """
            向主对话添加消息
            """
            result = await self.conversationService.add_message_to_main(conversation_id, content)
            ok = result["ok"]
            message = result["message"]
            if ok:
                return ResultUtils.success(None)
            else:
                return ResultUtils.error(ErrorCode.UNKNOWN_ERROR)

        @self.router.get("")
        async def getMessages(conversation_id: str, target: str) -> BaseResponse[List[Dict[str, Any]]]:
            """
            获取对话消息，从 '消息根路径/conversationId/target'
            """
            result = await self.conversationService.get_messages(conversation_id, target)
            ok = result["ok"]
            message = result["message"]
            if ok:
                data: List[Dict[str, Any]] = result["messages"]
                return ResultUtils.success(data)
            else:
                return ResultUtils.error(ErrorCode.UNKNOWN_ERROR)

        @self.router.post("/add_stream")
        async def addMessageToStream(conversation_id: str, target: str, content: str) -> BaseResponse[None]:
            """
            向流对话添加消息
            """
            result = await self.conversationService.add_message_to_stream(conversation_id, target, content)
            ok = result["ok"]
            message = result["message"]
            if ok:
                return ResultUtils.success(None)
            else:
                return ResultUtils.error(ErrorCode.UNKNOWN_ERROR)
