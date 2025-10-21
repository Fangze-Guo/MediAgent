# test_agent_a.py
# 目的：端到端联通：对话编排器 → 执行器(原B) → TaskManager，并以“实时输入”的方式进行对话
from __future__ import annotations

import asyncio
from pathlib import Path
from pprint import pprint
from typing import Optional, Dict, Any

# ========= ① 需要你填写/确认的变量（建议使用绝对路径） =========
from mediagent.paths import in_data, in_mediagent

PUBLIC_DATASETS_ROOT = in_data("files", "public")
WORKSPACE_ROOT       = in_data("files", "private")
DATABASE_FILE        = in_data("db", "app.sqlite3")
CONVERSATIONS_ROOT   = in_data("conversations")
MCPSERVER_FILE       = in_mediagent("mcp_server_tools", "mcp_server.py")

# —— LLM（LM Studio / OpenAI 兼容网关 / 官方 API 均可）——
OPENAI_API_KEY  = "sk-d0e27c4c590a454e8284309067c03f04"                 # 本地网关通常可用占位符；用官方API请改为真实key
OPENAI_BASE_URL = "https://api.deepseek.com/v1"  # 本地网关示例；用官方API可置为 None
OPENAI_MODEL    = "deepseek-chat"   # 你的模型名称

# OPENAI_API_KEY  = "sk-d0e27c4c590a454e8284309067c03f04"                 # 本地网关通常可用占位符；用官方API请改为真实key
# OPENAI_BASE_URL = "http://127.0.0.1:1234/v1"  # 本地网关示例；用官方API可置为 None
# OPENAI_MODEL    = "qwen/qwen3-30b-a3b-2507"   # 你的模型名称

# —— 用户 / 对话标识（可留空以便脚本交互创建）——
OWNER_UID: str = "6127016735"                 # create_conversation() 需要：必须存在于 users(uid)
CONVERSATION_UID: Optional[str] = None        # 为空则首轮自动创建

# —— 内部信息流识别码（你分配，用于落盘 <conversation_uid>/<stream_id>.json）——
STREAM_ID: str = "agentA_internal_stream"

# —— 是否启用“完全离线”LLM模拟（无模型/无网关环境可用）——
MOCK_LLM = False   # True 时脚本会跳过真实 LLM 调用，用内置假响应替代


# ========= ② 工程内导入 =========
# TaskManager（按你的工程结构）
from mediagent.modules.task_manager import AsyncTaskManager
# Agent B（你的执行器 / 任务创建编排器）
from mediagent.agents.task_create_agent import TaskCreationAgentB, AgentBConfig
# Agent A（新版：仅暴露 converse，并需要 cm/stream_id/task_manager）
from mediagent.agents.A_test import DialogueAgentA, AgentAConfig
# 对话管理器
from mediagent.modules.conversation_manager import ConversationManager


# ========= ③ （可选）Mock LLM：完全离线自检 =========
def patch_agent_for_mock_llm(agent_a: DialogueAgentA) -> None:
    """
    为对话编排器打补丁，绕过真实 LLM：
    - 第一轮：emit_user_reply
    - 后续：emit_task_request（并把执行器回执喂回去，再由模型总结）
    """
    state = {"count": 0}

    async def _fake_call_llm(messages, tools):
        state["count"] += 1
        # 简单从最后一条 user 消息中取输入
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break

        if state["count"] == 1:
            # 直接回复用户
            return {
                "choices": [{
                    "message": {
                        "tool_calls": [{
                            "function": {
                                "name": "emit_user_reply",
                                "arguments": '{"content":"（mock）好的，我已收到你的消息：' + last_user.replace('"','\\"') + '"}'
                            }
                        }]
                    }
                }]
            }, None
        elif state["count"] == 2:
            # 触发任务创建
            return {
                "choices": [{
                    "message": {
                        "tool_calls": [{
                            "function": {
                                "name": "emit_task_request",
                                "arguments": '{"description":"（mock）请执行标准DCE流水线：导入→预处理→训练→评估，并导出 summary.xlsx"}'
                            }
                        }]
                    }
                }]
            }, None
        else:
            # 让模型给出总结
            return {
                "choices": [{
                    "message": {
                        "tool_calls": [{
                            "function": {
                                "name": "emit_user_reply",
                                "arguments": '{"content":"（mock）任务已受理/或等待补充信息。后续我会同步进展。"}'
                            }
                        }]
                    }
                }]
            }, None

    agent_a._call_llm = _fake_call_llm  # type: ignore


# ========= ④ 工具函数：安全读取输入 =========
async def ainput(prompt: str = "") -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: input(prompt))


# ========= ⑤ 端到端：实时对话 =========
async def main():
    # 基础路径检查
    for label, p in [
        ("public_datasets_source_root", PUBLIC_DATASETS_ROOT),
        ("workspace_root", WORKSPACE_ROOT),
        ("database_file", DATABASE_FILE),
        ("conversations_root", CONVERSATIONS_ROOT),
        ("mcpserver_file", MCPSERVER_FILE),
    ]:
        path = Path(p).expanduser().resolve()
        print(f"[check] {label}: {path}")

    # 数据库 & MCP 服务器脚本存在性检查（你的 TaskManager 可能要求 DB 先准备好）
    if not Path(DATABASE_FILE).exists():
        print("[FATAL] 数据库文件不存在，请先准备好 app.sqlite3（并确保 users 表内存在 OWNER_UID）")
        return
    if not Path(MCPSERVER_FILE).exists():
        print("[FATAL] MCP 服务器脚本不存在，请检查路径")
        return

    # 1) 启动 TaskManager
    tm = AsyncTaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCPSERVER_FILE,
    )
    await tm.astart()
    print("[ok] AsyncTaskManager 启动成功。")

    # 2) 构造 执行器（原B）
    cfg_b = AgentBConfig(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        max_retries=3,
        allowed_tools=None,            # 默认使用 tm.list_tools()
        allowed_datasets=None,
        extra_param_rules=None,
        prompt_tools_limit=20,
    )
    executor = TaskCreationAgentB(task_manager=tm, config=cfg_b)

    # 3) 对话管理器
    cm = ConversationManager(database_path=str(DATABASE_FILE), conversation_root=str(CONVERSATIONS_ROOT))

    # 4) 构造 对话编排器（新版：注意需传入 task_manager）
    cfg_a = AgentAConfig(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        request_timeout=60.0,
    )
    agent = DialogueAgentA(
        executor, cfg_a,
        cm=cm,
        stream_id=STREAM_ID,
        task_manager=tm, # ← 关键新增：用于注入工具目录
        db_path=str(DATABASE_FILE),
    )

    # 5) 可选：完全离线时，打补丁模拟 LLM
    if MOCK_LLM:
        patch_agent_for_mock_llm(agent)

    # 6) 若未提供对话 ID，则尝试创建（需要 OWNER_UID 存在于 users 表）
    conversation_uid = CONVERSATION_UID
    if not conversation_uid:
        print("[info] 未提供 CONVERSATION_UID，尝试创建新对话...")
        created = await cm.create_conversation(OWNER_UID)
        if not created.get("ok"):
            print(f"[FATAL] 创建对话失败：{created}")
            await tm.aclose()
            return
        conversation_uid = created["conversation_uid"]
        print(f"[ok] 新对话已创建：conversation_uid={conversation_uid}")

    # 7) 打印可用工具（便于确认）
    tools = await tm.list_tools()
    print("\n[tools] 当前 TM 提供的工具（仅 name/description）：")
    for t in tools:
        name = t.get("name")
        desc = (t.get("description") or "")[:100]
        more = "..." if len(t.get("description") or "") > 100 else ""
        print(f" - {name}: {desc}{more}")

    # 8) 进入实时对话循环
    print("\n====== 进入实时对话（输入 /new 新建对话；/id 查看当前ID；/quit 退出）======")
    print(f"[当前对话] {conversation_uid}")

    try:
        while True:
            text = (await ainput("\n你: ")).strip()
            if not text:
                continue
            if text in ("/quit", ":q", "exit"):
                break
            if text == "/id":
                print(f"[对话ID] {conversation_uid}")
                continue
            if text == "/new":
                print("[info] 创建新对话...")
                created = await cm.create_conversation(OWNER_UID)
                if created.get("ok"):
                    conversation_uid = created["conversation_uid"]
                    print(f"[ok] 新对话ID: {conversation_uid}")
                else:
                    print(f"[err] 创建失败：{created}")
                continue

            # 调用新版唯一接口 converse()
            reply = await agent.converse(conversation_uid, text)
            print(f"编排器: {reply}")

    except KeyboardInterrupt:
        print("\n[interrupt] 用户中断。")
    finally:
        await tm.aclose()
        print("\n[cleanup] 资源释放完成。")


if __name__ == "__main__":
    asyncio.run(main())
