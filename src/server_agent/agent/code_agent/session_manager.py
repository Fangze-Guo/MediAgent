"""
Code Agent 会话管理器基类
定义会话管理的抽象接口，具体实现由 Qwen 或 Claude 完成
"""
import asyncio
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict

logger = logging.getLogger(__name__)


class BaseSessionManager(ABC):
    """会话管理器基类"""

    def __init__(self, agent_type: str = "unknown"):
        """
        初始化会话管理器

        Args:
            agent_type: Agent 类型标识 (qwen/claude)
        """
        self.agent_type = agent_type

    @abstractmethod
    async def send_message(
        self,
        session_id: str = "",
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
        pass

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

    def _windows_to_wsl_path(self, windows_path: str) -> str:
        """
        将 Windows 路径转换为 WSL 路径

        Args:
            windows_path: Windows 路径（如 C:/Users/...）

        Returns:
            WSL 路径（如 /mnt/c/Users/...）
        """
        # 标准化路径：将反斜杠转换为正斜杠
        normalized_path = windows_path.replace('\\', '/')

        # 使用正则表达式匹配 Windows 路径格式
        match = re.match(r'^([A-Za-z]):/(.*)$', normalized_path)
        if match:
            drive = match.group(1).lower()
            path = match.group(2)
            return f'/mnt/{drive}/{path}'

        logger.warning(f"路径格式不符合 Windows 规范: {windows_path}")
        return windows_path

    @staticmethod
    async def test_command(command_path: str, agent_type: str = "unknown") -> dict:
        """
        测试命令是否可用

        Args:
            command_path: 命令路径
            agent_type: Agent 类型

        Returns:
            包含测试结果的字典
        """
        result = {
            "available": False,
            "version": None,
            "error": None
        }

        try:
            logger.info(f"正在测试 {agent_type} 命令: {command_path}")
            process = await asyncio.create_subprocess_shell(
                f'"{command_path}" --help',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

            if process.returncode == 0:
                result["available"] = True
                help_text = stdout.decode('utf-8', errors='ignore') + stderr.decode('utf-8', errors='ignore')
                logger.info(f"{agent_type} 帮助信息: {help_text[:200]}...")
            else:
                result["error"] = f"命令执行失败，返回码 {process.returncode}"
                logger.error(f"{agent_type} 命令测试失败: {result['error']}")

        except asyncio.TimeoutError:
            result["error"] = "命令执行超时"
            logger.error(f"{agent_type} 命令测试超时")
        except FileNotFoundError:
            result["error"] = f"命令未找到: {command_path}"
            logger.error(f"未找到 {agent_type} 命令: {command_path}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"测试 {agent_type} 时发生错误: {e}")

        return result
