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
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.server_agent.mapper.AgentMapper import AgentMapper

logger = logging.getLogger(__name__)

GLOBAL_SKILLS_DIR = Path(os.getenv("GLOBAL_SKILLS_DIR", os.path.expanduser("~/.claude/skills")))
ROLE_REGISTRY_ENV = os.getenv("MEDIAGENT_ROLE_REGISTRY")
ROLE_REGISTRY_PATH = Path(ROLE_REGISTRY_ENV).expanduser() if ROLE_REGISTRY_ENV else None
SKILL_ID_RE = re.compile(r"^[a-z0-9_]+$")
STANDARD_WRAPPER_ARGS = (
    "--patient-context",
    "--run-dir",
    "--run-id",
    "--phase",
    "--overwrite",
    "--keep-workspace",
)


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


def _read_json(path: Path) -> dict[str, Any]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class SkillRegistryService:

    def __init__(self, mapper: "AgentMapper"):
        self._mapper = mapper

    def _load_role_registry(self) -> dict[str, Any]:
        if ROLE_REGISTRY_PATH is None:
            return {}
        if not ROLE_REGISTRY_PATH.is_file():
            return {}
        payload = _read_json(ROLE_REGISTRY_PATH)
        roles = payload.get("roles")
        return roles if isinstance(roles, dict) else {}

    def validate_skill_dir(self, skill_dir: Path) -> dict:
        """
        Validate a Skill directory against the MediAgent patient Skill contract.

        This intentionally does not require every uploaded Skill to be patient-ready:
        a plain SKILL.md package can still be installed as a normal ClaudeCode Skill.
        """
        skill_dir = skill_dir.resolve()
        errors: list[str] = []
        warnings: list[str] = []
        result: dict[str, Any] = {
            "skill_dir": str(skill_dir),
            "installable": False,
            "skill_level": "invalid",
            "valid_patient_skill": False,
            "pipeline_ready": False,
            "skill_id": None,
            "errors": errors,
            "warnings": warnings,
        }

        if not skill_dir.is_dir():
            errors.append(f"Skill directory does not exist: {skill_dir}")
            return result

        skill_md = skill_dir / "SKILL.md"
        config_path = skill_dir / "skill.config.json"
        if not skill_md.is_file():
            errors.append("Missing SKILL.md.")
            return result

        result["installable"] = True
        result["skill_level"] = "plain_claude_skill"

        if not config_path.is_file():
            warnings.append("Missing skill.config.json; this Skill will be installed as a plain ClaudeCode Skill.")
            return result

        try:
            config = _read_json(config_path)
        except Exception as exc:
            errors.append(f"Invalid skill.config.json: {exc}")
            return result

        roles = self._load_role_registry()
        validate_roles = ROLE_REGISTRY_PATH is not None
        skill_id = config.get("skill_id")
        result["skill_id"] = skill_id
        if not isinstance(skill_id, str) or not SKILL_ID_RE.fullmatch(skill_id):
            errors.append("skill_id must match ^[a-z0-9_]+$.")
        if config.get("schema_version") != "medagent.skill_config.v1":
            errors.append("schema_version must be medagent.skill_config.v1.")
        if config.get("run_mode") != "patient_context":
            errors.append("run_mode must be patient_context for MediAgent Patient Skill.")

        entrypoints = config.get("entrypoints")
        if not isinstance(entrypoints, dict):
            errors.append("entrypoints must be an object.")
            entrypoints = {}

        wrapper_path: Path | None = None
        wrapper_rel = entrypoints.get("patient_wrapper")
        if not isinstance(wrapper_rel, str) or not wrapper_rel:
            errors.append("entrypoints.patient_wrapper is required.")
        else:
            wrapper_path = (skill_dir / wrapper_rel).resolve()
            try:
                wrapper_path.relative_to(skill_dir)
            except ValueError:
                errors.append("entrypoints.patient_wrapper must stay inside skill directory.")
            if not wrapper_path.is_file():
                errors.append(f"Wrapper file does not exist: {wrapper_rel}")

        native_rel = entrypoints.get("native_script")
        if isinstance(native_rel, str) and native_rel:
            native_path = (skill_dir / native_rel).resolve()
            try:
                native_path.relative_to(skill_dir)
            except ValueError:
                errors.append("entrypoints.native_script must stay inside skill directory.")
            if not native_path.is_file():
                warnings.append(f"Native script does not exist: {native_rel}")

        phase = config.get("phase")
        if not isinstance(phase, dict):
            errors.append("phase must be an object.")
        else:
            supported = _as_list(phase.get("supported"))
            default = phase.get("default")
            if default not in supported:
                errors.append("phase.default must be included in phase.supported.")
            for item in supported:
                if item not in {"pre", "post", "both"}:
                    errors.append(f"Unsupported phase value: {item}")

        run_id = config.get("run_id")
        if not isinstance(run_id, dict):
            errors.append("run_id must be an object.")
        elif "{patient_dir}" not in str(run_id.get("required_run_dir_template", "")):
            errors.append("run_id.required_run_dir_template must include {patient_dir}.")

        output_refs: set[tuple[str, Optional[str]]] = set()
        for input_spec in _as_list(config.get("inputs")):
            if not isinstance(input_spec, dict):
                errors.append("Each inputs item must be an object.")
                continue
            role = input_spec.get("role")
            if validate_roles and role not in roles:
                warnings.append(
                    f"Unknown input role: {role}; it should be registered or mapped when the Skill is installed into an agent."
                )

        for output_spec in _as_list(config.get("outputs")):
            if not isinstance(output_spec, dict):
                errors.append("Each outputs item must be an object.")
                continue
            role = output_spec.get("role")
            if validate_roles and role not in roles:
                warnings.append(
                    f"Unknown output role: {role}; it should be registered or mapped when the Skill is installed into an agent."
                )
            phases = _as_list(output_spec.get("phases"))
            if isinstance(role, str) and not phases:
                output_refs.add((role, None))
            for phase_item in phases:
                if phase_item in {"pre", "post"} and isinstance(role, str):
                    output_refs.add((role, phase_item))
                elif phase_item == "both" and isinstance(role, str):
                    output_refs.add((role, None))
            if "_internal" in str(output_spec.get("path_template", "")):
                errors.append("outputs[].path_template must not point to _internal.")

        context_exports = _as_list(config.get("context_exports"))
        for export in context_exports:
            if not isinstance(export, dict):
                errors.append("Each context_exports item must be an object.")
                continue
            output_role = export.get("output_role")
            phase_value = export.get("phase")
            target_path_key = export.get("target_path_key")
            priority = export.get("priority")
            if (output_role, phase_value) not in output_refs:
                errors.append(f"context_exports item does not match outputs role/phase: {output_role}/{phase_value}")
            role_config = roles.get(output_role)
            if not validate_roles:
                pass
            elif not isinstance(role_config, dict):
                warnings.append(
                    f"Unknown context export role: {output_role}; export target validation is deferred until agent installation."
                )
            elif target_path_key not in _as_list(role_config.get("path_keys")):
                errors.append(f"context_exports target_path_key is not valid for role {output_role}: {target_path_key}")
            if priority != "fallback_when_no_uploaded_file":
                errors.append("context_exports.priority must be fallback_when_no_uploaded_file.")

        manifest = config.get("manifest")
        if not isinstance(manifest, dict):
            errors.append("manifest must be an object.")
        else:
            status_values = set(_as_list(manifest.get("status_values")))
            if not {"running", "success", "failed", "cancelled"}.issubset(status_values):
                errors.append("manifest.status_values must include running, success, failed and cancelled.")

        safety = config.get("safety")
        if not isinstance(safety, dict):
            errors.append("safety must be an object.")
        else:
            if safety.get("writes_only_to_run_dir") is not True:
                errors.append("safety.writes_only_to_run_dir must be true.")
            if safety.get("modifies_patient_source_files") is not False:
                errors.append("safety.modifies_patient_source_files must be false.")

        if wrapper_path and wrapper_path.is_file():
            try:
                help_result = subprocess.run(
                    [sys.executable, str(wrapper_path), "--help"],
                    cwd=str(skill_dir),
                    text=True,
                    capture_output=True,
                    timeout=10,
                )
                help_text = f"{help_result.stdout}\n{help_result.stderr}"
                if help_result.returncode not in {0, 1}:
                    warnings.append(f"Wrapper --help returned {help_result.returncode}.")
                for arg in STANDARD_WRAPPER_ARGS:
                    if arg not in help_text:
                        errors.append(f"Wrapper help does not expose standard argument: {arg}")
            except Exception as exc:
                warnings.append(f"Could not inspect wrapper --help: {exc}")

        if not errors:
            result["valid_patient_skill"] = True
            result["pipeline_ready"] = bool(context_exports)
            result["skill_level"] = "pipeline_ready" if context_exports else "patient_skill"
        return result

    def _extract_uploaded_zip(self, zip_bytes: bytes, tmpdir: str) -> Path:
        zip_path = Path(tmpdir) / "upload.zip"
        zip_path.write_bytes(zip_bytes)
        tmp_root = Path(tmpdir).resolve()

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            roots = {n.split("/")[0] for n in names if n.strip("/")}
            if len(roots) != 1:
                raise ValueError("zip 包必须包含且仅包含一个顶层目录作为 skill slug")

            root = roots.pop()
            if f"{root}/SKILL.md" not in names:
                raise ValueError("zip 包中未找到 SKILL.md，不是有效的 Skill 包")

            for member in zf.infolist():
                target = (tmp_root / member.filename).resolve()
                try:
                    target.relative_to(tmp_root)
                except ValueError as exc:
                    raise ValueError("zip 包包含非法路径") from exc
            zf.extractall(tmpdir)
        return Path(tmpdir) / root

    def validate_skill_zip(self, zip_bytes: bytes) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            extracted = self._extract_uploaded_zip(zip_bytes, tmpdir)
            return self.validate_skill_dir(extracted)

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
            extracted = self._extract_uploaded_zip(zip_bytes, tmpdir)
            validation = self.validate_skill_dir(extracted)
            if validation.get("errors"):
                raise ValueError("Skill 包校验失败: " + "; ".join(validation["errors"]))

            root = extracted.name
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
        record["validation"] = self.validate_skill_dir(dst)
        record["skill_level"] = record["validation"].get("skill_level")
        record["valid_patient_skill"] = record["validation"].get("valid_patient_skill")
        record["pipeline_ready"] = record["validation"].get("pipeline_ready")
        logger.info("[SkillRegistryService] Uploaded skill '%s'", slug)
        return record
