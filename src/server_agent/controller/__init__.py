"""
Controllers包 - 统一管理所有API控制器
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.server_agent.exceptions import setup_exception_handlers
from .ChatController import ChatController
from .ConversationController import ConversationController
from .FileController import FileController
from .progress_controller import router as progress_router
from .system_controller import SystemController
from .user_controller import UserController


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="MediAgent Backend",
        description="智能医疗助手后端API",
        version="2.0.0"
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
    chat_controller = ChatController()
    file_controller = FileController()
    system_controller = SystemController()
    user_controller = UserController()
    conversation_controller = ConversationController()

    # 注册路由
    app.include_router(chat_controller.router)
    app.include_router(file_controller.router)
    app.include_router(system_controller.router)
    app.include_router(user_controller.router)
    app.include_router(progress_router)
    app.include_router(conversation_controller.router)

    # 设置异常处理器
    setup_exception_handlers(app)

    return app


# 导出主要接口
__all__ = [
    'create_app',
    'ChatController',
    'FileController',
    'SystemController',
    'UserController',
    'ConversationController'
]
