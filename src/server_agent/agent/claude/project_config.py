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


# 预定义项目配置
PROJECT_CONFIGS: Dict[str, ProjectConfig] = {
    "gl-nict": ProjectConfig(
        project_id="gl-nict",
        project_name="GL-NICT 肺癌分析",
        base_dir=Path("/home/fetters/project/GL-NICT"),
        system_prompt="""【项目专属：GL-NICT 肺癌新辅助治疗影像分析】

你是 GL-NICT 项目的肺癌影像 AI 分析助手，专注于新辅助化疗前后 CT 影像分析与主要病理缓解（MPR）预测。

【GL-NICT 专属规则】
- pre/post CT 必须同时处理，任何任务不得只处理其中一个时间点
- MPR 预测需要临床基线特征，若用户未提供须主动询问后再执行
- 所有影像分析结果需给出直观的临床解读，不暴露技术细节""",
        allow_execute=False,
    ),
}


def get_project_config(project_id: str) -> Optional[ProjectConfig]:
    """获取项目配置"""
    return PROJECT_CONFIGS.get(project_id)


def list_available_projects() -> List[str]:
    """列出所有可用项目"""
    return list(PROJECT_CONFIGS.keys())
