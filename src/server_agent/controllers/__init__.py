"""
Controllers包 - 统一管理所有API控制器
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .chat_controller import ChatController
from .tool_controller import ToolController
from .file_controller import FileController
from .local_file_controller import LocalFileController
from .system_controller import SystemController


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
    tool_controller = ToolController()
    file_controller = FileController()
    local_file_controller = LocalFileController()
    system_controller = SystemController()

    # 注册路由
    app.include_router(chat_controller.router)
    app.include_router(tool_controller.router)
    app.include_router(file_controller.router)
    app.include_router(local_file_controller.router)
    app.include_router(system_controller.router)

    return app


def get_all_controllers():
    """获取所有控制器实例"""
    return {
        'chat': ChatController(),
        'tool': ToolController(),
        'file': FileController(),
        'local_file': LocalFileController(),
        'system': SystemController(),
    }


# 导出主要接口
__all__ = [
    'create_app',
    'get_all_controllers',
    'ChatController',
    'ToolController', 
    'FileController',
    'LocalFileController',
    'SystemController',
]
