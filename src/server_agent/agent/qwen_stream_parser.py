"""
Qwen Code 流式 JSON 解析器 - 解析流式 JSON 输出的事件
"""
import json
import logging
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QwenStreamEvent:
    """Qwen 流式事件基类"""
    type: str
    uuid: str
    session_id: str
    parent_tool_use_id: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class SystemEvent(QwenStreamEvent):
    """系统初始化事件"""
    subtype: str = ""
    cwd: str = ""
    tools: list = field(default_factory=list)
    mcp_servers: list = field(default_factory=list)
    model: str = ""
    permission_mode: str = ""
    slash_commands: list = field(default_factory=list)
    qwen_code_version: str = ""
    agents: list = field(default_factory=list)


@dataclass
class StreamEvent(QwenStreamEvent):
    """流式事件"""
    event_type: str = ""
    event_data: Optional[Dict[str, Any]] = None


@dataclass
class MessageStartEvent(StreamEvent):
    """消息开始事件"""
    message_id: str = ""
    role: str = ""
    model: str = ""


@dataclass
class ContentBlockDeltaEvent(StreamEvent):
    """内容块增量事件"""
    index: int = 0
    delta_type: str = ""
    text: str = ""


@dataclass
class ContentBlockStopEvent(StreamEvent):
    """内容块停止事件"""
    index: int = 0


@dataclass
class MessageStopEvent(StreamEvent):
    """消息停止事件"""


@dataclass
class AssistantEvent(QwenStreamEvent):
    """助手消息事件"""
    message: Optional[Dict[str, Any]] = None
    stop_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


@dataclass
class ResultEvent(QwenStreamEvent):
    """结果事件"""
    subtype: str = ""
    is_error: bool = False
    duration_ms: int = 0
    duration_api_ms: int = 0
    num_turns: int = 0
    result: str = ""
    usage: Optional[Dict[str, Any]] = None
    permission_denials: list = field(default_factory=list)


class QwenStreamParser:
    """Qwen 流式 JSON 解析器"""

    def __init__(self):
        self._buffer = ""
        self._events = []

    def parse_line(self, line: str) -> Optional[QwenStreamEvent]:
        """
        解析单行 JSON 数据

        Args:
            line: JSON 字符串

        Returns:
            解析后的事件对象，如果解析失败返回 None
        """
        try:
            data = json.loads(line.strip())
            event_type = data.get("type", "")

            # 基础字段
            uuid = data.get("uuid", "")
            session_id = data.get("session_id", "")
            parent_tool_use_id = data.get("parent_tool_use_id")

            if event_type == "system":
                return SystemEvent(
                    type=event_type,
                    uuid=uuid,
                    session_id=session_id,
                    parent_tool_use_id=parent_tool_use_id,
                    raw_data=data,
                    subtype=data.get("subtype", ""),
                    cwd=data.get("cwd", ""),
                    tools=data.get("tools", []),
                    mcp_servers=data.get("mcp_servers", []),
                    model=data.get("model", ""),
                    permission_mode=data.get("permission_mode", ""),
                    slash_commands=data.get("slash_commands", []),
                    qwen_code_version=data.get("qwen_code_version", ""),
                    agents=data.get("agents", [])
                )

            elif event_type == "stream_event":
                event = data.get("event", {})
                inner_event_type = event.get("type", "")

                if inner_event_type == "message_start":
                    message = event.get("message", {})
                    return MessageStartEvent(
                        type=event_type,
                        uuid=uuid,
                        session_id=session_id,
                        parent_tool_use_id=parent_tool_use_id,
                        raw_data=data,
                        event_type=inner_event_type,
                        event_data=event,
                        message_id=message.get("id", ""),
                        role=message.get("role", ""),
                        model=message.get("model", "")
                    )

                elif inner_event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    return ContentBlockDeltaEvent(
                        type=event_type,
                        uuid=uuid,
                        session_id=session_id,
                        parent_tool_use_id=parent_tool_use_id,
                        raw_data=data,
                        event_type=inner_event_type,
                        event_data=event,
                        index=event.get("index", 0),
                        delta_type=delta.get("type", ""),
                        text=delta.get("text", "")
                    )

                elif inner_event_type == "content_block_stop":
                    return ContentBlockStopEvent(
                        type=event_type,
                        uuid=uuid,
                        session_id=session_id,
                        parent_tool_use_id=parent_tool_use_id,
                        raw_data=data,
                        event_type=inner_event_type,
                        event_data=event,
                        index=event.get("index", 0)
                    )

                elif inner_event_type == "message_stop":
                    return MessageStopEvent(
                        type=event_type,
                        uuid=uuid,
                        session_id=session_id,
                        parent_tool_use_id=parent_tool_use_id,
                        raw_data=data,
                        event_type=inner_event_type,
                        event_data=event
                    )

            elif event_type == "assistant":
                message = data.get("message", {})
                return AssistantEvent(
                    type=event_type,
                    uuid=uuid,
                    session_id=session_id,
                    parent_tool_use_id=parent_tool_use_id,
                    raw_data=data,
                    message=message,
                    stop_reason=message.get("stop_reason"),
                    usage=message.get("usage")
                )

            elif event_type == "result":
                return ResultEvent(
                    type=event_type,
                    uuid=uuid,
                    session_id=session_id,
                    parent_tool_use_id=parent_tool_use_id,
                    raw_data=data,
                    subtype=data.get("subtype", ""),
                    is_error=data.get("is_error", False),
                    duration_ms=data.get("duration_ms", 0),
                    duration_api_ms=data.get("duration_api_ms", 0),
                    num_turns=data.get("num_turns", 0),
                    result=data.get("result", ""),
                    usage=data.get("usage", {}),
                    permission_denials=data.get("permission_denials", [])
                )

            # 未知事件类型
            logger.warning(f"Unknown event type: {event_type}")
            return QwenStreamEvent(
                type=event_type,
                uuid=uuid,
                session_id=session_id,
                parent_tool_use_id=parent_tool_use_id,
                raw_data=data
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON line: {e}, line: {line[:100]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None


async def parse_qwen_stream(
    stream: AsyncGenerator[str, None],
    on_event: Callable[[QwenStreamEvent], None],
    on_text: Callable[[str], None],
    on_complete: Callable[[str], None],
    on_error: Callable[[str], None]
) -> str:
    """
    解析 Qwen 流式输出

    Args:
        stream: 流式生成器
        on_event: 事件回调函数
        on_text: 文本回调函数
        on_complete: 完成回调函数
        on_error: 错误回调函数

    Returns:
        完整的文本内容
    """
    parser = QwenStreamParser()
    full_text = ""
    current_message_id = None

    try:
        async for line in stream:
            line = line.strip()
            if not line:
                continue

            event = parser.parse_line(line)
            if not event:
                continue

            # 调用事件回调
            try:
                on_event(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

            # 处理不同类型的事件
            if isinstance(event, ContentBlockDeltaEvent):
                if event.delta_type == "text_delta":
                    text = event.text
                    full_text += text
                    try:
                        on_text(text)
                    except Exception as e:
                        logger.error(f"Error in text callback: {e}")

            elif isinstance(event, MessageStartEvent):
                current_message_id = event.message_id
                logger.info(f"Message started: {current_message_id}")

            elif isinstance(event, MessageStopEvent):
                logger.info(f"Message stopped: {current_message_id}")

            elif isinstance(event, ResultEvent):
                logger.info(f"Result received: duration={event.duration_ms}ms, is_error={event.is_error}")
                if event.is_error:
                    on_error(f"Qwen Code error: {event.result}")

            elif isinstance(event, SystemEvent):
                logger.info(f"System initialized: model={event.model}, version={event.qwen_code_version}")

    except Exception as e:
        error_msg = f"Stream parsing error: {str(e)}"
        logger.error(error_msg)
        on_error(error_msg)

    # 调用完成回调
    try:
        on_complete(full_text)
    except Exception as e:
        logger.error(f"Error in complete callback: {e}")

    return full_text
