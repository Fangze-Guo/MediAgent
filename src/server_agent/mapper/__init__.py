"""
数据访问层 - 处理数据库操作
"""
from .UserMapper import UserMapper
from .DatasetMapper import DatasetMapper
from .BaseMapper import BaseMapper
from .paths import in_data, ensure_data_dirs, get_db_path, DATA_DIR

__all__ = [
    # 用户数据访问
    'UserMapper',
    'DatasetMapper',

    # 基础类
    'BaseMapper',

    # 工具
    'in_data',
    'ensure_data_dirs',
    'get_db_path',
    'DATA_DIR',
]
