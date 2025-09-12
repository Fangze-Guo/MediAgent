"""
工具管理API控制器
"""
from fastapi import HTTPException
from pydantic import BaseModel

from .base import BaseController


class ToolReq(BaseModel):
    name: str
    args: dict


class ToolController(BaseController):
    """工具控制器"""
    
    def __init__(self):
        super().__init__(prefix="/tools", tags=["工具管理"])
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.get("")
        async def list_tools():
            """获取工具列表"""
            await self.ensure_initialized()
            return {"tools": self.agent.tools}
        
        @self.router.post("/refresh")
        async def refresh_tools():
            """刷新工具列表"""
            await self.agent.init_tools()
            return {"ok": True, "count": len(self.agent.tools)}
        
        @self.router.post("/call")
        async def call_tool(req: ToolReq):
            """直接调用工具（绕过LLM，快速排障）"""
            await self.ensure_initialized()
            
            names = [t["function"]["name"] for t in self.agent.tools if "function" in t]
            if req.name not in names:
                raise HTTPException(404, f"tool not found: {req.name}")
            
            # 内部方法，直接调用 MCP 工具
            result = await self.agent._call_tool(req.name, req.args)
            return {"ok": True, "result": result}
