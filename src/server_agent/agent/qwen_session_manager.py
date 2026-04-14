"""
Qwen Code 会话管理器 - 使用 --resume 机制实现有状态对话
移除临时文件方案，完全依赖 Qwen 的 JSONL 文件管理上下文
"""
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict
import json

logger = logging.getLogger(__name__)


class QwenSessionManager:
    """Qwen Code 会话管理器 - 使用 --resume 机制"""

    def __init__(self, qwen_path: str = "qwen"):
        """
        初始化会话管理器

        Args:
            qwen_path: qwen 命令路径
        """
        self.qwen_path = os.getenv("QWEN_CODE_PATH", qwen_path)

        # 检查是否使用WSL
        self.use_wsl = os.getenv("QWEN_USE_WSL", "").lower() == "true"

        if self.use_wsl:
            # 添加WSL前缀到qwen命令
            self.qwen_path = f"wsl {self.qwen_path}"

        logger.info(f"Qwen session manager initialized (WSL: {self.use_wsl}, qwen_path: {self.qwen_path})")

    @staticmethod
    async def test_qwen_command(qwen_path: str) -> dict:
        """
        测试 Qwen Code 命令是否可用

        Args:
            qwen_path: qwen 命令路径

        Returns:
            包含测试结果的字典
        """
        result = {
            "available": False,
            "version": None,
            "error": None
        }

        try:
            # 测试基本命令是否可用
            logger.info(f"Testing Qwen Code command: {qwen_path}")
            process = await asyncio.create_subprocess_shell(
                f'"{qwen_path}" --help',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

            if process.returncode == 0:
                result["available"] = True
                help_text = stdout.decode('utf-8', errors='ignore') + stderr.decode('utf-8', errors='ignore')
                logger.info(f"Qwen Code help text: {help_text[:200]}...")
            else:
                result["error"] = f"Command failed with return code {process.returncode}"
                logger.error(f"Qwen Code command test failed: {result['error']}")

        except asyncio.TimeoutError:
            result["error"] = "Command timeout - Qwen Code may not be responding"
            logger.error("Qwen Code command test timeout")
        except FileNotFoundError:
            result["error"] = f"Qwen Code command not found: {qwen_path}"
            logger.error(f"Qwen Code not found at: {qwen_path}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error testing Qwen Code: {e}")

        return result

    async def send_message(
        self,
        session_id: str = None,
        prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        """
        发送消息到指定会话

        Args:
            session_id: 会话ID（UUID格式），为None则创建新会话
            prompt: 用户消息

        Yields:
            流式响应的文本片段
        """
        # 捕获用户输入
        logger.info(f"用户：{prompt}")
        logger.info(f"会话ID: {session_id if session_id else '新会话'}")

        full_response = ""

        if session_id:
            # 继续会话：使用 --resume
            logger.info(f"恢复会话: {session_id}")
            async for chunk in self._resume_session(session_id, prompt):
                full_response += chunk
                yield chunk
        else:
            # 新建会话：直接发送消息
            logger.info("创建新会话")
            async for chunk in self._create_new_session(prompt):
                full_response += chunk
                yield chunk

        # 捕获 Qwen Code 输出
        logger.info(f"助手：{full_response}")

    async def _create_new_session(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        创建新会话并发送消息

        Args:
            prompt: 用户消息

        Yields:
            流式响应的文本片段
        """
        try:
            # 转义 prompt 中的特殊字符
            escaped_prompt = self._escape_prompt(prompt)

            # 构建命令：qwen -p "prompt"
            if self.use_wsl:
                escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                command = f'wsl bash -c "qwen -p \'{escaped_prompt_linux}\'"'
            elif os.name == 'nt':  # Windows
                command = f'"{self.qwen_path}" -p "{escaped_prompt}"'
            else:  # Linux/Mac
                escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                command = f'"{self.qwen_path}" -p \'{escaped_prompt_linux}\''

            # 记录命令摘要
            command_preview = command[:100] + "..." if len(command) > 100 else command
            logger.info(f"Executing new session command: {command_preview}")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
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
                    stderr_output = await process.stderr.read()
                    stderr_text = stderr_output.decode('utf-8', errors='ignore')
                    if stderr_text:
                        logger.error(f"Command stderr: {stderr_text[:500]}")
                    raise RuntimeError(f"Qwen Code command exited with code {process.returncode}")

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
            logger.error(f"Error creating new session: {e}")
            raise

    async def _resume_session(self, session_id: str, prompt: str) -> AsyncGenerator[str, None]:
        """
        恢复现有会话并发送消息

        Args:
            session_id: 会话ID
            prompt: 用户消息

        Yields:
            流式响应的文本片段
        """
        try:
            # 转义 prompt 中的特殊字符
            escaped_prompt = self._escape_prompt(prompt)

            # 构建命令：qwen --resume {session_id} -p "prompt"
            if self.use_wsl:
                escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                command = f'wsl bash -c "qwen --resume {session_id} -p \'{escaped_prompt_linux}\'"'
            elif os.name == 'nt':  # Windows
                command = f'"{self.qwen_path}" --resume {session_id} -p "{escaped_prompt}"'
            else:  # Linux/Mac
                escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                command = f'"{self.qwen_path}" --resume {session_id} -p \'{escaped_prompt_linux}\''

            # 记录命令摘要
            command_preview = command[:100] + "..." if len(command) > 100 else command
            logger.info(f"Executing resume session command: {command_preview}")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
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
                    stderr_output = await process.stderr.read()
                    stderr_text = stderr_output.decode('utf-8', errors='ignore')
                    if stderr_text:
                        logger.error(f"Command stderr: {stderr_text[:500]}")
                    raise RuntimeError(f"Qwen Code command exited with code {process.returncode}")

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
            logger.error(f"Error resuming session {session_id}: {e}")
            raise

    def _escape_prompt(self, prompt: str) -> str:
        """
        转义 prompt 中的特殊字符

        Args:
            prompt: 用户消息

        Returns:
            转义后的 prompt
        """
        # 根据不同的 shell 转义规则
        if os.name == 'nt':  # Windows cmd
            # 转义双引号
            escaped = prompt.replace('"', '""')
            return escaped
        else:  # Linux/Mac bash
            # 转义单引号为 '\''
            escaped = prompt.replace("'", "'\\''")
            return escaped

    async def get_session_info_from_qwen(self) -> Optional[Dict]:
        """
        尝试从 Qwen 获取当前会话信息

        Returns:
            包含 session_id 等信息的字典，如果无法获取则返回 None
        """
        try:
            # 尝试获取会话列表
            command = f'"{self.qwen_path}" --list'
            if self.use_wsl:
                command = f'wsl bash -c "qwen --list"'

            logger.info(f"Getting session list: {command}")
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)

            if process.returncode == 0:
                output = stdout.decode('utf-8', errors='ignore')
                logger.info(f"Session list output: {output[:500]}")

                # 尝试解析输出获取会话信息
                # 这里需要根据实际的 --list 输出格式进行调整
                return {"raw_output": output}
            else:
                logger.warning(f"Failed to get session list: {stderr.decode('utf-8', errors='ignore')}")
                return None

        except Exception as e:
            logger.warning(f"Error getting session info: {e}")
            return None
