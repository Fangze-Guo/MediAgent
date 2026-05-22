"""
Agent 服务层 - 临床智能体管理 & Skill 安装/卸载

Skill 安装策略：hardcopy（从全局仓库复制到 agent 的 .claude/skills/ 目录）
"""
import os
import re
import shutil
import logging
from pathlib import Path
from typing import List, Optional

from src.server_agent.mapper.AgentMapper import AgentMapper

logger = logging.getLogger(__name__)

GLOBAL_SKILLS_DIR = Path(os.getenv("GLOBAL_SKILLS_DIR", os.path.expanduser("~/.claude/skills")))
CLINICAL_AGENTS_DIR = Path(os.getenv("CLINICAL_AGENTS_DIR", os.path.expanduser("~/mediagent/agents")))


def _make_agent_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    return slug + "-" + os.urandom(3).hex()


class AgentService:

    def __init__(self, mapper: AgentMapper):
        self._mapper = mapper

    async def register_existing_agent(
        self,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        base_dir: str,
    ) -> dict:
        """
        将已有项目目录注册为 clinical agent，不在文件系统创建任何目录。
        若 agent_id 已存在则幂等返回现有记录。
        """
        existing = await self._mapper.get_agent(agent_id)
        if existing:
            return existing

        record = await self._mapper.create_agent(
            agent_id=agent_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            base_dir=base_dir,
        )

        from src.server_agent.agent.claude.project_config import PROJECT_CONFIGS, ProjectConfig
        PROJECT_CONFIGS[agent_id] = ProjectConfig(
            project_id=agent_id,
            project_name=name,
            base_dir=Path(base_dir),
            system_prompt=system_prompt,
        )
        logger.info("[AgentService] Registered existing agent '%s' at %s", agent_id, base_dir)
        return record

    async def sync_to_project_configs(self) -> None:
        """
        启动时将 DB 中的 clinical_agents 同步到 PROJECT_CONFIGS，
        使 get_project_config() 能够感知到动态创建的 agent。
        """
        from src.server_agent.agent.claude.project_config import PROJECT_CONFIGS, ProjectConfig
        agents = await self._mapper.list_agents()
        for agent in agents:
            agent_id = agent["agent_id"]
            if agent_id not in PROJECT_CONFIGS:
                PROJECT_CONFIGS[agent_id] = ProjectConfig(
                    project_id=agent_id,
                    project_name=agent["name"],
                    base_dir=Path(agent["base_dir"]),
                    system_prompt=agent["system_prompt"] or "",
                )
        logger.info("[AgentService] Synced %d dynamic agents to PROJECT_CONFIGS", len(agents))

    async def create_agent(
        self,
        name: str,
        description: str,
        system_prompt: str,
        user_id: Optional[int] = None,
    ) -> dict:
        agent_id = _make_agent_id(name)
        base_dir = CLINICAL_AGENTS_DIR / agent_id
        skills_dir = base_dir / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        record = await self._mapper.create_agent(
            agent_id=agent_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            base_dir=str(base_dir),
            user_id=user_id,
        )

        # 同步到进程内的 PROJECT_CONFIGS
        from src.server_agent.agent.claude.project_config import PROJECT_CONFIGS, ProjectConfig
        PROJECT_CONFIGS[agent_id] = ProjectConfig(
            project_id=agent_id,
            project_name=name,
            base_dir=base_dir,
            system_prompt=system_prompt,
        )
        logger.info("[AgentService] Created agent '%s' at %s", agent_id, base_dir)
        return record

    async def list_agents(self, user_id: Optional[int] = None) -> List[dict]:
        return await self._mapper.list_agents(user_id)

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        return await self._mapper.get_agent(agent_id)

    async def update_agent(
        self,
        agent_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[dict]:
        record = await self._mapper.update_agent(agent_id, name, description, system_prompt)
        if record and system_prompt is not None:
            from src.server_agent.agent.claude.project_config import PROJECT_CONFIGS
            if agent_id in PROJECT_CONFIGS:
                PROJECT_CONFIGS[agent_id].system_prompt = system_prompt
        return record

    async def delete_agent(self, agent_id: str) -> bool:
        agent = await self._mapper.get_agent(agent_id)
        if not agent:
            return False
        base_dir = Path(agent["base_dir"])
        if base_dir.exists():
            shutil.rmtree(base_dir)
        ok = await self._mapper.delete_agent(agent_id)
        # 从 PROJECT_CONFIGS 移除
        from src.server_agent.agent.claude.project_config import PROJECT_CONFIGS
        PROJECT_CONFIGS.pop(agent_id, None)
        logger.info("[AgentService] Deleted agent '%s'", agent_id)
        return ok

    # ------------------------------------------------------------------ #
    # Skill 安装 / 卸载
    # ------------------------------------------------------------------ #

    async def install_skill(self, agent_id: str, skill_slug: str) -> bool:
        agent = await self._mapper.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent '{agent_id}' 不存在")

        src = GLOBAL_SKILLS_DIR / skill_slug
        if not src.exists():
            raise ValueError(f"Skill '{skill_slug}' 在全局仓库中不存在")

        dst = Path(agent["base_dir"]) / ".claude" / "skills" / skill_slug
        if dst.exists():
            return True  # 已安装，幂等

        shutil.copytree(src, dst)
        logger.info("[AgentService] Installed skill '%s' -> agent '%s'", skill_slug, agent_id)
        return True

    async def uninstall_skill(self, agent_id: str, skill_slug: str) -> bool:
        agent = await self._mapper.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent '{agent_id}' 不存在")

        dst = Path(agent["base_dir"]) / ".claude" / "skills" / skill_slug
        if not dst.exists():
            return False

        shutil.rmtree(dst)
        logger.info("[AgentService] Uninstalled skill '%s' from agent '%s'", skill_slug, agent_id)
        return True

    async def list_installed_skills(self, agent_id: str) -> Optional[List[str]]:
        agent = await self._mapper.get_agent(agent_id)
        if not agent:
            return None
        skills_dir = Path(agent["base_dir"]) / ".claude" / "skills"
        if not skills_dir.exists():
            return []
        return [d.name for d in skills_dir.iterdir() if d.is_dir()]
