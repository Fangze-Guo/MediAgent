"""
服务依赖模块
提供统一的服务实例依赖注入
"""
from typing import Optional

from src.server_agent.service.UserService import UserService
from src.server_agent.service.ConversationService import ConversationService
from src.server_agent.service.FileService import FileService
from src.server_agent.service.DatasetService import DatasetService
from src.server_agent.service.TaskService import TaskService
from src.server_agent.service.ModelConfigService import ModelConfigService
from src.server_agent.service.AppStoreService import AppStoreService


# ==================== 服务实例缓存 ====================
# 使用模块级变量缓存服务实例，避免重复创建

_user_service: Optional[UserService] = None
_conversation_service: Optional[ConversationService] = None
_file_service: Optional[FileService] = None
_dataset_service: Optional[DatasetService] = None
_task_service: Optional[TaskService] = None
_model_config_service: Optional[ModelConfigService] = None
_app_store_service: Optional[AppStoreService] = None


# ==================== 服务依赖函数 ====================

def get_user_service() -> UserService:
    """获取用户服务实例"""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service


def get_conversation_service() -> ConversationService:
    """获取会话服务实例"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService(
            database_path="src/server_new/data/db/app.sqlite3",
            conversation_root="src/server_agent/conversations"
        )
    return _conversation_service


def get_file_service() -> FileService:
    """获取文件服务实例"""
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service


def get_dataset_service() -> DatasetService:
    """获取数据集服务实例"""
    global _dataset_service
    if _dataset_service is None:
        _dataset_service = DatasetService()
    return _dataset_service


def get_task_service() -> TaskService:
    """获取任务服务实例"""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service


def get_model_config_service() -> ModelConfigService:
    """获取模型配置服务实例"""
    global _model_config_service
    if _model_config_service is None:
        _model_config_service = ModelConfigService()
    return _model_config_service


def get_app_store_service() -> AppStoreService:
    """获取应用商店服务实例"""
    global _app_store_service
    if _app_store_service is None:
        _app_store_service = AppStoreService()
    return _app_store_service


# CodeAgent 服务需要特殊处理，因为它依赖 FastAPI app.state
def get_code_agent_service():
    """
    获取 CodeAgent 服务实例
    注意：这个服务需要从 FastAPI Request 中获取
    """
    # 这个函数暂时保留，实际使用时需要从 request.app.state 获取
    raise NotImplementedError(
        "CodeAgent service should be accessed via request.app.state.code_agent_mapper"
    )


# ==================== 清理函数 ====================

def clear_service_cache():
    """清理所有服务缓存（用于测试或重启）"""
    global _user_service, _conversation_service, _file_service
    global _dataset_service, _task_service, _model_config_service, _app_store_service
    
    _user_service = None
    _conversation_service = None
    _file_service = None
    _dataset_service = None
    _task_service = None
    _model_config_service = None
    _app_store_service = None
