from typing import Generic, TypeVar, Any, Optional, Union
from .BaseResponse import BaseResponse  # 假设BaseResponse在base_response模块中
from src.server_agent.exceptions.error_codes import ErrorCode

T = TypeVar('T')


class ResultUtils:
    """响应结果工具类，用于创建各种类型的响应对象"""

    @staticmethod
    def success(data: T) -> BaseResponse[T]:
        """
        创建成功响应

        Args:
            data: 响应数据

        Returns:
            包含数据的成功响应对象
        """
        return BaseResponse(code=200, data=data, message="ok")

    @staticmethod
    def error(error_code: Union[ErrorCode, int], custom_message: Optional[str] = None) -> BaseResponse[Any]:
        """
        根据错误码创建失败响应

        Args:
            error_code: 错误码对象（ErrorCode枚举）或HTTP状态码（int）
            custom_message: 自定义错误消息（可选），如果提供则覆盖默认消息

        Returns:
            包含错误信息的响应对象
            
        Examples:
            # 使用ErrorCode枚举
            ResultUtils.error(ErrorCode.RESOURCE_NOT_FOUND)
            
            # 使用ErrorCode枚举 + 自定义消息
            ResultUtils.error(ErrorCode.RESOURCE_NOT_FOUND, "应用不存在")
            
            # 使用HTTP状态码 + 自定义消息
            ResultUtils.error(404, "应用不存在")
        """
        if isinstance(error_code, ErrorCode):
            # 如果是ErrorCode枚举
            response = BaseResponse.from_error_code(error_code)
            if custom_message:
                # 如果提供了自定义消息，覆盖默认消息
                response.message = custom_message
            return response
        elif isinstance(error_code, int):
            # 如果是HTTP状态码
            return BaseResponse(
                code=error_code,
                data=None,
                message=custom_message or "操作失败"
            )
        else:
            # 兼容旧的error_code对象
            return BaseResponse.from_error_code(error_code)