"""
App Store控制器
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import Body

from common import ResultUtils, BaseResponse
from src.server_agent.controller.base import BaseController
from src.server_agent.service.AppStoreService import AppStoreService
from src.server_agent.exceptions.error_codes import ErrorCode


class AppInfo(BaseModel):
    """应用信息模型"""
    id: str
    name: str
    category: str
    description: str
    full_description: Optional[str] = None  # 详细描述
    icon: str
    version: str
    author: str
    downloads: int
    rating: float
    installed: bool = False
    featured: bool = False  # 是否精选
    tags: List[str] = []


class ReviewInfo(BaseModel):
    """评论信息模型"""
    id: int
    app_id: str
    user_name: str
    rating: int
    comment: str
    helpful_count: int
    created_at: str


class AddReviewRequest(BaseModel):
    """添加评论请求模型"""
    user_name: str
    rating: int
    comment: str


class ToggleHelpfulRequest(BaseModel):
    """点赞请求模型"""
    user_id: int


class AppStoreController(BaseController):
    """App Store控制器 - 使用数据库版本"""
    
    def __init__(self):
        super().__init__(prefix="/app-store", tags=["应用商店"])
        self.app_service = AppStoreService()  # 初始化数据库服务
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.get("/apps")
        async def get_apps(category: Optional[str] = None, search: Optional[str] = None) -> BaseResponse[List[dict]]:
            """
            获取应用列表
            Args:
                category: 分类筛选 (可选)
                search: 搜索关键词 (可选)
            """
            try:
                apps = await self.app_service.get_apps(category=category, search=search)
                return ResultUtils.success(apps)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取应用列表失败: {str(e)}")
        
        @self.router.get("/apps/{app_id}")
        async def get_app_detail(app_id: str) -> BaseResponse[dict]:
            """
            获取应用详情
            Args:
                app_id: 应用ID
            """
            try:
                app = await self.app_service.get_app_detail(app_id)
                if not app:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "应用不存在")
                return ResultUtils.success(app)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取应用详情失败: {str(e)}")
        
        @self.router.get("/categories")
        async def get_categories() -> BaseResponse[List[str]]:
            """获取所有分类"""
            try:
                categories = await self.app_service.get_categories()
                return ResultUtils.success(categories)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取分类失败: {str(e)}")
        
        @self.router.get("/featured")
        async def get_featured_apps(limit: int = 6) -> BaseResponse[List[dict]]:
            """
            获取精选应用
            Args:
                limit: 返回数量限制
            """
            try:
                apps = await self.app_service.get_featured_apps(limit=limit)
                return ResultUtils.success(apps)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取精选应用失败: {str(e)}")
        
        @self.router.post("/apps/{app_id}/install")
        async def install_app(app_id: str) -> BaseResponse[dict]:
            """
            安装应用
            Args:
                app_id: 应用ID
            """
            try:
                success = await self.app_service.install_app(app_id)
                if success:
                    return ResultUtils.success({"message": "安装成功"})
                else:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "应用不存在")
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"安装应用失败: {str(e)}")
        
        @self.router.post("/apps/{app_id}/uninstall")
        async def uninstall_app(app_id: str) -> BaseResponse[dict]:
            """
            卸载应用
            Args:
                app_id: 应用ID
            """
            try:
                success = await self.app_service.uninstall_app(app_id)
                if success:
                    return ResultUtils.success({"message": "卸载成功"})
                else:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "应用不存在")
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"卸载应用失败: {str(e)}")
        
        @self.router.get("/apps/{app_id}/reviews")
        async def get_app_reviews(app_id: str, user_id: Optional[int] = None) -> BaseResponse[dict]:
            """
            获取应用评论
            Args:
                app_id: 应用ID
                user_id: 用户ID (可选，用于获取用户点赞状态)
            """
            try:
                reviews_data = await self.app_service.get_app_reviews(app_id, user_id)
                return ResultUtils.success(reviews_data)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取评论失败: {str(e)}")
        
        @self.router.post("/apps/{app_id}/reviews")
        async def add_review(app_id: str, request: AddReviewRequest) -> BaseResponse[dict]:
            """
            添加评论
            Args:
                app_id: 应用ID
                request: 评论请求数据
            """
            try:
                # 验证评分范围
                if not (1 <= request.rating <= 5):
                    return ResultUtils.error(ErrorCode.INVALID_PARAMETER, "评分必须在1-5之间")
                
                success = await self.app_service.add_review(
                    app_id=app_id,
                    user_name=request.user_name,
                    rating=request.rating,
                    comment=request.comment
                )
                
                if success:
                    return ResultUtils.success({"message": "评论添加成功"})
                else:
                    return ResultUtils.error(ErrorCode.SYSTEM_ERROR, "评论添加失败")
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"添加评论失败: {str(e)}")

        @self.router.put("/apps/{app_id}/reviews/{review_id}")
        async def update_review(app_id: str, review_id: int, request: AddReviewRequest) -> BaseResponse[dict]:
            """
            更新评论
            Args:
                app_id: 应用ID
                review_id: 评论ID
                request: 评论请求数据
            """
            try:
                # 验证评分范围
                if not (1 <= request.rating <= 5):
                    return ResultUtils.error(ErrorCode.INVALID_PARAMETER, "评分必须在1-5之间")
                
                success = await self.app_service.update_review(
                    review_id=review_id,
                    app_id=app_id,
                    user_name=request.user_name,
                    rating=request.rating,
                    comment=request.comment
                )
                
                if success:
                    return ResultUtils.success({"message": "评论修改成功"})
                else:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "评论不存在或修改失败")
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"修改评论失败: {str(e)}")
        
        @self.router.delete("/apps/{app_id}/reviews/{review_id}")
        async def delete_review(app_id: str, review_id: int, user_name: str) -> BaseResponse[dict]:
            """
            删除评论
            Args:
                app_id: 应用ID
                review_id: 评论ID
                user_name: 用户名（通过查询参数传递）
            """
            try:
                success = await self.app_service.delete_review(
                    review_id=review_id,
                    app_id=app_id,
                    user_name=user_name
                )
                
                if success:
                    return ResultUtils.success({"message": "评论删除成功"})
                else:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "评论不存在或删除失败")
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"删除评论失败: {str(e)}")
        
        @self.router.post("/apps/{app_id}/reviews/{review_id}/helpful")
        async def toggle_helpful(app_id: str, review_id: int, request: ToggleHelpfulRequest) -> BaseResponse[dict]:
            """
            切换评论点赞状态
            Args:
                app_id: 应用ID (用于验证评论归属)
                review_id: 评论ID
                request: 点赞请求数据 (包含user_id)
            """
            try:
                result = await self.app_service.toggle_helpful(review_id, request.user_id)
                return ResultUtils.success(result)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"操作失败: {str(e)}")
        
        @self.router.get("/stats")
        async def get_app_stats() -> BaseResponse[dict]:
            """获取应用商店统计信息"""
            try:
                stats = await self.app_service.get_app_stats()
                return ResultUtils.success(stats)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取统计信息失败: {str(e)}")
        
        @self.router.put("/apps/{app_id}/features")
        async def update_app_features(app_id: str, request: dict = Body(...)) -> BaseResponse[dict]:
            """
            更新应用功能特点
            Args:
                app_id: 应用ID
                request: 包含features字段的请求体
            """
            try:
                features = request.get('features', '')
                success = await self.app_service.update_app_features(app_id, features)
                
                if success:
                    return ResultUtils.success({"message": "功能特点更新成功"})
                else:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "应用不存在")
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"更新功能特点失败: {str(e)}")