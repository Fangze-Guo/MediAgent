"""
自定义异常类
"""
from typing import Optional, Dict, Any
from .error_codes import ErrorCode


class MediAgentException(Exception):
    """MediAgent 基础异常类"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.detail = detail or error_code.message
        self.context = context or {}
        super().__init__(self.detail)
    
    @property
    def code(self) -> str:
        """错误代码"""
        return self.error_code.code
    
    @property
    def message(self) -> str:
        """错误消息"""
        return self.error_code.message
    
    @property
    def http_status(self) -> int:
        """HTTP状态码"""
        return self.error_code.http_status
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": self.code,
            "message": self.message,
            "detail": self.detail,
            "context": self.context
        }


class ValidationError(MediAgentException):
    """验证错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.VALIDATION_ERROR, detail, context)
        if field:
            self.context["field"] = field


class AuthenticationError(MediAgentException):
    """认证错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.AUTHENTICATION_ERROR, detail, context)


class AuthorizationError(MediAgentException):
    """授权错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.AUTHORIZATION_ERROR, detail, context)


class NotFoundError(MediAgentException):
    """资源未找到错误"""
    
    def __init__(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        if resource_type and resource_id:
            detail = detail or f"{resource_type} '{resource_id}' not found"
            context = context or {}
            context.update({"resource_type": resource_type, "resource_id": resource_id})
        super().__init__(ErrorCode.NOT_FOUND, detail, context)


class ConflictError(MediAgentException):
    """冲突错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.CONFLICT_ERROR, detail, context)


class DatabaseError(MediAgentException):
    """数据库错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.DATABASE_ERROR, detail, context)
        if operation:
            self.context["operation"] = operation


class ServiceError(MediAgentException):
    """服务错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        service_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.SERVICE_UNAVAILABLE, detail, context)
        if service_name:
            self.context["service_name"] = service_name


class ExternalServiceError(MediAgentException):
    """外部服务错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        service_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.EXTERNAL_SERVICE_ERROR, detail, context)
        if service_name:
            self.context["service_name"] = service_name


class BusinessLogicError(MediAgentException):
    """业务逻辑错误"""
    
    def __init__(
        self,
        detail: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ErrorCode.BUSINESS_LOGIC_ERROR, detail, context)
        if operation:
            self.context["operation"] = operation
