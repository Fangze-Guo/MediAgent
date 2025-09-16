"""
全局异常处理器
"""
import logging
import traceback
from typing import Union
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from .custom_exceptions import MediAgentException
from .error_codes import ErrorCode

# 配置日志
logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI):
    """设置全局异常处理器"""
    
    @app.exception_handler(MediAgentException)
    async def mediagent_exception_handler(request: Request, exc: MediAgentException):
        """处理 MediAgent 自定义异常"""
        logger.error(f"MediAgent Exception: {exc.code} - {exc.detail}")
        logger.debug(f"Exception context: {exc.context}")
        
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "context": exc.context,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理 FastAPI HTTP 异常"""
        logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": "HTTP Error",
                "detail": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证异常"""
        logger.warning(f"Validation Error: {exc.errors()}")
        
        # 格式化验证错误
        formatted_errors = []
        for error in exc.errors():
            formatted_errors.append({
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        return JSONResponse(
            status_code=400,
            content={
                "error": ErrorCode.VALIDATION_ERROR.code,
                "message": ErrorCode.VALIDATION_ERROR.message,
                "detail": "Request validation failed",
                "validation_errors": formatted_errors,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError):
        """处理 Pydantic 验证异常"""
        logger.warning(f"Pydantic Validation Error: {exc.errors()}")
        
        formatted_errors = []
        for error in exc.errors():
            formatted_errors.append({
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        return JSONResponse(
            status_code=400,
            content={
                "error": ErrorCode.VALIDATION_ERROR.code,
                "message": ErrorCode.VALIDATION_ERROR.message,
                "detail": "Data validation failed",
                "validation_errors": formatted_errors,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理通用异常"""
        logger.error(f"Unhandled Exception: {type(exc).__name__}: {str(exc)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": ErrorCode.INTERNAL_SERVER_ERROR.code,
                "message": ErrorCode.INTERNAL_SERVER_ERROR.message,
                "detail": "An unexpected error occurred",
                "path": str(request.url.path)
            }
        )


def handle_service_exception(func):
    """服务层异常处理装饰器"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except MediAgentException:
            # 重新抛出 MediAgent 异常
            raise
        except Exception as e:
            # 将其他异常包装为 ServiceError
            logger.error(f"Service error in {func.__name__}: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            from .custom_exceptions import ServiceError
            raise ServiceError(
                detail=f"Service error in {func.__name__}: {str(e)}",
                service_name=func.__name__
            )
    return wrapper


def handle_mapper_exception(func):
    """数据访问层异常处理装饰器"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except MediAgentException:
            # 重新抛出 MediAgent 异常
            raise
        except Exception as e:
            # 将其他异常包装为 DatabaseError
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            from .custom_exceptions import DatabaseError
            raise DatabaseError(
                detail=f"Database error in {func.__name__}: {str(e)}",
                operation=func.__name__
            )
    return wrapper
