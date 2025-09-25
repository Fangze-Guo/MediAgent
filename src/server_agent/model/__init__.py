"""
Model包 - 统一管理所有数据模型
"""
from .dto.chat.ChatRequest import ChatRequest
from .dto.file.BatchDeleteFilesRequest import BatchDeleteFilesRequest
from .dto.file.CreateFolderRequest import CreateFolderRequest
from .dto.file.DeleteFileRequest import DeleteFileRequest
from .dto.user.UserRegisterRequest import UserRegisterRequest
from .entity.ChatInfo import ChatInfo
from .entity.ConversationInfo import ConversationInfo
from .entity.FileInfo import FileInfo
from .entity.ToolCallInfo import ToolCallInfo
from .entity.UserInfo import UserInfo
from .vo.FileListVO import FileListVO

# 重建模型以解决前向引用问题
ChatRequest.model_rebuild()
ChatInfo.model_rebuild()

__all__ = [
    'ChatRequest',
    'BatchDeleteFilesRequest',
    'CreateFolderRequest',
    'DeleteFileRequest',
    'UserRegisterRequest',
    'ChatInfo',
    'ConversationInfo',
    'FileInfo',
    'ToolCallInfo',
    'UserInfo',
    'FileListVO',
]
