"""
Skill 控制器
提供从真实 ~/.claude/skills 目录读取 skill 的 API 接口
"""
from typing import List, Optional
from fastapi import Query

from src.server_agent.common import ResultUtils, BaseResponse
from src.server_agent.controller.base import BaseController
from src.server_agent.service.SkillService import SkillService
from src.server_agent.exceptions.error_codes import ErrorCode


class SkillController(BaseController):
    """Skill 控制器 - 从文件系统读取真实的 skills"""
    
    def __init__(self):
        super().__init__(prefix="/skills", tags=["技能仓库"])
        self.skill_service = SkillService()
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.get("/list")
        async def get_skills(
            category: Optional[str] = Query(None, description="分类筛选"),
            search: Optional[str] = Query(None, description="搜索关键词")
        ) -> BaseResponse[List[dict]]:
            """
            获取 skill 列表
            Args:
                category: 分类筛选 (可选)
                search: 搜索关键词 (可选)
            """
            try:
                skills = await self.skill_service.get_skills(category=category, search=search)
                return ResultUtils.success(skills)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取 skill 列表失败: {str(e)}")
        
        @self.router.get("/detail/{skill_id}")
        async def get_skill_detail(skill_id: str) -> BaseResponse[dict]:
            """
            获取 skill 详情
            Args:
                skill_id: skill ID（目录名）
            """
            try:
                skill = await self.skill_service.get_skill_detail(skill_id)
                if not skill:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                return ResultUtils.success(skill)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取 skill 详情失败: {str(e)}")
        
        @self.router.get("/categories")
        async def get_categories() -> BaseResponse[List[str]]:
            """获取所有分类"""
            try:
                categories = await self.skill_service.get_categories()
                return ResultUtils.success(categories)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取分类失败: {str(e)}")

        @self.router.get("/files/{skill_id}")
        async def get_skill_files(skill_id: str) -> BaseResponse[List[dict]]:
            """
            获取 skill 的文件树结构
            Args:
                skill_id: skill ID（目录名）
            """
            try:
                files = await self.skill_service.get_skill_files(skill_id)
                if files is None:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                return ResultUtils.success(files)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取文件列表失败: {str(e)}")

        @self.router.get("/file-content/{skill_id}")
        async def get_skill_file_content(
            skill_id: str,
            path: str = Query(..., description="文件相对路径")
        ) -> BaseResponse[dict]:
            """
            获取 skill 中某个文件的内容
            Args:
                skill_id: skill ID（目录名）
                path: 文件相对路径
            """
            try:
                content = await self.skill_service.get_skill_file_content(skill_id, path)
                if content is None:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "文件不存在")
                return ResultUtils.success(content)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取文件内容失败: {str(e)}")
