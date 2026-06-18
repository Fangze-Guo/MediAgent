"""
Code 智能体服务 - 简化版

使用 Claude SDK 内置的会话管理，不再需要 SessionAuditService
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from src.server_agent.agent.claude import get_code_agent, get_agent_type, MessageKind
from src.server_agent.agent.claude.claude_agent import find_agent_by_session
from src.server_agent.agent.claude.project_config import get_project_config
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

# 模块级：后台 Claude 任务注册表（conversation_id → asyncio.Task）
# Task 独立于 SSE 连接运行，SSE 断流后 Claude 进程继续写 JSONL
_background_tasks: Dict[str, asyncio.Task] = {}


def is_conversation_active(conversation_id: str) -> bool:
    """检查指定会话的 Claude 后台任务是否仍在运行"""
    task = _background_tasks.get(conversation_id)
    return task is not None and not task.done()


async def shutdown_background_tasks() -> None:
    """取消仍在运行的 Claude worker，避免应用退出后遗留子资源。"""
    tasks = [task for task in _background_tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _background_tasks.clear()


class CodeAgentService:
    """Code 智能体服务 - SDK 模式"""

    def __init__(self, mapper: Optional[CodeAgentMapper] = None):
        """初始化服务

        Args:
            mapper: 可选，外部传入的 mapper 实例（用于共享连接池）
        """
        self.mapper = mapper if mapper is not None else CodeAgentMapper()
        logger.info(f"[CodeAgentService] Using agent type: {get_agent_type()}")

    def _get_agent_for_project(self, project_id: Optional[str] = None):
        """根据 project_id 获取对应的隔离 Agent"""
        if project_id:
            config = get_project_config(project_id)
            if config:
                logger.info(f"[CodeAgentService] Using isolated agent for project: {project_id}")
                return get_code_agent(config)
            else:
                logger.warning(f"[CodeAgentService] Unknown project_id: {project_id}, using default agent")
        return get_code_agent()

    async def stream_chat(
        self,
        conversation_id: Optional[str],
        messages: List[dict],
        current_message: str,
        user_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式对话方法（后台 Task 解耦版）

        Claude SDK 在独立 asyncio.Task 中运行，SSE 生成器只消费 Queue。
        SSE 断流后 Task 继续写 JSONL，前端可通过轮询 /session-status + JSONL 恢复进度。
        """
        if not conversation_id:
            raise ValidationError(detail="conversation_id is required")

        existing = await self.mapper.get_conversation_by_id(conversation_id)
        if not existing:
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)
        if user_id is not None and int(existing.user_id) != int(user_id):
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)

        if is_conversation_active(conversation_id):
            raise ValidationError(detail="当前会话仍在处理中，请等待任务完成后再发送消息")

        sdk_session_id = existing.session_id
        code_agent = self._get_agent_for_project(existing.project_id)

        if sdk_session_id and hasattr(code_agent, '_dead_sessions') and sdk_session_id in code_agent._dead_sessions:
            logger.warning(f"[CodeAgentService] Session {sdk_session_id} is dead, forcing new session")
            await self.mapper.update_conversation_session_id(conversation_id, None)
            code_agent._dead_sessions.discard(sdk_session_id)
            sdk_session_id = None

        if not sdk_session_id:
            logger.info(f"[CodeAgentService] First message for {conversation_id}")
        else:
            logger.info(f"[CodeAgentService] Resuming {conversation_id} with sdk_session={sdk_session_id}")

        # ── 创建事件 Queue，启动独立 Claude 后台 Task ───────────────────────
        queue: asyncio.Queue = asyncio.Queue()  # 无限制，防止 SSE 断流后 put 阻塞

        async def _claude_worker():
            """独立后台任务：运行 Claude SDK，结果写入 Queue。
            本 Task 不受 SSE 连接生命周期影响，SSE 断开后继续运行直到完成。
            """
            try:
                async for chunk_json in code_agent.stream_chat(
                    current_message, sdk_session_id, user_id=user_id,
                    conversation_id=conversation_id
                ):
                    await queue.put(chunk_json)
            except asyncio.CancelledError:
                logger.info(f"[Worker] Explicitly cancelled: {conversation_id}")
                raise
            except Exception as e:
                logger.error(f"[Worker] Error for {conversation_id}: {e}")
                await queue.put(json.dumps({"kind": "error", "content": str(e), "isError": True}))
            finally:
                await queue.put(None)  # 哨兵，通知 SSE 生成器结束
                _background_tasks.pop(conversation_id, None)
                logger.info(f"[Worker] Done: {conversation_id}")

        task = asyncio.create_task(_claude_worker())
        _background_tasks[conversation_id] = task

        # ── SSE 生成器：从 Queue 读取，发给前端 ──────────────────────────────
        try:
            full_content = ""
            while True:
                try:
                    chunk_json = await asyncio.wait_for(queue.get(), timeout=55.0)
                except asyncio.TimeoutError:
                    # 发送 keep-alive ping 防止代理超时断连
                    yield f"data: {json.dumps({'kind': 'ping'})}\n\n"
                    continue

                if chunk_json is None:  # 后台 Task 已完成
                    break

                chunk_data = json.loads(chunk_json)
                kind = chunk_data.get("kind", "")

                if kind == MessageKind.STREAM_DELTA:
                    full_content += chunk_data.get("content", "")
                    chunk_data["type"] = "text"
                elif kind == MessageKind.THINKING:
                    chunk_data["type"] = "thinking"
                elif kind == MessageKind.SESSION_CREATED:
                    chunk_data["type"] = "session_created"
                    init_session_id = chunk_data.get("sessionId") or chunk_data.get("newSessionId")
                    if init_session_id:
                        logger.info(f"[CodeAgentService] SDK session created: {init_session_id}")
                        if existing.session_id != init_session_id:
                            await self.mapper.update_conversation_session_id(conversation_id, init_session_id)
                            existing.session_id = init_session_id
                    chunk_data["conversation_id"] = conversation_id
                elif kind == MessageKind.COMPLETE:
                    chunk_data["type"] = "done"
                    chunk_data["conversation_id"] = conversation_id
                elif kind == MessageKind.ERROR:
                    chunk_data["type"] = "error"
                elif kind == MessageKind.TOOL_USE:
                    chunk_data["type"] = "tool_use"
                    logger.info(f"[CodeAgentService] Tool use: {chunk_data.get('toolName')}")
                elif kind == MessageKind.PERMISSION_REQUEST:
                    chunk_data["type"] = "permission_request"
                    logger.info(f"[CodeAgentService] Permission request: {chunk_data.get('toolName')}")
                elif kind == MessageKind.USER_QUESTION_REQUEST:
                    chunk_data["type"] = "user_question_request"
                    logger.info(f"[CodeAgentService] User question request: {chunk_data.get('requestId')}")
                elif kind == "skill_submitted":
                    chunk_data["type"] = "skill_submitted"
                    logger.info(f"[CodeAgentService] Skill submitted: task={chunk_data.get('taskId')}")

                yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"

        except (asyncio.CancelledError, GeneratorExit):
            # SSE 断流：后台 Task 继续运行，不取消
            logger.warning(f"[CodeAgentService] SSE disconnected for {conversation_id}, background task continues")
        except Exception as e:
            logger.error(f"[CodeAgentService] SSE generator error for {conversation_id}: {e}")
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

    async def confirm_permission(self, session_id: str, request_id: Optional[str] = None):
        """确认权限请求 — 通过 session_id 找到持有该 session 的 Agent"""
        agent = find_agent_by_session(session_id) or get_code_agent()
        await agent.confirm_permission(session_id, request_id)

    async def cancel_permission(self, session_id: str, request_id: Optional[str] = None):
        """取消权限请求 — 通过 session_id 找到持有该 session 的 Agent"""
        agent = find_agent_by_session(session_id) or get_code_agent()
        await agent.cancel_permission(session_id, request_id)

    async def answer_user_question(self, session_id: str, request_id: str, answers: dict):
        """提交 AskUserQuestion 的前端确认答案。"""
        agent = find_agent_by_session(session_id) or get_code_agent()
        await agent.answer_user_question(session_id, request_id, answers)

    async def cancel_user_question(self, session_id: str, request_id: str):
        """取消 AskUserQuestion 的前端确认。"""
        agent = find_agent_by_session(session_id) or get_code_agent()
        await agent.cancel_user_question(session_id, request_id)

    async def interrupt_session(self, session_id: str) -> bool:
        """中断会话"""
        agent = find_agent_by_session(session_id) or get_code_agent()
        return await agent.interrupt(session_id)

    @handle_service_exception
    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> ConversationInfo:
        """创建新会话"""
        if not user_id:
            raise ValidationError(detail="user_id is required")

        conversation = await self.mapper.create_conversation(
            user_id=user_id, title=title, project_id=project_id
        )

        return ConversationInfo(
            conversation_id=conversation.conversation_id,
            user_id=conversation.user_id,
            project_id=conversation.project_id,
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
        offset: int = 0,
        project_id: Optional[str] = None
    ) -> List[ConversationInfo]:
        """获取用户的会话列表"""
        if not user_id:
            raise ValidationError(detail="user_id is required")
        return await self.mapper.get_conversations_by_user(
            user_id, limit, offset, project_id
        )

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
        """删除会话（同时清理 SDK jsonl 文件和 agent client）"""
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)

        if user_id and conversation.user_id != user_id:
            raise ValidationError(detail="无权删除此会话")

        sdk_session_id = conversation.session_id
        project_id = conversation.project_id

        # 1. 清理 agent 中的 client 和映射
        code_agent = self._get_agent_for_project(project_id)
        if sdk_session_id:
            await code_agent.close_client(sdk_session_id)
            code_agent._session_conversation_map.pop(sdk_session_id, None)
            if hasattr(code_agent, '_dead_sessions'):
                code_agent._dead_sessions.discard(sdk_session_id)

            # 清理 _tool_task_map 中属于该 session 的条目
            code_agent._tool_task_map = {
                k: v for k, v in code_agent._tool_task_map.items()
                if not k.startswith(sdk_session_id)
            }

        # 清理 SkillTaskManager 内存中属于该会话的任务
        try:
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            task_manager = get_skill_task_manager()
            for task in task_manager.list_tasks(conversation_id=conversation_id):
                # 取消后台 watcher
                watcher = code_agent._bg_watchers.pop(task.task_id, None)
                if watcher and not watcher.done():
                    watcher.cancel()
                # 清理内存中的任务
                task_manager._tasks.pop(task.task_id, None)
        except Exception as e:
            logger.warning(f"[CodeAgentService] Failed to cleanup skill tasks for conversation {conversation_id}: {e}")

        # 2. 删除 SDK 本地 jsonl 会话文件及空目录
        if sdk_session_id:
            try:
                home_dir = Path.home()
                # SDK jsonl 路径规则：~/.claude/projects/-<encoded_path>/<session_id>.jsonl
                # encoded_path: 将项目 base_dir 的 / 替换为 -，前面加 -
                if project_id:
                    config = get_project_config(project_id)
                    if config and config.base_dir:
                        encoded = str(config.base_dir).replace("/", "-")
                        project_dir = home_dir / ".claude" / "projects" / encoded
                        jsonl_path = project_dir / f"{sdk_session_id}.jsonl"
                        logger.info(f"[CodeAgentService] Trying to delete jsonl: {jsonl_path} (exists={jsonl_path.exists()})")
                        if jsonl_path.exists():
                            jsonl_path.unlink()
                            logger.info(f"[CodeAgentService] Deleted jsonl: {jsonl_path}")

                        # 清理以 session_id 命名的子目录（SDK 有时会创建此类目录）
                        session_dir = project_dir / sdk_session_id
                        if session_dir.is_dir():
                            import shutil
                            shutil.rmtree(session_dir, ignore_errors=True)
                            logger.info(f"[CodeAgentService] Deleted session dir: {session_dir}")

                        # 如果项目目录为空则删除
                        try:
                            if project_dir.is_dir() and not any(project_dir.iterdir()):
                                project_dir.rmdir()
                                logger.info(f"[CodeAgentService] Deleted empty project dir: {project_dir}")
                        except Exception:
                            pass
                    else:
                        logger.warning(f"[CodeAgentService] No project config for project_id={project_id}, cannot locate jsonl")
                else:
                    logger.warning(f"[CodeAgentService] No project_id for conversation {conversation_id}, cannot locate jsonl")
            except Exception as e:
                logger.warning(f"[CodeAgentService] Failed to delete jsonl for session {sdk_session_id}: {e}")
        else:
            logger.info(f"[CodeAgentService] No sdk_session_id for conversation {conversation_id}, skipping jsonl cleanup")

        # 3. 删除 DB 记录
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

    @handle_service_exception
    async def export_conversation(
        self,
        conversation_id: str,
        user_id: Optional[int] = None,
        fmt: str = "markdown",
    ) -> Tuple[str, str, str]:
        """导出会话内容

        使用与前端 getConversationDetail 相同的数据源（_parse_jsonl_messages），
        确保导出内容与用户在聊天界面看到的一致。

        Args:
            conversation_id: 会话ID
            user_id: 用户ID（用于权限校验）
            fmt: 导出格式 "markdown" | "json" | "html"

        Returns:
            (渲染内容, MIME类型, 建议文件名)
        """
        from src.server_agent.service.clinical_tools.JsonlSessionService import get_session_service
        from src.server_agent.service.clinical_tools.export_renderer import (
            ExportConversation,
            ExportMessage,
            render_conversation,
            get_mime_type,
            get_file_extension,
        )

        # 1. 校验权限
        conversation = await self.mapper.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(resource_type="conversation", resource_id=conversation_id)

        if user_id and conversation.user_id != user_id:
            raise ValidationError(detail="无权导出此会话")

        # 2. 获取全量消息（与前端 getConversationDetail 使用相同的数据源）
        session_id = conversation.session_id
        logger.info(f"[export] conversation_id={conversation_id}, session_id={session_id}")
        if not session_id:
            # 无 session_id 的空会话
            export_conv = ExportConversation(
                conversation_id=conversation_id,
                title=conversation.title,
                project_id=conversation.project_id,
                created_at=conversation.created_at.isoformat() if conversation.created_at else None,
                updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
            )
            content = render_conversation(export_conv, [], fmt)
        else:
            session_service = get_session_service()
            jsonl_messages, _, _ = await session_service.get_session_messages(
                session_id=session_id,
                project_path=None,
                limit=None,  # 获取全部消息
                offset=0,
            )
            logger.info(f"[export] jsonl_messages count={len(jsonl_messages)}")

            # 3. 使用与前端相同的解析逻辑（_parse_jsonl_messages）
            #    这里需要调用 Controller 的解析方法，但 Service 层不应依赖 Controller
            #    所以将解析逻辑提取为独立函数供 Service 调用
            from src.server_agent.service.clinical_tools.message_parser import parse_jsonl_messages
            parsed_messages = parse_jsonl_messages(jsonl_messages, conversation_id)
            logger.info(f"[export] parsed_messages count={len(parsed_messages)}")

            # 4. 转换为 ExportMessage 并渲染
            export_messages = [ExportMessage.from_message_response(m) for m in parsed_messages]
            export_conv = ExportConversation(
                conversation_id=conversation_id,
                title=conversation.title,
                project_id=conversation.project_id,
                created_at=conversation.created_at.isoformat() if conversation.created_at else None,
                updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
            )
            content = render_conversation(export_conv, export_messages, fmt)

        # 5. 生成安全文件名（包含用户ID和导出时间戳）
        safe_title = (conversation.title or "conversation").replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")
        user_tag = f"uid{user_id}" if user_id else "unknown"
        export_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{safe_title}_{user_tag}_{export_ts}{get_file_extension(fmt)}"
        mime = get_mime_type(fmt)

        return content, mime, filename

    async def close(self):
        """关闭资源"""
        try:
            await self.mapper.close()
        except Exception as e:
            logger.error(f"Error closing service resources: {e}")
