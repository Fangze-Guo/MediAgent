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
        self.default_skill_service = SkillService()
        self._register_routes()

    def _get_service(self, project_id: Optional[str]) -> SkillService:
        if project_id:
            return SkillService.for_project(project_id)
        return self.default_skill_service

    def _register_routes(self):
        """注册路由"""

        @self.router.get("/projects")
        async def get_projects() -> BaseResponse[List[dict]]:
            try:
                from src.server_agent.agent.claude.project_config import PROJECT_CONFIGS
                projects = [
                    {"id": pid, "name": cfg.project_name}
                    for pid, cfg in PROJECT_CONFIGS.items()
                    if (cfg.base_dir / ".claude" / "skills").exists()
                ]
                return ResultUtils.success(projects)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取项目列表失败: {str(e)}")

        @self.router.get("/list")
        async def get_skills(
            type: Optional[str] = Query(None, description="类型筛选"),
            search: Optional[str] = Query(None, description="搜索关键词"),
            project_id: Optional[str] = Query(None, description="项目ID，不传则使用默认目录")
        ) -> BaseResponse[List[dict]]:
            try:
                svc = self._get_service(project_id)
                skills = await svc.get_skills(type=type, search=search)
                return ResultUtils.success(skills)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取 skill 列表失败: {str(e)}")
        
        @self.router.get("/detail/{skill_id}")
        async def get_skill_detail(
            skill_id: str,
            project_id: Optional[str] = Query(None, description="项目ID")
        ) -> BaseResponse[dict]:
            try:
                svc = self._get_service(project_id)
                skill = await svc.get_skill_detail(skill_id)
                if not skill:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                return ResultUtils.success(skill)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取 skill 详情失败: {str(e)}")
        
        @self.router.get("/types")
        async def get_types(
            project_id: Optional[str] = Query(None, description="项目ID")
        ) -> BaseResponse[List[str]]:
            try:
                svc = self._get_service(project_id)
                types = await svc.get_types()
                return ResultUtils.success(types)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取类型失败: {str(e)}")

        @self.router.get("/files/{skill_id}")
        async def get_skill_files(
            skill_id: str,
            project_id: Optional[str] = Query(None, description="项目ID")
        ) -> BaseResponse[List[dict]]:
            try:
                svc = self._get_service(project_id)
                files = await svc.get_skill_files(skill_id)
                if files is None:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                return ResultUtils.success(files)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取文件列表失败: {str(e)}")

        @self.router.get("/file-content/{skill_id}")
        async def get_skill_file_content(
            skill_id: str,
            path: str = Query(..., description="文件相对路径"),
            project_id: Optional[str] = Query(None, description="项目ID")
        ) -> BaseResponse[dict]:
            try:
                svc = self._get_service(project_id)
                content = await svc.get_skill_file_content(skill_id, path)
                if content is None:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "文件不存在")
                return ResultUtils.success(content)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取文件内容失败: {str(e)}")
