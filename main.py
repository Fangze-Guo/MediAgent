"""
主应用文件
使用绝对导入启动 MediAgent 后端服务
"""

import logging

from src.server_agent.controller import create_app

logging.basicConfig(
    level=logging.INFO,  # 显示 INFO 及以上
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn

    print("🚀 启动 MediAgent 后端服务...")
    print("🌐 访问地址: http://localhost:8000")
    print("📚 API 文档: http://localhost:8000/docs")
    print("📖 ReDoc: http://localhost:8000/redoc")
    print("按 Ctrl+C 停止服务")
    uvicorn.run(app, host="0.0.0.0", port=8000)
