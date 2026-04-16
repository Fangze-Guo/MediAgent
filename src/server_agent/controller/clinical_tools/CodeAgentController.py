"""
CodeAgent控制器
提供Agent相关的API接口
"""
from typing import List, Optional

from fastapi import Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.server_agent.common import BaseResponse, ResultUtils
from src.server_agent.controller.base import BaseController
from src.server_agent.exceptions import NotFoundError
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service.clinical_tools.CodeAgentService import CodeAgentService


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., pattern="^(user|assistant)$", description="消息角色：user 或 assistant")
    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""
    conversation_id: Optional[str] = Field(None, description="会话ID（可选，UUID格式）")
    message: str = Field(..., min_length=1, max_length=5000, description="当前消息")


class CreateConversationRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(None, max_length=500, description="会话标题")


class UpdateConversationRequest(BaseModel):
    """更新会话请求"""
    title: Optional[str] = Field(None, max_length=500, description="新标题")


class ConversationInfoResponse(BaseModel):
    """会话信息响应"""
    conversation_id: str
    user_id: int
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int
    last_message: Optional[str] = None


class MessageResponse(BaseModel):
    """消息响应"""
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: Optional[str] = None


class ConversationDetailResponse(BaseModel):
    """会话详情响应"""
    conversation_id: str
    user_id: int
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    messages: List[MessageResponse]


class CodeAgentController(BaseController):
    """代码智能体控制器"""

    def __init__(self):
        super().__init__(prefix="/code-agent", tags=["Code Agent"])
        self.service = CodeAgentService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.post("/taking")
        async def taking(request: ChatRequest, user_vo: UserVO = Depends(self._get_current_user)) -> StreamingResponse:
            """流式对话接口，支持消息历史"""
            from fastapi.responses import StreamingResponse

            # 调用 Service 的流式方法（不再需要历史消息，由Qwen Code管理）
            async def generate_stream():
                async for chunk in self.service.stream_chat(
                    request.conversation_id,
                    [],  # 空的历史消息列表，由Qwen管理
                    request.message,
                    user_vo.uid
                ):
                    yield chunk

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.router.post("/taking/sync")
        async def taking_sync(
            request: ChatRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[str]:
            """同步对话接口（用于接口文档测试）"""
            try:
                # 调用 Service 的同步方法（不再需要历史消息，由Qwen Code管理）
                response_content = await self.service.chat(
                    request.conversation_id,
                    [],  # 空的历史消息列表，由Qwen管理
                    request.message,
                    user_id=user_vo.uid
                )
                return ResultUtils.success(response_content)
            except Exception as e:
                return ResultUtils.error(500, f"对话失败: {str(e)}")

        @self.router.post("/conversations")
        async def create_conversation(
            request: CreateConversationRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[ConversationInfoResponse]:
            """创建新会话"""
            conversation = await self.service.create_conversation(
                user_id=user_vo.uid,
                title=request.title
            )

            response = ConversationInfoResponse(
                conversation_id=conversation.conversation_id,
                user_id=conversation.user_id,
                title=conversation.title,
                created_at=conversation.created_at.isoformat() if conversation.created_at else None,
                updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
                message_count=conversation.message_count,
                last_message=conversation.last_message
            )

            return ResultUtils.success(response)

        @self.router.get("/conversations")
        async def get_conversations(
            limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
            offset: int = Query(0, ge=0, description="偏移量"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[List[ConversationInfoResponse]]:
            """获取用户的会话列表"""
            conversations = await self.service.get_conversations(
                user_id=user_vo.uid,
                limit=limit,
                offset=offset
            )

            response_list = [
                ConversationInfoResponse(
                    conversation_id=conv.conversation_id,
                    user_id=conv.user_id,
                    title=conv.title,
                    created_at=conv.created_at.isoformat() if conv.created_at else None,
                    updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
                    message_count=conv.message_count,
                    last_message=conv.last_message
                )
                for conv in conversations
            ]

            return ResultUtils.success(response_list)

        @self.router.get("/conversations/{conversation_id}")
        async def get_conversation_detail(
            conversation_id: str,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[ConversationDetailResponse]:
            """获取会话详情（包含消息）"""
            detail = await self.service.get_conversation_detail(
                conversation_id=conversation_id,
                user_id=user_vo.uid
            )
            
            if detail is None:
                raise NotFoundError(detail="会话不存在")

            messages_response = [
                MessageResponse(
                    message_id=msg.message_id,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    created_at=msg.created_at.isoformat() if msg.created_at else None
                )
                for msg in detail.messages
            ]

            response = ConversationDetailResponse(
                conversation_id=detail.conversation.conversation_id,
                user_id=detail.conversation.user_id,
                title=detail.conversation.title,
                created_at=detail.conversation.created_at.isoformat() if detail.conversation.created_at else None,
                updated_at=detail.conversation.updated_at.isoformat() if detail.conversation.updated_at else None,
                messages=messages_response
            )

            return ResultUtils.success(response)

        @self.router.put("/conversations/{conversation_id}")
        async def update_conversation(
            conversation_id: str,
            request: UpdateConversationRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            """更新会话信息"""
            success = await self.service.update_conversation_info(
                conversation_id=conversation_id,
                user_id=user_vo.uid,
                title=request.title
            )

            return ResultUtils.success(success)

        @self.router.delete("/conversations/{conversation_id}")
        async def delete_conversation(
            conversation_id: str,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            """删除会话"""
            success = await self.service.delete_conversation(
                conversation_id=conversation_id,
                user_id=user_vo.uid
            )

            return ResultUtils.success(success)

    async def _get_current_user(self, authorization: str = Header(None)) -> UserVO:
        """根据token获取用户信息的依赖函数"""
        from src.server_agent.exceptions import AuthenticationError
        from src.server_agent.service.UserService import UserService

        if not authorization:
            raise AuthenticationError(
                detail="Missing authorization header",
                context={"header": "Authorization"}
            )

        # 支持多种格式：Bearer token 或直接 token
        if authorization.startswith("Bearer "):
            token = authorization[7:]  # 移除 "Bearer " 前缀
        else:
            token = authorization  # 直接使用 token

        user_service = UserService()
        user_vo: UserVO = await user_service.get_user_by_token(token)
        if not user_vo:
            raise AuthenticationError(
                detail="Invalid token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return user_vo
