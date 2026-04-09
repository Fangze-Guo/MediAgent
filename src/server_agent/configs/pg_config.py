"""
PostgreSQL配置管理
管理医学咨询功能的PostgreSQL数据库连接配置
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


@dataclass(frozen=True)
class PostgresConfig:
    """PostgreSQL配置类"""
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> 'PostgresConfig':
        """从环境变量创建配置"""
        return cls(
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5432")),
            database=os.getenv("PG_DATABASE", "mediagent"),
            user=os.getenv("PG_USER", "postgres"),
            password=os.getenv("PG_PASSWORD", "")
        )

    def get_dsn(self) -> str:
        """获取PostgreSQL DSN字符串"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class PostgresConfigProvider:
    """PostgreSQL配置提供者"""

    def __init__(self):
        self._config = PostgresConfig.from_env()

    def get_config(self) -> PostgresConfig:
        """获取PostgreSQL配置"""
        return self._config

    def reload(self) -> None:
        """重新加载配置（从环境变量）"""
        self._config = PostgresConfig.from_env()


# 全局配置提供者实例
_postgres_config_provider = PostgresConfigProvider()


def get_pg_config() -> PostgresConfig:
    """获取PostgreSQL配置（全局单例）"""
    return _postgres_config_provider.get_config()
