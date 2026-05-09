"""
Skill 后台任务管理器

负责将 Skill 工具调用从 SSE 流中解耦，挂入后台异步执行。
任务状态同时写入内存和 PostgreSQL，服务重启后自动恢复。
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
    proc: Optional[asyncio.subprocess.Process] = None  # 运行中子进程句柄（不参与序列化）
    cancelled: bool = False         # 是否被用户主动取消

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
        self._mapper = None  # 延迟初始化，避免循环导入

    def _get_mapper(self):
        """延迟获取 mapper，避免模块循环导入"""
        if self._mapper is None:
            from src.server_agent.mapper.CodeAgentMapper import CodeAgentMapper
            self._mapper = CodeAgentMapper()
        return self._mapper

    def _persist(self, task: SkillTask):
        """异步写 DB，不阻塞调用方"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._persist_async(task))
        except Exception as e:
            logger.warning(f"[SkillTaskManager] persist schedule failed: {e}")

    async def _persist_async(self, task: SkillTask):
        """将任务状态写入 DB"""
        try:
            mapper = self._get_mapper()
            await mapper.upsert_skill_task({
                "task_id": task.task_id,
                "skill_name": task.skill_name,
                "params": task.params,
                "conversation_id": task.conversation_id,
                "status": task.status,
                "progress": task.progress,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "error": task.error,
                "output": task.output,
                "cancelled": task.cancelled,
            })
        except Exception as e:
            logger.warning(f"[SkillTaskManager] DB persist failed for {task.task_id}: {e}")

    async def restore_from_db(self):
        """服务启动时从 DB 恢复任务列表（跳过已在内存中的任务）"""
        try:
            mapper = self._get_mapper()
            rows = await mapper.list_skill_tasks()
            restored = 0
            for row in rows:
                task_id = row["task_id"]
                if task_id in self._tasks:
                    continue
                status = row["status"]
                # 服务重启后，上次未完成的任务进程已死，标记为 failed
                if status in ("pending", "running"):
                    status = "failed"
                    row["error"] = (row.get("error") or "") + " [服务重启，任务中断]"
                    row["finished_at"] = row["finished_at"] or datetime.now()
                task = SkillTask(
                    task_id=task_id,
                    skill_name=row["skill_name"],
                    params=row["params"],
                    conversation_id=row["conversation_id"],
                    status=status,
                    progress=row["progress"],
                    created_at=row["created_at"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    error=row["error"],
                    output=row["output"],
                    cancelled=row["cancelled"],
                )
                self._tasks[task_id] = task
                # 如果状态被修正，同步写回 DB
                if status != row.get("status"):
                    self._persist(task)
                restored += 1
            logger.info(f"[SkillTaskManager] Restored {restored} tasks from DB")
        except Exception as e:
            logger.warning(f"[SkillTaskManager] restore_from_db failed: {e}")

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
        self._persist(task)  # 写 DB

        # 在事件循环中创建后台任务
        asyncio.create_task(self._run_skill(task_id))
        logger.info(f"[SkillTaskManager] Submitted task {task_id} for skill '{skill_name}'")
        return task_id

    def get_task(self, task_id: str) -> Optional[SkillTask]:
        return self._tasks.get(task_id)

    async def wait_for_task(self, task_id: str, poll_interval: float = 2.0) -> Optional[SkillTask]:
        """等待任务进入终态（success/failed），期间每隔 poll_interval 秒检查一次"""
        while True:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if task.status in ("success", "failed"):
                return task
            await asyncio.sleep(poll_interval)

    def list_tasks(self, conversation_id: Optional[str] = None) -> List[SkillTask]:
        tasks = list(self._tasks.values())
        if conversation_id:
            tasks = [t for t in tasks if t.conversation_id == conversation_id]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def cancel(self, task_id: str) -> bool:
        """中断正在运行 / 等待中的任务。已完成或失败的任务不做处理。"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status not in ("pending", "running"):
            return False
        task.cancelled = True
        self._persist(task)  # 持久化 cancelled 标记
        if task.proc is not None and task.proc.returncode is None:
            try:
                task.proc.terminate()
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.warning(f"[SkillTaskManager] terminate proc failed: {e}")
        else:
            # 还没起子进程（pending），直接置为失败
            task.status = "failed"
            task.error = "已取消"
            task.finished_at = datetime.now()
            self._persist(task)  # 写 DB
        logger.info(f"[SkillTaskManager] Cancel requested for task {task_id}")
        return True

    def delete(self, task_id: str) -> bool:
        """从任务表中移除单个任务（运行中的会先取消）。"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status in ("pending", "running"):
            self.cancel(task_id)
        self._tasks.pop(task_id, None)
        # 从 DB 删除
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._get_mapper().delete_skill_task(task_id))
        except Exception as e:
            logger.warning(f"[SkillTaskManager] DB delete failed for {task_id}: {e}")
        return True

    def clear(self, conversation_id: Optional[str] = None, only_finished: bool = True) -> int:
        """批量清理任务。

        Args:
            conversation_id: 仅清理指定会话的任务；None 表示全部会话。
            only_finished: True 仅清理已完成 / 失败任务（保留运行中）；
                           False 同时取消并清理运行中任务。

        Returns:
            被清理的任务数量。
        """
        removed = 0
        removed_ids = []
        for tid in list(self._tasks.keys()):
            task = self._tasks[tid]
            if conversation_id and task.conversation_id != conversation_id:
                continue
            is_finished = task.status in ("success", "failed")
            if only_finished and not is_finished:
                continue
            if not is_finished:
                self.cancel(tid)
            self._tasks.pop(tid, None)
            removed_ids.append(tid)
            removed += 1
        # 批量从 DB 删除
        if removed_ids:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    async def _bulk_delete(ids):
                        mapper = self._get_mapper()
                        for tid in ids:
                            await mapper.delete_skill_task(tid)
                    asyncio.create_task(_bulk_delete(removed_ids))
            except Exception as e:
                logger.warning(f"[SkillTaskManager] DB bulk delete failed: {e}")
        logger.info(f"[SkillTaskManager] Cleared {removed} tasks (conv={conversation_id}, only_finished={only_finished})")
        return removed

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
        self._persist(task)  # 写 DB：running
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
                task.proc = proc
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
                task.proc = proc

            # 实时读取输出
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                self._append_log(task, line)
                logger.debug(f"[skill:{task.skill_name}] {line}")

            await proc.wait()

            if task.cancelled:
                task.status = "failed"
                task.error = "已取消"
                logger.info(f"[SkillTaskManager] Task {task_id} cancelled by user")
            elif proc.returncode == 0:
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
            self._persist(task)  # 写 DB：终态


# 进程级单例
_skill_task_manager: Optional[SkillTaskManager] = None


def get_skill_task_manager() -> SkillTaskManager:
    global _skill_task_manager
    if _skill_task_manager is None:
        _skill_task_manager = SkillTaskManager()
    return _skill_task_manager
