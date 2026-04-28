"""
依赖注入模块
提供全局可复用的依赖项
"""
from .auth import get_current_user, get_current_admin_user
from .services import (
    get_user_service,
    get_conversation_service,
    get_code_agent_service,
    get_file_service,
    get_dataset_service,
    get_task_service,
    get_model_config_service,
    get_app_store_service
)

__all__ = [
    # 认证依赖
    "get_current_user",
    "get_current_admin_user",
    # 服务依赖
    "get_user_service",
    "get_conversation_service",
    "get_code_agent_service",
    "get_file_service",
    "get_dataset_service",
    "get_task_service",
    "get_model_config_service",
    "get_app_store_service",
]
