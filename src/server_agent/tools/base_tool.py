"""
基础工具类
提供通用的工具方法和错误处理
"""
import json
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# 设置日志
log = logging.getLogger("tools").debug


class BaseTool:
    """基础工具类"""
    
    def __init__(self, mcp_server: FastMCP = None):
        self.log = log
        self.mcp_server = mcp_server
    
    def register_tools(self):
        """注册工具到MCP服务器 - 子类需要重写此方法"""
        pass
    
    def _json_response(
        self, 
        code: int, 
        stdout: str = "", 
        stderr: str = "", 
        extra: Optional[Dict[str, Any]] = None
    ) -> str:
        """统一的JSON响应格式"""
        payload = {
            "code": code,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timestamp": time.time()
        }
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)
    
    def _validate_file_path(self, file_path: str, must_exist: bool = True) -> tuple[bool, str, Path]:
        """验证文件路径"""
        try:
            path = Path(file_path)
            if must_exist and not path.exists():
                return False, f"文件不存在: {path}", path
            return True, "", path
        except Exception as e:
            return False, f"路径错误: {e}", Path()
    
    def _ensure_output_dir(self, output_path: Path) -> tuple[bool, str]:
        """确保输出目录存在"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return True, ""
        except Exception as e:
            return False, f"创建输出目录失败: {e}"
    
    def _log_operation(self, operation: str, **kwargs):
        """记录操作日志"""
        self.log(f"[{operation}] {kwargs}")
