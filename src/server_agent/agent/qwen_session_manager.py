"""
Qwen Code 会话管理器 - 使用临时文件存储历史记录作为 memory
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Callable, Optional, List, Tuple

logger = logging.getLogger(__name__)


class QwenSessionManager:
    """Qwen Code 会话管理器 - 使用临时文件存储历史记录作为 memory"""

    def __init__(self, qwen_path: str = "qwen", history_provider: Optional[Callable] = None):
        """
        初始化会话管理器

        Args:
            qwen_path: qwen 命令路径
            history_provider: 获取历史记录的回调函数，签名为 async def get_history(conversation_id: str) -> List[Tuple[str, str, str]]
                           返回格式：[(role, content, message_id), ...]
        """
        self.qwen_path = os.getenv("QWEN_CODE_PATH", qwen_path)
        self.history_provider = history_provider

        # 创建临时文件目录
        self.temp_dir = Path(tempfile.gettempdir()) / "qwen_sessions"
        self.temp_dir.mkdir(exist_ok=True)
        logger.info(f"Qwen session temp directory: {self.temp_dir}")

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
        session_id: str,
        prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        发送消息到指定会话

        Args:
            session_id: 会话ID（UUID格式，为None则不使用会话历史）
            prompt: 用户消息

        Yields:
            流式响应的文本片段
        """
        # 捕获用户输入
        logger.info(f"用户：{prompt}")

        # 获取历史记录并写入临时文件
        history = None
        if session_id and self.history_provider:
            # 从数据库加载历史记录
            logger.info(f"Loading conversation history from database for {session_id}")
            history = await self.history_provider(session_id)
            logger.info(f"Loaded {len(history)} turns from database")
        else:
            logger.info("No history provider or no session_id, using empty history")
            history = []

        # 将历史记录写入临时文件
        memory_file_path = self.temp_dir / f"{session_id}.md" if session_id else self.temp_dir / "temp.md"
        memory_content = self._build_memory_content(history)

        # 写入临时文件
        memory_file_path.write_text(memory_content, encoding='utf-8')
        logger.info(f"Memory file written to: {memory_file_path}")
        logger.info(f"Memory file content length: {len(memory_content)} 字符")

        # 打印临时文件内容（仅记录摘要，避免日志过大）
        logger.info(f"=== 临时文件内容 ===")
        logger.info(f"{memory_content[:500]}{'...' if len(memory_content) > 500 else ''}")
        logger.info(f"=== 文件内容结束 ===")

        # 使用管道方式执行：cat file | qwen -p "当前消息"
        full_response = ""
        async for chunk in self._execute_with_memory_file(memory_file_path, prompt):
            full_response += chunk
            yield chunk

        # 捕获 Qwen Code 输出
        logger.info(f"助手：{full_response}")

        # 注意：不更新临时文件，因为下次对话会重新从数据库加载最新历史

    def _build_memory_content(self, history: List[Tuple[str, str, str]]) -> str:
        """
        构建内存文件内容

        Args:
            history: 历史对话记录，格式：[(role, content, message_id), ...]

        Returns:
            内存文件内容
        """
        if not history:
            return ""

        # 限制历史长度
        max_history_turns = 20  # 最多保留20轮对话
        if len(history) > max_history_turns:
            history = history[-max_history_turns:]

        # 构建历史对话文本
        memory_content = "## 对话历史\n\n"
        for i, (role, content, message_id) in enumerate(history):
            role_name = "用户" if role == "user" else "助手"
            memory_content += f"**第{i+1}轮对话**\n\n"
            memory_content += f"**{role_name}**：{content}\n\n"

        return memory_content

    async def _execute_with_memory_file(self, memory_file_path: Path, current_prompt: str) -> AsyncGenerator[str, None]:
        """
        使用临时文件执行命令：type file | qwen -p "当前prompt"

        Args:
            memory_file_path: 内存文件路径
            current_prompt: 当前用户消息

        Yields:
            流式响应的文本片段

        Raises:
            RuntimeError: 当命令执行失败时
        """
        try:
            # 转义 prompt 中的特殊字符（双引号、反引号等）
            # 注意：Windows cmd 中的转义规则比较复杂，这里处理常见情况
            escaped_prompt = current_prompt.replace('"', '""')  # 双引号转义为两个双引号

            # 构建命令（Windows: type file | qwen -p "prompt"）
            # Linux/Mac: cat file | qwen -p "prompt"
            if os.name == 'nt':  # Windows
                command = f'type "{memory_file_path}" | "{self.qwen_path}" -p "{escaped_prompt}"'
            else:  # Linux/Mac
                # Linux shell 中需要处理单引号
                escaped_prompt_linux = escaped_prompt.replace("'", "'\\''")
                command = f'cat "{memory_file_path}" | "{self.qwen_path}" -p \'{escaped_prompt_linux}\''

            # 记录命令摘要（隐藏 prompt 内容以保护隐私）
            command_preview = command[:100] + "..." if len(command) > 100 else command
            logger.info(f"Executing command: {command_preview}")
            logger.debug(f"Prompt length: {len(current_prompt)} characters")

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
                        logger.error(f"Command stderr: {stderr_text[:500]}")  # 限制日志长度
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
            logger.error(f"Error executing command with memory file: {e}")
            raise

    async def delete_session_file(self, session_id: str):
        """
        删除指定会话的临时文件

        Args:
            session_id: 会话ID
        """
        memory_file_path = self.temp_dir / f"{session_id}.md"
        if memory_file_path.exists():
            memory_file_path.unlink()
            logger.info(f"Deleted memory file: {memory_file_path}")

    async def clear_all_session_files(self):
        """清除所有会话临时文件"""
        # 删除所有临时文件
        for file_path in self.temp_dir.glob("*.md"):
            try:
                file_path.unlink()
                logger.info(f"Deleted memory file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting memory file {file_path}: {e}")
        logger.info("Cleared all session memory files")
