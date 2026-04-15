"""
Code 智能体服务 - 处理处理 Code 智能体相关的业务逻辑
集成Qwen Code的--resume机制和PostgreSQL持久化，使用新的会话管理方式，第一次对话不使用resume，后续对话使用resume
"""
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, List, Optional, Union

from src.server_agent.agent.qwen_agent import QwenAgent
from src.server_agent.common import ResultUtils
from src.server_agent.exceptions import (
    ValidationError, NotFoundError, DatabaseError,
    ConflictError, handle_service_exception
)
from src.server_agent.mapper.CodeAgentMapper import CodeAgentMapper
from src.server_agent.service.SessionAuditService import SessionAuditService
from src.server_agent.model.entity.CodeAgentConversation import (
    ConversationDetail,
    ConversationInfo,
    CodeAgentConversation,
    CodeAgentMessage
)

logger = logging.getLogger(__name__)


class CodeAgentService:
    """Code 智能体服务 - 正确的 --resume 流程"""

    def __init__(self):
        """初始化服务"""
        self.mapper = CodeAgentMapper()
        self.session_audit_service = SessionAuditService()

        # 创建 Qwen Code Agent(移除 history_provider 参数)
        # 历史消息管理完全由 Qwen 的 --resume 机制处理
        self.qwen_agent = QwenAgent()

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

        Args:
            conversation_id: 会话ID(如果为None，则不保存历史消息)
            messages: 历史消息列表(已弃用参数，保留以兼容接口)
                      格式为 [{"role": "user|assistant", "content": "..."}]
            current_message: 当前用户消息
            user_id: 用户ID(用于权限验证)

        Yields:
            SSE 格式的 JSON 字符串，每个 chunk 都使用 BaseResponse 格式
        """
        # 获取或创建会话审计记录
        session_audit = None
        qwen_session_id = None
        is_first_message = False

        if conversation_id:
            # 验证会话是否存在且属于该用户
            conversation = await self.mapper.get_conversation_by_id(conversation_id)
            if not conversation:
                raise NotFoundError(
                    resource_type="conversation",
                    resource_id=conversation_id,
                    detail="会话不存在"
                )

            if user_id and conversation.user_id != user_id:
                raise ValidationError(
                    detail="无权访问此会话",
                    context={"conversation_id": conversation_id, "user_id": user_id}
                )

            # 获取会话审计记录
            session_audit = await self.session_audit_service.get_conversation_audit(conversation_id)

            # 检查是否是第一次对话
            is_first_message = await self.session_audit_service.is_first_message(conversation_id)

            if is_first_message:
                # 第一次对话:不使用 --resume，直接创建新会话
                logger.info(f"First message for conversation {conversation_id}, creating new Qwen session")
                qwen_session_id = None  # 不使用 --resume
            else:
                # 后续对话:使用 --resume
                qwen_session_id = await self.session_audit_service.get_qwen_session_id(conversation_id)
                if not qwen_session_id:
                    logger.warning(f"Qwen session_id not found for conversation {conversation_id}, treating as first message")
                    qwen_session_id = None
                else:
                    logger.info(f"Resuming Qwen session {qwen_session_id} for conversation {conversation_id}")
        else:
            # 没有 conversation_id 的情况，也认为是新对话，需要注入上下文
            is_first_message = True

        # 第一次对话时注入用户上下文
        context_file_path = None
        if is_first_message and user_id:
            # 创建临时文件保存上下文
            user_context = f"""[SYSTEM]
当前用户ID: {user_id}
用户数据目录: /mnt/c/MediaLab/MediAgent/src/server_new/data/files/private/{user_id}/dataset
工作空间路径: /mnt/c/MediaLab/MediAgent/src/server_new/data/files/private/{user_id}/workspace

当用户询问数据集或文件时，请优先在上述目录中查找。

{current_message}
"""
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(user_context)
                context_file_path = f.name
            logger.info(f"User context written to temp file: {context_file_path}")
        else:
            context_file_path = None

        # 保存用户消息到数据库
        if conversation_id:
            try:
                await self.mapper.add_message(conversation_id, "user", current_message)
            except Exception as e:
                logger.error(f"Failed to save user message: {e}")
        try:
            full_content = ""

            # 调用 Qwen Code Agent
            # 第一次对话:session_id 为 None，创建新会话，使用 context_file_path 或 current_message
            # 后续对话:使用 --resume {session_id}，使用 current_message
            message_to_send = context_file_path if context_file_path else current_message
            async for chunk_json in self.qwen_agent.stream_chat(message_to_send, qwen_session_id, is_file=context_file_path is not None):  # type: ignore
                chunk_data = json.loads(chunk_json)

                if "error" in chunk_data:
                    # 错误情况
                    response = ResultUtils.error(500, chunk_data["error"])
                    error_data = json.dumps({
                        "code": response.code,
                        "data": response.data,
                        "message": response.message,
                    }, ensure_ascii=False)
                    yield f"data: {error_data}\n\n"
                    return

                # 正常输出
                full_content = chunk_data.get("full_content", "")
                is_done = chunk_data.get("done", False)

                response = ResultUtils.success(chunk_data)
                data = json.dumps({
                    "code": response.code,
                    "data": response.data,
                    "message": response.message,
                }, ensure_ascii=False)
                yield f"data: {data}\n\n"

                # 如果完成，保存AI回复
                if is_done and conversation_id:
                    try:
                        await self.mapper.add_message(conversation_id, "assistant", full_content)
                    except Exception as e:
                        logger.error(f"Failed to save assistant message: {e}")

                    # 第一次对话后，提取并保存 session_id
                    if qwen_session_id is None:
                        logger.info(f"First message completed, extracting session_id...")
                        await self.session_audit_service.update_session_id_after_first_message(conversation_id)

        except Exception as e:
            # 发送错误响应
            logger.error(f"Stream chat error: {e}")
            error_response = ResultUtils.error(500, f"流式输出失败: {str(e)}")
            error_data = json.dumps({
                "code": error_response.code,
                "data": error_response.data,
                "message": error_response.message,
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
        finally:
            # 清理临时文件
            if context_file_path and os.path.exists(context_file_path):
                try:
                    os.unlink(context_file_path)
                    logger.info(f"Temp file deleted: {context_file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete temp file {context_file_path}: {e}")

    @handle_service_exception
    async def chat(
        self,
        conversation_id: Optional[str],
        messages: List[dict],
        current_message: str,
        user_id: Optional[int] = None
    ) -> str:
        """
        同步对话方法(用于非流式场景)
        Args:
            conversation_id: 会话ID(如果为None，则不保存历史消息)
            messages: 历史消息列表(已弃用参数，保留以兼容接口)
            current_message: 当前用户消息
            user_id: 用户ID(用于权限验证)

        Returns:
            AI 回复内容
        """
        # 获取或创建会话审计记录
        session_audit = None
        qwen_session_id = None
        is_first_message = False

        if conversation_id:
            # 验证会话是否存在且属于该用户
            conversation = await self.mapper.get_conversation_by_id(conversation_id)
            if not conversation:
                raise NotFoundError(
                    resource_type="conversation",
                    resource_id=conversation_id,
                    detail="会话不存在"
                )

            if user_id and conversation.user_id != user_id:
                raise ValidationError(
                    detail="无权访问此会话",
                    context={"conversation_id": conversation_id, "user_id": user_id}
                )

            # 获取会话审计记录
            session_audit = await self.session_audit_service.get_conversation_audit(conversation_id)

            # 检查是否是第一次对话
            is_first_message = await self.session_audit_service.is_first_message(conversation_id)

            if is_first_message:
                # 第一次对话:不使用 --resume，直接创建新会话
                logger.info(f"First message for conversation {conversation_id}, creating new Qwen session")
                qwen_session_id = None  # 不使用 --resume
            else:
                # 后续对话:使用 --resume
                qwen_session_id = await self.session_audit_service.get_qwen_session_id(conversation_id)
                if not qwen_session_id:
                    logger.warning(f"Qwen session_id not found for conversation {conversation_id}, treating as first message")
                    qwen_session_id = None
                else:
                    logger.info(f"Resuming Qwen session {qwen_session_id} for conversation {conversation_id}")
        else:
            # 没有 conversation_id 的情况，也认为是新对话，需要注入上下文
            is_first_message = True

        # 第一次对话时注入用户上下文
        context_file_path = None
        if is_first_message and user_id:
            # 创建临时文件保存上下文
            user_context = f"""[SYSTEM]
当前用户ID: {user_id}
用户数据目录: /mnt/c/MediaLab/MediAgent/src/server_new/data/files/private/{user_id}/dataset
工作空间路径: /mnt/c/MediaLab/MediAgent/src/server_new/data/files/private/{user_id}/workspace

当用户询问数据集或文件时，请优先在上述目录中查找。

{current_message}
"""
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(user_context)
                context_file_path = f.name
            logger.info(f"User context written to temp file: {context_file_path}")
        else:
            context_file_path = None

        # 保存用户消息到数据库
        if conversation_id:
            try:
                await self.mapper.add_message(conversation_id, "user", current_message)
            except Exception as e:
                logger.error(f"Failed to save user message: {e}")

        # 调用 Qwen Code Agent
        try:
            # 第一次对话:session_id 为 None，创建新会话，使用 context_file_path 或 current_message
            # 后续对话:使用 --resume {session_id}，使用 current_message
            message_to_send = context_file_path if context_file_path else current_message
            response_content = await self.qwen_agent.chat(message_to_send, qwen_session_id, is_file=context_file_path is not None)  # type: ignore

            # 保存AI回复
            if conversation_id:
                try:
                    await self.mapper.add_message(conversation_id, "assistant", response_content)
                except Exception as e:
                    logger.error(f"Failed to save assistant message: {e}")

                # 第一次对话后，提取并保存 session_id
                if qwen_session_id is None:
                    logger.info(f"First message completed, extracting session_id...")
                    await self.session_audit_service.update_session_id_after_first_message(conversation_id)

            return response_content
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise
        finally:
            # 清理临时文件
            if context_file_path and os.path.exists(context_file_path):
                try:
                    os.unlink(context_file_path)
                    logger.info(f"Temp file deleted: {context_file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete temp file {context_file_path}: {e}")

    @handle_service_exception
    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None
    ) -> ConversationInfo:
        """
        创建新会话
        Args:
            user_id: 用户ID
            title: 会话标题(可选)

        Returns:
            创建的会话信息
        """
        if not user_id:
            raise ValidationError(
                detail="user_id is required",
                context={"user_id": user_id}
            )

        # 创建会话
        conversation = await self.mapper.create_conversation(
            user_id=user_id,
            title=title
        )

        # 创建对应的会话审计记录(session_id 为 None，第一次对话后才设置)
        await self.session_audit_service.create_conversation_audit(
            user_id=user_id,
            conversation_id=conversation.conversation_id,
            extra={
                "title": title
            }
        )

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
        """
        获取用户的会话列表
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
        Returns:
            会话信息列表
        """
        if not user_id:
            raise ValidationError(
                detail="user_id is required",
                context={"user_id": user_id}
            )

        return await self.mapper.get_conversations_by_user(user_id, limit, offset)

    @handle_service_exception
    async def get_conversation_detail(
        self,
        conversation_id: str,
        user_id: Optional[int] = None
    ) -> Optional[ConversationDetail]:
        """
        获取会话详情(包含消息)

        Args:
            conversation_id: 会话ID
            user_id: 用户ID(用于权限验证)

        Returns:
            会话详情或None
        """
        # 验证会话是否存在
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_id,
                detail="会话不存在"
            )

        # 权限验证
        if user_id and conversation.user_id != user_id:
            raise ValidationError(
                detail="无权访问此会话",
                context={"conversation_id": conversation_id, "user_id": user_id}
            )

        return await self.mapper.get_conversation_detail(conversation_id)

    @handle_service_exception
    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: Optional[int] = None
    ) -> bool:
        """
        删除会话

        Args:
            conversation_id: 会话ID
            user_id: 用户ID(用于权限验证)

        Returns:
            是否删除成功
        """
        # 验证会话是否存在
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_id,
                detail="会话不存在"
            )

        # 权限验证
        if user_id and conversation.user_id != user_id:
            raise ValidationError(
                detail="无权删除此会话",
                context={"conversation_id": conversation_id, "user_id": user_id}
            )

        # 关闭对应的会话审计记录
        try:
            await self.session_audit_service.close_session(conversation_id)
        except Exception as e:
            logger.error(f"Failed to close session audit for conversation {conversation_id}: {e}")

        # 删除会话审计记录
        try:
            await self.session_audit_service.delete_session(conversation_id)
        except Exception as e:
            logger.error(f"Failed to delete session audit for conversation {conversation_id}: {e}")

        return await self.mapper.delete_conversation(conversation_id)

    @handle_service_exception
    async def update_conversation_info(
        self,
        conversation_id: str,
        user_id: Optional[int],
        title: Optional[str] = None
    ) -> bool:
        """
        更新会话信息

        Args:
            conversation_id: 会话ID
            user_id: 用户ID(用于权限验证)
            title: 新标题(可选)

        Returns:
            是否更新成功
        """
        # 验证会话是否存在
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_id,
                detail="会话不存在"
            )

        # 权限验证
        if user_id and conversation.user_id != user_id:
            raise ValidationError(
                detail="无权修改此会话",
                context={"conversation_id": conversation_id, "user_id": user_id}
            )

        # 更新会话审计记录的额外信息
        try:
            extra = {}
            if title:
                extra["title"] = title

            if extra:
                await self.session_audit_service.update_session_extra(conversation_id, extra)
        except Exception as e:
            logger.error(f"Failed to update session audit for conversation {conversation_id}: {e}")

        return await self.mapper.update_conversation_info(
            conversation_id,
            title=title
        )

    async def close(self):
        """关闭资源"""
        try:
            await self.mapper.close()
            # 不再关闭所有 Qwen 会话，因为会话状态由审计服务管理
        except Exception as e:
            logger.error(f"Error closing service resources: {e}")
