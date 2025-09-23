# src/server_new/mediagent/controller/__init__.py
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os


from pydantic_settings import BaseSettings, SettingsConfigDict

from .user_controller import router as user_router

from mediagent.modules.task_manager import TaskManager
from mediagent.paths import in_data
from mediagent.paths import in_mediagent

# 数据目录（保持你的逻辑）
try:
    from mediagent.paths import DATA_DIR
except Exception:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"

class Settings(BaseSettings):
    MODEL_URL=os.getenv("MODEL_URL")
    MODEL_API_KEY=os.getenv("MODEL_API_KEY")
    MODEL=os.getenv("MODEL")

    PUBLIC_DATASETS_ROOT = in_data("files", "public")  # 例如：r"D:\datasets\public"
    WORKSPACE_ROOT = in_data("files", "private")  # 例如：r"D:\projects\MediAgent\workspace"
    DATABASE_FILE = in_data("db", "app.sqlite3")  # 例如：r"D:\projects\MediAgent\data\app.sqlite3"  (必须已存在)
    MCPSERVER_FILE = in_mediagent("mcp_server_tools","mcp_server.py")  # 例如：r"D:\projects\MediAgent\server\mcp_server.py"  (必须已存在)


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
        self.tm: TaskManager | None = None

    async def ainit(self):
        # 重/异步初始化

        self.tm = TaskManager(
            public_datasets_source_root=self.settings.PUBLIC_DATASETS_ROOT,
            workspace_root=self.settings.WORKSPACE_ROOT,
            database_file=self.settings.DATABASE_FILE,
            mcpserver_file=self.settings.MCPSERVER_FILE
        )
        self.tm.start()#完成对任务管理器的初始化，而任务管理器会连带着把mcp服务器一起初始化

        pass

    async def aclose(self):
        # 统一释放
        # if self.bg_task: self.bg_task.cancel(); await self.bg_task
        # if self.redis: await self.redis.close()
        # if self.db: await self.db.dispose()
        # if self.llm: await self.llm.aclose()
        pass

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


    return app

__all__ = ["create_app", "Settings", "Services"]
