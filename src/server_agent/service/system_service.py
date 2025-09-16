"""
系统管理服务层
处理系统相关的业务逻辑
"""
import pathlib
import logging
from typing import Dict, Any
from PIL import Image

from src.server_agent.exceptions import ServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class SystemService:
    """系统服务类"""
    
    def __init__(self, agent, base_url: str, model: str):
        self.agent = agent
        self.base_url = base_url
        self.model = model
    
    @handle_service_exception
    async def health_check(self) -> Dict[str, Any]:
        """
        系统健康检查
        
        Returns:
            健康检查结果
        """
        try:
            health_info = self._get_health_info()
            return {
                "status": "ok",
                **health_info
            }
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            raise ServiceError(
                detail="健康检查失败",
                service_name="system_service",
                context={"error": str(e)}
            )
    
    @handle_service_exception
    async def self_test(self) -> Dict[str, Any]:
        """
        系统自测
        
        Returns:
            自测结果
        """
        try:
            # 创建测试图片
            root = pathlib.Path("../..")
            inp = root / "selftest_in.jpg"
            outp = root / "selftest_out.jpg"
            
            # 生成测试图片
            Image.new("RGB", (320, 200), (180, 200, 240)).save(inp)
            
            # 调用图片调整工具
            result = await self.agent._call_tool("resize_image", {
                "input_path": str(inp.resolve()),
                "output_path": str(outp.resolve()),
                "width": 128,
                "height": 128,
                "timeout": 30
            })
            
            # 清理测试文件
            try:
                if inp.exists():
                    inp.unlink()
                if outp.exists():
                    outp.unlink()
            except Exception as cleanup_error:
                logger.warning(f"清理测试文件失败: {cleanup_error}")
            
            return {"ok": True, "result": result}
            
        except Exception as e:
            logger.error(f"系统自测失败: {e}")
            raise ServiceError(
                detail="系统自测失败",
                service_name="system_service",
                context={"error": str(e)}
            )
    
    def _get_health_info(self) -> Dict[str, Any]:
        """
        获取健康检查信息
        
        Returns:
            健康检查信息
        """
        try:
            # 获取Python解释器路径
            mcp_py = "unknown"
            try:
                import sys
                mcp_py = sys.executable
            except Exception:
                pass
            
            return {
                "model": self.model,
                "lm_server": self.base_url,
                "tools_count": len(self.agent.tools),
                "python": mcp_py,
            }
        except Exception as e:
            logger.error(f"获取健康检查信息失败: {e}")
            return {
                "model": "unknown",
                "lm_server": "unknown",
                "tools_count": 0,
                "python": "unknown",
            }
