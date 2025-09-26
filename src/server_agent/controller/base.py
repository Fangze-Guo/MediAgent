"""
基础Controller类
提供通用的依赖注入和工具方法
"""
import asyncio
from typing import List

from fastapi import APIRouter

# 全局变量
_init_lock = asyncio.Lock()
_initialized = False


class BaseController:
    """基础Controller类"""

    def __init__(self, prefix: str = "", tags: List[list] = None):
        self.router = APIRouter(prefix=prefix, tags=tags or [])
        self._init_lock = _init_lock
        self._initialized = _initialized
