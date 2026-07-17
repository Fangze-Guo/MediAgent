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
    model_id: Optional[str] = None
    images: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None


class AddMessageRequest(BaseModel):
    conversation_id: str
    content: str
    model_id: Optional[str] = None
    images: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None


class ConversationController(BaseController):
    """会话控制器"""

    def __init__(self):
        super().__init__(prefix="/conversation", tags=["会话"])
        self._register_routes()

    def _register_routes(self):

        async def resolve_model_id(
            request: Request,
            current_user: UserVO,
            requested_model_id: Optional[str],
        ) -> str:
            provider = request.app.state.config_provider
            if requested_model_id:
                if provider.get_model_snapshot(requested_model_id) is None:
                    from src.server_agent.exceptions import ValidationError
                    raise ValidationError(
                        detail=f"模型 '{requested_model_id}' 不存在或未启用",
                        field="model_id",
                    )
                return requested_model_id

            mapper = request.app.state.conv_mapper
            preferred_model_id = await mapper.get_user_model_preference(str(current_user.uid))
            if preferred_model_id and provider.get_model_snapshot(preferred_model_id) is not None:
                return preferred_model_id

            default_model_id = provider.get_default_model_id()
            if default_model_id:
                await mapper.set_user_model_preference(str(current_user.uid), default_model_id)
            return default_model_id

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
            current_user: UserVO = Depends(get_current_user),
            conversation_service: ConversationService = Depends(get_conversation_service),
        ) -> BaseResponse[Dict[str, Any]]:
            """发送消息，等待完整回复，返回 {reply, sources}"""
            model_id = await resolve_model_id(request, current_user, body.model_id)
            result = await conversation_service.send_message(
                request,
                body.conversation_id,
                body.content,
                body.images,
                body.attachments,
                user_id=str(current_user.uid),
                model_id=model_id,
            )
            return ResultUtils.success(result)

        @self.router.post("/stream")
        async def streamMessage(
            body: StreamMessageRequest,
            request: Request,
            current_user: UserVO = Depends(get_current_user),
            conversation_service: ConversationService = Depends(get_conversation_service),
        ):
            """流式发送消息，SSE 逐 token 返回；结束时发送 [DONE]"""
            model_id = await resolve_model_id(request, current_user, body.model_id)
            async def generator():
                async for token in conversation_service.stream_message(
                    request,
                    body.conversation_id,
                    body.content,
                    body.images,
                    body.attachments,
                    user_id=str(current_user.uid),
                    user_role=current_user.role,
                    model_id=model_id,
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
