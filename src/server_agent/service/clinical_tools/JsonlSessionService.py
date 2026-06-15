"""
JSONL Session Service - 读取 Claude SDK 的 JSONL 文件

对标参考项目 claudecodeui 的 projects.js
Claude SDK 会话历史存储在 ~/.claude/projects/{project_name}/{session_id}.jsonl
"""
import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Claude 配置路径
CLAUDE_HOME = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_HOME / "projects"


class JsonlSessionService:
    """JSONL 会话服务 - 读取 Claude SDK 的会话文件"""

    def __init__(self):
        self._ensure_projects_dir()

    def _ensure_projects_dir(self):
        """确保 projects 目录存在"""
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    def session_exists(self, session_id: str) -> bool:
        """
        检查 SDK 会话是否存在（即 JSONL 文件是否存在）

        Args:
            session_id: 会话 ID

        Returns:
            是否存在对应的 JSONL 文件
        """
        if not session_id:
            return False

        # 扫描所有项目目录查找 session
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            jsonl_file = project_dir / f"{session_id}.jsonl"
            if jsonl_file.exists():
                return True
        return False

    def _normalize_project_name(self, project_path: str) -> str:
        """将项目路径规范化为目录名（路径分隔符替换为 -）"""
        # Windows 路径处理
        normalized = project_path.replace("\\", "/").replace(":", "")
        # 替换 / 为 - 来创建目录名
        return re.sub(r"[/\\~_]", "-", normalized)

    def get_project_dir(self, project_name: str) -> Path:
        """获取项目目录"""
        return PROJECTS_DIR / project_name

    async def get_session_messages(
        self,
        session_id: str,
        project_path: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Tuple[List[dict], int, bool]:
        """
        获取会话消息

        Args:
            session_id: 会话 ID
            project_path: 项目路径（用于定位项目目录）
            limit: 限制条数
            offset: 偏移量

        Returns:
            (messages, total, has_more)
        """
        messages = []

        # 扫描所有项目目录查找 session
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            jsonl_file = project_dir / f"{session_id}.jsonl"
            if jsonl_file.exists():
                messages = await self._read_jsonl_file(jsonl_file, session_id)
                break

        if not messages:
            return [], 0, False

        total = len(messages)

        # 按 timestamp 排序
        messages.sort(key=lambda x: x.get("timestamp", ""))

        # 应用分页
        if limit is not None:
            start_index = max(0, total - offset - limit)
            end_index = total - offset
            messages = messages[start_index:end_index]
            has_more = start_index > 0
        else:
            has_more = False

        return messages, total, has_more

    async def _read_jsonl_file(self, jsonl_path: Path, session_id: str) -> List[dict]:
        """读取 JSONL 文件并过滤指定 session 的消息"""
        messages = []
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("sessionId") == session_id:
                            messages.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error reading JSONL file {jsonl_path}: {e}")

        return messages

    async def get_sessions(
        self,
        project_name: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[dict], int, bool]:
        """
        获取会话列表

        Args:
            project_name: 项目名（可选）
            limit: 限制条数
            offset: 偏移量

        Returns:
            (sessions, total, has_more)
        """
        sessions = []
        project_dirs = []

        if project_name:
            project_dir = self.get_project_dir(project_name)
            if project_dir.exists():
                project_dirs.append(project_dir)
        else:
            # 扫描所有项目
            for item in PROJECTS_DIR.iterdir():
                if item.is_dir():
                    project_dirs.append(item)

        # 收集所有会话
        for project_dir in project_dirs:
            try:
                for jsonl_file in project_dir.glob("*.jsonl"):
                    if jsonl_file.stem.startswith("agent-"):
                        continue  # 跳过 agent 文件

                    session_id = jsonl_file.stem
                    stat = jsonl_file.stat()
                    mtime = stat.st_mtime

                    # 读取第一条消息作为 summary
                    summary = "New Session"
                    last_activity = mtime

                    try:
                        with open(jsonl_file, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    entry = json.loads(line)
                                    if entry.get("sessionId") == session_id:
                                        # 尝试从 message.content 提取 summary
                                        msg_content = entry.get("message", {}).get("content", "")
                                        if isinstance(msg_content, list):
                                            for part in msg_content:
                                                if part.get("type") == "text" and part.get("text"):
                                                    summary = part["text"][:50]
                                                    break
                                        elif isinstance(msg_content, str) and msg_content:
                                            summary = msg_content[:50]

                                        ts = entry.get("timestamp")
                                        if ts:
                                            last_activity = ts / 1000  # ms to s
                                        break
                                except json.JSONDecodeError:
                                    continue
                                break
                    except Exception as e:
                        logger.debug(f"Error reading session summary: {e}")

                    sessions.append({
                        "id": session_id,
                        "summary": summary,
                        "lastActivity": last_activity,
                        "cwd": str(project_dir.name),
                        "projectName": project_dir.name,
                    })
            except Exception as e:
                logger.error(f"Error scanning project {project_dir}: {e}")

        # 按最后活动时间排序
        sessions.sort(key=lambda x: x.get("lastActivity", 0), reverse=True)

        total = len(sessions)
        has_more = offset + limit < total

        return sessions[offset:offset + limit], total, has_more

    def _read_jsonl_entries(self, jsonl_file: Path) -> List[dict]:
        """读取 JSONL 文件，忽略空行和坏行。"""
        entries: List[dict] = []
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"[JSONL] Error reading {jsonl_file}: {e}")
            return []
        return entries

    def _resolve_sub_agent_ids_from_parent(self, parent_jsonl: Path, tool_use_id: str) -> List[str]:
        """
        从父会话 JSONL 中解析 Task tool_use id 对应的 agentId。

        流式阶段前端可能只拿到 Task tool_use block id；Claude 在后续 tool_result
        中才写入 toolUseResult.agentId。这里按需补一次映射，避免必须等整轮结束刷新。
        """
        resolved: List[str] = []
        for entry in self._read_jsonl_entries(parent_jsonl):
            tool_use_result = entry.get("toolUseResult")
            if not isinstance(tool_use_result, dict):
                continue
            agent_id = tool_use_result.get("agentId")
            if not agent_id:
                continue

            message = entry.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "tool_result":
                    continue
                if part.get("tool_use_id") == tool_use_id and agent_id not in resolved:
                    resolved.append(agent_id)
        return resolved

    async def get_sub_agent_messages_for_tool_use(
        self,
        parent_session_id: str,
        tool_use_id: str,
    ) -> List[dict]:
        """
        返回子智能体的 JSONL 全量记录。

        Claude SDK 实际路径结构：
          ~/.claude/projects/{project_dir}/{session_id}/subagents/agent-{agentId}.jsonl

        message_parser.py 预扫描 toolUseResult.agentId 后，会将 agentId 存入
        MessageResponse.tool_use_id，因此此处 tool_use_id 参数实际携带的是 agentId。

        Args:
            parent_session_id: 父会话的 session_id，用于定位项目目录
            tool_use_id: agentId（即文件名中 agent-{agentId} 的部分）

        Returns:
            子智能体 JSONL 全量记录列表（供 parse_jsonl_messages 处理）
        """
        # 找到父会话所在的项目目录。历史上同一个 Claude session 可能出现在不同
        # project dir，不能只取第一个，否则会漏掉 subagents 目录。
        project_dirs: List[Path] = []
        for pdir in PROJECTS_DIR.iterdir():
            if not pdir.is_dir():
                continue
            if (pdir / f"{parent_session_id}.jsonl").exists():
                project_dirs.append(pdir)

        if not project_dirs:
            logger.debug(f"[SubAgent] Parent session {parent_session_id} not found in any project dir")
            return []

        candidate_agent_ids = [tool_use_id]
        for pdir in project_dirs:
            parent_jsonl = pdir / f"{parent_session_id}.jsonl"
            for resolved_id in self._resolve_sub_agent_ids_from_parent(parent_jsonl, tool_use_id):
                if resolved_id not in candidate_agent_ids:
                    candidate_agent_ids.append(resolved_id)

        for pdir in project_dirs:
            subagents_dir = pdir / parent_session_id / "subagents"
            for agent_id in candidate_agent_ids:
                agent_file = subagents_dir / f"agent-{agent_id}.jsonl"
                if not agent_file.exists():
                    continue
                entries = self._read_jsonl_entries(agent_file)
                logger.info(f"[SubAgent] Loaded {len(entries)} entries from {agent_file}")
                return entries

        # 流式早期 toolUseResult.agentId 可能尚未写入父会话。若当前父 session
        # 下只有一个子智能体文件，采用它作为安全 fallback；多个文件时不猜。
        fallback_files: List[Path] = []
        for pdir in project_dirs:
            subagents_dir = pdir / parent_session_id / "subagents"
            if subagents_dir.exists():
                fallback_files.extend(sorted(subagents_dir.glob("agent-*.jsonl")))

        if len(fallback_files) == 1:
            agent_file = fallback_files[0]
            entries = self._read_jsonl_entries(agent_file)
            logger.info(f"[SubAgent] Loaded {len(entries)} entries from fallback {agent_file}")
            return entries

        logger.debug(
            "[SubAgent] Agent file not found for parent_session=%s tool_use_id=%s candidates=%s fallback_count=%s",
            parent_session_id,
            tool_use_id,
            candidate_agent_ids,
            len(fallback_files),
        )
        return []

    async def get_conversation_by_id(self, session_id: str) -> Optional[dict]:
        """根据 ID 获取会话信息"""
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            jsonl_file = project_dir / f"{session_id}.jsonl"
            if jsonl_file.exists():
                stat = jsonl_file.stat()
                return {
                    "id": session_id,
                    "cwd": str(project_dir),
                    "projectName": project_dir.name,
                    "lastActivity": stat.st_mtime,
                    "filePath": str(jsonl_file),
                }

        return None


# 全局实例
_session_service: Optional[JsonlSessionService] = None


def get_session_service() -> JsonlSessionService:
    """获取会话服务实例"""
    global _session_service
    if _session_service is None:
        _session_service = JsonlSessionService()
    return _session_service
