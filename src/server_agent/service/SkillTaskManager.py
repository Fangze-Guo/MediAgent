"""
Skill 后台任务管理器

负责将 Skill 工具调用从 SSE 流中解耦，挂入后台异步执行。
任务状态保存在内存中，服务重启后丢失（可接受）。
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

SkillStatus = Literal["pending", "running", "success", "failed"]

# 日志环形缓冲大小
MAX_LOG_LINES = 200


@dataclass
class SkillTask:
    task_id: str
    skill_name: str
    params: dict
    conversation_id: str
    status: SkillStatus = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    logs: List[str] = field(default_factory=list)
    progress: int = 0          # 0~100，从日志中解析（可选）
    output: Optional[dict] = None   # 成功后的输出信息
    error: Optional[str] = None     # 失败原因

    def elapsed_seconds(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "skill_name": self.skill_name,
            "conversation_id": self.conversation_id,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "elapsed_seconds": self.elapsed_seconds(),
            "logs": self.logs[-50:],   # 只返回最后 50 行给前端
            "output": self.output,
            "error": self.error,
        }


class SkillTaskManager:
    """Skill 后台任务管理器（进程级单例）"""

    def __init__(self):
        self._tasks: Dict[str, SkillTask] = {}

    def submit(self, skill_name: str, params: dict, conversation_id: str) -> str:
        """
        提交 Skill 任务，立即返回 task_id，后台异步执行。

        Args:
            skill_name: Skill 名称，如 "bodycomp-seg-nnunet"
            params:     Skill 的原始 tool_input 参数
            conversation_id: 归属会话 ID

        Returns:
            task_id (UUID 字符串)
        """
        task_id = str(uuid.uuid4())
        task = SkillTask(
            task_id=task_id,
            skill_name=skill_name,
            params=params,
            conversation_id=conversation_id,
        )
        self._tasks[task_id] = task

        # 在事件循环中创建后台任务
        asyncio.create_task(self._run_skill(task_id))
        logger.info(f"[SkillTaskManager] Submitted task {task_id} for skill '{skill_name}'")
        return task_id

    def get_task(self, task_id: str) -> Optional[SkillTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, conversation_id: Optional[str] = None) -> List[SkillTask]:
        tasks = list(self._tasks.values())
        if conversation_id:
            tasks = [t for t in tasks if t.conversation_id == conversation_id]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def _append_log(self, task: SkillTask, line: str):
        task.logs.append(line)
        if len(task.logs) > MAX_LOG_LINES:
            task.logs = task.logs[-MAX_LOG_LINES:]

    async def _run_skill(self, task_id: str):
        """后台执行 Skill 脚本"""
        task = self._tasks.get(task_id)
        if not task:
            return

        task.status = "running"
        task.started_at = datetime.now()
        logger.info(f"[SkillTaskManager] Starting skill '{task.skill_name}', task={task_id}")

        try:
            # 检查是否是 Bash 命令格式（从 Bash tool 拦截来的）
            if "command" in task.params and isinstance(task.params["command"], str):
                # 直接执行 Bash 命令
                command = task.params["command"]
                logger.info(f"[SkillTaskManager] Executing bash command: {command}")

                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            else:
                # 标准 Skill 格式：执行 run.sh
                skill_dir = Path.home() / ".claude" / "skills" / task.skill_name
                run_script = skill_dir / "run.sh"
                if not run_script.exists():
                    raise FileNotFoundError(f"Skill run.sh 不存在: {run_script}")

                # 构建命令：bash run.sh，并将 params 作为环境变量传入
                import os
                env = os.environ.copy()
                for k, v in task.params.items():
                    if k != "skill":
                        env[f"SKILL_PARAM_{k.upper()}"] = str(v)
                env["SKILL_TASK_ID"] = task_id
                env["SKILL_NAME"] = task.skill_name

                proc = await asyncio.create_subprocess_exec(
                    "bash", str(run_script),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(skill_dir),
                    env=env,
                )

            # 实时读取输出
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                self._append_log(task, line)
                logger.debug(f"[skill:{task.skill_name}] {line}")

            await proc.wait()

            if proc.returncode == 0:
                task.status = "success"
                task.progress = 100
                task.output = {"return_code": 0}
                logger.info(f"[SkillTaskManager] Task {task_id} succeeded")
            else:
                task.status = "failed"
                task.error = f"脚本退出码: {proc.returncode}"
                logger.warning(f"[SkillTaskManager] Task {task_id} failed (rc={proc.returncode})")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self._append_log(task, f"[ERROR] {e}")
            logger.error(f"[SkillTaskManager] Task {task_id} exception: {e}")
        finally:
            task.finished_at = datetime.now()


# 进程级单例
_skill_task_manager: Optional[SkillTaskManager] = None


def get_skill_task_manager() -> SkillTaskManager:
    global _skill_task_manager
    if _skill_task_manager is None:
        _skill_task_manager = SkillTaskManager()
    return _skill_task_manager
