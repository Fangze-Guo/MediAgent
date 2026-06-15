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


from src.server_agent.model.entity.MessageResponse import MessageResponse


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$", description="消息角色")
    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="会话ID")
    message: str = Field(..., min_length=1, max_length=5000, description="消息文本")
    project_id: Optional[str] = Field(None, description="项目标识，如 bc, spine")


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="会话标题")
    project_id: Optional[str] = Field(None, description="项目标识，如 bc, spine")


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="会话标题")


class PermissionRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    request_id: Optional[str] = Field(None, description="权限请求ID，用于精确定位并发工具调用")


class ConversationInfoResponse(BaseModel):
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: int
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int
    last_message: Optional[str] = None


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

    def _parse_jsonl_messages(self, jsonl_messages: List[Dict[str, Any]], conversation_id: str) -> List[MessageResponse]:
        """
        将原始 JSONL 记录转换成前端可渲染消息。
        委托给 message_parser.parse_jsonl_messages，确保 Controller 和 Service 使用同一套解析逻辑。
        """
        from src.server_agent.service.clinical_tools.message_parser import parse_jsonl_messages
        return parse_jsonl_messages(jsonl_messages, conversation_id)

    def _register_routes(self):
        async def _owned_conversation_ids(user_id: int) -> set[str]:
            return set(await self.service.mapper.get_conversation_ids_by_user(user_id))

        async def _is_owned_conversation(conversation_id: Optional[str], user_id: int) -> bool:
            if not conversation_id:
                return False
            conversation = await self.service.mapper.get_conversation_by_id(conversation_id)
            return bool(conversation and int(conversation.user_id) == int(user_id))

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

        @self.router.post("/confirm_permission")
        async def confirm_permission(
            request: PermissionRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[str]:
            """确认权限请求"""
            try:
                await self.service.confirm_permission(request.session_id, request.request_id)
                return ResultUtils.success("权限已确认")
            except Exception as e:
                return ResultUtils.error(500, f"确认权限失败: {str(e)}")

        @self.router.post("/cancel_permission")
        async def cancel_permission(
            request: PermissionRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[str]:
            """取消权限请求"""
            try:
                await self.service.cancel_permission(request.session_id, request.request_id)
                return ResultUtils.success("权限已取消")
            except Exception as e:
                return ResultUtils.error(500, f"取消权限失败: {str(e)}")

        @self.router.post("/interrupt/{session_id}")
        async def interrupt_session(
            session_id: str,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            """中断会话"""
            try:
                success = await self.service.interrupt_session(session_id)
                return ResultUtils.success(success)
            except Exception as e:
                return ResultUtils.error(500, f"中断会话失败: {str(e)}")

        @self.router.get("/skill-tasks")
        async def list_skill_tasks(
            conversation_id: Optional[str] = Query(None, description="按会话 ID 筛选"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[list]:
            """查询 Skill 后台任务列表"""
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            manager = get_skill_task_manager()
            if conversation_id:
                if not await _is_owned_conversation(conversation_id, user_vo.uid):
                    return ResultUtils.success([])
                tasks = manager.list_tasks(conversation_id=conversation_id)
            else:
                owned_ids = await _owned_conversation_ids(user_vo.uid)
                tasks = manager.list_tasks(conversation_ids=owned_ids)
            return ResultUtils.success([t.to_dict() for t in tasks])

        @self.router.get("/skill-tasks/{task_id}")
        async def get_skill_task(
            task_id: str,
            conversation_id: str = Query(..., description="任务所属会话 ID"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            """查询单个 Skill 后台任务状态"""
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            manager = get_skill_task_manager()
            task = manager.get_task(task_id)
            if (
                not task
                or task.conversation_id != conversation_id
                or not await _is_owned_conversation(task.conversation_id, user_vo.uid)
            ):
                return ResultUtils.error(404, f"任务不存在: {task_id}")
            return ResultUtils.success(task.to_dict())

        @self.router.delete("/skill-tasks/{task_id}")
        async def delete_skill_task(
            task_id: str,
            conversation_id: str = Query(..., description="任务所属会话 ID"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            """删除单个 Skill 后台任务（运行中会先取消）"""
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            manager = get_skill_task_manager()
            task = manager.get_task(task_id)
            if (
                not task
                or task.conversation_id != conversation_id
                or not await _is_owned_conversation(task.conversation_id, user_vo.uid)
            ):
                return ResultUtils.error(404, f"任务不存在: {task_id}")
            ok = manager.delete(task_id)
            if not ok:
                return ResultUtils.error(404, f"任务不存在: {task_id}")
            return ResultUtils.success(True)

        @self.router.post("/skill-tasks/{task_id}/cancel")
        async def cancel_skill_task(
            task_id: str,
            conversation_id: str = Query(..., description="任务所属会话 ID"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[bool]:
            """请求取消 Skill 任务。

            标准 runner 写入 task_process.json 后可可靠终止进程组；
            若缺少进程组信息，则拒绝假取消。
            """
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            manager = get_skill_task_manager()
            task = manager.get_task(task_id)
            if (
                not task
                or task.conversation_id != conversation_id
                or not await _is_owned_conversation(task.conversation_id, user_vo.uid)
            ):
                return ResultUtils.error(404, f"任务不存在: {task_id}")
            ok = manager.cancel(task_id)
            if not ok:
                return ResultUtils.error(409, "当前任务缺少进程组信息，无法可靠取消")
            return ResultUtils.success(True)

        @self.router.delete("/skill-tasks")
        async def clear_skill_tasks(
            conversation_id: Optional[str] = Query(None, description="仅清理指定会话的任务"),
            only_finished: bool = Query(True, description="True 仅清理已完成/失败任务；False 同时取消并清理运行中任务"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[int]:
            """批量清理 Skill 后台任务，返回清理的数量"""
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            manager = get_skill_task_manager()
            if conversation_id:
                if not await _is_owned_conversation(conversation_id, user_vo.uid):
                    return ResultUtils.success(0)
                removed = manager.clear(conversation_id=conversation_id, only_finished=only_finished)
            else:
                removed = 0
                for owned_conversation_id in await _owned_conversation_ids(user_vo.uid):
                    removed += manager.clear(
                        conversation_id=owned_conversation_id,
                        only_finished=only_finished,
                    )
            return ResultUtils.success(removed)

        @self.router.post("/conversations")
        async def create_conversation(
            request: CreateConversationRequest,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[ConversationInfoResponse]:
            conversation = await self.service.create_conversation(
                user_id=user_vo.uid,
                title=request.title,
                project_id=request.project_id,
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
            project_id: Optional[str] = Query(None, description="项目标识，如 bc, spine"),
            limit: int = Query(50, ge=1, le=100, description="分页大小"),
            offset: int = Query(0, ge=0, description="偏移量"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[List[ConversationInfoResponse]]:
            conversations = await self.service.get_conversations(
                user_id=user_vo.uid,
                limit=limit,
                offset=offset,
                project_id=project_id,
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

        @self.router.get("/conversations/{conversation_id}/export")
        async def export_conversation(
            conversation_id: str,
            format: str = Query("markdown", regex="^(markdown|json|html)$", description="导出格式"),
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> StreamingResponse:
            """导出会话内容为 Markdown / JSON / HTML 文件"""
            content, mime_type, filename = await self.service.export_conversation(
                conversation_id=conversation_id,
                user_id=user_vo.uid,
                fmt=format,
            )

            import io
            from urllib.parse import quote
            # RFC 5987: 用 filename* 支持非 ASCII 文件名（中文等），同时保留 filename 作 fallback
            encoded_filename = quote(filename, safe='')
            ascii_fallback = encoded_filename if not filename.isascii() else filename
            disposition = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_filename}"
            return StreamingResponse(
                io.BytesIO(content.encode("utf-8")),
                media_type=mime_type,
                headers={
                    "Content-Disposition": disposition,
                },
            )

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

        @self.router.get("/conversations/{conversation_id}/sub-agents/{tool_use_id}")
        async def get_sub_agent_messages(
            conversation_id: str,
            tool_use_id: str,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            """
            获取子智能体（Task 工具）的会话消息。

            通过父会话的 session_id 定位项目目录，扫描 agent-*.jsonl 文件，
            找到 parent_tool_use_id 匹配的子智能体会话并返回解析后的消息列表。
            """
            from src.server_agent.service.clinical_tools.JsonlSessionService import get_session_service
            from src.server_agent.service.clinical_tools.message_parser import parse_jsonl_messages

            conversation = await self.service.mapper.get_conversation_by_id(conversation_id)
            if not conversation or not conversation.session_id:
                return ResultUtils.success({"messages": [], "found": False})

            session_service = get_session_service()
            raw_entries = await session_service.get_sub_agent_messages_for_tool_use(
                parent_session_id=conversation.session_id,
                tool_use_id=tool_use_id,
            )

            if not raw_entries:
                return ResultUtils.success({"messages": [], "found": False})

            parsed = parse_jsonl_messages(raw_entries, conversation_id=f"sub_{tool_use_id}")
            messages_list = [msg.model_dump() for msg in parsed]
            return ResultUtils.success({"messages": messages_list, "found": True})

        @self.router.get("/conversations/{conversation_id}/session-status")
        async def get_session_status(
            conversation_id: str,
            user_vo: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            """
            查询会话 session 活跃状态。
            active=True 说明后台 Claude Task 仍在运行（即使 SSE 已断开），
            前端可据此轮询 JSONL 获取最新内容。
            """
            from src.server_agent.service.clinical_tools.CodeAgentService import is_conversation_active
            conversation = await self.service.mapper.get_conversation_by_id(conversation_id)
            if not conversation:
                raise NotFoundError(detail="会话不存在")
            active = is_conversation_active(conversation_id)
            return ResultUtils.success({
                "conversation_id": conversation_id,
                "sdk_session_id": conversation.session_id,
                "active": active,
            })

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
        from src.server_agent.dependencies.services import get_user_service

        if not authorization:
            raise AuthenticationError(
                detail="缺少认证请求头",
                context={"header": "Authorization"}
            )

        token = authorization[7:] if authorization.startswith("Bearer ") else authorization

        user_service = get_user_service()
        user_vo: UserVO = await user_service.get_user_by_token(token)
        if not user_vo:
            raise AuthenticationError(
                detail="无效的 token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return user_vo
