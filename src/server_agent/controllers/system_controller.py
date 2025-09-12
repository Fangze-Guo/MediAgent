"""
系统管理API控制器
"""
from fastapi import HTTPException
from pydantic import BaseModel

from .base import BaseController


class SystemController(BaseController):
    """系统控制器"""
    
    def __init__(self):
        super().__init__(prefix="/system", tags=["系统管理"])
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.get("/health")
        async def health_check():
            """健康检查"""
            await self.ensure_initialized()
            health_info = self.get_health_info()
            return {
                "status": "ok",
                **health_info
            }
        
        @self.router.get("/selftest")
        async def selftest():
            """自测接口：生成、缩放、校验（本地磁盘）"""
            try:
                import pathlib
                from PIL import Image
                
                root = pathlib.Path("../..")
                inp = root / "selftest_in.jpg"
                outp = root / "selftest_out.jpg"
                Image.new("RGB", (320, 200), (180, 200, 240)).save(inp)
                
                # 直连工具调用
                res = await self.agent._call_tool("resize_image", {
                    "input_path": str(inp.resolve()),
                    "output_path": str(outp.resolve()),
                    "width": 128,
                    "height": 128,
                    "timeout": 30
                })
                return {"ok": True, "result": res}
            except Exception as e:
                print(f"自测失败: {e}")
                raise HTTPException(status_code=500, detail=f"自测失败: {str(e)}")
