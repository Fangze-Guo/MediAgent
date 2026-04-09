"""
Qwen Code Agent - 通过subprocess调用Qwen Code无头模式
提供流式和同步的对话功能
"""
import asyncio
import logging
import os
import uuid
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class QwenAgent:
    """Qwen Code Agent类"""

    def _convert_to_uuid(self, session_id: str) -> str:
        """
        将字符串转换为 UUID 格式
        使用 uuid5 基于原始字符串生成确定性的 UUID

        Args:
            session_id: 原始会话ID

        Returns:
            UUID 格式的字符串
        """
        try:
            # 如果已经是 UUID 格式，直接返回
            uuid.UUID(session_id)
            return session_id
        except ValueError:
            # 不是有效 UUID，生成一个确定性的 UUID
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, session_id))

    def __init__(self, qwen_path: str = "qwen", timeout: int = 120):
        """
        初始化Qwen Code Agent

        Args:
            qwen_path: qwen命令的路径，默认为"qwen"（假设在PATH中）
            timeout: 命令执行超时时间（秒）
        """
        self.qwen_path = os.getenv("QWEN_CODE_PATH", qwen_path)
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
            session_id: 会话ID，用于管理历史对话
            timeout: 超时时间（秒），如果为None则使用实例默认值

        Yields:
            流式输出的文本片段
        """
        timeout = timeout or self.timeout

        # 将 session_id 转换为 UUID 格式
        uuid_session_id = self._convert_to_uuid(session_id) if session_id else None

        try:
            # 构建命令
            if os.name == 'nt':  # Windows
                # Windows下使用shell执行
                if uuid_session_id:
                    command = f'"{self.qwen_path}" --session-id "{uuid_session_id}" -p "{prompt}"'
                else:
                    command = f'"{self.qwen_path}" -p "{prompt}"'

                logger.info(f"Executing Qwen command: {command}")
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:  # Linux/Mac
                if uuid_session_id:
                    command_args = [self.qwen_path, "--session-id", uuid_session_id, "-p", prompt]
                    command_str = f'{" ".join(command_args[:3])} -p "{prompt}"'  # 隐藏完整prompt
                    logger.info(f"Executing Qwen command: {command_str}")
                    process = await asyncio.create_subprocess_exec(
                        *command_args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                else:
                    command_args = [self.qwen_path, "-p", prompt]
                    command_str = f'{self.qwen_path} -p "{prompt}"'  # 隐藏完整prompt
                    logger.info(f"Executing Qwen command: {command_str}")
                    process = await asyncio.create_subprocess_exec(
                        *command_args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

            session_info = f" with session_id: {session_id} (UUID: {uuid_session_id})" if session_id else ""
            logger.info(f"Started Qwen Code process{session_info} with prompt length: {len(prompt)}")

            # 读取stdout流
            try:
                while True:
                    try:
                        # 等待输出，带超时
                        line_bytes = await asyncio.wait_for(
                            process.stdout.readline(),
                            timeout=timeout
                        )

                        if not line_bytes:
                            # EOF
                            break

                        # 解码文本
                        line = line_bytes.decode('utf-8', errors='ignore')

                        if line:
                            yield line

                    except asyncio.TimeoutError:
                        logger.error(f"Qwen Code process timeout after {timeout} seconds")
                        process.kill()
                        await process.wait()
                        raise TimeoutError(f"Qwen Code execution timed out after {timeout} seconds")

                # 等待进程结束
                await asyncio.wait_for(process.wait(), timeout=timeout)

                # 检查stderr
                if process.returncode != 0:
                    stderr_output = await process.stderr.read()
                    stderr_text = stderr_output.decode('utf-8', errors='ignore')
                    if stderr_text:
                        logger.error(f"Qwen Code stderr: {stderr_text}")
                    raise RuntimeError(
                        f"Qwen Code process exited with code {process.returncode}: {stderr_text}"
                    )

            except Exception as e:
                # 确保进程被终止
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                raise

        except FileNotFoundError:
            logger.error(f"Qwen Code command not found at: {self.qwen_path}")
            raise FileNotFoundError(
                f"Qwen Code command not found. Please install Qwen Code or set QWEN_CODE_PATH environment variable."
            )
        except Exception as e:
            logger.error(f"Error executing Qwen Code: {e}")
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
        import json

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
