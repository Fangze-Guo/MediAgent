"""
Qwen Code 会话管理器 - 使用 --resume 机制实现有状态对话
继承自 BaseSessionManager
"""
import asyncio
import logging
import os
from typing import AsyncGenerator, Optional, Dict

from src.server_agent.agent.code_agent.session_manager import BaseSessionManager

logger = logging.getLogger(__name__)


class QwenSessionManager(BaseSessionManager):
    """Qwen Code 会话管理器 - 使用 --resume 机制"""

    def __init__(self, qwen_path: str = "qwen"):
        """
        初始化会话管理器

        Args:
            qwen_path: qwen 命令路径
        """
        super().__init__(agent_type="qwen")
        self.qwen_path = os.getenv("QWEN_CODE_PATH", qwen_path)

        # 检查是否使用WSL
        self.use_wsl = os.getenv("QWEN_USE_WSL", "").lower() == "true"

        if self.use_wsl:
            # 添加WSL前缀到qwen命令
            self.qwen_path = f"wsl {self.qwen_path}"

        logger.info(f"Qwen 会话管理器已初始化 (WSL: {self.use_wsl}, qwen_path: {self.qwen_path})")

    async def send_message(
        self,
        session_id: Optional[str] = None,
        prompt: str = "",
        is_file: bool = False,
        use_stream_json: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        发送消息到指定会话

        Args:
            session_id: 会话ID（UUID格式），为None则创建新会话
            prompt: 用户消息或文件路径（如果is_file=True）
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Yields:
            流式响应的文本片段
        """
        # 捕获用户输入
        input_source = f"文件 {prompt}" if is_file else prompt
        logger.info(f"用户输入：{input_source}")
        logger.info(f"会话ID: {session_id if session_id else '新会话'}")
        logger.info(f"流式JSON模式: {use_stream_json}")

        full_response = ""

        if session_id:
            # 继续会话：使用 --resume
            logger.info(f"恢复会话: {session_id}")
            async for chunk in self._resume_session(session_id, prompt, is_file=is_file, use_stream_json=use_stream_json):
                full_response += chunk
                yield chunk
        else:
            # 新建会话：直接发送消息
            logger.info("创建新会话")
            async for chunk in self._create_new_session(prompt, is_file=is_file, use_stream_json=use_stream_json):
                full_response += chunk
                yield chunk

        # 捕获 Qwen Code 输出
        logger.info(f"助手：{full_response}")

    async def _create_new_session(self, prompt: str, is_file: bool = False, use_stream_json: bool = True) -> AsyncGenerator[str, None]:
        """
        创建新会话并发送消息

        Args:
            prompt: 用户消息或文件路径（如果is_file=True）
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Yields:
            流式响应的文本片段
        """
        try:
            # 构建流式 JSON 输出参数
            stream_json_params = "--output-format stream-json --include-partial-messages" if use_stream_json else ""

            if is_file:
                # 使用管道输入：cat file | qwen --yolo --output-format stream-json --include-partial-messages
                if self.use_wsl:
                    # WSL 模式：wsl bash -c "cat file | qwen --yolo --output-format stream-json --include-partial-messages"
                    wsl_path = self._windows_to_wsl_path(prompt)
                    command = f'wsl bash -c "cat {wsl_path} | qwen --yolo {stream_json_params}"'
                else:
                    # Windows/Linux 直接使用管道
                    if os.name == 'nt':  # Windows cmd
                        command = f'type "{prompt}" | "{self.qwen_path}" --yolo {stream_json_params}'
                    else:  # Linux/Mac
                        command = f'cat "{prompt}" | "{self.qwen_path}" --yolo {stream_json_params}'
            else:
                # 转义 prompt 中的特殊字符
                escaped_prompt = self._escape_prompt(prompt)

                # 构建命令：qwen --yolo --output-format stream-json --include-partial-messages -p "prompt"
                if self.use_wsl:
                    escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                    command = f"wsl bash -c \"qwen --yolo {stream_json_params} -p '{escaped_prompt_linux}'\""
                elif os.name == 'nt':  # Windows
                    command = f'"{self.qwen_path}" --yolo {stream_json_params} -p "{escaped_prompt}"'
                else:  # Linux/Mac
                    escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                    command = f'"{self.qwen_path}" --yolo {stream_json_params} -p \'{escaped_prompt_linux}\''

            # 记录命令摘要
            command_preview = command[:100] + "..." if len(command) > 100 else command
            logger.info(f"正在执行新会话命令: {command_preview}")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                assert process.stdout is not None
                while True:
                    line_bytes = await process.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode('utf-8', errors='ignore')
                    if line:
                        yield line

                # 等待进程结束
                await process.wait()

                if process.returncode != 0:
                    assert process.stderr is not None
                    stderr_output = await process.stderr.read()
                    stderr_text = stderr_output.decode('utf-8', errors='ignore')
                    if stderr_text:
                        logger.error(f"命令 stderr 输出: {stderr_text[:500]}")
                    raise RuntimeError(f"Qwen Code 命令退出，代码 {process.returncode}")

            except Exception as e:
                # 确保进程被清理
                if process.returncode is None:
                    try:
                        process.kill()
                        await process.wait()
                    except Exception:
                        pass
                raise

        except Exception as e:
            logger.error(f"创建新会话时发生错误: {e}")
            raise

    async def _resume_session(self, session_id: str, prompt: str, is_file: bool = False, use_stream_json: bool = True) -> AsyncGenerator[str, None]:
        """
        恢复现有会话并发送消息

        Args:
            session_id: 会话ID
            prompt: 用户消息或文件路径（如果is_file=True）
            is_file: 是否为文件路径（使用管道输入）
            use_stream_json: 是否使用流式 JSON 输出格式

        Yields:
            流式响应的文本片段
        """
        try:
            # 构建流式 JSON 输出参数
            stream_json_params = "--output-format stream-json --include-partial-messages" if use_stream_json else ""

            if is_file:
                # 使用管道输入：cat file | qwen --resume {session_id} --yolo --output-format stream-json --include-partial-messages
                if self.use_wsl:
                    wsl_path = self._windows_to_wsl_path(prompt)
                    command = f'wsl bash -c "cat {wsl_path} | qwen --resume {session_id} --yolo {stream_json_params}"'
                else:
                    if os.name == 'nt':  # Windows cmd
                        command = f'type "{prompt}" | "{self.qwen_path}" --resume {session_id} --yolo {stream_json_params}'
                    else:  # Linux/Mac
                        command = f'cat "{prompt}" | "{self.qwen_path}" --resume {session_id} --yolo {stream_json_params}'
            else:
                # 转义 prompt 中的特殊字符
                escaped_prompt = self._escape_prompt(prompt)

                # 构建命令：qwen --resume {session_id} --yolo --output-format stream-json --include-partial-messages -p "prompt"
                if self.use_wsl:
                    escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                    command = f"wsl bash -c \"qwen --resume {session_id} --yolo {stream_json_params} -p '{escaped_prompt_linux}'\""
                elif os.name == 'nt':  # Windows
                    command = f'"{self.qwen_path}" --resume {session_id} --yolo {stream_json_params} -p "{escaped_prompt}"'
                else:  # Linux/Mac
                    escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                    command = f'"{self.qwen_path}" --resume {session_id} --yolo {stream_json_params} -p \'{escaped_prompt_linux}\''

            logger.info(f"正在执行恢复会话命令: {command}")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                assert process.stdout is not None
                while True:
                    line_bytes = await process.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode('utf-8', errors='ignore')
                    if line:
                        yield line

                # 等待进程结束
                await process.wait()

                if process.returncode != 0:
                    assert process.stderr is not None
                    stderr_output = await process.stderr.read()
                    stderr_text = stderr_output.decode('utf-8', errors='ignore')
                    if stderr_text:
                        logger.error(f"命令 stderr 输出: {stderr_text[:500]}")
                    raise RuntimeError(f"Qwen Code 命令退出，代码 {process.returncode}")

            except Exception as e:
                # 确保进程被清理
                if process.returncode is None:
                    try:
                        process.kill()
                        await process.wait()
                    except Exception:
                        pass
                raise

        except Exception as e:
            logger.error(f"恢复会话 {session_id} 时发生错误: {e}")
            raise

    async def get_session_info(self) -> Optional[Dict]:
        """
        尝试获取当前会话信息

        Returns:
            包含 session_id 等信息的字典，如果无法获取则返回 None
        """
        try:
            # 尝试获取会话列表
            command = f'"{self.qwen_path}" --list'
            if self.use_wsl:
                command = f"wsl bash -c \"qwen --list\""

            logger.info(f"正在获取会话列表: {command}")
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)

            if process.returncode == 0:
                output = stdout.decode('utf-8', errors='ignore')
                logger.info(f"会话列表输出: {output[:500]}")
                return {"raw_output": output}
            else:
                logger.warning(f"获取会话列表失败: {stderr.decode('utf-8', errors='ignore')}")
                return None

        except Exception as e:
            logger.warning(f"获取会话信息时发生错误: {e}")
            return None
