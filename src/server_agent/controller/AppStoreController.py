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
        self._init_reviews()
    
    def _init_apps(self):
        """初始化应用数据"""
        self.apps = [
            {
                "id": "dicom-converter",
                "name": "DICOM转换器",
                "category": "医学影像",
                "description": "将DICOM文件转换为NIfTI格式，支持批量处理",
                "fullDescription": "DICOM转换器是一款专业的医学影像格式转换工具，专为医疗研究人员和临床医生设计。它能够高效地将DICOM格式的医学影像转换为NIfTI格式，同时保持图像质量和元数据完整性。支持批量处理功能，可以一次性转换大量文件，极大提高工作效率。",
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
        
        @self.router.get("/apps/{app_id}/reviews")
        async def get_app_reviews(app_id: str) -> BaseResponse[dict]:
            """
            获取应用的评论列表
            :param app_id: 应用ID
            :return: 包含评论列表和统计信息的字典
            """
            # 获取该应用的评论
            reviews = self.reviews_db.get(app_id, [])
            
            if not reviews:
                return ResultUtils.success({
                    "reviews": [],
                    "total": 0,
                    "average_rating": 0,
                    "rating_distribution": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
                })
            
            # 计算平均评分
            total_rating = sum(review["rating"] for review in reviews)
            average_rating = round(total_rating / len(reviews), 1)
            
            # 计算评分分布
            rating_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
            for review in reviews:
                rating_str = str(review["rating"])
                rating_distribution[rating_str] = rating_distribution.get(rating_str, 0) + 1
            
            return ResultUtils.success({
                "reviews": reviews,
                "total": len(reviews),
                "average_rating": average_rating,
                "rating_distribution": rating_distribution
            })
        
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
    
    def _init_reviews(self):
        """初始化评论数据"""
        self.reviews_db = {
            "dicom-converter": [
                {
                    "id": 1,
                    "app_id": "dicom-converter",
                    "user_name": "张医生",
                    "rating": 5,
                    "comment": "非常好用的工具，大大提高了我的工作效率。界面设计简洁，功能强大。",
                    "helpful_count": 24,
                    "date": "2025年9月15日"
                },
                {
                    "id": 2,
                    "app_id": "dicom-converter",
                    "user_name": "李研究员",
                    "rating": 5,
                    "comment": "处理速度很快，支持批量转换，省了很多时间。强烈推荐！",
                    "helpful_count": 18,
                    "date": "2025年9月10日"
                },
                {
                    "id": 3,
                    "app_id": "dicom-converter",
                    "user_name": "王医师",
                    "rating": 4,
                    "comment": "整体很不错，就是有时候处理大文件会有点慢。希望能继续优化。",
                    "helpful_count": 12,
                    "date": "2025年9月5日"
                },
                {
                    "id": 4,
                    "app_id": "dicom-converter",
                    "user_name": "陈博士",
                    "rating": 5,
                    "comment": "专业的医学影像处理工具，转换质量高，没有数据丢失。",
                    "helpful_count": 20,
                    "date": "2025年9月1日"
                },
                {
                    "id": 5,
                    "app_id": "dicom-converter",
                    "user_name": "刘主任",
                    "rating": 4,
                    "comment": "功能齐全，操作简单，适合临床使用。期待增加更多格式支持。",
                    "helpful_count": 15,
                    "date": "2025年8月28日"
                }
            ],
            "image-resample": [
                {
                    "id": 1,
                    "app_id": "image-resample",
                    "user_name": "周教授",
                    "rating": 5,
                    "comment": "重采样效果非常好，保持了图像质量的同时提升了处理速度。",
                    "helpful_count": 16,
                    "date": "2025年9月12日"
                },
                {
                    "id": 2,
                    "app_id": "image-resample",
                    "user_name": "吴医生",
                    "rating": 4,
                    "comment": "实用的工具，可以自定义体素大小。建议增加更多插值算法选项。",
                    "helpful_count": 11,
                    "date": "2025年9月8日"
                },
                {
                    "id": 3,
                    "app_id": "image-resample",
                    "user_name": "郑研究员",
                    "rating": 5,
                    "comment": "对于大规模数据预处理非常有帮助，批处理功能很赞！",
                    "helpful_count": 14,
                    "date": "2025年9月3日"
                }
            ],
            "intensity-normalize": [
                {
                    "id": 1,
                    "app_id": "intensity-normalize",
                    "user_name": "孙医师",
                    "rating": 5,
                    "comment": "归一化效果稳定，对后续的AI分析帮助很大。",
                    "helpful_count": 19,
                    "date": "2025年9月14日"
                },
                {
                    "id": 2,
                    "app_id": "intensity-normalize",
                    "user_name": "赵博士",
                    "rating": 4,
                    "comment": "处理效果不错，建议添加更多归一化方法的选项。",
                    "helpful_count": 13,
                    "date": "2025年9月6日"
                }
            ],
            "nnunet-segmentation": [
                {
                    "id": 1,
                    "app_id": "nnunet-segmentation",
                    "user_name": "钱教授",
                    "rating": 5,
                    "comment": "nnU-Net集成得很好，分割精度高，是做医学图像分析的利器！",
                    "helpful_count": 45,
                    "date": "2025年9月16日"
                },
                {
                    "id": 2,
                    "app_id": "nnunet-segmentation",
                    "user_name": "冯医生",
                    "rating": 5,
                    "comment": "自动分割效果惊艳，大大减少了手动标注的工作量。",
                    "helpful_count": 38,
                    "date": "2025年9月11日"
                },
                {
                    "id": 3,
                    "app_id": "nnunet-segmentation",
                    "user_name": "韩研究员",
                    "rating": 4,
                    "comment": "功能强大，就是对GPU要求比较高，希望能优化性能。",
                    "helpful_count": 22,
                    "date": "2025年9月4日"
                },
                {
                    "id": 4,
                    "app_id": "nnunet-segmentation",
                    "user_name": "蒋博士",
                    "rating": 5,
                    "comment": "支持多种器官的分割，模型库很丰富，值得推荐！",
                    "helpful_count": 31,
                    "date": "2025年8月30日"
                }
            ],
            "n4-bias-correction": [
                {
                    "id": 1,
                    "app_id": "n4-bias-correction",
                    "user_name": "沈医师",
                    "rating": 4,
                    "comment": "N4校正算法经典，对MRI图像处理效果明显。",
                    "helpful_count": 10,
                    "date": "2025年9月9日"
                },
                {
                    "id": 2,
                    "app_id": "n4-bias-correction",
                    "user_name": "蔡教授",
                    "rating": 5,
                    "comment": "偏置场校正很彻底，提高了后续处理的准确性。",
                    "helpful_count": 15,
                    "date": "2025年9月2日"
                }
            ],
            "image-registration": [
                {
                    "id": 1,
                    "app_id": "image-registration",
                    "user_name": "许医生",
                    "rating": 5,
                    "comment": "配准算法先进，支持多模态配准，对纵向研究很有帮助。",
                    "helpful_count": 21,
                    "date": "2025年9月13日"
                },
                {
                    "id": 2,
                    "app_id": "image-registration",
                    "user_name": "杨研究员",
                    "rating": 4,
                    "comment": "配准精度高，但处理时间稍长，期待性能优化。",
                    "helpful_count": 17,
                    "date": "2025年9月7日"
                },
                {
                    "id": 3,
                    "app_id": "image-registration",
                    "user_name": "丁博士",
                    "rating": 5,
                    "comment": "可视化配准结果很直观，方便验证配准效果。",
                    "helpful_count": 19,
                    "date": "2025年8月29日"
                }
            ],
            "data-viewer": [
                {
                    "id": 1,
                    "app_id": "data-viewer",
                    "user_name": "程医师",
                    "rating": 5,
                    "comment": "3D可视化效果出色，支持多平面显示，非常实用！",
                    "helpful_count": 28,
                    "date": "2025年9月17日"
                },
                {
                    "id": 2,
                    "app_id": "data-viewer",
                    "user_name": "贺教授",
                    "rating": 5,
                    "comment": "界面友好，操作流畅，是查看医学影像的好工具。",
                    "helpful_count": 33,
                    "date": "2025年9月12日"
                },
                {
                    "id": 3,
                    "app_id": "data-viewer",
                    "user_name": "叶医生",
                    "rating": 4,
                    "comment": "功能丰富，希望能增加更多测量工具。",
                    "helpful_count": 20,
                    "date": "2025年9月5日"
                }
            ],
            "report-generator": [
                {
                    "id": 1,
                    "app_id": "report-generator",
                    "user_name": "魏医师",
                    "rating": 4,
                    "comment": "自动生成报告节省了很多时间，但模板还可以更丰富一些。",
                    "helpful_count": 12,
                    "date": "2025年9月10日"
                },
                {
                    "id": 2,
                    "app_id": "report-generator",
                    "user_name": "余博士",
                    "rating": 4,
                    "comment": "报告格式专业，内容准确。期待支持自定义模板。",
                    "helpful_count": 14,
                    "date": "2025年9月3日"
                }
            ],
            "dataset-manager": [
                {
                    "id": 1,
                    "app_id": "dataset-manager",
                    "user_name": "谢教授",
                    "rating": 5,
                    "comment": "数据集管理很方便，标注功能也很实用。",
                    "helpful_count": 25,
                    "date": "2025年9月15日"
                },
                {
                    "id": 2,
                    "app_id": "dataset-manager",
                    "user_name": "朱研究员",
                    "rating": 4,
                    "comment": "支持多种数据格式，导入导出都很便捷。",
                    "helpful_count": 18,
                    "date": "2025年9月8日"
                },
                {
                    "id": 3,
                    "app_id": "dataset-manager",
                    "user_name": "邹医生",
                    "rating": 5,
                    "comment": "团队协作功能很棒，大家可以共享数据集。",
                    "helpful_count": 22,
                    "date": "2025年9月1日"
                }
            ],
            "ai-diagnosis-assistant": [
                {
                    "id": 1,
                    "app_id": "ai-diagnosis-assistant",
                    "user_name": "顾医师",
                    "rating": 5,
                    "comment": "AI辅助诊断准确率很高，是临床工作的好帮手！",
                    "helpful_count": 42,
                    "date": "2025年9月18日"
                },
                {
                    "id": 2,
                    "app_id": "ai-diagnosis-assistant",
                    "user_name": "崔教授",
                    "rating": 5,
                    "comment": "多模态分析功能强大，对复杂病例的判断很有参考价值。",
                    "helpful_count": 36,
                    "date": "2025年9月13日"
                },
                {
                    "id": 3,
                    "app_id": "ai-diagnosis-assistant",
                    "user_name": "苏博士",
                    "rating": 4,
                    "comment": "整体表现优秀，建议增加更多疾病类型的支持。",
                    "helpful_count": 27,
                    "date": "2025年9月6日"
                },
                {
                    "id": 4,
                    "app_id": "ai-diagnosis-assistant",
                    "user_name": "潘医生",
                    "rating": 5,
                    "comment": "可解释性强，AI给出的诊断依据很清晰。",
                    "helpful_count": 30,
                    "date": "2025年8月31日"
                }
            ]
        }

