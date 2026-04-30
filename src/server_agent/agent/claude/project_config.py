"""
项目配置模块 - 定义每个项目的隔离配置
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional


@dataclass
class ProjectConfig:
    """项目配置"""
    project_id: str  # 项目唯一标识，如 "bc", "spine"
    project_name: str  # 项目显示名称
    base_dir: Path  # 项目根目录（绝对路径）
    allowed_skills: List[str]  # 允许的 skill 列表
    allowed_tools: List[str]  # 允许的工具白名单
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
    "bc": ProjectConfig(
        project_id="bc",
        project_name="体成分分析",
        base_dir=Path("/home/fetters/project/BC"),
        allowed_skills=[
            "bodycomp-seg-nnunet",
            "ct-bodycomp-metrics-thoracic",
            "nice-bc",
            "spine-seg-nnunet",  # BC 项目需要脊柱分割作为前置
        ],
        allowed_tools=[
            "view",
            "codebase-retrieval",
            "save-file",
            "str-replace-editor",
        ],
        system_prompt="""你是体成分分析助手。

你的职责：
1. 帮助用户进行 CT 图像的体成分分割和定量分析
2. 使用 nnUNet 进行体成分和脊柱分割
3. 基于胸椎范围计算体成分指标（肌肉、脂肪等）
4. 生成分析报告和统计表格

可用功能：
- 体成分分割（bodycomp-seg-nnunet）
- 脊柱分割（spine-seg-nnunet）
- 胸椎范围体成分统计（ct-bodycomp-metrics-thoracic）
- NICE-BC 指标计算（nice-bc）

安全规则：
- 只能访问 BC 项目目录下的文件
- 不能访问系统级信息
- 不能执行系统命令
- 所有输出面向用户友好，不暴露技术细节
""",
        allow_execute=False,  # BC 项目不允许执行命令
    ),
    
    "spine": ProjectConfig(
        project_id="spine",
        project_name="脊柱分析",
        base_dir=Path("/home/fetters/project/Spine"),
        allowed_skills=[
            "spine-seg-nnunet",
        ],
        allowed_tools=[
            "view",
            "codebase-retrieval",
            "save-file",
            "str-replace-editor",
        ],
        system_prompt="""你是脊柱分析助手。

你的职责：
1. 帮助用户进行 CT 图像的脊柱分割
2. 使用 nnUNet 进行脊柱椎体分割
3. 识别和标注椎体位置

可用功能：
- 脊柱分割（spine-seg-nnunet）

安全规则：
- 只能访问 Spine 项目目录下的文件
- 不能访问系统级信息
- 不能执行系统命令
- 所有输出面向用户友好，不暴露技术细节
""",
        allow_execute=False,
    ),
}


def get_project_config(project_id: str) -> Optional[ProjectConfig]:
    """获取项目配置"""
    return PROJECT_CONFIGS.get(project_id)


def list_available_projects() -> List[str]:
    """列出所有可用项目"""
    return list(PROJECT_CONFIGS.keys())
