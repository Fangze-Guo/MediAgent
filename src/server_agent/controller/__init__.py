"""
Controllers包 - 统一管理所有API控制器
"""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.server_agent.agent.conversation_agent import AgentConfig, ConversationAgent
from src.server_agent.configs.config_provider import ConfigProvider
from src.server_agent.exceptions import setup_exception_handlers
from src.server_agent.runtime_registry import RuntimeRegistry

from .clinical_tools.CodeAgentController import CodeAgentController
from .ConversationController import ConversationController
from .FileController import FileController
from .KnowledgeBaseController import KnowledgeBaseController
from .ModelController import ModelController
from .SkillController import SkillController
from .UserController import UserController

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    启动期间初始化所有全局单例并挂载到 app.state。
    """
    # ---- Mappers ----
    from src.server_agent.mapper.CodeAgentMapper import CodeAgentMapper
    from src.server_agent.mapper.ConversationMapper import ConversationMapper
    from src.server_agent.mapper.KnowledgeBaseMapper import KnowledgeBaseMapper

    code_agent_mapper = CodeAgentMapper()
    await code_agent_mapper.init()

    conv_mapper = ConversationMapper()
    await conv_mapper.init()

    kb_mapper = KnowledgeBaseMapper()
    await kb_mapper.init()

    app.state.code_agent_mapper = code_agent_mapper
    app.state.conv_mapper = conv_mapper

    # ---- Skill task manager ----
    from src.server_agent.service.SkillTaskManager import get_skill_task_manager

    skill_task_manager = get_skill_task_manager()
    skill_task_manager._mapper = code_agent_mapper
    await skill_task_manager.restore_from_db()

    # ---- Model config provider ----
    provider = ConfigProvider()
    app.state.config_provider = provider

    # ---- Conversation agent ----
    snapshot = provider.get_snapshot()
    agent_cfg = AgentConfig(
        model=snapshot.current_model_id if snapshot else os.getenv("MODEL", "qwen3-30b-a3b"),
        api_key=snapshot.api_key if snapshot else os.getenv("MODEL_API_KEY"),
        base_url=snapshot.base_url if snapshot else os.getenv("MODEL_URL"),
    )
    agent = ConversationAgent(agent_cfg)
    registry = RuntimeRegistry(agent)
    app.state.runtime_registry = registry

    logger.info("[LIFESPAN] Application startup completed")

    try:
        yield
    finally:
        logger.info("[LIFESPAN] Application shutdown started")
        from src.server_agent.agent.claude.claude_agent import shutdown_all_agents
        await shutdown_all_agents()
        await code_agent_mapper.close()
        await conv_mapper.close()
        logger.info("[LIFESPAN] Application shutdown completed")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="MediAgent Backend",
        description="智能医学助手后端API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载静态文件服务（必须在路由注册之前）
    static_dir = Path(__file__).parent.parent / "static"
    print(f"🗂️  静态文件目录: {static_dir}")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        print(f"✅ 静态文件服务已挂载: /static -> {static_dir}")
    else:
        print(f"❌ 静态文件目录不存在: {static_dir}")

    # 创建控制器实例
    file_controller = FileController()
    user_controller = UserController()
    conversation_controller = ConversationController()
    model_controller = ModelController()
    skill_controller = SkillController()
    code_agent_controller = CodeAgentController()
    knowledge_base_controller = KnowledgeBaseController()

    # 注册路由
    app.include_router(file_controller.router)
    app.include_router(user_controller.router)
    app.include_router(conversation_controller.router)
    app.include_router(model_controller.router)
    app.include_router(skill_controller.router)
    app.include_router(code_agent_controller.router)
    app.include_router(knowledge_base_controller.router)
    # 设置异常处理器
    setup_exception_handlers(app)

    return app


# 导出主要接口
__all__ = [
    "create_app",
    "FileController",
    "UserController",
    "ConversationController",
    "ModelController",
    "SkillController",
    "CodeAgentController",
    "KnowledgeBaseController",
]
