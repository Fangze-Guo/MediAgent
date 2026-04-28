from typing import TypeVar, Any, Optional, Union
from .BaseResponse import BaseResponse
from src.server_agent.exceptions.error_codes import ErrorCode

T = TypeVar('T')


class ResultUtils:
    """
    统一的响应结果工具类
    提供标准化的成功和失败响应构建方法
    """

    @staticmethod
    def success(data: Optional[T] = None, message: str = "success") -> BaseResponse[T]:
        """
        构建成功响应

        Args:
            data: 响应数据（可选）
            message: 响应消息，默认为 "success"

        Returns:
            BaseResponse[T]: 成功响应对象

        Example:
            >>> ResultUtils.success({"user_id": 123})
            BaseResponse(code=200, message="success", data={"user_id": 123})
        """
        return BaseResponse(code=200, message=message, data=data)

    @staticmethod
    def error(
        code: int = 500,
        message: str = "error",
        data: Optional[T] = None
    ) -> BaseResponse[T]:
        """
        构建错误响应

        Args:
            code: HTTP 状态码，默认为 500
            message: 错误消息，默认为 "error"
            data: 可选的错误详情数据

        Returns:
            BaseResponse[T]: 错误响应对象

        Example:
            >>> ResultUtils.error(400, "Invalid input")
            BaseResponse(code=400, message="Invalid input", data=None)
        """
        return BaseResponse(code=code, message=message, data=data)

    @staticmethod
    def from_error_code(
        error_code: ErrorCode,
        data: Optional[T] = None
    ) -> BaseResponse[T]:
        """
        从错误码对象创建响应

        Args:
            error_code: 错误码对象
            data: 可选的错误详情数据

        Returns:
            BaseResponse[T]: 错误响应对象

        Example:
            >>> ResultUtils.from_error_code(ErrorCode.NOT_FOUND)
            BaseResponse(code=404, message="Resource not found", data=None)
        """
        return BaseResponse.from_error_code(error_code, data)

    @staticmethod
    def created(data: Optional[T] = None, message: str = "created") -> BaseResponse[T]:
        """构建资源创建成功响应（201）"""
        return BaseResponse(code=201, message=message, data=data)

    @staticmethod
    def no_content(message: str = "no content") -> BaseResponse[None]:
        """构建无内容响应（204）"""
        return BaseResponse(code=204, message=message, data=None)

    @staticmethod
    def bad_request(message: str = "bad request", data: Optional[T] = None) -> BaseResponse[T]:
        """构建错误请求响应（400）"""
        return BaseResponse(code=400, message=message, data=data)

    @staticmethod
    def unauthorized(message: str = "unauthorized", data: Optional[T] = None) -> BaseResponse[T]:
        """构建未授权响应（401）"""
        return BaseResponse(code=401, message=message, data=data)

    @staticmethod
    def forbidden(message: str = "forbidden", data: Optional[T] = None) -> BaseResponse[T]:
        """构建禁止访问响应（403）"""
        return BaseResponse(code=403, message=message, data=data)

    @staticmethod
    def not_found(message: str = "not found", data: Optional[T] = None) -> BaseResponse[T]:
        """构建资源未找到响应（404）"""
        return BaseResponse(code=404, message=message, data=data)