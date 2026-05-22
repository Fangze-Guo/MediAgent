"""
项目配置模块 - 定义每个项目的隔离配置
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ProjectConfig:
    """项目配置"""
    project_id: str  # 项目唯一标识，如 "bc", "spine"
    project_name: str  # 项目显示名称
    base_dir: Path  # 项目根目录（绝对路径）
    system_prompt: str  # 项目专属的 system prompt
    max_sessions_per_user: int = 5  # 每个用户最大会话数
    session_timeout: int = 3600  # 会话超时时间（秒）
    
    # 安全配置
    allow_file_read: bool = True  # 是否允许读取文件
    allow_file_write: bool = True  # 是否允许写入文件
    allow_execute: bool = False  # 是否允许执行命令
    allowed_file_extensions: List[str] = field(default_factory=lambda: [".nii", ".nii.gz", ".json", ".csv", ".xlsx"])
    
    # 资源限制
    max_file_size_mb: int = 500  # 最大文件大小
    max_output_size_mb: int = 1000  # 最大输出大小


# 项目配置字典 - 运行时由 AgentService.sync_to_project_configs() 从 DB 动态填充
PROJECT_CONFIGS: Dict[str, ProjectConfig] = {}


def get_project_config(project_id: str) -> Optional[ProjectConfig]:
    """获取项目配置"""
    return PROJECT_CONFIGS.get(project_id)


def list_available_projects() -> List[str]:
    """列出所有可用项目"""
    return list(PROJECT_CONFIGS.keys())
