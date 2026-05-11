"""
Skill 任务管理器

负责记录和跟踪 Skill 任务的状态，不代替 CC 执行任务。
任务状态同时写入内存和 PostgreSQL，服务重启后自动恢复。

任务状态流转：
  1. Skill 工具调用 → submit() 创建任务（pending）
  2. Bash 工具执行 → mark_running() 标记为 running
  3. ResultMessage 回调 → mark_finished() 标记为 success/failed
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
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
        """取消 pending 任务（running 任务无法中断，由 CC 自己管理）"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status != "pending":
            logger.warning(f"[SkillTaskManager] Cannot cancel task {task_id} in status {task.status}")
            return False

        # pending 任务直接置为 failed
        task.status = "failed"
        task.error = "已取消"
        task.finished_at = datetime.now()
        self._persist(task)
        logger.info(f"[SkillTaskManager] Cancelled pending task {task_id}")
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

    def find_pending_task(self, skill_name: str, conversation_id: str) -> Optional["SkillTask"]:
        """按 skill_name + conversation_id 找最近一条 pending 任务（Bash 拦截时关联用）"""
        candidates = [
            t for t in self._tasks.values()
            if t.skill_name == skill_name
            and t.conversation_id == conversation_id
            and t.status == "pending"
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.created_at)

    def mark_running(self, task_id: str) -> bool:
        """将任务标记为 running（Bash 开始执行时调用）"""
        task = self._tasks.get(task_id)
        if not task or task.status != "pending":
            return False
        task.status = "running"
        task.started_at = datetime.now()
        self._persist(task)
        logger.info(f"[SkillTaskManager] Task {task_id} marked as running")
        return True

    def mark_finished(self, task_id: str, success: bool, error: Optional[str] = None) -> bool:
        """将任务标记为终态（Bash tool_result 回调时调用）"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.status = "success" if success else "failed"
        task.error = error
        task.finished_at = datetime.now()
        if success:
            task.progress = 100
        self._persist(task)
        logger.info(f"[SkillTaskManager] Task {task_id} marked as {'success' if success else 'failed'}")
        return True


# 进程级单例
_skill_task_manager: Optional[SkillTaskManager] = None


def get_skill_task_manager() -> SkillTaskManager:
    global _skill_task_manager
    if _skill_task_manager is None:
        _skill_task_manager = SkillTaskManager()
    return _skill_task_manager
