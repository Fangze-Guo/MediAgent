# src/server_new/mediagent/controller/__init__.py
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os


from pydantic_settings import BaseSettings, SettingsConfigDict

from .user_controller import router as user_router

# 数据目录（保持你的逻辑）
try:
    from ..paths import DATA_DIR
except Exception:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"

class Settings(BaseSettings):
    MODEL_URL=os.getenv("MODEL_URL")
    MODEL_API_KEY=os.getenv("MODEL_API_KEY")
    MODEL=os.getenv("MODEL")


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

    async def ainit(self):
        # 重/异步初始化
        # self.db = await create_async_engine(self.settings.db_url)
        # self.redis = await aioredis.from_url(self.settings.redis_url)
        # self.llm = AsyncLLMClient(...)
        # self.bg_task = asyncio.create_task(worker(...))
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
