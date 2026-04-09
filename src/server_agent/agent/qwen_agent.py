"""
Qwen Code Agent - 通过临时文件传递历史记录调用Qwen Code
提供流式和同步的对话功能
"""
import json
import logging
from typing import AsyncGenerator

from src.server_agent.agent.qwen_session_manager import QwenSessionManager

logger = logging.getLogger(__name__)


class QwenAgent:
    """Qwen Code Agent类 - 使用会话管理器"""

    def __init__(self, qwen_path: str = "qwen", timeout: int = 120, history_provider = None):
        """
        初始化Qwen Code Agent

        Args:
            qwen_path: qwen命令的路径，默认为"qwen"（假设在PATH中）
            timeout: 命令执行超时时间（秒）
            history_provider: 获取历史记录的回调函数
        """
        self.session_manager = QwenSessionManager(qwen_path, history_provider)
        self.timeout = timeout

    async def _execute_qwen(
        self,
        prompt: str,
        session_id: str = None,
        timeout: int = None
    ) -> AsyncGenerator[str, None]:
        """
        异步执行qwen命令并流式输出结果

        Args:
            prompt: 用户提示词
            session_id: 会话ID（UUID格式，用于管理历史对话）
            timeout: 超时时间（秒），如果为None则使用实例默认值

        Yields:
            流式输出的文本片段
        """
        timeout = timeout or self.timeout

        try:
            session_info = f" with session_id: {session_id}" if session_id else ""
            logger.info(f"[QwenAgent] Sending message to Qwen Code{session_info}, prompt length: {len(prompt)}")

            # 使用会话管理器发送消息
            chunk_count = 0
            if session_id:
                logger.info(f"[QwenAgent] Using session manager with UUID: {session_id}")
                async for chunk in self.session_manager.send_message(session_id, prompt):
                    chunk_count += 1
                    if chunk_count == 1:
                        logger.info(f"[QwenAgent] First chunk received")
                    if chunk_count % 10 == 0:
                        logger.info(f"[QwenAgent] Received {chunk_count} chunks so far")
                    yield chunk
            else:
                # 无会话ID，不使用会话历史
                logger.warning(f"[QwenAgent] No session_id provided, creating temporary session")
                async for chunk in self.session_manager.send_message(None, prompt):
                    chunk_count += 1
                    yield chunk

            logger.info(f"[QwenAgent] Message sending completed, total chunks: {chunk_count}")

        except Exception as e:
            logger.error(f"[QwenAgent] Error executing Qwen Code: {e}")
            raise

    async def stream_chat(
        self,
        current_message: str,
        session_id: str = None
    ) -> AsyncGenerator[str, None]:
        """
        流式对话（适合前端SSE流式响应）

        Args:
            current_message: 当前用户消息
            session_id: 会话ID，用于管理历史对话

        Yields:
            每个输出片段的JSON字符串（SSE格式）
        """
        # 使用当前消息和session_id执行qwen命令
        # 历史消息管理由qwen通过session_id处理

        full_content = ""
        try:
            async for chunk in self._execute_qwen(current_message, session_id):
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
        session_id: str = None
    ) -> str:
        """
        同步对话（非流式，用于测试）

        Args:
            current_message: 当前用户消息
            session_id: 会话ID，用于管理历史对话

        Returns:
            AI的完整回复
        """
        full_content = ""
        async for chunk in self._execute_qwen(current_message, session_id):
            full_content += chunk

        return full_content

    async def close_session(self, session_id: str):
        """
        关闭指定会话（删除临时文件）

        Args:
            session_id: 会话ID
        """
        await self.session_manager.delete_session_file(session_id)
        logger.info(f"Closed session and deleted memory file: {session_id}")

    async def close_all_sessions(self):
        """关闭所有会话（删除所有临时文件）"""
        await self.session_manager.clear_all_session_files()
        logger.info("Closed all sessions and deleted all memory files")
