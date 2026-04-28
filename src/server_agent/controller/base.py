"""
基础Controller类
提供通用的依赖注入和工具方法
"""
import asyncio
from typing import List, TypeVar, Generic, Optional, Dict, Any
from math import ceil

from fastapi import APIRouter, Query

from src.server_agent.exceptions import ValidationError

# 全局变量
_init_lock = asyncio.Lock()
_initialized = False

# 泛型类型变量
T = TypeVar('T')


class PaginationResult(Generic[T]):
    """分页结果封装"""

    def __init__(
        self,
        items: List[T],
        total: int,
        page: int,
        size: int
    ):
        self.items = items
        self.total = total
        self.page = page
        self.size = size
        self.pages = ceil(total / size) if size > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "size": self.size,
            "pages": self.pages
        }


class BaseController:
    """
    基础Controller类
    提供通用的工具方法和依赖注入支持
    """

    def __init__(self, prefix: str = "", tags: List[str] = None):
        """
        初始化基础控制器

        Args:
            prefix: 路由前缀
            tags: API 标签列表
        """
        self.router = APIRouter(prefix=prefix, tags=tags or [])
        self._init_lock = _init_lock
        self._initialized = _initialized

    # ==================== 分页工具 ====================

    def paginate(
        self,
        items: List[T],
        page: int = 1,
        size: int = 10
    ) -> PaginationResult[T]:
        """
        通用分页方法

        Args:
            items: 要分页的数据列表
            page: 页码（从1开始）
            size: 每页大小

        Returns:
            PaginationResult: 分页结果对象

        Raises:
            ValidationError: 当分页参数无效时

        Example:
            >>> items = [1, 2, 3, 4, 5]
            >>> result = self.paginate(items, page=1, size=2)
            >>> result.items  # [1, 2]
            >>> result.total  # 5
            >>> result.pages  # 3
        """
        # 验证分页参数
        if page < 1:
            raise ValidationError(
                detail="Page number must be greater than 0",
                field="page",
                context={"page": page}
            )

        if size < 1:
            raise ValidationError(
                detail="Page size must be greater than 0",
                field="size",
                context={"size": size}
            )

        total = len(items)
        start = (page - 1) * size
        end = start + size

        return PaginationResult(
            items=items[start:end],
            total=total,
            page=page,
            size=size
        )

    # ==================== 验证工具 ====================

    def validate_id(
        self,
        id_value: int,
        resource_name: str = "resource",
        min_value: int = 1
    ) -> None:
        """
        验证 ID 是否有效

        Args:
            id_value: 要验证的 ID
            resource_name: 资源名称（用于错误消息）
            min_value: 最小有效值

        Raises:
            ValidationError: 当 ID 无效时

        Example:
            >>> self.validate_id(123, "user")  # 通过
            >>> self.validate_id(0, "user")    # 抛出 ValidationError
        """
        if id_value < min_value:
            raise ValidationError(
                detail=f"Invalid {resource_name} ID: must be >= {min_value}",
                field="id",
                context={"id": id_value, "resource": resource_name, "min_value": min_value}
            )

    def validate_string(
        self,
        value: Optional[str],
        field_name: str,
        min_length: int = 1,
        max_length: Optional[int] = None,
        required: bool = True
    ) -> None:
        """
        验证字符串字段

        Args:
            value: 要验证的字符串
            field_name: 字段名称
            min_length: 最小长度
            max_length: 最大长度（可选）
            required: 是否必填

        Raises:
            ValidationError: 当字符串无效时
        """
        if required and not value:
            raise ValidationError(
                detail=f"{field_name} is required",
                field=field_name,
                context={"field": field_name}
            )

        if value:
            if len(value) < min_length:
                raise ValidationError(
                    detail=f"{field_name} must be at least {min_length} characters",
                    field=field_name,
                    context={"field": field_name, "min_length": min_length, "actual_length": len(value)}
                )

            if max_length and len(value) > max_length:
                raise ValidationError(
                    detail=f"{field_name} must be at most {max_length} characters",
                    field=field_name,
                    context={"field": field_name, "max_length": max_length, "actual_length": len(value)}
                )
