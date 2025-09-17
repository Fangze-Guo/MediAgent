"""
Tools包 - 统一管理所有MCP工具
"""
from mcp.server.fastmcp import FastMCP
from .image_tools import ImageTools
from .data_tools import DataTools
from .medical_tools import MedicalTools


def register_all_tools(mcp_server: FastMCP):
    """注册所有工具到MCP服务器"""
    # 创建工具实例并注册
    image_tools = ImageTools(mcp_server)
    data_tools = DataTools(mcp_server)
    medical_tools = MedicalTools(mcp_server)
    
    # 注册工具
    image_tools.register_tools()
    data_tools.register_tools()
    medical_tools.register_tools()
    
    return {
        'image_tools': image_tools,
        'data_tools': data_tools,
        'medical_tools': medical_tools
    }


# 导出工具类
__all__ = [
    'ImageTools',
    'DataTools',
    'MedicalTools',
    'register_all_tools',
]
