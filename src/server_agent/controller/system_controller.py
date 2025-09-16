"""
系统管理API控制器
"""

from .base import BaseController
from src.server_agent.constants.EnvConfig import BASE_URL, MODEL
from src.server_agent.service import SystemService


class SystemController(BaseController):
    """系统控制器"""

    def __init__(self):
        super().__init__(prefix="/system", tags=["系统管理"])
        self.system_service = SystemService(self.agent, BASE_URL, MODEL)
        self._register_routes()

    def _register_routes(self):
        """注册路由"""

        @self.router.get("/health")
        async def health_check():
            """健康检查"""
            await self.ensure_initialized()
            return await self.system_service.health_check()

        @self.router.get("/selftest")
        async def selftest():
            """自测接口：生成、缩放、校验（本地磁盘）"""
            await self.ensure_initialized()
            return await self.system_service.self_test()
