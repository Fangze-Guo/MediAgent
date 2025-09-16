"""
数据访问层 - 处理数据库操作
"""
from .user_mapper import UserMapper, user_mapper
from .base_mapper import BaseMapper
from .paths import in_data, ensure_data_dirs, DATA_DIR
from .config import DatabaseConfig, default_config
from .migrations import DatabaseMigrator, Migration, run_migrations

__all__ = [
    # 用户数据访问
    'UserMapper',
    'user_mapper',
    
    # 基础类
    'BaseMapper',
    
    # 工具
    'in_data',
    'ensure_data_dirs',
    'DATA_DIR',
    
    # 配置
    'DatabaseConfig',
    'default_config',
    
    # 迁移
    'DatabaseMigrator',
    'Migration',
    'run_migrations'
]
