from mcp.server.fastmcp import FastMCP
import logging
import pathlib
from logging.handlers import TimedRotatingFileHandler

# 导入工具注册函数
try:
    from .tools import register_all_tools
except ImportError:
    try:
        from src.server_agent.tools import register_all_tools
    except ImportError:
        # 添加当前目录到Python路径
        import sys
        current_dir = pathlib.Path(__file__).parent
        sys.path.insert(0, str(current_dir))
        from tools import register_all_tools

# ========== 日志配置 ==========
LOG_DIR = pathlib.Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_handler = TimedRotatingFileHandler(
    LOG_DIR / "tools_server.log", 
    when="D", 
    interval=1, 
    backupCount=7, 
    encoding="utf-8"
)
logging.basicConfig(
    level=logging.DEBUG, 
    handlers=[_handler], 
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("tools_server").debug

log("=== 完全模块化的tools_server启动 ===")

# 创建MCP服务器
mcp = FastMCP("local-tools")

# 注册所有工具
tool_instances = register_all_tools(mcp)

log(f"已注册工具: {list(tool_instances.keys())}")

if __name__ == "__main__":
    # 通过 stdio 运行
    mcp.run(transport="stdio")
