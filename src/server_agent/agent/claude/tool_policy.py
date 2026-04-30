"""
工具策略模块 - 在工具执行前强制校验工具名和参数
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .filesystem_sandbox import FileSystemSandbox
    from .project_config import ProjectConfig
except ImportError:
    from filesystem_sandbox import FileSystemSandbox
    from project_config import ProjectConfig

logger = logging.getLogger(__name__)

# 需要校验路径参数的工具及其路径字段
TOOLS_WITH_PATH_PARAMS: Dict[str, List[str]] = {
    "view": ["path"],
    "save-file": ["path"],
    "str-replace-editor": ["path"],
    "remove-files": ["file_paths"],  # 列表类型
    "codebase-retrieval": [],  # 无路径参数
}


class ToolPolicy:
    """工具策略：白名单 + 参数校验"""

    def __init__(self, project_config: ProjectConfig):
        self.project_config = project_config
        self.sandbox = FileSystemSandbox(project_config.base_dir)
        self.allowed_tools = set(project_config.allowed_tools)

    def validate_tool_call(
        self, tool_name: str, input_data: Any
    ) -> tuple[bool, Optional[str]]:
        """
        校验工具调用是否合法

        Args:
            tool_name: 工具名称
            input_data: 工具输入参数

        Returns:
            (allowed, deny_reason) - allowed=True 表示允许，deny_reason 为拒绝原因
        """
        # 1. 工具白名单检查
        if tool_name not in self.allowed_tools:
            reason = f"工具 {tool_name} 不在项目 {self.project_config.project_id} 的白名单中"
            logger.warning(f"[ToolPolicy] {reason}")
            return False, reason

        # 2. 路径参数校验
        if isinstance(input_data, dict):
            path_fields = TOOLS_WITH_PATH_PARAMS.get(tool_name, [])
            for field in path_fields:
                value = input_data.get(field)
                if value is None:
                    continue

                # 处理列表类型（如 remove-files 的 file_paths）
                paths = value if isinstance(value, list) else [value]
                for p in paths:
                    if not self.sandbox.validate_path(p):
                        reason = (
                            f"路径 {p} 不在项目 "
                            f"{self.project_config.project_id} 目录内"
                        )
                        logger.warning(f"[ToolPolicy] {reason}")
                        return False, reason

        logger.debug(f"[ToolPolicy] 允许工具调用: {tool_name}")
        return True, None
