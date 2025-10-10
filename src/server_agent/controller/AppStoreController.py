"""
App Store控制器 - 管理医疗应用市场
"""
from typing import List, Optional
from pydantic import BaseModel

from common import ResultUtils, BaseResponse
from src.server_agent.controller.base import BaseController
from src.server_agent.exceptions.error_codes import ErrorCode


class AppInfo(BaseModel):
    """应用信息模型"""
    id: str
    name: str
    category: str
    description: str
    icon: str
    version: str
    author: str
    downloads: int
    rating: float
    installed: bool = False
    tags: List[str] = []


class AppStoreController(BaseController):
    """App Store控制器"""
    
    def __init__(self):
        super().__init__(prefix="/app-store", tags=["应用商店"])
        self._register_routes()
        self._init_apps()
    
    def _init_apps(self):
        """初始化应用数据"""
        self.apps = [
            {
                "id": "dicom-converter",
                "name": "DICOM转换器",
                "category": "医学影像",
                "description": "将DICOM文件转换为NIfTI格式，支持批量处理",
                "icon": "🏥",
                "version": "1.0.0",
                "author": "MediAgent团队",
                "downloads": 1200,
                "rating": 4.8,
                "installed": False,
                "tags": ["DICOM", "NIfTI", "图像转换"]
            },
            {
                "id": "image-resample",
                "name": "图像重采样",
                "category": "医学影像",
                "description": "对医学影像进行重采样，调整分辨率和体素大小",
                "icon": "📐",
                "version": "1.2.0",
                "author": "MediAgent团队",
                "downloads": 980,
                "rating": 4.6,
                "installed": False,
                "tags": ["重采样", "分辨率", "预处理"]
            },
            {
                "id": "intensity-normalize",
                "name": "强度归一化",
                "category": "医学影像",
                "description": "标准化医学影像的灰度值，提高数据一致性",
                "icon": "📊",
                "version": "1.1.0",
                "author": "MediAgent团队",
                "downloads": 850,
                "rating": 4.7,
                "installed": False,
                "tags": ["归一化", "预处理", "标准化"]
            },
            {
                "id": "nnunet-segmentation",
                "name": "nnU-Net分割",
                "category": "AI模型",
                "description": "基于nnU-Net的医学图像自动分割工具",
                "icon": "🧠",
                "version": "2.0.0",
                "author": "MediAgent团队",
                "downloads": 2500,
                "rating": 4.9,
                "installed": False,
                "tags": ["分割", "深度学习", "nnU-Net"]
            },
            {
                "id": "n4-bias-correction",
                "name": "N4偏置场校正",
                "category": "医学影像",
                "description": "使用N4算法校正MRI图像的偏置场",
                "icon": "🔧",
                "version": "1.0.2",
                "author": "MediAgent团队",
                "downloads": 670,
                "rating": 4.5,
                "installed": False,
                "tags": ["MRI", "偏置场", "校正"]
            },
            {
                "id": "image-registration",
                "name": "图像配准",
                "category": "医学影像",
                "description": "多模态医学图像配准工具",
                "icon": "🎯",
                "version": "1.3.0",
                "author": "MediAgent团队",
                "downloads": 1100,
                "rating": 4.7,
                "installed": False,
                "tags": ["配准", "多模态", "对齐"]
            },
            {
                "id": "data-viewer",
                "name": "医学影像查看器",
                "category": "可视化",
                "description": "3D医学影像可视化工具，支持多种格式",
                "icon": "👁️",
                "version": "2.1.0",
                "author": "MediAgent团队",
                "downloads": 3200,
                "rating": 4.8,
                "installed": False,
                "tags": ["可视化", "3D", "查看器"]
            },
            {
                "id": "report-generator",
                "name": "报告生成器",
                "category": "工具",
                "description": "自动生成医学影像分析报告",
                "icon": "📝",
                "version": "1.0.0",
                "author": "MediAgent团队",
                "downloads": 540,
                "rating": 4.4,
                "installed": False,
                "tags": ["报告", "自动化", "文档"]
            },
            {
                "id": "dataset-manager",
                "name": "数据集管理器",
                "category": "数据管理",
                "description": "管理和组织医学影像数据集",
                "icon": "📦",
                "version": "1.5.0",
                "author": "MediAgent团队",
                "downloads": 1450,
                "rating": 4.6,
                "installed": False,
                "tags": ["数据集", "管理", "组织"]
            },
            {
                "id": "ai-diagnosis-assistant",
                "name": "AI诊断助手",
                "category": "AI模型",
                "description": "基于深度学习的疾病诊断辅助工具",
                "icon": "🤖",
                "version": "1.0.0",
                "author": "MediAgent团队",
                "downloads": 1800,
                "rating": 4.9,
                "installed": False,
                "tags": ["AI", "诊断", "深度学习"]
            }
        ]
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.get("/apps")
        async def get_apps(
            category: Optional[str] = None,
            search: Optional[str] = None
        ) -> BaseResponse[List[AppInfo]]:
            """
            获取应用列表
            :param category: 分类过滤
            :param search: 搜索关键词
            """
            apps = self.apps.copy()
            
            # 分类过滤
            if category and category != "全部":
                apps = [app for app in apps if app["category"] == category]
            
            # 搜索过滤
            if search:
                search_lower = search.lower()
                apps = [
                    app for app in apps
                    if search_lower in app["name"].lower() 
                    or search_lower in app["description"].lower()
                    or any(search_lower in tag.lower() for tag in app["tags"])
                ]
            
            return ResultUtils.success(apps)
        
        @self.router.get("/apps/{app_id}")
        async def get_app_detail(app_id: str) -> BaseResponse[AppInfo]:
            """
            获取应用详情
            :param app_id: 应用ID
            """
            for app in self.apps:
                if app["id"] == app_id:
                    return ResultUtils.success(app)
            
            return ResultUtils.error(ErrorCode.RESOURCE_NOT_FOUND, f"应用 {app_id} 不存在")
        
        @self.router.get("/categories")
        async def get_categories() -> BaseResponse[List[str]]:
            """获取所有分类"""
            categories = list(set(app["category"] for app in self.apps))
            categories.sort()
            return ResultUtils.success(["全部"] + categories)
        
        @self.router.post("/apps/{app_id}/install")
        async def install_app(app_id: str) -> BaseResponse[str]:
            """
            安装应用
            :param app_id: 应用ID
            """
            for app in self.apps:
                if app["id"] == app_id:
                    app["installed"] = True
                    return ResultUtils.success(f"应用 {app['name']} 安装成功")
            
            return ResultUtils.error(ErrorCode.RESOURCE_NOT_FOUND, f"应用 {app_id} 不存在，无法安装")
        
        @self.router.post("/apps/{app_id}/uninstall")
        async def uninstall_app(app_id: str) -> BaseResponse[str]:
            """
            卸载应用
            :param app_id: 应用ID
            """
            for app in self.apps:
                if app["id"] == app_id:
                    app["installed"] = False
                    return ResultUtils.success(f"应用 {app['name']} 卸载成功")
            
            return ResultUtils.error(ErrorCode.RESOURCE_NOT_FOUND, f"应用 {app_id} 不存在，无法卸载")

