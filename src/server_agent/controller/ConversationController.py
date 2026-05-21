from typing import Any, Dict, List, Optional

from fastapi import Depends, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.server_agent.common import ResultUtils, BaseResponse
from src.server_agent.model.entity.ConversationInfo import ConversationInfo
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service.ConversationService import ConversationService
from src.server_agent.dependencies import get_current_user, get_conversation_service
from .base import BaseController


class StreamMessageRequest(BaseModel):
    conversation_id: str
    content: str
    images: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None


class AddMessageRequest(BaseModel):
    conversation_id: str
    content: str
    images: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None


class ConversationController(BaseController):
    """会话控制器"""

    def __init__(self):
        super().__init__(prefix="/conversation", tags=["会话"])
        self._register_routes()

    def _register_routes(self):

        @self.router.post("/create")
        async def createConversation(
            request: Request,
            user_id: str,
            conversation_service: ConversationService = Depends(get_conversation_service),
        ) -> BaseResponse[ConversationInfo]:
            """创建对话"""
            uid = await conversation_service.create_conversation(request, user_id)
            return ResultUtils.success(ConversationInfo(conversation_uid=uid, owner_uid=user_id))

        @self.router.post("/add")
        async def sendMessage(
            body: AddMessageRequest,
            request: Request,
            conversation_service: ConversationService = Depends(get_conversation_service),
        ) -> BaseResponse[Dict[str, Any]]:
            """发送消息，等待完整回复，返回 {reply, sources}"""
            result = await conversation_service.send_message(
                request, body.conversation_id, body.content, body.images, body.attachments
            )
            return ResultUtils.success(result)

        @self.router.post("/stream")
        async def streamMessage(
            body: StreamMessageRequest,
            request: Request,
            conversation_service: ConversationService = Depends(get_conversation_service),
        ):
            """流式发送消息，SSE 逐 token 返回；结束时发送 [DONE]"""
            async def generator():
                async for token in conversation_service.stream_message(
                    request, body.conversation_id, body.content, body.images, body.attachments
                ):
                    yield {"data": token.replace("\n", "%0A")}
                yield {"data": "[DONE]"}

            return EventSourceResponse(generator())

        @self.router.get("")
        async def getMessages(
            request: Request,
            conversation_id: str,
            current_user: UserVO = Depends(get_current_user),
            conversation_service: ConversationService = Depends(get_conversation_service),
        ) -> BaseResponse[List[Dict[str, Any]]]:
            """获取对话全量消息"""
            messages = await conversation_service.get_messages(
                request, conversation_id, str(current_user.uid)
            )
            return ResultUtils.success(messages)

        @self.router.get("/user/{user_id}")
        async def getUserConversations(
            request: Request,
            user_id: str,
            conversation_service: ConversationService = Depends(get_conversation_service),
        ) -> BaseResponse[List[str]]:
            """获取用户所有对话 uid 列表"""
            uids = await conversation_service.get_user_conversation_uids(request, user_id)
            return ResultUtils.success(uids)

        @self.router.delete("/{conversation_id}")
        async def deleteConversation(
            request: Request,
            conversation_id: str,
            conversation_service: ConversationService = Depends(get_conversation_service),
        ) -> BaseResponse[bool]:
            """删除对话"""
            result = await conversation_service.delete_conversation(request, conversation_id)
            return ResultUtils.success(result)