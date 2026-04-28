from dataclasses import dataclass
from typing import Generic, TypeVar, Optional, Any, Dict

from src.server_agent.exceptions import ErrorCode

# 定义泛型类型变量
T = TypeVar('T')


@dataclass
class BaseResponse(Generic[T]):
    """
    统一的 API 响应封装类

    响应格式：
    {
        "code": 200,           # HTTP 状态码
        "message": "success",  # 响应消息
        "data": {...}          # 响应数据（可选）
    }
    """
    code: int
    message: str
    data: Optional[T] = None

    @classmethod
    def from_error_code(cls, error_code: ErrorCode, data: Optional[T] = None) -> 'BaseResponse[T]':
        """
        从错误码对象创建响应实例

        Args:
            error_code: 错误码对象
            data: 可选的响应数据

        Returns:
            BaseResponse 实例
        """
        return cls(
            code=error_code.http_status,
            message=error_code.message,
            data=data
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            字典格式的响应
        """
        result = {
            "code": self.code,
            "message": self.message
        }
        if self.data is not None:
            result["data"] = self.data
        return result
