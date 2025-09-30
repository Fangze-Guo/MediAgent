"""
Controllers包 - 统一管理所有API控制器
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mediagent.modules.conversation_manager import ConversationManager
from mediagent.modules.task_manager import AsyncTaskManager
from src.server_agent.configs.config_provider import ConfigProvider
from src.server_agent.exceptions import setup_exception_handlers
from src.server_agent.runtime_registry import RuntimeRegistry
from .ConversationController import ConversationController
from .FileController import FileController
from .ModelController import ModelController
from .UserController import UserController

# 数据目录（保持你的逻辑）
try:
    from mediagent.paths import DATA_DIR, in_data, in_mediagent
except Exception:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class Settings:
    """最简单的配置容器：不做校验、不自动读取 .env，仅存放数值。"""

    def __init__(self):
        # 环境相关（可选：保留 None）
        self.MODEL_URL = os.getenv("MODEL_URL")  # 或者写死: None
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
    """
    在应用启动期间创建"全局唯一"的 ConfigProvider 与 RuntimeRegistry，
    并挂载到 app.state，供所有路由按需使用
    """
    settings = Settings()
    services = Services(settings)
    app.state.settings = settings
    app.state.services = services
    await services.ainit()  # ✅ 重/异步初始化放这里
    # 配置提供者与运行态注册器
    provider = ConfigProvider()
    app.state.config_provider = provider
    registry = RuntimeRegistry(
        task_manager=services.tm,
        conversation_manager=ConversationManager(str(settings.DATABASE_FILE), str("src/server_agent/conversations")),
        database_path=str(settings.DATABASE_FILE),
        stream_id="agentA_internal_stream"
    )
    app.state.runtime_registry = registry
    # 首次刷新运行实例
    registry.refresh_runtime(provider.get_snapshot())
    try:
        yield
    finally:
        await services.aclose()  # ✅ 对应释放


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="MediAgent Backend",
        description="智能医学助手后端API",
        version="2.0.0",
        lifespan=lifespan
    )

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 创建控制器实例
    file_controller = FileController()
    user_controller = UserController()
    conversation_controller = ConversationController()
    model_controller = ModelController()

    # 注册路由
    app.include_router(file_controller.router)
    app.include_router(user_controller.router)
    app.include_router(conversation_controller.router)
    app.include_router(model_controller.router)

    # 设置异常处理器
    setup_exception_handlers(app)

    return app


# 导出主要接口
__all__ = [
    'create_app',
    'FileController',
    'UserController',
    'ConversationController',
    'ModelController'
]
