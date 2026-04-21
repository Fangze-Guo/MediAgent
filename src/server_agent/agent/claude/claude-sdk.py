"""
Claude SDK Integration

使用 claude_agent_sdk 包

核心功能:
- 直接 SDK 集成，无需子进程
- 会话管理，利用 asyncio 保证实时的中断能力
- 消息流式推送
- 权限请求处理（解决多用户并发冲突）
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from claude_agent_sdk import (
    ClaudeAgentOptions,
    query,
)

logger = logging.getLogger(__name__)

class MessageKind(Enum):
    """消息类型枚举"""
    TEXT = "text"
    STREAM_DELTA = "stream_delta"
    STREAM_END = "stream_end"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    ERROR = "error"
    COMPLETE = "complete"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_CANCELLED = "permission_cancelled"
    SESSION_CREATED = "session_created"
    STATUS = "status"


@dataclass
class NormalizedMessage:
    """标准化消息格式"""
    kind: str
    content: Optional[str] = None
    session_id: Optional[str] = None
    provider: str = "claude"
    role: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_id: Optional[str] = None
    tool_result: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    reason: Optional[str] = None
    exit_code: Optional[int] = None
    is_error: bool = False
    is_new_session: bool = False
    token_budget: Optional[Dict[str, int]] = None
    text: Optional[str] = None
    subagent_tools: Optional[List[str]] = None
    subagent_state: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 JSON 序列化"""
        result: Dict[str, Any] = {"kind": self.kind, "provider": self.provider}
        if self.content is not None:
            result["content"] = self.content
        if self.session_id is not None:
            result["session_id"] = self.session_id
        if self.role is not None:
            result["role"] = self.role
        if self.tool_name is not None:
            result["toolName"] = self.tool_name
        if self.tool_input is not None:
            result["toolInput"] = self.tool_input
        if self.tool_id is not None:
            result["toolId"] = self.tool_id
        if self.tool_result is not None:
            result["toolResult"] = self.tool_result
        if self.request_id is not None:
            result["requestId"] = self.request_id
        if self.reason is not None:
            result["reason"] = self.reason
        if self.exit_code is not None:
            result["exitCode"] = self.exit_code
        if self.is_error:
            result["isError"] = self.is_error
        if self.is_new_session:
            result["isNewSession"] = self.is_new_session
        if self.token_budget is not None:
            result["tokenBudget"] = self.token_budget
        if self.text is not None:
            result["text"] = self.text
        if self.subagent_tools is not None:
            result["subagentTools"] = self.subagent_tools
        if self.subagent_state is not None:
            result["subagentState"] = self.subagent_state
        return result


@dataclass
class SessionState:
    """会话状态"""
    session_id: str
    status: str = "active"  # active, aborted, completed
    start_time: float = 0.0
    interrupt_event: Optional[asyncio.Event] = None  # 中断信号 Event


class PendingApproval:
    """待批准的权限请求"""

    def __init__(self, request_id: str, tool_name: str, tool_input: Dict[str, Any]):
        self.request_id = request_id
        self.tool_name = tool_name
        self.tool_input = tool_input
        self._decision: Optional[Dict[str, Any]] = None
        self._event = asyncio.Event()

    async def wait_for_decision(self, timeout_ms: int = 55000) -> Optional[Dict[str, Any]]:
        """等待用户决策"""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_ms / 1000)
            return self._decision
        except asyncio.TimeoutError:
            return None

    def resolve(self, decision: Dict[str, Any]):
        """设置决策结果"""
        self._decision = decision
        self._event.set()


class ClaudeSDK:
    """
    Claude SDK 集成类

    模仿 JavaScript 版本的 claude-sdk.js，实现:
    - 直接 SDK 调用（无需子进程）
    - 会话管理
    - 权限请求处理
    - 消息流式推送
    """

    def __init__(
        self,
        cli_path: Optional[str] = None,
    ):
        """
        初始化 Claude SDK

        Args:
            cli_path: Claude CLI 可执行文件路径（可选，默认使用 PATH 中的 claude）
        """

        self._cli_path = cli_path

        # 活动会话映射
        self._active_sessions: Dict[str, SessionState] = {}

        # 待批准的权限请求
        self._pending_approvals: Dict[str, PendingApproval] = {}

        # 工具白名单/黑名单配置
        self._allowed_tools: List[str] = []
        self._disallowed_tools: List[str] = []

        # 权限模式: default, bypassPermissions, plan
        self._permission_mode: str = "default"

        # 超时配置（毫秒）
        self._tool_approval_timeout_ms: int = 55000

    def set_tool_permissions(
        self,
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        permission_mode: str = "default",
    ):
        """
        设置工具权限

        Args:
            allowed_tools: 允许的工具列表
            disallowed_tools: 禁止的工具列表
            permission_mode: 权限模式 (default/acceptEdits/plan/bypassPermissions/dontAsk/auto)
        """
        if allowed_tools is not None:
            self._allowed_tools = allowed_tools
        if disallowed_tools is not None:
            self._disallowed_tools = disallowed_tools
        self._permission_mode = permission_mode

    def _matches_tool_permission(self, entry: str, tool_name: str, tool_input: Any) -> bool:
        """
        检查工具是否匹配权限规则

        Args:
            entry: 权限条目（如 "Bash" 或 "Bash(npm:*")
            tool_name: 工具名称
            tool_input: 工具输入参数

        Returns:
            是否匹配
        """
        if entry == tool_name:
            return True

        # 处理 Bash(command:*) 简写
        bash_match = re.match(r"^Bash\((.+):\*\)$", entry)
        if tool_name == "Bash" and bash_match:
            allowed_prefix = bash_match.group(1)
            command = ""
            if isinstance(tool_input, str):
                command = tool_input.strip()
            elif isinstance(tool_input, dict) and "command" in tool_input:
                command = tool_input["command"].strip()

            if command and command.startswith(allowed_prefix):
                return True

        return False

    def _create_request_id(self) -> str:
        """生成请求 ID"""
        return str(uuid.uuid4())

    async def _wait_for_tool_approval(
        self,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        timeout_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        等待工具使用批准

        Args:
            request_id: 请求 ID
            tool_name: 工具名称
            tool_input: 工具输入
            timeout_ms: 超时时间（毫秒）

        Returns:
            决策结果
        """
        timeout_ms = timeout_ms or self._tool_approval_timeout_ms

        approval = PendingApproval(request_id, tool_name, tool_input)
        self._pending_approvals[request_id] = approval

        try:
            decision = await approval.wait_for_decision(timeout_ms)
            return decision
        finally:
            self._pending_approvals.pop(request_id, None)

    def resolve_tool_approval(self, request_id: str, decision: Dict[str, Any]):
        """
        解析工具批准请求（由外部调用，如 WebSocket 处理器）

        Args:
            request_id: 请求 ID
            decision: 决策 {"allow": bool, ...}
        """
        if request_id in self._pending_approvals:
            self._pending_approvals[request_id].resolve(decision)

    def _should_allow_tool(self, tool_name: str, tool_input: Any) -> bool:
        """
        检查工具是否应该被允许

        Args:
            tool_name: 工具名称
            tool_input: 工具输入

        Returns:
            是否允许
        """
        # bypassPermissions 模式直接允许
        if self._permission_mode == "bypassPermissions":
            return True

        # 检查黑名单
        for entry in self._disallowed_tools:
            if self._matches_tool_permission(entry, tool_name, tool_input):
                return False

        # 检查白名单
        for entry in self._allowed_tools:
            if self._matches_tool_permission(entry, tool_name, tool_input):
                return True

        # 白名单为空时，不拦截，交由用户决策
        if not self._allowed_tools:
            return True
        return False

    def _create_message(self, kind: str, **kwargs) -> NormalizedMessage:
        """创建标准化消息"""
        return NormalizedMessage(kind=kind, **kwargs)

    def _normalize_message(self, message: Any, session_id: Optional[str]) -> List[NormalizedMessage]:
        """
        标准化 SDK 消息

        Args:
            message: SDK 返回的原始消息
            session_id: 会话 ID

        Returns:
            标准化消息列表
        """
        messages: List[NormalizedMessage] = []
        provider = "claude"

        # 获取消息类型名称
        msg_type_name = type(message).__name__

        # 处理 StreamEvent - 流式内容块
        if msg_type_name == "StreamEvent":
            event = message.event
            event_type = event.get("type", "")

            if event_type == "content_block_delta":
                delta = event.get("delta", {})
                delta_type = delta.get("type", "")

                if delta_type == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        messages.append(self._create_message(
                            kind=MessageKind.STREAM_DELTA.value,
                            content=text,
                            session_id=session_id,
                            provider=provider,
                        ))

                elif delta_type == "thinking_delta":
                    thinking = delta.get("thinking", "")
                    if thinking:
                        messages.append(self._create_message(
                            kind=MessageKind.STREAM_DELTA.value,
                            content=thinking,
                            session_id=session_id,
                            provider=provider,
                            text="thinking",
                        ))

            elif event_type == "content_block_stop":
                messages.append(self._create_message(
                    kind=MessageKind.STREAM_END.value,
                    session_id=session_id,
                    provider=provider,
                ))

        # 处理 AssistantMessage - 助手消息
        elif msg_type_name == "AssistantMessage":
            for block in message.content:
                block_type_name = type(block).__name__

                if block_type_name == "TextBlock":
                    if block.text:
                        messages.append(self._create_message(
                            kind=MessageKind.TEXT.value,
                            content=block.text,
                            session_id=session_id,
                            provider=provider,
                            role="assistant",
                        ))

                elif block_type_name == "ThinkingBlock":
                    if block.thinking:
                        messages.append(self._create_message(
                            kind=MessageKind.THINKING.value,
                            content=block.thinking,
                            session_id=session_id,
                            provider=provider,
                        ))

                elif block_type_name == "ToolUseBlock":
                    messages.append(self._create_message(
                        kind=MessageKind.TOOL_USE.value,
                        session_id=session_id,
                        provider=provider,
                        tool_name=block.name,
                        tool_input=block.input,
                        tool_id=block.id,
                    ))

        # 处理 ResultMessage - 结果消息
        elif msg_type_name == "ResultMessage":
            # 如果有结果文本，发送文本消息
            if message.result:
                messages.append(self._create_message(
                    kind=MessageKind.TEXT.value,
                    content=message.result,
                    session_id=session_id,
                    provider=provider,
                    role="assistant",
                ))

            # 发送完成消息
            messages.append(self._create_message(
                kind=MessageKind.COMPLETE.value,
                exit_code=0 if not message.is_error else 1,
                session_id=session_id,
                provider=provider,
            ))

        # 处理 SystemMessage - 系统消息
        elif msg_type_name == "SystemMessage":
            subtype = message.subtype

            if subtype == "session_created":
                data = message.data
                new_session_id = data.get("session_id", session_id)
                messages.append(self._create_message(
                    kind=MessageKind.SESSION_CREATED.value,
                    session_id=new_session_id,
                    is_new_session=data.get("is_new_session", False),
                    provider=provider,
                ))

            elif subtype == "permission_request":
                data = message.data
                messages.append(self._create_message(
                    kind=MessageKind.PERMISSION_REQUEST.value,
                    session_id=session_id,
                    provider=provider,
                    request_id=data.get("request_id", ""),
                    tool_name=data.get("tool_name", ""),
                    tool_input=data.get("tool_input", {}),
                ))

        return messages
    
    async def query(
            self,
            prompt: str,
            session_id: Optional[str] = None,
            model: str = "sonnet",
            cwd: Optional[str] = None,
            ws_callback: Optional[Callable[[NormalizedMessage], None]] = None,
            resume: Optional[str] = None,
        ) -> AsyncGenerator[NormalizedMessage, None]:
            """
            执行 Claude 查询（异步生成器）
            """
            # [修复] 妥善处理 resume 与 session_id 的关系，避免 KeyError
            captured_session_id = session_id or resume

            try:
                # 发送会话创建消息（如果是新会话）
                if not captured_session_id:
                    captured_session_id = str(uuid.uuid4())
                    yield self._create_message(
                        kind=MessageKind.SESSION_CREATED.value,
                        session_id=captured_session_id,
                        is_new_session=True,
                    )

                # 定义闭包拦截器
                async def can_use_tool_hook(tool_name: str, tool_input: Dict[str, Any], context: Any) -> Any:
                    if not self._should_allow_tool(tool_name, tool_input):
                        from claude_agent_sdk.types import PermissionResultDeny
                        return PermissionResultDeny(message=f"Tool {tool_name} is not allowed")

                    request_id = self._create_request_id()
                    msg = self._create_message(
                        kind=MessageKind.PERMISSION_REQUEST.value,
                        session_id=captured_session_id,
                        provider="claude",
                        request_id=request_id,
                        tool_name=tool_name,
                        tool_input=tool_input,
                    )
                    
                    if ws_callback:
                        if asyncio.iscoroutinefunction(ws_callback):
                            await ws_callback(msg)
                        else:
                            ws_callback(msg)

                    decision = await self._wait_for_tool_approval(
                        request_id, tool_name, tool_input, self._tool_approval_timeout_ms
                    )

                    if decision is None:
                        from claude_agent_sdk.types import PermissionResultDeny
                        return PermissionResultDeny(message="Approval timeout")
                    elif decision.get("allow"):
                        from claude_agent_sdk.types import PermissionResultAllow
                        return PermissionResultAllow()
                    else:
                        from claude_agent_sdk.types import PermissionResultDeny
                        return PermissionResultDeny(message=decision.get("reason", "Denied by user"))

                # 构建选项
                options = ClaudeAgentOptions(
                    permission_mode=self._permission_mode,
                    cwd=cwd,
                    cli_path=self._cli_path,
                    model=model,
                    can_use_tool=can_use_tool_hook,
                )

                # 恢复会话设置
                if resume:
                    options.resume = resume
                elif session_id:
                    options.session_id = session_id

                if self._allowed_tools or self._disallowed_tools:
                    options.allowed_tools = self._allowed_tools
                    options.disallowed_tools = self._disallowed_tools

                # 注册会话
                if captured_session_id not in self._active_sessions:
                    interrupt_event = asyncio.Event()
                    self._active_sessions[captured_session_id] = SessionState(
                        session_id=captured_session_id,
                        start_time=time.time(),
                        interrupt_event=interrupt_event,
                    )

                session_state = self._active_sessions[captured_session_id]
                interrupt_event = session_state.interrupt_event

                # 包装生成器
                async def run_query_stream():
                    async for message in query(prompt=prompt, options=options):
                        yield message

                stream_gen = run_query_stream()
                
                # [修复] 将 anext() 包装为标准协程，解决 create_task 报错问题
                async def _get_next_item():
                    return await anext(stream_gen)

                # [修复] 将中断监听移到循环外，只创建一次，极大降低性能开销
                interrupt_task = asyncio.create_task(interrupt_event.wait())
                
                try:
                    while True:
                        next_item_task = asyncio.create_task(_get_next_item())
                        
                        done, pending = await asyncio.wait(
                            [next_item_task, interrupt_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        if interrupt_task in done:
                            # 触发了中断
                            next_item_task.cancel()
                            # [修复] 显式关闭底层生成器，释放内存和网络资源
                            await stream_gen.aclose()
                            yield self._create_message(
                                kind=MessageKind.ERROR.value,
                                session_id=captured_session_id,
                                content="Session interrupted by user",
                                is_error=True,
                            )
                            return
                        else:
                            # 成功获取数据，不要 cancel interrupt_task，让它在下一轮循环继续监听
                            try:
                                message = next_item_task.result()
                            except StopAsyncIteration:
                                break # 正常结束

                            # 处理会话 ID 可能的更新
                            msg_session_id = getattr(message, 'session_id', None)
                            if msg_session_id and msg_session_id != captured_session_id:
                                # 同步更新 active_sessions 的注册键
                                if captured_session_id in self._active_sessions:
                                    state = self._active_sessions.pop(captured_session_id)
                                    state.session_id = msg_session_id
                                    self._active_sessions[msg_session_id] = state
                                captured_session_id = msg_session_id

                            # 标准化并推送消息
                            normalized_messages = self._normalize_message(message, captured_session_id)
                            for msg in normalized_messages:
                                if ws_callback:
                                    if asyncio.iscoroutinefunction(ws_callback):
                                        await ws_callback(msg)
                                    else:
                                        ws_callback(msg)
                                yield msg
                finally:
                    # 循环结束（或异常退出）后，清理挂起的中断监听任务
                    if not interrupt_task.done():
                        interrupt_task.cancel()

            except asyncio.CancelledError:
                logger.warning(f"Session {captured_session_id} task was cancelled")
                raise

            except Exception as e:
                logger.error(f"Claude SDK query error: {e}")
                yield self._create_message(
                    kind=MessageKind.ERROR.value,
                    session_id=captured_session_id,
                    content=str(e),
                    is_error=True,
                )

            finally:
                # 清理全局会话状态
                if captured_session_id in self._active_sessions:
                    self._active_sessions.pop(captured_session_id, None)

    async def interrupt(self, session_id: str) -> bool:
        """
        中断指定会话

        Args:
            session_id: 会话 ID

        Returns:
            是否成功中断
        """
        if session_id not in self._active_sessions:
            return False

        session_state = self._active_sessions[session_id]
        session_state.status = "aborted"
        
        # 触发中断事件，打断 query() 内部的 asyncio.wait
        if session_state.interrupt_event:
            session_state.interrupt_event.set()
            
        logger.info(f"Session {session_id} interrupted")
        return True

    def is_session_active(self, session_id: str) -> bool:
        """
        检查会话是否处于活跃状态

        Args:
            session_id: 会话 ID

        Returns:
            是否活跃
        """
        if session_id not in self._active_sessions:
            return False
        return self._active_sessions[session_id].status == "active"

    def get_active_sessions(self) -> List[str]:
        """
        获取所有活跃会话 ID

        Returns:
            活跃会话 ID 列表
        """
        return [
            sid for sid, state in self._active_sessions.items()
            if state.status == "active"
        ]


# 全局 SDK 实例
_sdk_instance: Optional[ClaudeSDK] = None


def get_sdk() -> ClaudeSDK:
    """获取全局 SDK 实例"""
    global _sdk_instance
    if _sdk_instance is None:
        _sdk_instance = ClaudeSDK()
    return _sdk_instance


async def query_claude(
    prompt: str,
    session_id: Optional[str] = None,
    model: str = "sonnet",
    cwd: Optional[str] = None,
    ws_callback: Optional[Callable[[NormalizedMessage], None]] = None,
    resume: Optional[str] = None,
) -> AsyncGenerator[NormalizedMessage, None]:
    """
    便捷函数：查询 Claude

    Args:
        prompt: 用户提示词
        session_id: 会话 ID
        model: 模型名称
        cwd: 工作目录
        ws_callback: WebSocket 回调
        resume: 恢复会话 ID

    Yields:
        标准化消息
    """
    sdk = get_sdk()
    async for msg in sdk.query(prompt, session_id, model, cwd, ws_callback, resume):
        yield msg