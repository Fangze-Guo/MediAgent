"""
工具管理服务层
处理工具相关的业务逻辑
"""
import logging
from typing import Dict, Any, List

from src.server_agent.exceptions import NotFoundError, ServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class ToolService:
    """工具服务类"""
    
    def __init__(self, agent):
        self.agent = agent
    
    @handle_service_exception
    async def get_tools_list(self) -> Dict[str, Any]:
        """
        获取工具列表
        
        Returns:
            工具列表信息
        """
        try:
            return {"tools": self.agent.tools}
        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
            raise ServiceError(
                detail="获取工具列表失败",
                service_name="tool_service",
                context={"error": str(e)}
            )
    
    @handle_service_exception
    async def refresh_tools(self) -> Dict[str, Any]:
        """
        刷新工具列表
        
        Returns:
            刷新结果
        """
        try:
            await self.agent.init_tools()
            return {"ok": True, "count": len(self.agent.tools)}
        except Exception as e:
            logger.error(f"刷新工具列表失败: {e}")
            raise ServiceError(
                detail="刷新工具列表失败",
                service_name="tool_service",
                context={"error": str(e)}
            )
    
    @handle_service_exception
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        直接调用工具
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            # 检查工具是否存在
            available_tools = [t["function"]["name"] for t in self.agent.tools if "function" in t]
            if tool_name not in available_tools:
                raise NotFoundError(
                    resource_type="tool",
                    resource_id=tool_name,
                    detail=f"工具不存在: {tool_name}"
                )
            
            # 调用工具
            result = await self.agent._call_tool(tool_name, args)
            return {"ok": True, "result": result}
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"调用工具失败: {e}")
            raise ServiceError(
                detail="调用工具失败",
                service_name="tool_service",
                context={"tool_name": tool_name, "args": args, "error": str(e)}
            )
    
    def get_available_tools(self) -> List[str]:
        """
        获取可用工具名称列表
        
        Returns:
            工具名称列表
        """
        try:
            return [t["function"]["name"] for t in self.agent.tools if "function" in t]
        except Exception as e:
            logger.error(f"获取可用工具名称失败: {e}")
            return []
