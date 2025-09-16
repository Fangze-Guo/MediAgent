"""
数据库配置管理
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from .paths import DATA_DIR


@dataclass
class DatabaseConfig:
    """数据库配置"""
    # 连接配置
    db_path: Path = field(default_factory=lambda: DATA_DIR / "db" / "app.sqlite3")
    timeout: float = 30.0
    isolation_level: Optional[str] = None
    
    # 连接池配置
    max_connections: int = 10
    min_connections: int = 1
    
    # SQLite 优化配置
    pragma_settings: Dict[str, Any] = field(default_factory=lambda: {
        "foreign_keys": "ON",
        "journal_mode": "WAL",
        "synchronous": "NORMAL",
        "busy_timeout": 30000,
        "cache_size": 10000,
        "temp_store": "MEMORY",
        "mmap_size": 268435456,  # 256MB
        "page_size": 4096,
        "auto_vacuum": "INCREMENTAL"
    })
    
    # 安全配置
    enable_wal_mode: bool = True
    enable_foreign_keys: bool = True
    enable_secure_delete: bool = False
    
    # 性能配置
    enable_query_plan_cache: bool = True
    enable_statistics: bool = True
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """从环境变量创建配置"""
        config = cls()
        
        # 从环境变量读取配置
        if db_path := os.getenv("MEDIAGENT_DB_PATH"):
            config.db_path = Path(db_path)
        
        if timeout := os.getenv("MEDIAGENT_DB_TIMEOUT"):
            config.timeout = float(timeout)
        
        if max_conn := os.getenv("MEDIAGENT_DB_MAX_CONNECTIONS"):
            config.max_connections = int(max_conn)
        
        if min_conn := os.getenv("MEDIAGENT_DB_MIN_CONNECTIONS"):
            config.min_connections = int(min_conn)
        
        # 布尔配置
        config.enable_wal_mode = os.getenv("MEDIAGENT_DB_WAL_MODE", "true").lower() == "true"
        config.enable_foreign_keys = os.getenv("MEDIAGENT_DB_FOREIGN_KEYS", "true").lower() == "true"
        config.enable_secure_delete = os.getenv("MEDIAGENT_DB_SECURE_DELETE", "false").lower() == "true"
        
        return config
    
    def get_pragma_sql(self) -> str:
        """获取 PRAGMA 设置 SQL"""
        pragmas = []
        
        for key, value in self.pragma_settings.items():
            if key == "foreign_keys" and not self.enable_foreign_keys:
                continue
            if key == "journal_mode" and not self.enable_wal_mode:
                continue
            
            pragmas.append(f"PRAGMA {key} = {value};")
        
        return "\n".join(pragmas)
    
    def validate(self) -> bool:
        """验证配置"""
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        
        if self.max_connections <= 0:
            raise ValueError("Max connections must be positive")
        
        if self.min_connections <= 0:
            raise ValueError("Min connections must be positive")
        
        if self.min_connections > self.max_connections:
            raise ValueError("Min connections cannot be greater than max connections")
        
        return True


# 默认配置实例
default_config = DatabaseConfig.from_env()
