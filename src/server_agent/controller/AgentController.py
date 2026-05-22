"""
AgentController - 临床智能体管理 API

路由前缀: /clinical-agents
"""
from typing import List, Optional

from fastapi import Request
from pydantic import BaseModel, Field

from src.server_agent.common import ResultUtils, BaseResponse
from src.server_agent.controller.base import BaseController
from src.server_agent.exceptions.error_codes import ErrorCode


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="智能体名称")
    description: str = Field("", max_length=500, description="描述")
    system_prompt: str = Field("", max_length=5000, description="系统提示词")


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = Field(None, max_length=5000)


class AgentController(BaseController):

    def __init__(self):
        super().__init__(prefix="/clinical-agents", tags=["临床智能体"])
        self._register_routes()

    def _get_service(self, request: Request):
        from src.server_agent.service.AgentService import AgentService
        return AgentService(request.app.state.agent_mapper)

    def _register_routes(self):

        @self.router.post("/create")
        async def create_agent(
            body: CreateAgentRequest, request: Request
        ) -> BaseResponse[dict]:
            try:
                svc = self._get_service(request)
                agent = await svc.create_agent(body.name, body.description, body.system_prompt)
                return ResultUtils.success(agent)
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

        @self.router.get("/list")
        async def list_agents(request: Request) -> BaseResponse[List[dict]]:
            try:
                svc = self._get_service(request)
                agents = await svc.list_agents()
                return ResultUtils.success(agents)
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

        @self.router.get("/{agent_id}")
        async def get_agent(agent_id: str, request: Request) -> BaseResponse[dict]:
            try:
                svc = self._get_service(request)
                agent = await svc.get_agent(agent_id)
                if not agent:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Agent 不存在")
                return ResultUtils.success(agent)
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

        @self.router.put("/{agent_id}")
        async def update_agent(
            agent_id: str, body: UpdateAgentRequest, request: Request
        ) -> BaseResponse[dict]:
            try:
                svc = self._get_service(request)
                agent = await svc.update_agent(
                    agent_id, body.name, body.description, body.system_prompt
                )
                if not agent:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Agent 不存在")
                return ResultUtils.success(agent)
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

        @self.router.delete("/{agent_id}")
        async def delete_agent(agent_id: str, request: Request) -> BaseResponse[bool]:
            try:
                svc = self._get_service(request)
                ok = await svc.delete_agent(agent_id)
                if not ok:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Agent 不存在")
                return ResultUtils.success(True)
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

        # ---- Skill 安装管理 ----

        @self.router.post("/{agent_id}/skills/{skill_slug}/install")
        async def install_skill(
            agent_id: str, skill_slug: str, request: Request
        ) -> BaseResponse[bool]:
            try:
                svc = self._get_service(request)
                await svc.install_skill(agent_id, skill_slug)
                return ResultUtils.success(True)
            except ValueError as e:
                return ResultUtils.error(ErrorCode.NOT_FOUND, str(e))
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

        @self.router.delete("/{agent_id}/skills/{skill_slug}")
        async def uninstall_skill(
            agent_id: str, skill_slug: str, request: Request
        ) -> BaseResponse[bool]:
            try:
                svc = self._get_service(request)
                ok = await svc.uninstall_skill(agent_id, skill_slug)
                if not ok:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Skill 未安装")
                return ResultUtils.success(True)
            except ValueError as e:
                return ResultUtils.error(ErrorCode.NOT_FOUND, str(e))
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

        @self.router.get("/{agent_id}/skills")
        async def list_installed_skills(
            agent_id: str, request: Request
        ) -> BaseResponse[List[str]]:
            try:
                svc = self._get_service(request)
                skills = await svc.list_installed_skills(agent_id)
                if skills is None:
                    return ResultUtils.error(ErrorCode.NOT_FOUND, "Agent 不存在")
                return ResultUtils.success(skills)
            except Exception as e:
                return ResultUtils.error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))
