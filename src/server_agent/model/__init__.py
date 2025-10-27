"""
Model包 - 统一管理所有数据模型
"""
from .dto.chat.ChatRequest import ChatRequest
from .dto.dataset import CreateDatasetRequest, UpdateDatasetRequest
from .dto.file.BatchDeleteFilesRequest import BatchDeleteFilesRequest
from .dto.file.CreateFolderRequest import CreateFolderRequest
from .dto.file.DeleteFileRequest import DeleteFileRequest
from .dto.user.UserLoginRequest import UserLoginRequest
from .dto.user.UserRegisterRequest import UserRegisterRequest
from .entity.ChatInfo import ChatInfo
from .entity.ConversationInfo import ConversationInfo
from .entity.DatasetInfo import DatasetInfo
from .entity.FileInfo import FileInfo
from .entity.ToolCallInfo import ToolCallInfo
from .entity.UserInfo import UserInfo
from .vo.DatasetVO import DatasetVO
from .vo.FileListVO import FileListVO
from .vo.UserVO import UserVO

# 重建模型以解决前向引用问题
ChatRequest.model_rebuild()
ChatInfo.model_rebuild()

__all__ = [
    'ChatRequest',
    'CreateDatasetRequest',
    'UpdateDatasetRequest',
    'BatchDeleteFilesRequest',
    'CreateFolderRequest',
    'DeleteFileRequest',
    'UserLoginRequest',
    'UserRegisterRequest',
    'ChatInfo',
    'ConversationInfo',
    'DatasetInfo',
    'FileInfo',
    'ToolCallInfo',
    'UserInfo',
    'DatasetVO',
    'FileListVO',
    'UserVO'
]
