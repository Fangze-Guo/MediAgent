"""
基础Controller类
提供通用的依赖注入和工具方法
"""
import asyncio
from typing import List

from fastapi import APIRouter

from src.server_agent.agent import MCPAgent

# 全局变量
agent = MCPAgent()
_init_lock = asyncio.Lock()
_initialized = False


class BaseController:
    """基础Controller类"""

    def __init__(self, prefix: str = "", tags: List[list] = None):
        self.router = APIRouter(prefix=prefix, tags=tags or [])
        self.agent = agent
        self._init_lock = _init_lock
        self._initialized = _initialized

    async def ensure_initialized(self):
        """确保agent已初始化"""
        global _initialized
        async with self._init_lock:
            if not _initialized:
                await self.agent.init_tools()
                _initialized = True
