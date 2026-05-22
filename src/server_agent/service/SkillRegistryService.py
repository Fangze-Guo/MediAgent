"""
SkillRegistryService - 全局技能仓库管理

负责：
1. 启动时扫描 GLOBAL_SKILLS_DIR，将未注册技能同步到 global_skills 表
2. 处理用户上传的 zip 包，解压并注册到 DB
"""
import logging
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from src.server_agent.mapper.AgentMapper import AgentMapper

logger = logging.getLogger(__name__)

GLOBAL_SKILLS_DIR = Path(os.getenv("GLOBAL_SKILLS_DIR", os.path.expanduser("~/.claude/skills")))


def _parse_skill_md(skill_md: Path) -> dict:
    """解析 SKILL.md 的 YAML front matter，返回 key-value 字典"""
    try:
        text = skill_md.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        meta: dict = {}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
        return meta
    except Exception:
        return {}


class SkillRegistryService:

    def __init__(self, mapper: AgentMapper):
        self._mapper = mapper

    async def sync_from_filesystem(self) -> int:
        """
        扫描 GLOBAL_SKILLS_DIR，将未注册的技能补录到 global_skills 表。
        已存在的记录不覆盖（用 upsert 以 slug 为主键）。
        """
        if not GLOBAL_SKILLS_DIR.exists():
            logger.info("[SkillRegistryService] GLOBAL_SKILLS_DIR 不存在，跳过同步: %s", GLOBAL_SKILLS_DIR)
            return 0

        count = 0
        for skill_dir in GLOBAL_SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            meta = _parse_skill_md(skill_md)
            await self._mapper.upsert_skill(
                slug=skill_dir.name,
                name=meta.get("name", skill_dir.name),
                description=meta.get("description", ""),
                type_=meta.get("type", "user-invocable"),
                version=meta.get("version", "1.0.0"),
                author=meta.get("author", ""),
                storage_path=str(skill_dir),
            )
            count += 1

        logger.info("[SkillRegistryService] Synced %d skills from filesystem", count)
        return count

    async def upload_skill(self, zip_bytes: bytes, user_id: Optional[int] = None) -> dict:
        """
        上传 zip 包流程：
        1. 解压到临时目录
        2. 校验顶层目录唯一 & 包含 SKILL.md
        3. 复制到 GLOBAL_SKILLS_DIR/<slug>/
        4. 注册（upsert）到 global_skills 表
        """
        GLOBAL_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "upload.zip"
            zip_path.write_bytes(zip_bytes)

            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                roots = {n.split("/")[0] for n in names if n.strip("/")}
                if len(roots) != 1:
                    raise ValueError("zip 包必须包含且仅包含一个顶层目录作为 skill slug")

                root = roots.pop()
                if f"{root}/SKILL.md" not in names:
                    raise ValueError("zip 包中未找到 SKILL.md，不是有效的 Skill 包")

                zf.extractall(tmpdir)

            extracted = Path(tmpdir) / root
            slug = re.sub(r"[^a-z0-9-]", "-", root.lower()).strip("-")
            dst = GLOBAL_SKILLS_DIR / slug

            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(extracted, dst)

        meta = _parse_skill_md(dst / "SKILL.md")
        record = await self._mapper.upsert_skill(
            slug=slug,
            name=meta.get("name", slug),
            description=meta.get("description", ""),
            type_=meta.get("type", "user-invocable"),
            version=meta.get("version", "1.0.0"),
            author=meta.get("author", ""),
            storage_path=str(dst),
            user_id=user_id,
        )
        logger.info("[SkillRegistryService] Uploaded skill '%s'", slug)
        return record
