#作为整个服务器的启动入口
from mediagent.controllers import create_app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000,env_file=".env")
