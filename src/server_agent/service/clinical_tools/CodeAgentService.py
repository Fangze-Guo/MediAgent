"""
Code 智能体服务 - 简化版

使用 Claude SDK 内置的会话管理，不再需要 SessionAuditService
"""
import json
import logging
from typing import AsyncGenerator, List, Optional

from src.server_agent.agent.claude import get_code_agent, get_agent_type, MessageKind
from src.server_agent.exceptions import (
    ValidationError, NotFoundError, handle_service_exception
)
from src.server_agent.mapper.CodeAgentMapper import CodeAgentMapper
from src.server_agent.model.entity.CodeAgentConversation import (
    ConversationDetail,
    ConversationInfo,
    CodeAgentConversation
)

logger = logging.getLogger(__name__)


class CodeAgentService:
    """Code 智能体服务 - SDK 模式"""

    def __init__(self, mapper: Optional[CodeAgentMapper] = None):
        """初始化服务

        Args:
            mapper: 可选，外部传入的 mapper 实例（用于共享连接池）
        """
        self.mapper = mapper if mapper is not None else CodeAgentMapper()
        self.code_agent = get_code_agent()
        logger.info(f"[CodeAgentService] Using agent type: {get_agent_type()}")

    @handle_service_exception
    async def stream_chat(
        self,
        conversation_id: Optional[str],
        messages: List[dict],
        current_message: str,
        user_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式对话方法

        流程：
        1. 前端创建会话 → POST /conversations → 后端生成 UUID 作为 conversation_id 存入 DB
        2. 前端发送消息 → POST /taking (带 conversation_id)
        3. 后端根据 conversation_id 查找 DB 中的 session_id
           - 如果 session_id 存在，传给 SDK 恢复会话
           - 如果 session_id 不存在，传 None 让 SDK 创建新会话
        4. SDK 返回 init 消息（含真实的 sdk_session_id）
        5. 如果 session_id 不存在，后端更新 DB 建立映射

        Args:
            conversation_id: 会话ID
            messages: 历史消息列表（已弃用）
            current_message: 当前用户消息
            user_id: 用户ID

        Yields:
            SSE 格式的 JSON 字符串
        """
        if not conversation_id:
            raise ValidationError(detail="conversation_id is required")

        # 查找会话，获取 sdk_session_id
        existing = await self.mapper.get_conversation_by_id(conversation_id)
        if not existing:
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)

        sdk_session_id = existing.session_id

        # 如果没有 session_id，说明是首次发消息，需要调用 SDK 获取
        if not sdk_session_id:
            logger.info(f"[CodeAgentService] First message for conversation {conversation_id}, SDK will create new session")
        else:
            logger.info(f"[CodeAgentService] Resuming session {conversation_id} with SDK session {sdk_session_id}")

        try:
            full_content = ""

            # 使用 SDK 进行流式对话
            async for chunk_json in self.code_agent.stream_chat(current_message, sdk_session_id):
                chunk_data = json.loads(chunk_json)
                kind = chunk_data.get("kind", "")

                # 统一消息类型
                if kind == MessageKind.STREAM_DELTA:
                    full_content += chunk_data.get("content", "")
                    chunk_data["type"] = "text"
                elif kind == MessageKind.THINKING:
                    chunk_data["type"] = "thinking"
                elif kind == MessageKind.SESSION_CREATED:
                    chunk_data["type"] = "session_created"

                    # 从 init 消息获取 SDK 真实的 session_id
                    init_session_id = chunk_data.get("sessionId") or chunk_data.get("newSessionId")
                    if init_session_id:
                        logger.info(f"[CodeAgentService] SDK init session_id: {init_session_id}")

                        # 如果 DB 中还没有 session_id，建立映射
                        if not existing.session_id:
                            await self.mapper.update_conversation_session_id(conversation_id, init_session_id)
                            logger.info(f"[CodeAgentService] Updated DB: conversation_id={conversation_id}, sdk_session_id={init_session_id}")

                    # 将 conversation_id 放到事件中传给前端
                    chunk_data["conversation_id"] = conversation_id

                elif kind == MessageKind.COMPLETE:
                    chunk_data["type"] = "done"
                    chunk_data["conversation_id"] = conversation_id
                elif kind == MessageKind.ERROR:
                    chunk_data["type"] = "error"
                elif kind == MessageKind.TOOL_USE:
                    # 工具调用事件
                    chunk_data["type"] = "tool_use"
                    logger.info(f"[CodeAgentService] Tool use: {chunk_data.get('toolName')}")
                elif kind == MessageKind.PERMISSION_REQUEST:
                    # 权限请求事件，直接转发给前端
                    chunk_data["type"] = "permission_request"
                    logger.info(f"[CodeAgentService] Permission request: {chunk_data.get('toolName')}")

                # 统一输出格式（SSE）
                yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Stream chat error: {e}")
            error_data = {"kind": "error", "content": str(e), "isError": True}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    @handle_service_exception
    async def chat(
        self,
        conversation_id: Optional[str],
        messages: List[dict],
        current_message: str,
        user_id: Optional[int] = None
    ) -> str:
        """
        同步对话方法
        """
        full_content = ""
        async for chunk in self.stream_chat(conversation_id, messages, current_message, user_id):
            try:
                data = json.loads(chunk.strip().replace("data: ", "").replace("\n\n", ""))
                if data.get("data", {}).get("content"):
                    full_content = data["data"]["content"]
                elif data.get("data", {}).get("kind") == MessageKind.COMPLETE:
                    full_content = data["data"].get("content", "")
            except json.JSONDecodeError:
                pass
        return full_content

    async def confirm_permission(self, session_id: str):
        """确认权限请求"""
        await self.code_agent.confirm_permission(session_id)

    async def cancel_permission(self, session_id: str):
        """取消权限请求"""
        await self.code_agent.cancel_permission(session_id)

    async def interrupt_session(self, session_id: str) -> bool:
        """中断会话"""
        return await self.code_agent.interrupt(session_id)

    @handle_service_exception
    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None
    ) -> ConversationInfo:
        """创建新会话"""
        if not user_id:
            raise ValidationError(detail="user_id is required")

        conversation = await self.mapper.create_conversation(user_id=user_id, title=title)

        return ConversationInfo(
            conversation_id=conversation.conversation_id,
            user_id=conversation.user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=0,
            last_message=None
        )

    @handle_service_exception
    async def get_conversations(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[ConversationInfo]:
        """获取用户的会话列表"""
        if not user_id:
            raise ValidationError(detail="user_id is required")
        return await self.mapper.get_conversations_by_user(user_id, limit, offset)

    @handle_service_exception
    async def get_conversation_detail(
        self,
        conversation_id: str,
        user_id: Optional[int] = None
    ) -> Optional[ConversationDetail]:
        """
        获取会话详情

        注意：消息内容不再从数据库读取，而是通过 /sessions/{session_id}/messages 从 JSONL 获取
        """
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)

        if user_id and conversation.user_id != user_id:
            raise ValidationError(detail="无权访问此会话")

        # 消息从 JSONL 读取，这里返回空列表
        # 前端会通过 /sessions/{session_id}/messages 获取实际消息
        return ConversationDetail(
            conversation=conversation,
            messages=[]  # 不再从数据库读取
        )

    @handle_service_exception
    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: Optional[int] = None
    ) -> bool:
        """删除会话"""
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)

        if user_id and conversation.user_id != user_id:
            raise ValidationError(detail="无权删除此会话")

        return await self.mapper.delete_conversation(conversation_id)

    @handle_service_exception
    async def update_conversation_info(
        self,
        conversation_id: str,
        user_id: Optional[int],
        title: Optional[str] = None
    ) -> bool:
        """更新会话信息"""
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)

        if user_id and conversation.user_id != user_id:
            raise ValidationError(detail="无权修改此会话")

        return await self.mapper.update_conversation_info(conversation_id, title=title)

    async def close(self):
        """关闭资源"""
        try:
            await self.mapper.close()
        except Exception as e:
            logger.error(f"Error closing service resources: {e}")
