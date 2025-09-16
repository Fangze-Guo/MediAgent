"""
工具管理API控制器
"""
from pydantic import BaseModel

from .base import BaseController
from src.server_agent.service import ToolService


class ToolReq(BaseModel):
    name: str
    args: dict


class ToolController(BaseController):
    """工具控制器"""
    
    def __init__(self):
        super().__init__(prefix="/tools", tags=["工具管理"])
        self.tool_service = ToolService(self.agent)
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.get("")
        async def list_tools():
            """获取工具列表"""
            await self.ensure_initialized()
            return await self.tool_service.get_tools_list()
        
        @self.router.post("/refresh")
        async def refresh_tools():
            """刷新工具列表"""
            await self.ensure_initialized()
            return await self.tool_service.refresh_tools()
        
        @self.router.post("/call")
        async def call_tool(req: ToolReq):
            """直接调用工具（绕过LLM，快速排障）"""
            await self.ensure_initialized()
            return await self.tool_service.call_tool(req.name, req.args)
