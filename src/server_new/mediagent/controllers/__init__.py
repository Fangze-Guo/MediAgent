# src/server_new/mediagent/controller/__init__.py
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os


from pydantic_settings import BaseSettings, SettingsConfigDict

from .user_controller import router as user_router
from .test_controller import router as test_router

from mediagent.modules.task_manager import AsyncTaskManager
from mediagent.paths import in_data
from mediagent.paths import in_mediagent

# 数据目录（保持你的逻辑）
try:
    from mediagent.paths import DATA_DIR
except Exception:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"

class Settings:
    """最简单的配置容器：不做校验、不自动读取 .env，仅存放数值。"""
    def __init__(self):
        # 环境相关（可选：保留 None）
        self.MODEL_URL = os.getenv("MODEL_URL")       # 或者写死: None
        self.MODEL_API_KEY = os.getenv("MODEL_API_KEY")
        self.MODEL = os.getenv("MODEL")

        # 供 Services 使用的路径
        self.data_dir: Path = DATA_DIR

        # TaskManager 需要的路径/文件
        self.PUBLIC_DATASETS_ROOT: Path = in_data("files", "public")
        self.WORKSPACE_ROOT: Path = in_data("files", "private")
        self.DATABASE_FILE: Path = in_data("db", "app.sqlite3")
        self.MCPSERVER_FILE: Path = in_mediagent("mcp_server_tools", "mcp_server.py")


class Services:
    def __init__(self, settings: Settings):
        self.settings = settings
        # 轻量：路径/日志器/纯内存对象等
        self.paths = {"incoming": settings.data_dir / "incoming"}
        self.logger = None  # 例如：structlog.get_logger(__name__)

        # 重资源句柄先置空，ainit 里真正创建
        self.db = None
        self.redis = None
        self.llm = None
        self.bg_task = None

        # 新增：唯一 TaskManager 实例占位
        self.tm: AsyncTaskManager | None = None

    async def ainit(self):
        # 重/异步初始化

        self.tm = AsyncTaskManager(
            public_datasets_source_root=self.settings.PUBLIC_DATASETS_ROOT,
            workspace_root=self.settings.WORKSPACE_ROOT,
            database_file=self.settings.DATABASE_FILE,
            mcpserver_file=self.settings.MCPSERVER_FILE
        )

        await self.tm.astart()

    async def aclose(self):
        # 统一释放

        if self.tm is not None:
            await self.tm.aclose()
            self.tm = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    services = Services(settings)
    app.state.settings = settings
    app.state.services = services
    await services.ainit()          # ✅ 重/异步初始化放这里
    try:
        yield
    finally:
        await services.aclose()     # ✅ 对应释放


def create_app() -> FastAPI:
    app = FastAPI(
        title="MediAgent Backend",
        description="智能医疗助手后端 API（重构主框架）",
        version="3.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(user_router)
    app.include_router(test_router)


    return app

__all__ = ["create_app", "Settings", "Services"]
