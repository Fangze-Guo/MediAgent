from typing import Generic, TypeVar, Any
from .BaseResponse import BaseResponse  # 假设BaseResponse在base_response模块中

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
    def error(error_code: Any) -> BaseResponse[Any]:
        """
        根据错误码创建失败响应

        Args:
            error_code: 错误码对象（需包含code和message属性）

        Returns:
            包含错误信息的响应对象
        """
        return BaseResponse.from_error_code(error_code)