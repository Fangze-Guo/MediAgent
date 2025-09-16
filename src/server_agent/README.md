# Server Agent 后端服务

## 📁 项目结构

```
src/server_agent/
├── controller/          # API 控制器层
├── service/            # 业务逻辑层
├── mapper/             # 数据访问层
├── exceptions/         # 异常处理
├── tools/             # 工具模块
├── constants/         # 常量配置
├── agent.py           # AI Agent 核心
├── main.py            # 应用入口
└── tools_server.py    # 工具服务器
```

## 🏗️ 架构设计

### 分层架构
- **Controller**: 处理 HTTP 请求，参数验证，响应格式化
- **Service**: 业务逻辑处理，数据验证，异常处理
- **Mapper**: 数据库操作，数据持久化
- **Exceptions**: 统一异常处理机制

### 设计原则
- **单一职责**: 每层只负责自己的职责
- **依赖注入**: 通过构造函数注入依赖
- **异常统一**: 统一的异常处理和错误码
- **类型安全**: 使用 Pydantic 进行数据验证

## 🚀 快速开始

### 启动服务
```bash
cd src/server_agent
python main.py
```

### API 文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📋 主要功能

- **用户管理**: 注册、登录、信息管理
- **聊天对话**: 普通聊天、流式聊天
- **文件管理**: 上传、下载、浏览
- **工具调用**: AI 工具集成
- **系统监控**: 健康检查、自测

## 🔧 开发指南

### 添加新功能
1. 在 `controller/` 添加 API 端点
2. 在 `service/` 实现业务逻辑
3. 在 `mapper/` 添加数据访问
4. 在 `exceptions/` 定义异常类型

### 代码规范
- 使用类型提示
- 遵循 PEP 8 规范
- 添加文档字符串
- 编写单元测试
