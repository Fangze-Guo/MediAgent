"""
错误代码定义
"""
from enum import Enum


class ErrorCode(Enum):
    """错误代码枚举"""
    
    # 通用错误 (1000-1999)
    UNKNOWN_ERROR = ("UNKNOWN_ERROR", "未知错误", 500)
    INTERNAL_SERVER_ERROR = ("INTERNAL_SERVER_ERROR", "内部服务器错误", 500)
    SERVICE_UNAVAILABLE = ("SERVICE_UNAVAILABLE", "服务不可用", 503)
    
    # 验证错误 (2000-2999)
    VALIDATION_ERROR = ("VALIDATION_ERROR", "验证错误", 400)
    INVALID_INPUT = ("INVALID_INPUT", "输入无效", 400)
    MISSING_REQUIRED_FIELD = ("MISSING_REQUIRED_FIELD", "缺少必需字段", 400)
    INVALID_FORMAT = ("INVALID_FORMAT", "格式无效", 400)
    
    # 认证错误 (3000-3999)
    AUTHENTICATION_ERROR = ("AUTHENTICATION_ERROR", "认证错误", 401)
    INVALID_TOKEN = ("INVALID_TOKEN", "无效的token", 401)
    TOKEN_EXPIRED = ("TOKEN_EXPIRED", "token已过期", 401)
    INVALID_CREDENTIALS = ("INVALID_CREDENTIALS", "无效的凭据", 401)
    
    # 授权错误 (4000-4999)
    AUTHORIZATION_ERROR = ("AUTHORIZATION_ERROR", "授权错误", 403)
    INSUFFICIENT_PERMISSIONS = ("INSUFFICIENT_PERMISSIONS", "权限不足", 403)
    ACCESS_DENIED = ("ACCESS_DENIED", "访问被拒绝", 403)
    
    # 资源错误 (5000-5999)
    NOT_FOUND = ("NOT_FOUND", "资源未找到", 404)
    USER_NOT_FOUND = ("USER_NOT_FOUND", "用户未找到", 404)
    RESOURCE_NOT_FOUND = ("RESOURCE_NOT_FOUND", "资源未找到", 404)
    
    # 冲突错误 (6000-6999)
    CONFLICT_ERROR = ("CONFLICT_ERROR", "冲突错误", 409)
    USERNAME_EXISTS = ("USERNAME_EXISTS", "用户名已存在", 409)
    RESOURCE_EXISTS = ("RESOURCE_EXISTS", "资源已存在", 409)
    
    # 数据库错误 (7000-7999)
    DATABASE_ERROR = ("DATABASE_ERROR", "数据库错误", 500)
    DATABASE_CONNECTION_ERROR = ("DATABASE_CONNECTION_ERROR", "数据库连接错误", 500)
    DATABASE_QUERY_ERROR = ("DATABASE_QUERY_ERROR", "数据库查询错误", 500)
    DATABASE_TRANSACTION_ERROR = ("DATABASE_TRANSACTION_ERROR", "数据库事务错误", 500)
    
    # 业务逻辑错误 (8000-8999)
    BUSINESS_LOGIC_ERROR = ("BUSINESS_LOGIC_ERROR", "业务逻辑错误", 400)
    OPERATION_FAILED = ("OPERATION_FAILED", "操作失败", 400)
    INVALID_OPERATION = ("INVALID_OPERATION", "无效操作", 400)
    
    # 外部服务错误 (9000-9999)
    EXTERNAL_SERVICE_ERROR = ("EXTERNAL_SERVICE_ERROR", "外部服务错误", 502)
    SERVICE_TIMEOUT = ("SERVICE_TIMEOUT", "服务超时", 504)
    SERVICE_RATE_LIMIT = ("SERVICE_RATE_LIMIT", "服务限流", 429)
    
    def __init__(self, code: str, message: str, http_status: int):
        self.code = code
        self.message = message
        self.http_status = http_status
    
    def __str__(self):
        return f"{self.code}: {self.message}"
