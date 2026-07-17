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

from src.server_agent.configs.config_provider import ConfigProvider
from src.server_agent.exceptions import setup_exception_handlers
from src.server_agent.runtime_registry import RuntimeRegistry

from .AgentController import AgentController
from .clinical_tools.CodeAgentController import CodeAgentController
from .ConversationController import ConversationController
from .FileController import FileController
from .KnowledgeBaseController import KnowledgeBaseController
from .ModelController import ModelController
from .PatientController import PatientController
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
    app.state.kb_mapper = kb_mapper
    app.state.code_agent_service.mapper = code_agent_mapper
    app.state.kb_service.mapper = kb_mapper
    await app.state.patient_service.init()

    # ---- Agent mapper (临床智能体 & 全局技能仓库) ----
    from src.server_agent.mapper.AgentMapper import AgentMapper
    from src.server_agent.service.AgentService import AgentService
    from src.server_agent.service.SkillRegistryService import SkillRegistryService

    agent_mapper = AgentMapper()
    await agent_mapper.init()
    app.state.agent_mapper = agent_mapper

    agent_svc = AgentService(agent_mapper)

    # 将 NICE-BCX 注册为 clinical agent（幂等，已存在则跳过）
    import os
    from pathlib import Path as _Path
    _clinical_agents_dir = _Path(os.getenv("CLINICAL_AGENTS_DIR", os.path.expanduser("~/mediagent/agents")))
    await agent_svc.register_existing_agent(
        agent_id="nice-bcx",
        name="NICE-BCX",
        description="肺癌新辅助治疗影像分析",
        system_prompt="""【项目专属：NICE-BCX 肺癌新辅助治疗影像分析】

你是 NICE-BCX 项目的肺癌影像 AI 分析助手，专注于新辅助化疗前后 CT 影像分析与主要病理缓解（MPR）预测。

【NICE-BCX 专属规则】
- 回答和分析应围绕非小细胞肺癌新辅助治疗场景，重点关注治疗前后 CT、肿瘤变化、体成分变化和 MPR/疗效评估。
- 处理具体患者前，应先确认 patient_id，并基于该患者已有的临床信息和影像资料开展分析；资料缺失时应明确说明缺失项。
- 涉及治疗前后对比时，应同时关注 PRE 和 POST，不应只基于单一时间点给出完整疗效判断。
- 医学结论应表达为辅助分析和风险提示，避免给出确定性诊断或替代医生决策。
""",
        base_dir=str(_clinical_agents_dir / "NICE-BCX"),
    )

    await agent_svc.sync_to_project_configs()

    skill_registry = SkillRegistryService(agent_mapper)
    await skill_registry.sync_from_filesystem()

    # ---- Skill task manager ----
    from src.server_agent.service.SkillTaskManager import get_skill_task_manager

    skill_task_manager = get_skill_task_manager()
    skill_task_manager._mapper = code_agent_mapper
    await skill_task_manager.restore_from_db()

    # ---- Model config provider ----
    provider = ConfigProvider()
    app.state.config_provider = provider

    # ---- Request-scoped conversation agent factory ----
    registry = RuntimeRegistry(provider)
    app.state.runtime_registry = registry

    logger.info("[LIFESPAN] Application startup completed")

    try:
        yield
    finally:
        logger.info("[LIFESPAN] Application shutdown started")
        from src.server_agent.agent.claude.claude_agent import shutdown_all_agents
        from src.server_agent.dependencies.services import close_service_cache
        from src.server_agent.service.clinical_tools.CodeAgentService import shutdown_background_tasks

        await shutdown_background_tasks()
        await shutdown_all_agents()
        for service in getattr(app.state, "shutdown_services", []):
            await service.close()
        await close_service_cache()
        await code_agent_mapper.close()
        await conv_mapper.close()
        await agent_mapper.close()
        await kb_mapper.close()
        await app.state.patient_service.close()
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
    patient_controller = PatientController()
    skill_controller = SkillController()
    code_agent_controller = CodeAgentController()
    knowledge_base_controller = KnowledgeBaseController()
    agent_controller = AgentController()
    app.state.shutdown_services = [
        code_agent_controller.service,
        knowledge_base_controller.kb_service,
    ]
    app.state.code_agent_service = code_agent_controller.service
    app.state.kb_service = knowledge_base_controller.kb_service
    app.state.patient_service = patient_controller.service

    # 注册路由
    app.include_router(file_controller.router)
    app.include_router(user_controller.router)
    app.include_router(conversation_controller.router)
    app.include_router(model_controller.router)
    app.include_router(patient_controller.router)
    app.include_router(skill_controller.router)
    app.include_router(code_agent_controller.router)
    app.include_router(knowledge_base_controller.router)
    app.include_router(agent_controller.router)
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
    "PatientController",
    "SkillController",
    "CodeAgentController",
    "KnowledgeBaseController",
    "AgentController",
]
