"""
Skill 控制器
提供从真实 ~/.claude/skills 目录读取 skill 的 API 接口
"""
from typing import List, Optional
from fastapi import Depends, Header, Query, Request, UploadFile, File

from src.server_agent.common import ResultUtils, BaseResponse
from src.server_agent.controller.base import BaseController
from src.server_agent.exceptions import AuthenticationError, AuthorizationError
from src.server_agent.model import UserVO
from src.server_agent.service.SkillService import SkillService
from src.server_agent.service.UserService import UserService
from src.server_agent.exceptions.error_codes import ErrorCode


class SkillController(BaseController):
    """Skill 控制器 - 从文件系统读取真实的 skills"""
    
    def __init__(self):
        super().__init__(prefix="/skills", tags=["技能仓库"])
        self.default_skill_service = SkillService()
        self.user_service = UserService()
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
            request: Request,
            search: Optional[str] = Query(None, description="搜索关键词"),
        ) -> BaseResponse[List[dict]]:
            try:
                mapper = request.app.state.agent_mapper
                rows = await mapper.list_skills(search=search)
                skills = [
                    {
                        "id":          r["slug"],
                        "name":        r["name"],
                        "type":        r["type"],
                        "description": r["description"] or "",
                        "version":     r["version"],
                        "author":      r["author"] or "",
                        "user_id":     r["user_id"],
                        "created_at":  str(r["created_at"]) if r.get("created_at") else "",
                        "installed":   True,
                        "tags":        [r["type"]] if r.get("type") else [],
                    }
                    for r in rows
                ]
                return ResultUtils.success(skills)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取 skill 列表失败: {str(e)}")
        
        @self.router.get("/detail/{skill_id}")
        async def get_skill_detail(
            request: Request,
            skill_id: str,
        ) -> BaseResponse[dict]:
            try:
                from pathlib import Path
                mapper = request.app.state.agent_mapper
                record = await mapper.get_skill_by_slug(skill_id)
                if not record:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                storage_path = Path(record["storage_path"])
                svc = SkillService(str(storage_path.parent))
                skill = await svc.get_skill_detail(storage_path.name)
                if not skill:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 文件不存在")
                skill["user_id"] = record["user_id"]
                skill["created_at"] = str(record["created_at"]) if record.get("created_at") else ""
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
            request: Request,
            skill_id: str,
        ) -> BaseResponse[List[dict]]:
            try:
                from pathlib import Path
                mapper = request.app.state.agent_mapper
                record = await mapper.get_skill_by_slug(skill_id)
                if not record:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                storage_path = Path(record["storage_path"])
                svc = SkillService(str(storage_path.parent))
                files = await svc.get_skill_files(storage_path.name)
                if files is None:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 文件不存在")
                return ResultUtils.success(files)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取文件列表失败: {str(e)}")

        @self.router.get("/file-content/{skill_id}")
        async def get_skill_file_content(
            request: Request,
            skill_id: str,
            path: str = Query(..., description="文件相对路径"),
        ) -> BaseResponse[dict]:
            try:
                from pathlib import Path
                mapper = request.app.state.agent_mapper
                record = await mapper.get_skill_by_slug(skill_id)
                if not record:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                storage_path = Path(record["storage_path"])
                svc = SkillService(str(storage_path.parent))
                content = await svc.get_skill_file_content(storage_path.name, path)
                if content is None:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "文件不存在")
                return ResultUtils.success(content)
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"获取文件内容失败: {str(e)}")

        @self.router.post("/upload")
        async def upload_skill(
            request: Request,
            file: UploadFile = File(..., description="Skill zip 包"),
            userVO: UserVO = Depends(self._get_current_user),
        ) -> BaseResponse[dict]:
            try:
                from src.server_agent.service.SkillRegistryService import SkillRegistryService
                registry = SkillRegistryService(request.app.state.agent_mapper)
                zip_bytes = await file.read()
                record = await registry.upload_skill(zip_bytes, user_id=userVO.uid)
                return ResultUtils.success(record)
            except ValueError as e:
                return ResultUtils.error(ErrorCode.INVALID_INPUT, str(e))
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, f"上传 Skill 失败: {str(e)}")

        @self.router.delete("/{slug}")
        async def delete_skill(
            request: Request,
            slug: str,
            userVO: UserVO = Depends(self._get_current_admin_user),
        ) -> BaseResponse[dict]:
            try:
                import shutil
                from pathlib import Path
                mapper = request.app.state.agent_mapper
                record = await mapper.get_skill_by_slug(slug)
                if not record:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 不存在")
                storage_path = Path(record["storage_path"])
                if storage_path.exists():
                    shutil.rmtree(storage_path)
                await mapper.delete_skill(slug)
                return ResultUtils.success({"deleted": slug})
            except AuthorizationError:
                raise
            except Exception as e:
                return ResultUtils.error(ErrorCode.SYSTEM_ERROR, f"删除失败: {str(e)}")

    # ―――――――――――――――――――――――――――――――
    # 辅助方法
    # ―――――――――――――――――――――――――――――――

    async def _get_current_user(self, authorization: str = Header(None)) -> UserVO:
        if not authorization:
            raise AuthenticationError(detail="Missing authorization header")
        token = authorization[7:] if authorization.startswith("Bearer ") else authorization
        user = await self.user_service.get_user_by_token(token)
        if not user:
            raise AuthenticationError(detail="Invalid or expired token")
        return user

    async def _get_current_admin_user(
        self,
        authorization: str = Header(None),
    ) -> UserVO:
        user = await self._get_current_user(authorization)
        if user.role != "admin":
            raise AuthorizationError(
                detail="Admin access required",
                context={"user_id": user.uid, "user_role": user.role},
            )
        return user
