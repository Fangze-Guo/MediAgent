"""
会话审计服务 - 管理 conversation_id <-> session_id 的映射
提供会话生命周期管理、追溯和合规支持
根据 QWEN_USE_WSL 环境变量自动选择正确的 JSONL 查找路径
"""
import asyncio
import json
import logging
import os
import platform
from pathlib import Path, PureWindowsPath
from typing import List, Optional, Dict

from src.server_agent.mapper.SessionAuditMapper import SessionAudit, SessionAuditMapper
from src.server_agent.exceptions import NotFoundError, ServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class QwenSessionExtractor:
    """从 Qwen JSONL 文件中提取 session_id - 支持 WSL/Windows 双模式"""

    def __init__(self):
        """初始化提取器"""
        # 检查环境变量
        self.use_wsl = os.getenv("QWEN_USE_WSL", "").lower() == "true"
        self.qwen_code_path = os.getenv("QWEN_CODE_PATH", "qwen")
        self.wsl_user = os.getenv("WSL_USER") or os.getenv("USERNAME", "fetters")

        # 初始化 chats 目录路径
        self._init_chats_dir()

        logger.info(f"QwenSessionExtractor initialized:")
        logger.info(f"  - WSL mode: {self.use_wsl}")
        logger.info(f"  - Qwen path: {self.qwen_code_path}")
        logger.info(f"  - WSL user: {self.wsl_user}")
        logger.info(f"  - Chats dir: {self.chats_dir}")

    def _init_chats_dir(self) -> None:
        """初始化 chats 目录路径"""
        if self.use_wsl:
            self.chats_dir = self._get_wsl_chats_dir()
            logger.info(f"WSL mode - chats dir: {self.chats_dir}")
        else:
            self.chats_dir = self._get_windows_chats_dir()
            logger.info(f"Windows mode - chats dir: {self.chats_dir}")

    @staticmethod
    def _get_windows_chats_dir() -> Path:
        """获取 Windows 环境的 Qwen chats 目录"""
        home = Path.home()
        chats_dir = home / ".qwen" / "projects"
        logger.debug(f"Windows chats directory: {chats_dir}")
        return chats_dir

    def _get_wsl_chats_dir(self) -> Path:
        """
        获取 WSL 环境的 Qwen chats 目录
        使用 WSL UNC 路径（Windows 可直接访问）
        WSL 路径格式：\\wsl.localhost\\Ubuntu\\home\\{user}\\.qwen\\projects
        """
        # WSL UNC 路径（Windows 可访问）
        wsl_unc = PureWindowsPath(f"\\\\wsl.localhost\\Ubuntu\\home\\{self.wsl_user}")
        chats_dir = wsl_unc / ".qwen" / "projects"

        logger.debug(f"WSL UNC chats directory: {chats_dir}")
        return Path(str(chats_dir))

    @staticmethod
    def _extract_session_id_from_jsonl(jsonl_file: Path) -> Optional[str]:
        """
        从 JSONL 文件的第一行提取 sessionId

        Args:
            jsonl_file: JSONL 文件路径

        Returns:
            session_id，如果提取失败返回 None
        """
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not first_line:
                    logger.error(f"JSONL file is empty: {jsonl_file}")
                    return None

                data = json.loads(first_line)
                session_id = data.get('sessionId')

                if session_id:
                    logger.info(f"Extracted sessionId: {session_id}")
                    return session_id
                else:
                    logger.error(f"sessionId not found in: {jsonl_file}")
                    return None

        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error reading JSONL file {jsonl_file}: {e}")
            return None

    async def find_latest_jsonl_file(self, time_window: int = 10) -> Optional[Path]:
        """
        在 chats 目录中查找最近修改的 JSONL 文件

        Args:
            time_window: 时间窗口（秒），只查找指定时间窗口内修改的文件

        Returns:
            最新的 JSONL 文件路径，如果没找到返回 None
        """
        if not self.chats_dir.exists():
            logger.error(f"Chats directory not found: {self.chats_dir}")
            return None

        try:
            # 查找所有 JSONL 文件
            jsonl_files = list(self.chats_dir.rglob("*.jsonl"))

            if not jsonl_files:
                logger.warning(f"No JSONL files found in {self.chats_dir}")
                return None

            # 筛选最近修改的文件
            from datetime import datetime, timedelta
            time_threshold = datetime.now() - timedelta(seconds=time_window)

            recent_files = [
                (file_path, datetime.fromtimestamp(file_path.stat().st_mtime))
                for file_path in jsonl_files
                if datetime.fromtimestamp(file_path.stat().st_mtime) >= time_threshold
            ]

            if not recent_files:
                logger.warning(f"No recent JSONL files found (within {time_window} seconds)")
                return None

            # 返回最新的文件
            latest_file = sorted(recent_files, key=lambda x: x[1], reverse=True)[0][0]
            logger.info(f"Found latest JSONL file: {latest_file.name}")
            return latest_file

        except (PermissionError, OSError) as e:
            logger.error(f"Error scanning chats directory {self.chats_dir}: {e}")
            return None

    async def extract_session_id(self, timeout: int = 10) -> Optional[str]:
        """
        从最新的 Qwen JSONL 文件中提取 session_id

        Args:
            timeout: 等待文件创建的超时时间（秒）

        Returns:
            提取的 session_id，如果失败则返回 None
        """
        # 等待新的 JSONL 文件被创建
        max_attempts = timeout
        for attempt in range(max_attempts):
            # 查找最新的 JSONL 文件
            latest_jsonl = await self.find_latest_jsonl_file(time_window=max_attempts - attempt)

            if latest_jsonl:
                # 从 JSONL 文件中提取 session_id
                session_id = self._extract_session_id_from_jsonl(latest_jsonl)
                if session_id:
                    logger.info(f"Successfully extracted session_id: {session_id}")
                    return session_id

            # 等待一段时间再重试
            if attempt < max_attempts - 1:
                await asyncio.sleep(1)

        logger.warning(f"Failed to extract session_id after {timeout} seconds")
        return None


class SessionAuditService:
    """会话审计服务"""

    def __init__(self):
        """初始化会话审计服务"""
        self.mapper = SessionAuditMapper()
        self.session_extractor = QwenSessionExtractor()
        logger.info("Session audit service initialized")

    @handle_service_exception
    async def create_conversation_audit(
        self,
        user_id: int,
        conversation_id: str,
        extra: Optional[Dict] = None
    ) -> SessionAudit:
        """
        创建新会话审计记录（第一次对话前）

        Args:
            user_id: 用户ID
            conversation_id: 会话ID（UUID格式）
            extra: 额外元数据

        Returns:
            创建的会话审计对象
        """
        logger.info(f"Creating conversation audit for user {user_id}, conversation {conversation_id}")
        return await self.mapper.create_conversation_audit(user_id, conversation_id, extra)

    @handle_service_exception
    async def get_conversation_audit(self, conversation_id: str) -> Optional[SessionAudit]:
        """
        根据 conversation_id 获取会话审计记录

        Args:
            conversation_id: 会话ID

        Returns:
            会话审计对象或None
        """
        return await self.mapper.get_by_conversation_id(conversation_id)

    @handle_service_exception
    async def get_qwen_session_id(self, conversation_id: str) -> Optional[str]:
        """
        获取会话对应的 Qwen session_id

        Args:
            conversation_id: 会话ID

        Returns:
            Qwen 的 session_id，如果不存在则返回 None
        """
        session_audit = await self.mapper.get_by_conversation_id(conversation_id)
        if session_audit:
            return session_audit.session_id
        return None

    @handle_service_exception
    async def update_session_id_after_first_message(self, conversation_id: str) -> bool:
        """
        第一次对话后，提取 session_id 并更新审计记录

        Args:
            conversation_id: 会话ID

        Returns:
            是否更新成功
        """
        logger.info(f"Extracting session_id for conversation {conversation_id}...")

        # 从 Qwen JSONL 文件中提取 session_id
        session_id = await self.session_extractor.extract_session_id(timeout=5)

        if session_id:
            # 更新审计记录
            success = await self.mapper.update_session_id(conversation_id, session_id)
            if success:
                logger.info(f"Successfully updated session_id: {session_id}")
            else:
                logger.warning(f"Failed to update session_id for conversation {conversation_id}")
            return success
        else:
            logger.warning(f"Failed to extract session_id for conversation {conversation_id}")
            return False

    @handle_service_exception
    async def get_user_conversations(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SessionAudit]:
        """
        获取用户的会话列表

        Args:
            user_id: 用户ID
            status: 状态过滤（可选：'active', 'closed'）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            会话审计对象列表
        """
        return await self.mapper.get_user_conversations(user_id, status, limit, offset)

    @handle_service_exception
    async def close_session(self, conversation_id: str) -> bool:
        """
        关闭会话

        Args:
            conversation_id: 会话ID

        Returns:
            是否关闭成功
        """
        logger.info(f"Closing conversation {conversation_id}")
        result = await self.mapper.close_session(conversation_id)
        if result:
            logger.info(f"Conversation {conversation_id} closed successfully")
        else:
            logger.warning(f"Failed to close conversation {conversation_id}")
        return result

    @handle_service_exception
    async def delete_session(self, conversation_id: str) -> bool:
        """
        删除会话（级联删除）

        Args:
            conversation_id: 会话ID

        Returns:
            是否删除成功
        """
        logger.info(f"Deleting conversation {conversation_id}")
        result = await self.mapper.delete_session(conversation_id)
        if result:
            logger.info(f"Conversation {conversation_id} deleted successfully")
        else:
            logger.warning(f"Failed to delete conversation {conversation_id}")
        return result

    @handle_service_exception
    async def update_session_extra(self, conversation_id: str, extra: Dict) -> bool:
        """
        更新会话的额外元数据

        Args:
            conversation_id: 会话ID
            extra: 新的额外元数据

        Returns:
            是否更新成功
        """
        return await self.mapper.update_extra(conversation_id, extra)

    @handle_service_exception
    async def get_session_count(self, user_id: int, status: Optional[str] = None) -> int:
        """
        获取用户的会话数量

        Args:
            user_id: 用户ID
            status: 状态过滤（可选）

        Returns:
            会话数量
        """
        sessions = await self.mapper.get_user_conversations(user_id, status, limit=1000)
        return len(sessions)

    @handle_service_exception
    async def validate_conversation_access(self, user_id: int, conversation_id: str) -> bool:
        """
        验证用户是否有权限访问指定会话

        Args:
            user_id: 用户ID
            conversation_id: 会话ID

        Returns:
            是否有权限
        """
        session = await self.mapper.get_by_conversation_id(conversation_id)
        if not session:
            return False
        return session.user_id == user_id

    @handle_service_exception
    async def is_first_message(self, conversation_id: str) -> bool:
        """
        检查是否是第一次对话（session_id 是否为空）

        Args:
            conversation_id: 会话ID

        Returns:
            是否是第一次对话
        """
        session_audit = await self.mapper.get_by_conversation_id(conversation_id)
        if not session_audit:
            return False
        return session_audit.session_id is None
