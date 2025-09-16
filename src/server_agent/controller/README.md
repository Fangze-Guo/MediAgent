# Controller 层 - API 控制器

## 📁 文件结构

```
controller/
├── __init__.py          # 控制器注册和 FastAPI 应用创建
├── base.py              # 基础控制器类
├── user_controller.py   # 用户管理 API
├── chat_controller.py   # 聊天对话 API
├── file_controller.py    # 文件管理 API
├── tool_controller.py   # 工具管理 API
└── system_controller.py # 系统管理 API
```

## 🎯 设计原则

### 职责分离
- **Controller**: 只负责接口暴露和请求响应
- **Service**: 业务逻辑处理（在 service 层）
- **Mapper**: 数据访问（在 mapper 层）

### 统一接口
- 所有控制器继承自 `BaseController`
- 统一的异常处理机制
- 标准化的响应格式

## 🚀 使用示例

### 基础控制器
```python
class BaseController:
    def __init__(self, prefix: str = "", tags: List[str] = None):
        self.router = APIRouter(prefix=prefix, tags=tags or [])
        self.agent = agent  # AI Agent 实例
    
    async def ensure_initialized(self):
        """确保 agent 已初始化"""
        # 初始化逻辑
```

### 具体控制器
```python
class UserController(BaseController):
    def __init__(self):
        super().__init__(prefix="/user", tags=["用户管理"])
        self.user_service = UserService()  # 注入服务层
        self._register_routes()
    
    def _register_routes(self):
        @self.router.post("/register")
        async def register(payload: RegisterIn):
            # 调用服务层处理业务逻辑
            result = await self.user_service.register_user(
                payload.user_name, payload.password
            )
            return result
```

## 📋 API 端点

### 用户管理 (`/user`)
- `POST /register` - 用户注册
- `POST /login` - 用户登录
- `GET /info` - 获取用户信息
- `PUT /info` - 更新用户信息

### 聊天对话 (`/chat`)
- `POST /` - 普通聊天
- `POST /stream` - 流式聊天

### 文件管理 (`/files`)
- `POST /upload` - 上传文件
- `GET /` - 获取文件列表
- `POST /delete` - 删除文件
- `GET /serve/{file_id}` - 下载文件

### 工具管理 (`/tools`)
- `GET /` - 获取工具列表
- `POST /refresh` - 刷新工具
- `POST /call` - 调用工具

### 系统管理 (`/system`)
- `GET /health` - 健康检查
- `GET /selftest` - 系统自测

## 🔧 开发指南

### 添加新控制器
1. 继承 `BaseController`
2. 注入相应的 Service
3. 注册路由方法
4. 在 `__init__.py` 中注册

### 异常处理
- 使用统一的异常类
- 自动转换为 HTTP 响应
- 提供详细的错误信息

### 数据验证
- 使用 Pydantic 模型
- 自动参数验证
- 类型安全保证
