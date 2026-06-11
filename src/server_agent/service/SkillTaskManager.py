"""
Skill 任务管理器

负责记录和跟踪 Skill 任务的状态，不代替 CC 执行任务。
任务状态同时写入内存和 PostgreSQL，服务重启后自动恢复。

任务状态以 manifest.json 为准：
  1. Bash 调用 runner 时 submit() 只登记任务。
  2. 前端轮询任务时读取 manifest.json 的 status/progress/outputs/logs。
  3. Bash/ClaudeCode 后台状态不作为医学任务终态。
"""
import asyncio
import json
import logging
import shlex
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

SkillStatus = Literal["running", "success", "failed"]


@dataclass
class SkillTask:
    task_id: str
    skill_name: str
    params: dict
    conversation_id: str
    status: SkillStatus = "running"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None     # 失败原因

    def elapsed_seconds(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def _read_manifest(self) -> Optional[dict]:
        manifest_path = self.params.get("manifest_path") if isinstance(self.params, dict) else None
        if not manifest_path:
            run_dir = self.params.get("run_dir") if isinstance(self.params, dict) else None
            manifest_path = str(Path(run_dir) / "manifest.json") if run_dir else None
        if not manifest_path:
            return None
        path = Path(str(manifest_path))
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"[SkillTaskManager] Failed to read manifest {path}: {exc}")
            return None
        return payload if isinstance(payload, dict) else None

    def to_dict(self) -> dict:
        manifest = self._read_manifest()
        manifest_status = manifest.get("status") if manifest else None
        status = manifest_status if manifest_status in ("running", "success", "failed") else "running"
        progress_payload = manifest.get("progress") if manifest else None
        if isinstance(progress_payload, dict) and progress_payload.get("total"):
            total = progress_payload.get("total") or 0
            completed = progress_payload.get("completed") or 0
            progress = int(completed / total * 100) if total else 0
        else:
            progress = 0

        logs = []
        if manifest:
            for step in manifest.get("steps") or []:
                if isinstance(step, dict):
                    logs.extend(step.get("log_files") or [])

        started_at = manifest.get("started_at") if manifest else None
        finished_at = manifest.get("finished_at") if manifest else None
        elapsed_seconds = None
        if started_at and finished_at:
            try:
                elapsed_seconds = (
                    datetime.fromisoformat(finished_at) -
                    datetime.fromisoformat(started_at)
                ).total_seconds()
            except Exception:
                elapsed_seconds = None

        return {
            "task_id": self.task_id,
            "skill_name": self.skill_name,
            "conversation_id": self.conversation_id,
            "status": status,
            "progress": progress,
            "created_at": self.created_at.isoformat(),
            "started_at": started_at,
            "finished_at": finished_at,
            "elapsed_seconds": elapsed_seconds,
            "error": ("; ".join(str(item) for item in (manifest.get("errors") or [])) if manifest else None),
            "patient_id": manifest.get("patient_id") if manifest else self.params.get("patient_id"),
            "run_id": manifest.get("run_id") if manifest else self.params.get("run_id"),
            "run_dir": manifest.get("run_dir") if manifest else self.params.get("run_dir"),
            "manifest_path": self.params.get("manifest_path"),
            "manifest": manifest,
            "logs": logs,
            "output": {
                "outputs": manifest.get("outputs", []),
                "steps": manifest.get("steps", []),
                "progress": manifest.get("progress"),
            } if manifest else None,
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

    def _enrich_params(self, params: dict) -> dict:
        payload = dict(params or {})
        command = payload.get("command")
        if not isinstance(command, str) or not command.strip():
            return payload
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()

        def option_value(*names: str) -> Optional[str]:
            for index, part in enumerate(parts):
                for name in names:
                    if part == name and index + 1 < len(parts):
                        return parts[index + 1]
                    prefix = f"{name}="
                    if part.startswith(prefix):
                        return part[len(prefix):]
            return None

        patient_id = option_value("--patient-id")
        run_id = option_value("--run-id")
        run_dir = option_value("--run-dir")
        patient_context = option_value("--patient-context")
        skill_id = option_value("--skill-id")

        if patient_id:
            payload.setdefault("patient_id", patient_id)
        if run_id:
            payload.setdefault("run_id", run_id)
        if run_dir:
            payload.setdefault("run_dir", run_dir)
            payload.setdefault("manifest_path", str(Path(run_dir) / "manifest.json"))
        elif patient_id and skill_id and run_id:
            patient_root = Path("/home/fetters/project/MediAgent/src/server_new/data/patient")
            computed_run_dir = patient_root / patient_id / "agent_outputs" / run_id / "steps" / skill_id
            payload.setdefault("run_dir", str(computed_run_dir))
            payload.setdefault("manifest_path", str(computed_run_dir / "manifest.json"))
        if patient_context:
            payload.setdefault("patient_context", patient_context)
        if skill_id:
            payload.setdefault("skill_id", skill_id)
        return payload

    def _persist(self, task: SkillTask):
        """异步写 DB，不阻塞调用方"""
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self._persist_async(task))
        except RuntimeError:
            pass  # 没有运行中的事件循环，跳过
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
                "created_at": task.created_at,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "error": task.error,
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
                if status == "running":
                    status = "failed"
                    row["error"] = (row.get("error") or "") + " [服务重启，任务中断]"
                    row["finished_at"] = row["finished_at"] or datetime.now()
                task = SkillTask(
                    task_id=task_id,
                    skill_name=row["skill_name"],
                    params=row["params"],
                    conversation_id=row["conversation_id"],
                    status=status,
                    created_at=row["created_at"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    error=row["error"],
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
        提交 Skill 任务，直接创建为 running 状态，立即返回 task_id。

        Args:
            skill_name: Skill 名称，如 "bodycomp-seg-nnunet"
            params:     Skill 的原始 tool_input 参数
            conversation_id: 归属会话 ID

        Returns:
            task_id (UUID 字符串)
        """
        task_id = str(uuid.uuid4())
        enriched_params = self._enrich_params(params)
        task = SkillTask(
            task_id=task_id,
            skill_name=skill_name,
            params=enriched_params,
            conversation_id=conversation_id,
            status="running",
            started_at=datetime.now(),
        )
        self._tasks[task_id] = task
        self._persist(task)  # 写 DB
        logger.info(f"[SkillTaskManager] Submitted task {task_id} for skill '{skill_name}' (running)")
        return task_id

    def get_task(self, task_id: str) -> Optional[SkillTask]:
        return self._tasks.get(task_id)

    def update_params(self, task_id: str, params: dict) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.params.update({k: v for k, v in (params or {}).items() if v is not None})
        self._persist(task)
        return True

    def list_tasks(
        self,
        conversation_id: Optional[str] = None,
        conversation_ids: Optional[set[str]] = None,
    ) -> List[SkillTask]:
        tasks = list(self._tasks.values())
        if conversation_id:
            tasks = [t for t in tasks if t.conversation_id == conversation_id]
        elif conversation_ids is not None:
            tasks = [t for t in tasks if t.conversation_id in conversation_ids]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def delete(self, task_id: str) -> bool:
        """从任务表中移除单个任务（直接删除，不论状态）。"""
        if task_id not in self._tasks:
            return False
        self._tasks.pop(task_id, None)
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self._get_mapper().delete_skill_task(task_id))
        except RuntimeError:
            pass
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
            if only_finished and task.status not in ("success", "failed"):
                continue
            self._tasks.pop(tid, None)
            removed_ids.append(tid)
            removed += 1
        # 批量从 DB 删除
        if removed_ids:
            try:
                asyncio.get_running_loop()
                async def _bulk_delete(ids):
                    mapper = self._get_mapper()
                    for tid in ids:
                        await mapper.delete_skill_task(tid)
                asyncio.create_task(_bulk_delete(removed_ids))
            except RuntimeError:
                pass
            except Exception as e:
                logger.warning(f"[SkillTaskManager] DB bulk delete failed: {e}")
        logger.info(f"[SkillTaskManager] Cleared {removed} tasks (conv={conversation_id}, only_finished={only_finished})")
        return removed

    def mark_finished(self, task_id: str, success: bool, error: Optional[str] = None) -> bool:
        """Legacy fallback for non-manifest tasks. Manifest-tracked tasks ignore Bash terminal state."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.params.get("manifest_path") or task.params.get("run_dir"):
            logger.info(f"[SkillTaskManager] Task {task_id} is manifest-tracked, skip mark_finished")
            return False
        if task.status in ("success", "failed"):
            logger.debug(f"[SkillTaskManager] Task {task_id} already in terminal state {task.status}, skip")
            return False
        task.status = "success" if success else "failed"
        task.error = error
        task.finished_at = datetime.now()
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
