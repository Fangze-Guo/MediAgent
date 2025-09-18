from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

# 定义泛型类型变量
T = TypeVar('T')


@dataclass
class BaseResponse(Generic[T]):
    """全局响应封装类"""
    code: int
    data: Optional[T] = None
    message: str = ""

    @classmethod
    def from_error_code(cls, error_code) -> 'BaseResponse[T]':
        """从错误码对象创建响应实例"""
        return cls(
            code=error_code.code,
            data=None,
            message=error_code.message
        )
