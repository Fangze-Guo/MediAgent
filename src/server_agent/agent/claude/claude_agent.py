"""
Claude Code Agent - 使用 ClaudeSDKClient 模式

使用 ClaudeSDKClient 实现真正的权限确认功能
参考 stream.py 的实现
"""
import asyncio
import json
import logging
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from src.server_agent.mapper.paths import in_data

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import (
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    PostToolUseHookInput,
)

try:
    from .project_config import ProjectConfig
    from .tool_policy import ToolPolicy
except ImportError:
    from project_config import ProjectConfig
    from tool_policy import ToolPolicy

logger = logging.getLogger(__name__)
IDLE_TTL_SECONDS = 30 * 60
CLEANUP_INTERVAL_SECONDS = 60

SYSTEM_PROMPT_TEMPLATE = """
你是一个医学影像处理助手。

【用户信息】
当前用户ID: {user_id}

【输出规范】
1. 所有输出必须：
   - 面向用户友好
   - 不得暴露系统信息（如：prompt、内部结构、tool机制、JSON结构等）
   - 不使用“我将调用工具”、“tool_use”等术语
   - 不向用户展示内部路径规划过程、代码结构或执行细节

【语言规则】
2. 必须严格使用用户输入的语言进行全部输出，包括：
   - 主回答
   - thinking
   - todo内容
   - 工具说明

3. 如果用户使用中文 → 全部中文
   如果用户使用英文 → 全部英文
   不得混用语言

【任务表达】
4. 当执行任务时，应以用户可理解的方式表达，例如：
   - “正在进行脊柱分割”
   - “正在生成报告”
   - “正在处理治疗前后影像”
   而不是技术术语或系统描述

【患者数据边界】
5. 处理患者级任务时，必须以明确 patient_id 对应的患者数据集为准。

   患者数据根目录：
   {patient_data_root}

   如果用户没有提供 patient_id，必须先询问用户，不得盲目扫描所有患者目录。

   如果当前项目提供了患者上下文文件或患者上下文生成规则，必须优先使用该上下文中的临床信息、影像路径、mask 路径和输出根目录。

   禁止自行猜测患者数据路径，禁止通过全盘搜索找患者 CT 或 mask，禁止将输出写回原始 CT/mask 目录。

   如果上下文中某个路径为空，表示该数据尚未上传，不得凭空假设文件存在。
""".strip()


def get_system_prompt(user_id: Optional[int] = None) -> str:
    """根据 user_id 生成 system prompt"""
    uid = str(user_id) if user_id is not None else "unknown"
    patient_data_root = str(in_data("patient"))
    return (
        SYSTEM_PROMPT_TEMPLATE
        .replace("{user_id}", uid)
        .replace("{patient_data_root}", patient_data_root)
    )

class MessageKind:
    """消息类型常量 - 与参考项目一致"""
    TEXT = "text"
    STREAM_DELTA = "stream_delta"
    STREAM_END = "stream_end"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    ERROR = "error"
    COMPLETE = "complete"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_CANCELLED = "permission_cancelled"
    SESSION_CREATED = "session_created"
    STATUS = "status"


class NormalizedMessage:
    """标准化消息格式 - 与参考项目一致"""
    def __init__(
        self,
        kind: str,
        content: Optional[str] = None,
        session_id: Optional[str] = None,
        provider: str = "claude",
        role: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_input: Optional[dict] = None,
        tool_id: Optional[str] = None,
        tool_result: Optional[dict] = None,
        request_id: Optional[str] = None,
        reason: Optional[str] = None,
        exit_code: Optional[int] = None,
        is_error: bool = False,
        is_new_session: bool = False,
        text: Optional[str] = None,
        new_session_id: Optional[str] = None,
        parent_tool_use_id: Optional[str] = None,
        tokens: Optional[int] = None,
        can_interrupt: Optional[bool] = None,
        token_budget: Optional[dict] = None,
        aborted: Optional[bool] = None,
    ):
        self.kind = kind
        self.content = content
        self.session_id = session_id
        self.provider = provider
        self.role = role
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.tool_id = tool_id
        self.tool_result = tool_result
        self.request_id = request_id
        self.reason = reason
        self.exit_code = exit_code
        self.is_error = is_error
        self.is_new_session = is_new_session
        self.text = text
        self.new_session_id = new_session_id
        self.parent_tool_use_id = parent_tool_use_id
        self.tokens = tokens
        self.can_interrupt = can_interrupt
        self.token_budget = token_budget
        self.aborted = aborted

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {"kind": self.kind, "provider": self.provider}
        if self.session_id:
            result["sessionId"] = self.session_id
        if self.new_session_id:
            result["newSessionId"] = self.new_session_id
        if self.content is not None:
            result["content"] = self.content
        if self.text is not None:
            result["text"] = self.text
        if self.role:
            result["role"] = self.role
        if self.tool_name:
            result["toolName"] = self.tool_name
        if self.tool_input:
            result["input"] = self.tool_input
        if self.tool_id:
            result["toolId"] = self.tool_id
        if self.tool_result:
            result["toolResult"] = self.tool_result
        if self.request_id:
            result["requestId"] = self.request_id
        if self.reason:
            result["reason"] = self.reason
        if self.exit_code is not None:
            result["exitCode"] = self.exit_code
        if self.is_error:
            result["isError"] = self.is_error
        if self.is_new_session:
            result["isNewSession"] = self.is_new_session
        if self.parent_tool_use_id:
            result["parentToolUseId"] = self.parent_tool_use_id
        if self.tokens is not None:
            result["tokens"] = self.tokens
        if self.can_interrupt is not None:
            result["canInterrupt"] = self.can_interrupt
        if self.token_budget:
            result["tokenBudget"] = self.token_budget
        if self.aborted is not None:
            result["aborted"] = self.aborted
        return result


class ClaudeAgent:
    """Claude Code Agent类 - 使用 ClaudeSDKClient 模式"""

    def __init__(
        self,
        permission_mode: str = "bypassPermissions",
        project_config: Optional[ProjectConfig] = None,
    ):
        """
        初始化 Claude Code Agent

        Args:
            permission_mode: 权限模式
                - bypassPermissions: 跳过权限检查（默认）
                - plan: AI 先输出计划，等待用户确认
                - default: 需要权限确认（通过队列机制实现）
            project_config: 项目配置（传入后启用工具/路径隔离）
        """
        self._permission_mode = permission_mode  # type: ignore
        self._project_config = project_config
        self._tool_policy: Optional[ToolPolicy] = None
        if project_config:
            self._tool_policy = ToolPolicy(project_config)
            logger.info(
                f"[ClaudeAgent] 启用项目隔离: project={project_config.project_id}, "
                f"base_dir={project_config.base_dir}"
            )

        self._last_session_id: Optional[str] = None
        self._active_sessions: dict[str, asyncio.Event] = {}

        # 权限确认相关 - 使用队列解耦 hook 和消息流
        self._permission_queue: asyncio.Queue = asyncio.Queue()  # 权限请求队列
        self._permission_events: dict[str, asyncio.Event] = {}  # request_id -> event
        self._permission_results: dict[str, bool] = {}  # request_id -> allow/deny
        self._skill_event_queues: dict[str, set[asyncio.Queue]] = {}

        # ClaudeSDKClient 实例（每个会话一个）
        self._clients: dict[str, ClaudeSDKClient] = {}  # session_id -> client
        self._session_last_active: dict[str, float] = {}
        self._dead_sessions: set[str] = set()

        # sdk_session_id -> conversation_id 映射，供 hook 提取 conversation_id
        self._session_conversation_map: dict[str, str] = {}

        # tool_use_id -> task_id 映射：Bash 执行前（_can_use_tool_hook）存入，
        # 执行后（_post_tool_use_hook）弹出并精确调用 mark_finished。
        # fallback key 格式："{session_id}|{command[:200]}"
        self._tool_task_map: dict[str, str] = {}

        # task_id -> asyncio.Task 映射，追踪后台 PID 监控协程，
        # 会话取消/异常时可撤销，防止僵尸 watcher 改写已终态的任务
        self._bg_watchers: dict[str, asyncio.Task] = {}

        # Skill 脚本映射缓存：{脚本文件名: skill_name | None}
        # 用于命令仅执行相对路径脚本时反查 skill。重名脚本标记为 None，避免误归类。
        self._skill_script_map: dict[str, Optional[str]] = {}
        if project_config:
            skills_dir = project_config.base_dir / ".claude" / "skills"
            if skills_dir.is_dir():
                for skill_dir in skills_dir.iterdir():
                    if not skill_dir.is_dir():
                        continue
                    skill_name = skill_dir.name
                    for script in skill_dir.rglob("*"):
                        if not script.is_file() or script.suffix not in (".py", ".sh"):
                            continue
                        existing = self._skill_script_map.get(script.name)
                        if existing is None and script.name in self._skill_script_map:
                            continue
                        self._skill_script_map[script.name] = (
                            skill_name if existing in (None, skill_name) else None
                        )
                logger.info(f"[ClaudeAgent] Skill script map: {len(self._skill_script_map)} entries")

        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_closing = False

    def _touch_session(self, session_id: Optional[str]):
        if session_id:
            self._session_last_active[session_id] = time.time()

    def _detect_skill_from_bash_command(self, command: str) -> Optional[str]:
        """Return the skill whose executable script is actually invoked by a Bash command."""
        import re
        import shlex

        if not command or re.search(r"(?:^|\s)(?:--help|-h)(?:\s|$)", command):
            return None

        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        if any(Path(part).name == "run_skill_task.py" for part in parts):
            for index, part in enumerate(parts):
                if part == "--skill-id" and index + 1 < len(parts):
                    return parts[index + 1]
                if part.startswith("--skill-id="):
                    return part.split("=", 1)[1]
            return "run_skill_task"

        # Match interpreter-backed entrypoints such as:
        #   python /.../.claude/skills/lung-crop/scripts/run_lung_crop.py
        #   cd /.../.claude/skills/foo/scripts && python run_predict.py
        script_match = re.search(
            r"(?:^|[;&|]\s*|\s)"
            r"(?:\S*/)?(?:python[0-9.]*|bash|sh|perl|ruby|node)"
            r"\s+(?:(?:-[^\s]+\s+)*)"
            r"(?P<script>[^\s;&|]+?\.(?:py|sh))(?=\s|$)",
            command,
        )
        if not script_match:
            return None

        script_path = script_match.group("script").strip("\"'")
        explicit_skill = re.search(r"[/~][^\s]*?/\.claude/skills/([^/\s]+)", script_path)
        if explicit_skill:
            return explicit_skill.group(1)

        return self._skill_script_map.get(Path(script_path).name)

    def _ensure_runner_run_id(self, command: str) -> str:
        """Inject a run_id for simple run_skill_task.py commands so manifest_path is known at submit time."""
        import shlex

        if not command or any(token in command for token in (";", "&&", "||", "|", "<", ">")):
            return command
        try:
            parts = shlex.split(command)
        except ValueError:
            return command
        if not any(Path(part).name == "run_skill_task.py" for part in parts):
            return command

        def option_value(name: str) -> Optional[str]:
            for index, part in enumerate(parts):
                if part == name and index + 1 < len(parts):
                    return parts[index + 1]
                prefix = f"{name}="
                if part.startswith(prefix):
                    return part[len(prefix):]
            return None

        if option_value("--run-id"):
            return command
        skill_id = option_value("--skill-id") or "skill_task"
        phase = option_value("--phase") or "both"
        slug = skill_id if phase == "both" else f"{skill_id}_{phase}"
        run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug.strip().lower().replace('-', '_')}"
        return shlex.join([*parts, "--run-id", run_id])

    def _register_skill_event_queue(self, conversation_id: Optional[str], queue: asyncio.Queue) -> None:
        if conversation_id:
            self._skill_event_queues.setdefault(conversation_id, set()).add(queue)

    def _unregister_skill_event_queue(self, conversation_id: Optional[str], queue: asyncio.Queue) -> None:
        if not conversation_id:
            return
        queues = self._skill_event_queues.get(conversation_id)
        if not queues:
            return
        queues.discard(queue)
        if not queues:
            self._skill_event_queues.pop(conversation_id, None)

    async def _publish_skill_event(self, conversation_id: str, event: dict) -> None:
        for queue in list(self._skill_event_queues.get(conversation_id) or []):
            await queue.put(event)

    async def _submit_skill_task_from_bash(
        self,
        *,
        command: str,
        tool_use_id: Optional[Any] = None,
        session_id: Optional[str] = None,
        run_in_background: bool = False,
        source: str = "tool_use",
    ) -> Optional[str]:
        """Register a Skill task when ClaudeCode invokes the Bash runner."""
        command = self._ensure_runner_run_id(command)
        detected_skill = self._detect_skill_from_bash_command(command)
        if not detected_skill:
            return None

        map_keys: list[str] = []
        if tool_use_id:
            map_keys.append(str(tool_use_id))
        if session_id and command:
            map_keys.append(f"{session_id}|{command[:200]}")

        for key in map_keys:
            existing_task_id = self._tool_task_map.get(key)
            if existing_task_id:
                from src.server_agent.service.SkillTaskManager import get_skill_task_manager
                get_skill_task_manager().update_params(
                    existing_task_id,
                    {
                        "command": command,
                        "run_in_background": run_in_background,
                        "registration_source": source,
                    },
                )
                if tool_use_id:
                    self._tool_task_map[str(tool_use_id)] = existing_task_id
                logger.info(
                    f"[SKILL_TASK] Reused task {existing_task_id} for '{detected_skill}' from {source}"
                )
                return existing_task_id

        conversation_id = self._session_conversation_map.get(session_id or "", "")

        from src.server_agent.service.SkillTaskManager import get_skill_task_manager
        task_manager = get_skill_task_manager()
        task_id = task_manager.submit(
            skill_name=detected_skill,
            params={
                "command": command,
                "run_in_background": run_in_background,
                "registration_source": source,
            },
            conversation_id=conversation_id,
        )

        if not map_keys and command:
            map_keys.append(f"{session_id or self._last_session_id or ''}|{command[:200]}")
        for key in map_keys:
            self._tool_task_map[key] = task_id

        logger.info(
            f"[SKILL_TASK] Registered task {task_id} for '{detected_skill}' "
            f"from {source}, tool_use_id={tool_use_id}, session={session_id}"
        )
        event = {
            "kind": "skill_submitted",
            "taskId": task_id,
            "skillName": detected_skill,
            "conversationId": conversation_id,
            "status": "running",
            "provider": "claude",
            "done": False,
            "_is_skill_submitted": True,
        }
        if conversation_id:
            await self._publish_skill_event(conversation_id, event)
        else:
            logger.warning(f"[SKILL_TASK] Task {task_id} has no conversation_id; skip SSE push")
        return task_id

    def _rekey_session(self, old_session_id: str, new_session_id: str) -> None:
        """Replace the SDK startup handle with Claude CLI's persisted session ID."""
        if not old_session_id or not new_session_id or old_session_id == new_session_id:
            return

        for mapping in (
            self._clients,
            self._active_sessions,
            self._session_last_active,
            self._session_conversation_map,
        ):
            if old_session_id in mapping:
                mapping[new_session_id] = mapping.pop(old_session_id)

        if old_session_id in self._dead_sessions:
            self._dead_sessions.discard(old_session_id)
            self._dead_sessions.add(new_session_id)

        if self._last_session_id == old_session_id:
            self._last_session_id = new_session_id

        logger.info(f"[SESSION] Rekeyed startup handle {old_session_id} -> {new_session_id}")

    def _start_cleanup_task_if_needed(self):
        if self._cleanup_task is not None and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(self._idle_cleanup_loop())

    async def _idle_cleanup_loop(self):
        try:
            while not self._is_closing:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                now = time.time()
                stale_sessions: list[tuple[str, float]] = []
                for sid, ts in self._session_last_active.items():
                    if sid not in self._clients:
                        continue
                    idle_seconds = now - ts
                    if idle_seconds > IDLE_TTL_SECONDS:
                        stale_sessions.append((sid, idle_seconds))

                for sid, idle_seconds in stale_sessions:
                    if sid in self._active_sessions:
                        logger.info(
                            f"[CLIENT] Skip idle cleanup for active session={sid}, "
                            f"idle_seconds={int(idle_seconds)}"
                        )
                        continue
                    logger.info(
                        f"[CLIENT] Closing idle client session={sid}, "
                        f"idle_seconds={int(idle_seconds)}, ttl_seconds={IDLE_TTL_SECONDS}"
                    )
                    await self.close_client(sid)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[CLIENT] Idle cleanup loop error: {e}")

    async def _dummy_hook(self, input_data: Any, tool_use_id: Any, context: Any):
        """
        Dummy hook - 官方文档要求的 Python workaround：保持流打开，才能触发 can_use_tool
        """
        logger.info(f"[DUMMY_HOOK] Called! tool_use_id={tool_use_id}")
        return {"continue_": True}  # type: ignore

    async def _post_tool_use_hook(self, input_data: PostToolUseHookInput, tool_use_id: Any, context: Any):
        """
        PostToolUse hook - Bash 工具执行完成后触发，用于更新 Skill 任务终态。
        通过 _tool_task_map[tool_use_id] 精确定位对应任务，不扫描全部 running 任务，
        避免误标、卡死等问题。
        """
        tool_name = input_data.get("tool_name") if isinstance(input_data, dict) else getattr(input_data, "tool_name", None)
        if tool_name != "Bash":
            return {"continue_": True}  # type: ignore

        tool_input = input_data.get("tool_input", {}) if isinstance(input_data, dict) else getattr(input_data, "tool_input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}

        # 1. 用 tool_use_id 直接查找对应的 task_id（最可靠路径）
        task_id: str | None = None
        if tool_use_id:
            task_id = self._tool_task_map.pop(str(tool_use_id), None)

        # 2. fallback：用 session_id + command[:200] 组成的 key 查找
        if not task_id:
            command = tool_input.get("command", "")
            if command:
                hook_session_id = self._last_session_id or ""
                fallback_key = f"{hook_session_id}|{command[:200]}"
                task_id = self._tool_task_map.pop(fallback_key, None)

        if not task_id:
            # 此 Bash 命令不对应任何 Skill 任务，直接放行
            return {"continue_": True}  # type: ignore

        # 3. 判断成功/失败
        run_in_background = tool_input.get("run_in_background", False)
        tool_response = input_data.get("tool_response") if isinstance(input_data, dict) else getattr(input_data, "tool_response", None)
        is_error = False
        response_text = ""
        if isinstance(tool_response, dict):
            is_error = tool_response.get("is_error", False)
            response_text = tool_response.get("content", "") or ""

        from src.server_agent.service.SkillTaskManager import get_skill_task_manager
        task_manager = get_skill_task_manager()

        def _extract_runner_payload(text: str) -> dict:
            import json as _json
            payload: dict = {}
            for line in (text or "").splitlines():
                line = line.strip()
                if not line.startswith("{") or not line.endswith("}"):
                    continue
                try:
                    item = _json.loads(line)
                except Exception:
                    continue
                if not isinstance(item, dict):
                    continue
                if item.get("event") in {"skill_task_start", "skill_task_finished"}:
                    for key in ("patient_id", "skill_id", "run_id", "run_dir", "manifest_path"):
                        if item.get(key):
                            payload[key] = item[key]
            return payload

        runner_payload = _extract_runner_payload(response_text)
        if runner_payload:
            task_manager.update_params(task_id, runner_payload)
            logger.info(f"[POST_TOOL_USE] Updated task {task_id} params from runner payload: {runner_payload}")

        task = task_manager.get_task(task_id)
        if task and (task.params.get("manifest_path") or task.params.get("run_dir")):
            logger.info(f"[POST_TOOL_USE] Task {task_id} is manifest-tracked; skip Bash terminal state")
            return {"continue_": True}  # type: ignore

        def _read_manifest_status(manifest_path: Optional[str]) -> tuple[Optional[str], Optional[str]]:
            if not manifest_path:
                return None, None
            try:
                manifest_file = Path(manifest_path)
                if not manifest_file.is_file():
                    return None, None
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    return None, None
                status = manifest.get("status")
                errors = manifest.get("errors") or []
                error_text = "; ".join(str(item) for item in errors) if isinstance(errors, list) else str(errors)
                return (status if isinstance(status, str) else None), (error_text or None)
            except Exception as exc:
                logger.warning(f"[POST_TOOL_USE] Failed to read manifest status: {exc}")
                return None, None

        response_indicates_background = "Command running in background" in response_text
        manifest_path = runner_payload.get("manifest_path") if runner_payload else None

        if run_in_background and not is_error:
            # 4a. 后台任务：从 stdout 提取 PID，启动监控协程而非立即标记终态
            import re as _re
            pid: Optional[int] = None
            m = _re.search(r'\[?\d+\]?\s+(\d+)', response_text)
            if m:
                pid = int(m.group(1))
            else:
                m2 = _re.match(r'^\s*(\d+)\s*$', response_text.strip())
                if m2:
                    pid = int(m2.group(1))

            if pid:
                watcher = asyncio.create_task(self._watch_background_task(task_id, pid))
                self._bg_watchers[task_id] = watcher
                logger.info(f"[POST_TOOL_USE] BG task {task_id} pid={pid}, watcher started")
            else:
                # 提取不到 PID，保守地直接标记 success
                task_manager.mark_finished(task_id, success=True)
                logger.warning(f"[POST_TOOL_USE] BG task {task_id}: no PID found in stdout, marked success conservatively")
        else:
            if response_indicates_background:
                # ClaudeCode auto-backgrounded the Bash command. This only means the shell
                # accepted the job; the Skill itself is still tracked by manifest.json.
                logger.info(f"[POST_TOOL_USE] Task {task_id} was auto-backgrounded by ClaudeCode; keep running")
                return {"continue_": True}  # type: ignore

            manifest_status, manifest_error = _read_manifest_status(manifest_path)
            if manifest_status in {"success", "failed"}:
                task_manager.mark_finished(
                    task_id,
                    success=manifest_status == "success",
                    error=manifest_error if manifest_status == "failed" else None,
                )
                logger.info(f"[POST_TOOL_USE] Task {task_id} marked from manifest status={manifest_status}")
            elif manifest_path:
                # A runner command finished but its manifest is missing or not terminal.
                # Avoid false success; leave the task visible as running so manifest polling
                # or manual inspection can reveal the real state.
                logger.warning(
                    f"[POST_TOOL_USE] Runner finished but manifest is not terminal for task {task_id}: "
                    f"manifest_path={manifest_path}, manifest_status={manifest_status}"
                )
            else:
                # Non-runner Skill commands without a manifest still fall back to tool status.
                success = not is_error
                error_msg = str(response_text)[:200] if not success else None
                task_manager.mark_finished(task_id, success=success, error=error_msg)
                logger.info(f"[POST_TOOL_USE] FG task {task_id} marked {'success' if success else 'failed'}")

        return {"continue_": True}  # type: ignore

    async def _watch_background_task(self, task_id: str, pid: int):
        """
        后台任务 PID 监控协程。
        每 30s 检查一次 psutil.pid_exists(pid)，
        进程消失后标记 success；超过 4h 未结束则标记 failed。
        """
        try:
            import psutil
        except ImportError:
            logger.warning("[BG_WATCH] psutil not installed, falling back to immediate success")
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            get_skill_task_manager().mark_finished(task_id, success=True)
            return

        MAX_WAIT_SECS = 4 * 3600
        POLL_INTERVAL = 30
        elapsed = 0
        logger.info(f"[BG_WATCH] Watching task {task_id} pid={pid}")
        try:
            while elapsed < MAX_WAIT_SECS:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                if not psutil.pid_exists(pid):
                    from src.server_agent.service.SkillTaskManager import get_skill_task_manager
                    get_skill_task_manager().mark_finished(task_id, success=True)
                    logger.info(f"[BG_WATCH] task {task_id} pid={pid} exited after {elapsed}s, marked success")
                    return
            # 超时
            from src.server_agent.service.SkillTaskManager import get_skill_task_manager
            get_skill_task_manager().mark_finished(task_id, success=False, error="后台任务超时（4h）")
            logger.warning(f"[BG_WATCH] task {task_id} pid={pid} timed out after 4h")
        except asyncio.CancelledError:
            logger.info(f"[BG_WATCH] task {task_id} watcher cancelled")
            raise
        except Exception as e:
            logger.warning(f"[BG_WATCH] task {task_id} watcher error: {e}")
        finally:
            self._bg_watchers.pop(task_id, None)

    async def _can_use_tool_hook(self, tool_name: str, input_data: Any, context: Any):
        """
        权限确认 hook - 在工具调用前拦截，等待用户确认

        Args:
            tool_name: 工具名称
            input_data: 工具输入参数
            context: 上下文信息

        Returns:
            PermissionResultAllow 或 PermissionResultDeny
        """
        logger.info(f"[PERMISSION] ===== Hook called! Tool: {tool_name} =====")
        logger.info(f"[PERMISSION] Input data: {input_data}")
        logger.info(f"[PERMISSION] Context: {context}")

        # ===== Bash 工具调用 Skill 脚本：检测并创建后台任务 =====
        if tool_name == "Bash":
            command = input_data.get("command", "") if isinstance(input_data, dict) else ""
            run_in_background = input_data.get("run_in_background", False) if isinstance(input_data, dict) else False
            command = self._ensure_runner_run_id(command)
            if isinstance(input_data, dict):
                input_data["command"] = command

            detected_skill = self._detect_skill_from_bash_command(command)
            if detected_skill:
                logger.info(f"[PERMISSION] Skill detected: '{detected_skill}' (background={run_in_background})")

            if detected_skill:
                hook_session_id = getattr(context, "session_id", None) or (
                    context.get("session_id") if isinstance(context, dict) else None
                ) or self._last_session_id or ""
                hook_tool_use_id = (
                    getattr(context, "tool_use_id", None) or
                    (context.get("tool_use_id") if isinstance(context, dict) else None)
                )
                await self._submit_skill_task_from_bash(
                    command=command,
                    tool_use_id=hook_tool_use_id,
                    session_id=hook_session_id,
                    run_in_background=run_in_background,
                    source="permission_hook",
                )

                # 放行，让 CC 自己执行；updated_input 包含后端补齐的 --run-id。
                return PermissionResultAllow(updated_input=input_data)

        # ===== 低风险 Bash 命令自动放行（已注释：全部放行后此段冗余） =====
        # if tool_name == "Bash":
        #     command = input_data.get("command", "") if isinstance(input_data, dict) else ""
        #     import re as _re
        #     _LOW_RISK_PATTERNS = [
        #         r'^\s*ls\b', r'^\s*mkdir\b', r'^\s*cat\b', r'^\s*head\b',
        #         r'^\s*tail\b', r'^\s*find\b', r'^\s*pwd\b', r'^\s*echo\b',
        #         r'^\s*wc\b', r'^\s*du\b', r'^\s*tree\b', r'^\s*stat\b',
        #         r'^\s*file\b', r'^\s*which\b', r'^\s*env\b', r'^\s*printenv\b',
        #         r'^\s*grep\b', r'^\s*sort\b', r'^\s*uniq\b', r'^\s*cut\b',
        #         r'^\s*awk\b', r'^\s*sed\b', r'^\s*tr\b', r'^\s*xargs\b',
        #         r'^\s*diff\b', r'^\s*lsblk\b', r'^\s*df\b', r'^\s*free\b',
        #         r'^\s*nproc\b', r'^\s*uname\b', r'^\s*date\b', r'^\s*whoami\b',
        #     ]
        #     _DANGEROUS_WRITE = re.compile(r'>(?!>&|/dev/null)|>>')
        #     _PIPE_SPLIT = _re.compile(r'\|(?!\|)')
        #     def _is_low_risk_cmd(cmd: str) -> bool:
        #         cmd = cmd.strip()
        #         cmd_cleaned = _re.sub(r'\s*\d*>/?\S*\s*$', '', cmd).strip()
        #         for pat in _LOW_RISK_PATTERNS:
        #             if _re.match(pat, cmd_cleaned):
        #                 return True
        #         return False
        #     if not _DANGEROUS_WRITE.search(command):
        #         segments = _PIPE_SPLIT.split(command)
        #         if all(_is_low_risk_cmd(seg) for seg in segments):
        #             logger.info(f"[PERMISSION] Low-risk command auto-allowed: {command[:80]}")
        #             return PermissionResultAllow()

        # ===== MVP-2: 工具白名单 + 路径校验 =====
        if self._tool_policy:
            allowed, deny_reason = self._tool_policy.validate_tool_call(
                tool_name, input_data
            )
            if not allowed:
                logger.warning(f"[PERMISSION] ToolPolicy denied: {deny_reason}")
                return PermissionResultDeny(message=deny_reason or "工具调用被拒绝")

        # ===== 全部放行（跳过用户确认） =====
        logger.info(f"[PERMISSION] Auto-allowed tool: {tool_name}")
        return PermissionResultAllow(updated_input=input_data)

        # logger.info(f"[PERMISSION] Tool: {tool_name}, Session: {session_id}, Input: {input_data}")

        # # 创建权限请求数据
        # request_id = str(uuid.uuid4())
        # permission_data = {
        #     "session_id": session_id,
        #     "tool_name": tool_name,
        #     "tool_input": input_data if isinstance(input_data, dict) else {},
        #     "request_id": request_id,
        # }

        # # 将权限请求放入队列（非阻塞）
        # await self._permission_queue.put(permission_data)
        # logger.info(f"[PERMISSION] Request queued: {session_id}, tool: {tool_name}, request_id: {request_id}")

        # # 创建等待事件，用 request_id 做 key 避免同 session 并发工具调用互相覆盖
        # event = asyncio.Event()
        # self._permission_events[request_id] = event

        # # 等待用户确认（阻塞），设置超时
        # logger.info(f"[PERMISSION] Waiting for user confirmation, request_id={request_id}")
        # try:
        #     await asyncio.wait_for(event.wait(), timeout=300.0)  # 5分钟超时
        # except asyncio.TimeoutError:
        #     logger.warning(f"[PERMISSION] Timeout for request_id: {request_id}")
        #     self._permission_events.pop(request_id, None)
        #     self._permission_results.pop(request_id, None)
        #     return PermissionResultDeny(message="权限请求超时")

        # # 获取确认结果
        # allowed = self._permission_results.get(request_id, False)

        # # 清理
        # self._permission_events.pop(request_id, None)
        # self._permission_results.pop(request_id, None)

        # if allowed:
        #     logger.info(f"[PERMISSION] User allowed tool: {tool_name}")
        #     return PermissionResultAllow(updated_input=input_data)
        # else:
        #     logger.info(f"[PERMISSION] User denied tool: {tool_name}")
        #     return PermissionResultDeny(message="用户拒绝了此操作")

    async def confirm_permission(self, session_id: str, request_id: Optional[str] = None):
        """确认权限请求，优先用 request_id 定位，兜底用 session_id 匹配第一个等待中的请求"""
        key = request_id or session_id
        logger.info(f"[PERMISSION] Confirming permission, key={key}")
        self._permission_results[key] = True
        if key in self._permission_events:
            self._permission_events[key].set()
        else:
            logger.warning(f"[PERMISSION] No pending event for key={key}")

    async def cancel_permission(self, session_id: str, request_id: Optional[str] = None):
        """取消权限请求，优先用 request_id 定位，兜底用 session_id 匹配第一个等待中的请求"""
        key = request_id or session_id
        logger.info(f"[PERMISSION] Canceling permission, key={key}")
        self._permission_results[key] = False
        if key in self._permission_events:
            self._permission_events[key].set()
        else:
            logger.warning(f"[PERMISSION] No pending event for key={key}")

    async def _get_or_create_client(self, session_id: Optional[str] = None, is_resume: bool = False, user_id: Optional[int] = None) -> tuple[ClaudeSDKClient, str]:
        """
        获取或创建 ClaudeSDKClient 实例

        Args:
            session_id: 会话ID
            is_resume: 是否为恢复已有会话（True 时使用 resume 参数）
            user_id: 用户ID，注入到 system_prompt 中

        Returns:
            (client, session_id) 元组
        """
        # 如果没有 session_id，创建新的
        if not session_id:
            session_id = str(uuid.uuid4())

        # 如果已有 client，返回
        if session_id in self._clients:
            self._touch_session(session_id)
            return self._clients[session_id], session_id

        # 创建新的 client
        logger.info(f"[CLIENT] Creating new client with permission_mode={self._permission_mode}, is_resume={is_resume}")

        # 基础 system_prompt（含 user_id 注入），项目专属内容追加在后
        system_prompt = get_system_prompt(user_id)
        if self._project_config and self._project_config.system_prompt:
            uid = str(user_id) if user_id is not None else "unknown"
            project_prompt = self._project_config.system_prompt.replace("{user_id}", uid)
            system_prompt = system_prompt + "\n\n" + project_prompt

        # 使用项目 base_dir 作为 cwd（如果有），否则使用当前目录
        cwd = str(Path.cwd())
        if self._project_config:
            cwd = str(self._project_config.base_dir)

        options = ClaudeAgentOptions(
            cwd=cwd,
            resume=session_id if is_resume else None,  # 仅恢复已有会话时才传 resume
            permission_mode=self._permission_mode,  # type: ignore
            system_prompt=system_prompt,
            can_use_tool=self._can_use_tool_hook,  # type: ignore
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher=None, hooks=[self._dummy_hook])  # type: ignore
                ],
                "PostToolUse": [
                    HookMatcher(matcher=None, hooks=[self._post_tool_use_hook])  # type: ignore
                ],
            },
        )

        logger.info(f"[CLIENT] Options configured: permission_mode={self._permission_mode}, can_use_tool=True, resume={session_id if is_resume else None}")

        # 使用 async with 打开 client
        client = ClaudeSDKClient(options=options)
        await client.__aenter__()
        self._clients[session_id] = client
        self._touch_session(session_id)
        self._start_cleanup_task_if_needed()

        logger.info(f"[CLIENT] Created new client for session: {session_id}")
        return client, session_id

    async def close_client(self, session_id: str):
        """关闭指定会话的 client"""
        if session_id in self._clients:
            client = self._clients.pop(session_id)
            try:
                await client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"[CLIENT] Error closing client for session {session_id}: {e}")
        self._session_last_active.pop(session_id, None)
        self._active_sessions.pop(session_id, None)
        self._session_conversation_map.pop(session_id, None)

    async def aclose(self):
        """关闭当前 Agent 的全部资源。"""
        self._is_closing = True
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._cleanup_task = None

        for task_id, watcher in list(self._bg_watchers.items()):
            if watcher and not watcher.done():
                watcher.cancel()
            self._bg_watchers.pop(task_id, None)

        for session_id in list(self._clients.keys()):
            await self.close_client(session_id)

        self._tool_task_map.clear()
        self._permission_events.clear()
        self._permission_results.clear()
        self._session_last_active.clear()

    async def query(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        ws_callback: Optional[callable] = None,
        user_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[NormalizedMessage, None]:
        """
        执行查询并流式输出结果（使用 ClaudeSDKClient）

        Args:
            prompt: 用户提示词
            session_id: 会话ID（用于恢复会话）
            ws_callback: 回调函数
            user_id: 用户ID

        Yields:
            标准化消息
        """
        captured_session_id = session_id

        # SDK client 启动前需要一个内部句柄。该 UUID 不是 Claude CLI 最终写入
        # JSONL 的 session_id，因此不能发送给前端或持久化到数据库。
        if not captured_session_id:
            captured_session_id = str(uuid.uuid4())
        if conversation_id:
            self._session_conversation_map[captured_session_id] = conversation_id

        # 创建中断事件
        interrupt_event = asyncio.Event()
        self._active_sessions[captured_session_id] = interrupt_event

        # 判断是否为恢复会话：传入了 session_id 说明是恢复已有会话
        is_resume = session_id is not None

        try:
            # 获取或创建 client
            client, _ = await self._get_or_create_client(captured_session_id, is_resume=is_resume, user_id=user_id)
            self._last_session_id = captured_session_id
            self._touch_session(captured_session_id)

            logger.info(f"[QUERY] Starting query with {self._permission_mode} mode, session={captured_session_id}")

            # 发送查询
            await client.query(prompt)

            # 接收响应
            stream_gen = client.receive_response()

            # 创建中断监听任务
            async def _get_next_item():
                return await stream_gen.__anext__()

            interrupt_task = asyncio.create_task(interrupt_event.wait())

            next_item_task = None
            try:
                while True:
                    next_item_task = asyncio.create_task(_get_next_item())

                    done, _ = await asyncio.wait(
                        [next_item_task, interrupt_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    if interrupt_task in done:
                        # 触发了中断
                        next_item_task.cancel()
                        try:
                            await next_item_task
                        except (asyncio.CancelledError, Exception):
                            pass
                        try:
                            await stream_gen.aclose()
                        except:
                            pass
                        yield NormalizedMessage(
                            kind=MessageKind.ERROR,
                            session_id=captured_session_id,
                            content="Session interrupted by user",
                            is_error=True,
                            aborted=True,
                        )
                        return
                    else:
                        # 成功获取数据
                        try:
                            message = next_item_task.result()
                        except StopAsyncIteration:
                            next_item_task = None  # 已自然结束，无需 cancel
                            break
                        except Exception:
                            break

                        # 标准化消息（一条 SDK 消息可能对应多个 block）
                        for normalized in self._normalize_message(message, captured_session_id):
                            if (
                                normalized.kind == MessageKind.SESSION_CREATED
                                and normalized.session_id
                                and normalized.session_id != captured_session_id
                            ):
                                self._rekey_session(captured_session_id, normalized.session_id)
                                captured_session_id = normalized.session_id
                            if (
                                normalized.kind == MessageKind.TOOL_USE
                                and normalized.tool_name == "Bash"
                            ):
                                tool_input = normalized.tool_input if isinstance(normalized.tool_input, dict) else {}
                                command = tool_input.get("command", "")
                                if command:
                                    import shlex as _shlex
                                    try:
                                        _parts = _shlex.split(command)
                                    except ValueError:
                                        _parts = command.split()
                                    _is_standard_runner = any(Path(part).name == "run_skill_task.py" for part in _parts)
                                    _has_run_id = any(part == "--run-id" or part.startswith("--run-id=") for part in _parts)
                                    if _is_standard_runner and not _has_run_id:
                                        if ws_callback:
                                            ws_callback(normalized)
                                        yield normalized
                                        continue
                                    command = self._ensure_runner_run_id(command)
                                    await self._submit_skill_task_from_bash(
                                        command=command,
                                        tool_use_id=normalized.tool_id,
                                        session_id=normalized.session_id or captured_session_id,
                                        run_in_background=bool(tool_input.get("run_in_background", False)),
                                        source="tool_use_message",
                                    )
                            if ws_callback:
                                ws_callback(normalized)
                            yield normalized

            finally:
                # 确保 next_item_task 被清理
                if next_item_task and not next_item_task.done():
                    next_item_task.cancel()
                    try:
                        await next_item_task
                    except (asyncio.CancelledError, Exception):
                        pass
                if not interrupt_task.done():
                    interrupt_task.cancel()

        except asyncio.CancelledError:
            # 区分两种取消原因：
            #   1) 用户主动中断（interrupt_event.is_set()）→ 清理 running 任务，不关 client
            #   2) SSE 断开（刷新页面/网络抖动）→ 保留后台任务和 PID 监控
            is_user_interrupt = interrupt_event.is_set()
            logger.warning(
                f"Session {captured_session_id} task was cancelled "
                f"({'user interrupt' if is_user_interrupt else 'SSE disconnect'})"
            )

            # 用户中断时不关闭 client，保留 resume 能力继续对话
            # client 只在进程真正死亡（Exception）时才关闭

            conversation_id = self._session_conversation_map.get(captured_session_id, "")
            if conversation_id:
                try:
                    from src.server_agent.service.SkillTaskManager import get_skill_task_manager
                    task_manager = get_skill_task_manager()
                    cancelled_ids: set[str] = set()
                    for task in task_manager.list_tasks(conversation_id=conversation_id):
                        if task.status != "running":
                            continue
                        if is_user_interrupt:
                            # 用户主动中断：所有 running 任务标 failed
                            task_manager.mark_finished(
                                task.task_id,
                                success=False,
                                error="会话被取消",
                            )
                            cancelled_ids.add(task.task_id)
                            logger.info(f"[CLEANUP] Skill task {task.task_id} marked failed on user interrupt")
                        else:
                            # SSE 断开：保留后台任务，PID 监控继续运行
                            # 只清理前台任务的 _tool_task_map 映射
                            logger.info(f"[CLEANUP] SSE disconnect: keeping background task {task.task_id} alive")
                    # 清理 _tool_task_map 中属于已取消任务的条目
                    self._tool_task_map = {
                        k: v for k, v in self._tool_task_map.items()
                        if v not in cancelled_ids
                    }
                    if is_user_interrupt:
                        # 仅用户主动中断时才撤销后台 PID 监控协程
                        for tid in cancelled_ids:
                            watcher = self._bg_watchers.pop(tid, None)
                            if watcher and not watcher.done():
                                watcher.cancel()
                except Exception as e:
                    logger.warning(f"[CLEANUP] Failed to update skill tasks on cancel: {e}")
            raise
        except Exception as e:
            logger.error(f"Claude SDK query error: {e}")

            # 先取 conversation_id（pop 之后就取不到了）
            conversation_id = self._session_conversation_map.get(captured_session_id, "")

            # 关闭死掉的 client，防止进程/线程泄露
            await self.close_client(captured_session_id)
            logger.info(f"[CLEANUP] Closed dead client for session {captured_session_id}")

            # 清除映射，避免下次 resume 死进程
            self._session_conversation_map.pop(captured_session_id, None)

            # 通知 Service 层清空 DB 中的 session_id（通过 _dead_sessions 集合标记）
            self._dead_sessions.add(captured_session_id)

            # 异常时：前台任务标 failed，后台任务保留 PID 监控继续运行
            if conversation_id:
                try:
                    from src.server_agent.service.SkillTaskManager import get_skill_task_manager
                    task_manager = get_skill_task_manager()
                    cancelled_ids: set[str] = set()
                    for task in task_manager.list_tasks(conversation_id=conversation_id):
                        if task.status != "running":
                            continue
                        # 检查是否有后台 PID 监控协程在追踪此任务
                        has_bg_watcher = task.task_id in self._bg_watchers
                        if has_bg_watcher:
                            # 后台任务：PID 监控仍在运行，不标记终态
                            logger.info(f"[CLEANUP] Exception: keeping background task {task.task_id} alive (watcher running)")
                        else:
                            # 前台任务：无 PID 监控，标记 failed
                            task_manager.mark_finished(
                                task.task_id,
                                success=False,
                                error=f"会话异常: {str(e)[:200]}",
                            )
                            cancelled_ids.add(task.task_id)
                            logger.info(f"[CLEANUP] Skill task {task.task_id} marked failed on exception")
                    self._tool_task_map = {
                        k: v for k, v in self._tool_task_map.items()
                        if v not in cancelled_ids
                    }
                    # 仅取消已标记 failed 的前台任务的 watcher（实际前台任务不会有 watcher）
                    for tid in cancelled_ids:
                        watcher = self._bg_watchers.pop(tid, None)
                        if watcher and not watcher.done():
                            watcher.cancel()
                except Exception as cleanup_error:
                    logger.warning(f"[CLEANUP] Failed to update skill tasks on exception: {cleanup_error}")
            yield NormalizedMessage(
                kind=MessageKind.ERROR,
                session_id=captured_session_id,
                content=str(e),
                is_error=True,
            )
        finally:
            self._active_sessions.pop(captured_session_id, None)

    def _normalize_message(self, message, session_id: Optional[str]) -> list[NormalizedMessage]:
        """标准化 SDK 消息，返回列表（一条 SDK 消息可能对应多个 block）"""
        msg_type_name = type(message).__name__

        # StreamEvent
        if msg_type_name == "StreamEvent":
            event = message.event
            event_type = event.get("type", "")

            if event_type == "content_block_delta":
                delta = event.get("delta", {})
                delta_type = delta.get("type", "")

                if delta_type == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        return [NormalizedMessage(
                            kind=MessageKind.STREAM_DELTA,
                            content=text,
                            session_id=session_id,
                        )]
                elif delta_type == "thinking_delta":
                    thinking = delta.get("thinking", "")
                    if thinking:
                        return [NormalizedMessage(
                            kind=MessageKind.THINKING,
                            content=thinking,
                            session_id=session_id,
                        )]

            elif event_type == "content_block_stop":
                return [NormalizedMessage(
                    kind=MessageKind.STREAM_END,
                    session_id=session_id,
                )]

        # AssistantMessage：一条消息可能包含多个 block，全部收集后返回
        elif msg_type_name == "AssistantMessage":
            results = []
            for block in message.content:
                block_type_name = type(block).__name__

                if block_type_name == "TextBlock":
                    if block.text:
                        results.append(NormalizedMessage(
                            kind=MessageKind.TEXT,
                            content=block.text,
                            session_id=session_id,
                            role="assistant",
                        ))
                elif block_type_name == "ThinkingBlock":
                    if block.thinking:
                        results.append(NormalizedMessage(
                            kind=MessageKind.THINKING,
                            content=block.thinking,
                            session_id=session_id,
                        ))
                elif block_type_name == "ToolUseBlock":
                    results.append(NormalizedMessage(
                        kind=MessageKind.TOOL_USE,
                        session_id=session_id,
                        tool_name=block.name,
                        tool_input=block.input,
                        tool_id=block.id,
                    ))
            return results

        # ResultMessage
        elif msg_type_name == "ResultMessage":
            # 注意：不在此处更新 Skill 任务状态。
            # ResultMessage 在每轮对话结束时都会触发（包括 Monitor 进度通知轮次），
            # 若在此处 mark_finished 会导致长时间运行的任务被误判为完成。
            # 任务终态由前端轮询 SkillTaskManager 驱动，或由 skill 脚本执行完成后显式标记。
            if message.result:
                return [NormalizedMessage(
                    kind=MessageKind.TEXT,
                    content=message.result,
                    session_id=session_id,
                    role="assistant",
                )]
            return [NormalizedMessage(
                kind=MessageKind.COMPLETE,
                session_id=session_id,
                exit_code=0 if not message.is_error else 1,
            )]

        # SystemMessage
        elif msg_type_name == "SystemMessage":
            subtype = message.subtype
            data = message.data

            if subtype == "init":
                # ✅ 从 init 消息获取 SDK 真实的 session_id
                real_session_id = data.get("session_id", session_id)
                return [NormalizedMessage(
                    kind=MessageKind.SESSION_CREATED,
                    session_id=real_session_id,
                    new_session_id=real_session_id,
                    is_new_session=True,
                )]

            elif subtype == "session_created":
                new_session_id = data.get("session_id", session_id)
                return [NormalizedMessage(
                    kind=MessageKind.SESSION_CREATED,
                    session_id=new_session_id,
                    new_session_id=new_session_id,
                    is_new_session=data.get("is_new_session", False),
                )]

        return []

    async def stream_chat(
        self,
        current_message: str,
        session_id: Optional[str] = None,
        is_file: bool = False,
        use_stream_json: bool = True,
        user_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话 - 输出与参考项目一致的格式
        使用队列机制同时监听消息流和权限请求

        Args:
            current_message: 当前用户消息
            session_id: 会话ID
            is_file: 是否为文件路径（SDK模式不支持）
            use_stream_json: 是否使用流式 JSON 输出格式
            user_id: 用户ID

        Yields:
            JSON 字符串
        """
        full_content = ""

        # 创建一个内部队列来合并消息流和权限请求
        output_queue: asyncio.Queue = asyncio.Queue()
        skill_event_queue: asyncio.Queue = asyncio.Queue()
        stream_done = asyncio.Event()
        self._register_skill_event_queue(conversation_id, skill_event_queue)

        # 后台任务：监听权限队列并转发到输出队列
        async def permission_listener():
            try:
                while not stream_done.is_set():
                    try:
                        permission_data = await asyncio.wait_for(
                            self._permission_queue.get(),
                            timeout=0.1
                        )
                        permission_msg = {
                            "kind": MessageKind.PERMISSION_REQUEST,
                            "sessionId": permission_data["session_id"],
                            "toolName": permission_data["tool_name"],
                            "input": permission_data["tool_input"],
                            "requestId": permission_data["request_id"],
                            "provider": "claude",
                            "done": False,
                        }
                        logger.info(f"[PERMISSION_LISTENER] Forwarding permission request: {permission_data['tool_name']}")
                        await output_queue.put(("permission", permission_msg))
                    except asyncio.TimeoutError:
                        continue
            except Exception as e:
                logger.error(f"[PERMISSION_LISTENER] Error: {e}")

        async def skill_event_listener():
            try:
                while not stream_done.is_set():
                    try:
                        event = await asyncio.wait_for(skill_event_queue.get(), timeout=0.1)
                        logger.info(f"[SKILL_EVENT_LISTENER] Forwarding skill_submitted: {event.get('skillName')}")
                        await output_queue.put(("skill_submitted", event))
                    except asyncio.TimeoutError:
                        continue
            except Exception as e:
                logger.error(f"[SKILL_EVENT_LISTENER] Error: {e}")

        # 后台任务：处理消息流
        async def message_stream_handler():
            try:
                async for msg in self.query(
                    current_message,
                    session_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                ):
                    await output_queue.put(("message", msg))
            except Exception as e:
                logger.error(f"[MESSAGE_STREAM] Error: {e}")
                await output_queue.put(("error", str(e)))
            finally:
                stream_done.set()
                await output_queue.put(("done", None))

        # 启动后台任务
        permission_task = asyncio.create_task(permission_listener())
        skill_event_task = asyncio.create_task(skill_event_listener())
        stream_task = asyncio.create_task(message_stream_handler())

        try:
            # 从输出队列读取并处理
            while True:
                item_type, item_data = await output_queue.get()

                if item_type == "done":
                    break

                elif item_type == "permission":
                    # 发送权限请求
                    logger.info(f"[PERMISSION_REQUEST] Sending to frontend: {item_data['toolName']}")
                    yield json.dumps(item_data, ensure_ascii=False)

                elif item_type == "skill_submitted":
                    # 发送 skill 后台任务提交事件
                    logger.info(f"[SKILL_SUBMITTED] Sending to frontend: {item_data.get('skillName')}, task={item_data.get('taskId')}")
                    # 去掉内部标记字段再推给前端
                    event = {k: v for k, v in item_data.items() if k != "_is_skill_submitted"}
                    yield json.dumps(event, ensure_ascii=False)

                elif item_type == "message":
                    msg = item_data

                    if msg.kind == MessageKind.STREAM_DELTA:
                        if msg.content:
                            full_content += msg.content
                            data = msg.to_dict()
                            data["done"] = False
                            yield json.dumps(data, ensure_ascii=False)

                    elif msg.kind == MessageKind.TEXT:
                        if msg.content:
                            full_content += msg.content
                            data = msg.to_dict()
                            data["done"] = False
                            yield json.dumps(data, ensure_ascii=False)

                    elif msg.kind == MessageKind.THINKING:
                        if msg.content:
                            data = {
                                "kind": MessageKind.THINKING,
                                "content": msg.content,
                                "sessionId": msg.session_id,
                                "provider": "claude",
                                "done": False
                            }
                            yield json.dumps(data, ensure_ascii=False)

                    elif msg.kind == MessageKind.TOOL_USE:
                        session_for_tool = msg.session_id or session_id
                        logger.info(f"[TOOL_USE] {msg.tool_name}, session={session_for_tool}")
                        data = msg.to_dict()
                        data["done"] = False
                        yield json.dumps(data, ensure_ascii=False)

                    elif msg.kind == MessageKind.PERMISSION_REQUEST:
                        # SDK 直接发送的权限请求
                        logger.info(f"[PERMISSION_REQUEST] {msg.tool_name}, session={msg.session_id}")
                        data = msg.to_dict()
                        data["done"] = False
                        yield json.dumps(data, ensure_ascii=False)

                    elif msg.kind == MessageKind.STREAM_END:
                        pass

                    elif msg.kind == MessageKind.SESSION_CREATED:
                        real_sid = msg.session_id or msg.new_session_id
                        self._last_session_id = real_sid
                        # 建立 sdk_session_id -> conversation_id 映射，供 hook 使用
                        if real_sid and conversation_id:
                            self._session_conversation_map[real_sid] = conversation_id
                        data = msg.to_dict()
                        data["done"] = False
                        yield json.dumps(data, ensure_ascii=False)

                    elif msg.kind == MessageKind.COMPLETE:
                        session_for_complete = msg.session_id or session_id
                        data = {
                            "kind": MessageKind.COMPLETE,
                            "sessionId": session_for_complete,
                            "provider": "claude",
                            "exitCode": msg.exit_code,
                            "done": True,
                            "content": full_content,
                            "aborted": msg.aborted or False,
                        }
                        yield json.dumps(data, ensure_ascii=False)

                    elif msg.kind == MessageKind.ERROR:
                        data = {
                            "kind": MessageKind.ERROR,
                            "sessionId": msg.session_id,
                            "provider": "claude",
                            "content": msg.content,
                            "isError": True,
                            "done": True,
                            "aborted": msg.aborted or False,
                        }
                        yield json.dumps(data, ensure_ascii=False)

        finally:
            # 清理任务
            stream_done.set()
            self._unregister_skill_event_queue(conversation_id, skill_event_queue)
            permission_task.cancel()
            skill_event_task.cancel()
            stream_task.cancel()
            try:
                await permission_task
            except asyncio.CancelledError:
                pass
            try:
                await skill_event_task
            except asyncio.CancelledError:
                pass
            try:
                await stream_task
            except asyncio.CancelledError:
                pass

            # 注意：正常完成后不关闭 client，保留 resume 能力
            # client 只在异常/中断路径中关闭（见 query() 的 except 块）

    async def chat(
        self,
        current_message: str,
        session_id: Optional[str] = None,
        is_file: bool = False,
        use_stream_json: bool = True,
        user_id: Optional[int] = None,
    ) -> str:
        """
        同步对话（非流式）

        Args:
            current_message: 当前用户消息
            session_id: 会话ID
            is_file: 是否为文件路径
            use_stream_json: 是否使用流式 JSON 输出格式
            user_id: 用户ID

        Returns:
            AI的完整回复
        """
        full_content = ""
        async for chunk in self.stream_chat(current_message, session_id, is_file, use_stream_json, user_id=user_id):
            try:
                event_data = json.loads(chunk.strip())
                if event_data.get("content"):
                    full_content = event_data["content"]
                elif event_data.get("kind") == MessageKind.COMPLETE:
                    full_content = event_data.get("content", "")
            except json.JSONDecodeError:
                pass
        return full_content

    async def interrupt(self, session_id: str) -> bool:
        """中断指定会话（不关闭 client，保留 resume 能力）"""
        if session_id in self._active_sessions:
            self._active_sessions[session_id].set()
            self._touch_session(session_id)
            logger.info(f"Session {session_id} interrupted")
            return True
        return False


# 全局 Agent 实例（按项目隔离）
_agent_instances: dict[str, ClaudeAgent] = {}
_default_agent: Optional[ClaudeAgent] = None


def find_agent_by_session(session_id: str) -> Optional[ClaudeAgent]:
    """通过 sdk_session_id 找到持有该 session 的 Agent 实例。
    用于权限确认路由：前端只知道 session_id，需要找到正确的 agent 实例。
    """
    # 先查项目隔离实例
    for agent in _agent_instances.values():
        if session_id in agent._session_conversation_map:
            return agent
    # 再查默认实例
    if _default_agent and session_id in _default_agent._session_conversation_map:
        return _default_agent
    # 兜底：返回默认实例（向后兼容）
    return _default_agent


def get_code_agent(project_config: Optional[ProjectConfig] = None) -> ClaudeAgent:
    """获取 Agent 实例

    Args:
        project_config: 项目配置。传入后返回该项目的隔离 Agent；
                        不传则返回默认全局 Agent（向后兼容）。
    """
    global _default_agent

    if project_config:
        pid = project_config.project_id
        if pid not in _agent_instances:
            _agent_instances[pid] = ClaudeAgent(
                permission_mode="default",
                project_config=project_config,
            )
        return _agent_instances[pid]

    # 向后兼容：无 project_config 时返回默认实例
    if _default_agent is None:
        _default_agent = ClaudeAgent(permission_mode="default")
    return _default_agent


def get_agent_type() -> str:
    """获取当前 Agent 类型"""
    return "claude"


async def shutdown_all_agents():
    """关闭默认 agent 和所有项目隔离 agent 的资源。"""
    global _default_agent

    for project_id, agent in list(_agent_instances.items()):
        try:
            await agent.aclose()
        except Exception as e:
            logger.error(f"[ClaudeAgent] Failed to close project agent {project_id}: {e}")
    _agent_instances.clear()

    if _default_agent is not None:
        try:
            await _default_agent.aclose()
        except Exception as e:
            logger.error(f"[ClaudeAgent] Failed to close default agent: {e}")
        _default_agent = None
