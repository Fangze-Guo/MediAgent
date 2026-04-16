"""
Qwen Code Agent - 使用 --resume 机制实现有状态对话
移除临时文件方案，完全依赖 Qwen 的 JSONL 文件管理上下文
"""
import json
import logging
from typing import AsyncGenerator, Optional

from src.server_agent.agent.qwen_session_manager import QwenSessionManager

logger = logging.getLogger(__name__)


class QwenAgent:
    """Qwen Code Agent类 - 使用 --resume 机制"""

    def __init__(self, qwen_path: str = "qwen", timeout: int = 120):
        """
        初始化Qwen Code Agent

        Args:
            qwen_path: qwen命令的路径，默认为"qwen"（假设在PATH中）
            timeout: 命令执行超时时间（秒）
        """
        self.session_manager = QwenSessionManager(qwen_path)
        self.timeout = timeout

    async def _execute_qwen(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        timeout: Optional[int] = None,
        is_file: bool = False,
        use_stream_json: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        异步执行qwen命令并流式输出结果

        Args:
            prompt: 用户提示词（如果是is_file=True，则为文件路径）
            session_id: 会话ID（UUID格式，用于管理历史对话）
            timeout: 超时时间（秒），如果为None则使用实例默认值
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Yields:
            流式输出的文本片段
        """
        timeout = timeout or self.timeout

        try:
            session_info = f" with session_id: {session_id}" if session_id else " (new session)"
            file_info = f" from file: {prompt}" if is_file else f", prompt length: {len(prompt)}"
            logger.info(f"[QwenAgent] Sending message to Qwen Code{session_info}{file_info}")

            # 使用会话管理器发送消息
            chunk_count = 0
            if session_id:
                logger.info(f"[QwenAgent] Resuming session with UUID: {session_id}")
                async for chunk in self.session_manager.send_message(session_id, prompt, is_file=is_file, use_stream_json=use_stream_json):
                    chunk_count += 1
                    if chunk_count == 1:
                        logger.info(f"[QwenAgent] First chunk received")
                    if chunk_count % 10 == 0:
                        logger.info(f"[QwenAgent] Received {chunk_count} chunks so far")
                    yield chunk
            else:
                # 新会话
                logger.info(f"[QwenAgent] Creating new session")
                async for chunk in self.session_manager.send_message(None, prompt, is_file=is_file, use_stream_json=use_stream_json):
                    chunk_count += 1
                    if chunk_count == 1:
                        logger.info(f"[QwenAgent] First chunk received")
                    if chunk_count % 10 == 0:
                        logger.info(f"[QwenAgent] Received {chunk_count} chunks so far")
                    yield chunk

            logger.info(f"[QwenAgent] Message sending completed, total chunks: {chunk_count}")

        except Exception as e:
            logger.error(f"[QwenAgent] Error executing Qwen Code: {e}")
            raise

    async def stream_chat(
        self,
        current_message: str,
        session_id: Optional[str] = None,
        is_file: bool = False,
        use_stream_json: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        流式对话（适合前端SSE流式响应）

        Args:
            current_message: 当前用户消息（如果是is_file=True，则为文件路径）
            session_id: 会话ID，用于管理历史对话
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Yields:
            每个输出片段的JSON字符串（SSE格式）
        """
        # 使用当前消息和session_id执行qwen命令
        # 历史消息管理由qwen通过session_id和JSONL文件处理

        full_content = ""
        try:
            if use_stream_json:
                # 使用流式 JSON 模式：需要解析 JSON 输出
                async for chunk in self._execute_qwen(current_message, session_id, is_file=is_file, use_stream_json=True):
                    try:
                        # 尝试解析 JSON
                        event_data = json.loads(chunk.strip())

                        # 处理不同的事件类型
                        if event_data.get("type") == "stream_event":
                            # 流式事件
                            event = event_data.get("event", {})
                            event_type = event.get("type", "")

                            if event_type == "content_block_delta":
                                # 文本增量事件
                                delta = event.get("delta", {})
                                text = delta.get("text", "")
                                if text:
                                    full_content += text
                                    # 返回SSE格式的数据
                                    data = {
                                        "content": text,
                                        "full_content": full_content,
                                        "done": False
                                    }
                                    yield json.dumps(data, ensure_ascii=False)
                            elif event_type == "message_stop":
                                # 消息结束
                                final_data = {
                                    "content": "",
                                    "full_content": full_content,
                                    "done": True
                                }
                                yield json.dumps(final_data, ensure_ascii=False)
                            elif event_type == "assistant":
                                # 助手消息（包含完整内容）
                                message = event.get("message", {})
                                content_blocks = message.get("content", [])
                                text_content = ""
                                for block in content_blocks:
                                    if block.get("type") == "text":
                                        text_content += block.get("text", "")
                                if text_content:
                                    full_content = text_content
                                    final_data = {
                                        "content": "",
                                        "full_content": full_content,
                                        "done": True
                                    }
                                    yield json.dumps(final_data, ensure_ascii=False)

                        elif event_data.get("type") == "result":
                            # 最终结果
                            result_text = event_data.get("result", "")
                            if result_text:
                                full_content = result_text
                            final_data = {
                                "content": "",
                                "full_content": full_content,
                                "done": True
                            }
                            yield json.dumps(final_data, ensure_ascii=False)

                        elif event_data.get("type") == "assistant":
                            # 助手消息
                            message = event_data.get("message", {})
                            content_blocks = message.get("content", [])
                            text_content = ""
                            for block in content_blocks:
                                if block.get("type") == "text":
                                    text_content += block.get("text", "")
                            if text_content:
                                full_content = text_content
                                final_data = {
                                    "content": "",
                                    "full_content": full_content,
                                    "done": True
                                }
                                yield json.dumps(final_data, ensure_ascii=False)

                    except json.JSONDecodeError:
                        # 如果不是 JSON，当作普通文本处理
                        full_content += chunk
                        data = {
                            "content": chunk,
                            "full_content": full_content,
                            "done": False
                        }
                        yield json.dumps(data, ensure_ascii=False)

            else:
                # 传统模式：直接返回文本
                async for chunk in self._execute_qwen(current_message, session_id, is_file=is_file, use_stream_json=False):
                    full_content += chunk
                    # 返回SSE格式的数据
                    data = {
                        "content": chunk,
                        "full_content": full_content,
                        "done": False
                    }
                    yield json.dumps(data, ensure_ascii=False)

                # 发送完成标记
                final_data = {
                    "content": "",
                    "full_content": full_content,
                    "done": True
                }
                yield json.dumps(final_data, ensure_ascii=False)

        except Exception as e:
            # 发送错误信息
            error_data = {
                "content": "",
                "full_content": "",
                "done": True,
                "error": str(e)
            }
            yield json.dumps(error_data, ensure_ascii=False)

    async def chat(
        self,
        current_message: str,
        session_id: Optional[str] = None,
        is_file: bool = False,
        use_stream_json: bool = True
    ) -> str:
        """
        同步对话（非流式，用于测试）

        Args:
            current_message: 当前用户消息（如果是is_file=True，则为文件路径）
            session_id: 会话ID，用于管理历史对话
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Returns:
            AI的完整回复
        """
        full_content = ""
        async for chunk in self._execute_qwen(current_message, session_id, is_file=is_file, use_stream_json=use_stream_json):
            full_content += chunk

        return full_content

    async def close_session(self, session_id: str):
        """
        关闭指定会话（仅标记状态，不删除Qwen的JSONL文件）

        Args:
            session_id: 会话ID
        """
        # 注意：不再删除Qwen的JSONL文件，因为由审计服务管理会话状态
        logger.info(f"Session closed (status marked): {session_id}")

    async def close_all_sessions(self):
        """关闭所有会话（仅标记状态，不删除Qwen的JSONL文件）"""
        # 注意：不再删除Qwen的JSONL文件，因为由审计服务管理会话状态
        logger.info("All sessions closed (status marked)")
