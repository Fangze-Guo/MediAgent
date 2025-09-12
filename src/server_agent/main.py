"""
主应用文件
使用controllers包的统一入口
"""
from controllers import create_app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
