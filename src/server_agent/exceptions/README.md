# Exceptions 层 - 异常处理

## 📁 文件结构

```
exceptions/
├── __init__.py              # 异常处理导出
├── custom_exceptions.py     # 自定义异常类
├── error_codes.py           # 错误码定义
└── exception_handler.py     # 异常处理器
```

## 🎯 设计原则

### 统一异常处理
- **自定义异常**: 继承自 `HTTPException` 或 `MediAgentException`
- **错误码**: 统一的错误码和消息
- **全局处理**: FastAPI 全局异常处理器

### 异常分类
- **验证错误**: 参数验证失败
- **认证错误**: 认证失败
- **授权错误**: 权限不足
- **资源错误**: 资源不存在或冲突
- **服务错误**: 业务逻辑错误
- **数据库错误**: 数据访问错误

## 🚀 使用示例

### 自定义异常类
```python
class ValidationError(MediAgentException):
    """验证错误"""
    def __init__(self, detail: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=400,
            detail=detail,
            error_code=ErrorCode.VALIDATION_ERROR,
            context=context or {}
        )

class AuthenticationError(MediAgentException):
    """认证错误"""
    def __init__(self, detail: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=401,
            detail=detail,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            context=context or {}
        )
```

### 错误码定义
```python
class ErrorCode(Enum):
    """错误码枚举"""
    VALIDATION_ERROR = ("VALIDATION_ERROR", "验证错误", 400)
    AUTHENTICATION_ERROR = ("AUTHENTICATION_ERROR", "认证错误", 401)
    AUTHORIZATION_ERROR = ("AUTHORIZATION_ERROR", "授权错误", 403)
    NOT_FOUND = ("NOT_FOUND", "资源未找到", 404)
    CONFLICT_ERROR = ("CONFLICT_ERROR", "冲突错误", 409)
    DATABASE_ERROR = ("DATABASE_ERROR", "数据库错误", 500)
    SERVICE_ERROR = ("SERVICE_ERROR", "服务错误", 500)
```

### 异常处理器
```python
def setup_exception_handlers(app: FastAPI):
    """设置全局异常处理器"""
    
    @app.exception_handler(MediAgentException)
    async def mediagent_exception_handler(request: Request, exc: MediAgentException):
        """处理自定义异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code.value[0],
                    "message": exc.detail,
                    "context": exc.context
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理通用异常"""
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "内部服务器错误",
                    "context": {"error": str(exc)}
                }
            }
        )
```

## 📋 异常类型

### 业务异常
- `ValidationError` - 参数验证失败
- `ConflictError` - 资源冲突
- `NotFoundError` - 资源不存在
- `ServiceError` - 业务逻辑错误

### 认证授权异常
- `AuthenticationError` - 认证失败
- `AuthorizationError` - 权限不足

### 数据访问异常
- `DatabaseError` - 数据库操作错误

### 基础异常
- `MediAgentException` - 自定义异常基类
- `HTTPException` - FastAPI 异常基类

## 🔧 开发指南

### 使用异常装饰器
```python
from ..exceptions import handle_service_exception, ValidationError

@handle_service_exception
async def service_method(self, param: str) -> Dict[str, Any]:
    """服务方法"""
    if not param:
        raise ValidationError(
            detail="参数不能为空",
            context={"param": param}
        )
    
    # 业务逻辑
    return {"ok": True}
```

### 在 Controller 中使用
```python
from ..exceptions import AuthenticationError, ValidationError

@self.router.post("/login")
async def login(payload: LoginIn):
    """用户登录"""
    if not payload.user_name or not payload.password:
        raise ValidationError(
            detail="用户名和密码不能为空",
            context={"user_name": payload.user_name}
        )
    
    user = await self.user_service.login_user(payload.user_name, payload.password)
    if not user:
        raise AuthenticationError(
            detail="用户名或密码错误",
            context={"user_name": payload.user_name}
        )
    
    return {"token": user.token}
```

### 在 Service 中使用
```python
from ..exceptions import ConflictError, ServiceError

@handle_service_exception
async def register_user(self, user_name: str, password: str) -> Dict[str, Any]:
    """用户注册"""
    # 检查用户名是否已存在
    if await self.user_mapper.check_username_exists(user_name):
        raise ConflictError(
            detail="用户名已存在",
            context={"username": user_name}
        )
    
    # 创建用户
    success = await self.user_mapper.create_user(uid, user_name, password)
    if not success:
        raise ServiceError(
            detail="用户创建失败",
            service_name="register_user"
        )
    
    return {"ok": True, "uid": uid}
```

### 在 Mapper 中使用
```python
from ..exceptions import DatabaseError, handle_mapper_exception

@handle_mapper_exception
async def find_user_by_name(self, user_name: str) -> Optional[User]:
    """查找用户"""
    try:
        result = await self.execute_query(
            "SELECT * FROM users WHERE user_name = ?",
            (user_name,),
            fetch_one=True
        )
        return User.from_result(result) if result else None
    except Exception as e:
        raise DatabaseError(
            detail="查找用户失败",
            operation="find_user_by_name",
            context={"user_name": user_name, "error": str(e)}
        )
```

## 🚀 异常处理流程

1. **异常抛出**: 在业务逻辑中抛出相应的异常
2. **异常捕获**: 装饰器或全局处理器捕获异常
3. **异常转换**: 转换为统一的响应格式
4. **错误响应**: 返回标准化的错误信息

## 📊 错误响应格式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "参数验证失败",
    "context": {
      "field": "user_name",
      "value": null
    }
  }
}
```
