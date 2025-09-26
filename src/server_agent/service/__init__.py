"""
Service包 - 统一管理所有业务服务
"""
from typing import Optional

from constants.EnvConfig import API_KEY, BASE_URL, MODEL
from mediagent.agents.chat_plan_agent import AgentAConfig
from mediagent.agents.task_create_agent import AgentBConfig, TaskCreationAgentB
from mediagent.modules.conversation_manager import ConversationManager
from mediagent.modules.task_manager import AsyncTaskManager
from mediagent.paths import in_data, in_mediagent
from .ConversationService import ConversationService
from .FileService import FileService
from .UserService import UserService

PUBLIC_DATASETS_ROOT = in_data("files", "public")
WORKSPACE_ROOT = in_data("files", "private")
DATABASE_FILE = in_data("db", "app.sqlite3")
CONVERSATIONS_ROOT = "src/server_agent/conversations"
MCPSERVER_FILE = in_mediagent("mcp_server_tools", "mcp_server.py")

# —— 用户 / 对话标识（可留空以便脚本交互创建）——
OWNER_UID: str = "6127016735"  # create_conversation() 需要：必须存在于 users(uid)
CONVERSATION_UID: Optional[str] = None  # 为空则首轮自动创建

# —— 内部信息流识别码（你分配，用于落盘 <conversation_uid>/<stream_id>.json）——
STREAM_ID: str = "agentA_internal_stream"

# —— 是否启用“完全离线”LLM模拟（无模型/无网关环境可用）——
MOCK_LLM = False  # True 时脚本会跳过真实 LLM 调用，用内置假响应替代

# 1) 启动 TaskManager
tm = AsyncTaskManager(
    public_datasets_source_root=PUBLIC_DATASETS_ROOT,
    workspace_root=WORKSPACE_ROOT,
    database_file=DATABASE_FILE,
    mcpserver_file=MCPSERVER_FILE,
)

# 使用asyncio.run来正确启动异步任务管理器
import asyncio

try:
    asyncio.run(tm.astart())
    print("[ok] AsyncTaskManager 启动成功。")
except RuntimeError:
    # 如果已经在事件循环中，使用create_task
    loop = asyncio.get_event_loop()
    loop.create_task(tm.astart())
    print("[ok] AsyncTaskManager 启动成功（在现有事件循环中）。")

# 2) 构造 执行器（原B）
cfg_b = AgentBConfig(
    model=MODEL,
    api_key=API_KEY,
    base_url=BASE_URL,
    max_retries=3,
    allowed_tools=None,  # 默认使用 tm.list_tools()
    allowed_datasets=None,
    extra_param_rules=None,
    prompt_tools_limit=20,
)
executor = TaskCreationAgentB(task_manager=tm, config=cfg_b)

# 3) 对话管理器
cm = ConversationManager(database_path=str(DATABASE_FILE), conversation_root=str(CONVERSATIONS_ROOT))

# 4) 构造 对话编排器（新版：注意需传入 task_manager）
cfg_a = AgentAConfig(
    model=MODEL,
    api_key=API_KEY,
    base_url=BASE_URL,
    request_timeout=60.0,
)

__all__ = [
    'FileService',
    'ConversationService',
    'UserService',
    'tm',
    'executor',
    'cm',
    'cfg_a',
    'STREAM_ID',
    'OWNER_UID'
]
