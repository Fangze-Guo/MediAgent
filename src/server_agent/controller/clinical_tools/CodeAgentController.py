"""
CodeAgent 控制器。
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.server_agent.common import BaseResponse, ResultUtils
from src.server_agent.controller.base import BaseController
from src.server_agent.exceptions import NotFoundError
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service.clinical_tools.CodeAgentService import CodeAgentService


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$", description="消息角色")
    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="会话ID")
    message: str = Field(..., min_length=1, max_length=5000, description="消息文本")


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="会话标题")


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="会话标题")


class ConversationInfoResponse(BaseModel):
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: int
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int
    last_message: Optional[str] = None


class MessageResponse(BaseModel):
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    role: str
    content: str
    thinking: Optional[str] = None
    created_at: Optional[str] = None


class ConversationDetailResponse(BaseModel):
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: int
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    messages: List[MessageResponse]


class CodeAgentController(BaseController):
    def __init__(self):
        super().__init__(prefix="/code-agent", tags=["Code Agent"])
        self.service = CodeAgentService()
        self._register_routes()

    def _extract_text_and_thinking(self, message_content: Any) -> Tuple[str, Optional[str]]:
        """
        从 JSONL 的 message.content 中提取可见文本与 thinking。
        支持 Claude 风格内容分块：text / thinking。
        """
        text_parts: List[str] = []
        thinking_parts: List[str] = []

        if isinstance(message_content, str):
            if message_content.strip():
                text_parts.append(message_content.strip())
        elif isinstance(message_content, list):
            for part in message_content:
                if isinstance(part, str):
                    if part.strip():
                        text_parts.append(part.strip())
                    continue

                if not isinstance(part, dict):
                    continue

                part_type = part.get("type")
                if part_type in ("text", "input_text", "output_text"):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        text_parts.append(text.strip())
                elif part_type == "thinking":
                    thinking = part.get("thinking") or part.get("text")
                    if isinstance(thinking, str) and thinking.strip():
                        thinking_parts.append(thinking.strip())

        text = "\n".join(text_parts).strip()
        thinking = "\n".join(thinking_parts).strip() if thinking_parts else None
        return text, thinking

    def _parse_jsonl_messages(self, jsonl_messages: List[Dict[str, Any]], conversation_id: str) -> List[MessageResponse]:
        """
        将原始 JSONL 记录转换成前端可渲染消息。
        - 跳过控制类记录（queue-operation / last-prompt / attachment）
        - 仅保留 user/assistant 消息
        - 对同一个 message.id 的 assistant thinking/text 片段做合并
        """
        sorted_entries = sorted(jsonl_messages, key=lambda x: x.get("timestamp", ""))
        messages_response: List[MessageResponse] = []
        assistant_index_by_message_id: Dict[str, int] = {}

        for i, entry in enumerate(sorted_entries):
            entry_type = entry.get("type", "")
            if entry_type in ("queue-operation", "last-prompt", "attachment"):
                continue

            raw_message = entry.get("message")
            if not isinstance(raw_message, dict):
                continue

            role = raw_message.get("role")
            if role not in ("user", "assistant"):
                continue

            content, thinking = self._extract_text_and_thinking(raw_message.get("content", ""))
            if not content and not thinking:
                continue

            message_id = entry.get("uuid") or f"msg_{i}"
            assistant_message_id = raw_message.get("id")

            if role == "assistant" and assistant_message_id and assistant_message_id in assistant_index_by_message_id:
                idx = assistant_index_by_message_id[assistant_message_id]
                existing = messages_response[idx]

                if content:
                    existing.content = f"{existing.content}\n{content}".strip() if existing.content else content
                if thinking:
                    existing.thinking = f"{existing.thinking}\n{thinking}".strip() if existing.thinking else thinking
                continue

            parsed_message = MessageResponse(
                message_id=message_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                thinking=thinking,
                created_at=entry.get("timestamp"),
            )
            messages_response.append(parsed_message)

            if role == "assistant" and assistant_message_id:
                assistant_index_by_message_id[assistant_message_id] = len(messages_response) - 1

        return messages_response

    def _register_routes(self):
        @self.router.post("/taking")
        async def taking(request: ChatRequest, user_vo: UserVO = Depends(self._get_current_user)) -> StreamingResponse:
            async def generate_stream():
                async for chunk in self.service.stream_chat(
                    request.conversation_id,
                    [],
                    request.message,
                    user_vo.uid,
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
            try:
                response_content = await self.service.chat(
                    request.conversation_id,
                    [],
                    request.message,
                    user_id=user_vo.uid,
                )
                return ResultUtils.success(response_content)
            except Exception as e:
                return ResultUtils.error(500, f"对话失败: {str(e)}")

        @self.router.post("/conversations")
        async def create_conversation(
            request: CreateConversationRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[ConversationInfoResponse]:
            conversation = await self.service.create_conversation(
                user_id=user_vo.uid,
                title=request.title,
            )

            response = ConversationInfoResponse(
                conversation_id=conversation.conversation_id,
                user_id=conversation.user_id,
                title=conversation.title,
                created_at=conversation.created_at.isoformat() if conversation.created_at else None,
                updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
                message_count=conversation.message_count,
                last_message=conversation.last_message,
            )

            return ResultUtils.success(response)

        @self.router.get("/conversations")
        async def get_conversations(
            limit: int = Query(50, ge=1, le=100, description="分页大小"),
            offset: int = Query(0, ge=0, description="偏移量"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[List[ConversationInfoResponse]]:
            conversations = await self.service.get_conversations(
                user_id=user_vo.uid,
                limit=limit,
                offset=offset,
            )

            response_list = [
                ConversationInfoResponse(
                    conversation_id=conv.conversation_id,
                    session_id=conv.session_id,
                    user_id=conv.user_id,
                    title=conv.title,
                    created_at=conv.created_at.isoformat() if conv.created_at else None,
                    updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
                    message_count=conv.message_count,
                    last_message=conv.last_message,
                )
                for conv in conversations
            ]

            return ResultUtils.success(response_list)

        @self.router.get("/conversations/{conversation_id}")
        async def get_conversation_detail(
            conversation_id: str,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[ConversationDetailResponse]:
            detail = await self.service.get_conversation_detail(
                conversation_id=conversation_id,
                user_id=user_vo.uid,
            )

            if detail is None:
                raise NotFoundError(detail="会话不存在")

            session_id = detail.conversation.session_id
            if session_id:
                from src.server_agent.service.clinical_tools.JsonlSessionService import get_session_service

                session_service = get_session_service()
                jsonl_messages, _, _ = await session_service.get_session_messages(
                    session_id=session_id,
                    project_path=None,
                    limit=500,
                    offset=0,
                )
                messages_response = self._parse_jsonl_messages(jsonl_messages, conversation_id)
            else:
                messages_response = []

            response = ConversationDetailResponse(
                conversation_id=detail.conversation.conversation_id,
                session_id=detail.conversation.session_id,
                user_id=detail.conversation.user_id,
                title=detail.conversation.title,
                created_at=detail.conversation.created_at.isoformat() if detail.conversation.created_at else None,
                updated_at=detail.conversation.updated_at.isoformat() if detail.conversation.updated_at else None,
                messages=messages_response,
            )

            return ResultUtils.success(response)

        @self.router.put("/conversations/{conversation_id}")
        async def update_conversation(
            conversation_id: str,
            request: UpdateConversationRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            success = await self.service.update_conversation_info(
                conversation_id=conversation_id,
                user_id=user_vo.uid,
                title=request.title,
            )

            return ResultUtils.success(success)

        @self.router.delete("/conversations/{conversation_id}")
        async def delete_conversation(
            conversation_id: str,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            success = await self.service.delete_conversation(
                conversation_id=conversation_id,
                user_id=user_vo.uid,
            )

            return ResultUtils.success(success)

        @self.router.get("/sessions/{session_id}/messages")
        async def get_session_messages(
            session_id: str,
            limit: int = Query(100, ge=1, le=500, description="分页大小"),
            offset: int = Query(0, ge=0, description="偏移量"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            from src.server_agent.service.clinical_tools.JsonlSessionService import get_session_service

            session_service = get_session_service()
            messages, total, has_more = await session_service.get_session_messages(
                session_id=session_id,
                project_path=None,
                limit=limit,
                offset=offset,
            )

            parsed_messages = self._parse_jsonl_messages(messages, conversation_id=session_id)
            normalized_messages = []
            for i, msg in enumerate(parsed_messages):
                kind = "thinking" if msg.thinking and not msg.content else "text"
                normalized_messages.append({
                    "id": msg.message_id or f"msg_{i}",
                    "sessionId": session_id,
                    "timestamp": msg.created_at or "",
                    "provider": "claude",
                    "kind": kind,
                    "role": msg.role,
                    "content": msg.content or msg.thinking or "",
                    "thinking": msg.thinking,
                })

            return ResultUtils.success({
                "messages": normalized_messages,
                "total": total,
                "hasMore": has_more,
            })

    async def _get_current_user(self, authorization: str = Header(None)) -> UserVO:
        from src.server_agent.exceptions import AuthenticationError
        from src.server_agent.service.UserService import UserService

        if not authorization:
            raise AuthenticationError(
                detail="缺少认证请求头",
                context={"header": "Authorization"}
            )

        token = authorization[7:] if authorization.startswith("Bearer ") else authorization

        user_service = UserService()
        user_vo: UserVO = await user_service.get_user_by_token(token)
        if not user_vo:
            raise AuthenticationError(
                detail="无效的 token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return user_vo
