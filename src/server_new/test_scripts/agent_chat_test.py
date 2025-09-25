# test_agent_a.py
# 目的：连同 TaskManager 一起在脚本内创建并启动，完成 AgentA→AgentB→TaskManager 的端到端测试
from __future__ import annotations
import asyncio
from pathlib import Path
from pprint import pprint

# ========= ① 需要你填写/确认的变量（建议使用绝对路径） =========
from mediagent.paths import in_data, in_mediagent
PUBLIC_DATASETS_ROOT = in_data("files", "public")
WORKSPACE_ROOT       = in_data("files", "private")
DATABASE_FILE        = in_data("db", "app.sqlite3")
MCPSERVER_FILE       = in_mediagent("mcp_server_tools", "mcp_server.py")

# —— LLM（LM Studio / OpenAI 兼容网关 / 官方 API 均可）——
OPENAI_API_KEY = "lm-studio"             # 本地网关通常可用占位符；用官方API请改为真实key
OPENAI_BASE_URL = "http://127.0.0.1:1234/v1"   # 本地网关示例；用官方API可置为 None
OPENAI_MODEL = "qwen/qwen3-30b-a3b-2507"       # 你的模型名称

# —— 用户 & 用例 ——
USER_UID = "6127016735"
INPUT_SHOULD_REPLY  = "帮我用通俗语言解释一下Dice系数是什么"
INPUT_SHOULD_CREATE = "帮我处理一些数据。数据源是公共数据集的test_set，先做数据导入，然后将导入的结果进行数据预处理，然后用预处理的结果进行训练，最后对训练的结果进行评估。"

# —— 是否启用“完全离线”LLM模拟（无模型/无网关环境可用）——
MOCK_LLM = False   # True 时脚本会跳过真实 LLM 调用，用内置假响应替代


# ========= ② 工程内导入 =========
# TaskManager（按你的工程结构）
from mediagent.modules.task_manager import AsyncTaskManager
# Agent B（你之前提供的版本）
from mediagent.agents.task_create_agent import TaskCreationAgentB, AgentBConfig
# Agent A（使用我给你的 agent_a.py；若你已放入 mediagent.agents，可改为绝对导入）
from mediagent.agents.chat_plan_agent import DialogueAgentA, AgentAConfig


# ========= ③ （可选）Mock LLM：完全离线自检 =========
def patch_agent_for_mock_llm(agent_a: DialogueAgentA) -> None:
    """
    为 Agent A 打补丁，绕过真实 LLM：
    - 第一次调用：emit_user_reply
    - 第二次调用：emit_task_request
    """
    state = {"count": 0}

    async def _fake_call_llm(messages, tools):
        state["count"] += 1
        if state["count"] == 1:
            # 直接回复用户
            return {
                "choices": [{
                    "message": {
                        "tool_calls": [{
                            "function": {
                                "name": "emit_user_reply",
                                "arguments": '{"content":"Dice系数用于衡量两个集合（或分割）重叠程度，取值0~1，越接近1越相似。"}'
                            }
                        }]
                    }
                }]
            }, None
        else:
            # 触发任务创建
            return {
                "choices": [{
                    "message": {
                        "tool_calls": [{
                            "function": {
                                "name": "emit_task_request",
                                "arguments": '{"description":"请对乳腺MRI数据执行标准DCE流程：从 dataset://breast_dce_2024 读取，完成配准、分相、特征计算与导出 summary.xlsx。"}'
                            }
                        }]
                    }
                }]
            }, None

    agent_a._call_llm = _fake_call_llm  # type: ignore


# ========= ④ 构造 TaskManager / AgentB / AgentA 并运行两条用例 =========
async def main():
    # 基础路径检查
    for label, p in [
        ("public_datasets_source_root", PUBLIC_DATASETS_ROOT),
        ("workspace_root", WORKSPACE_ROOT),
        ("database_file", DATABASE_FILE),
        ("mcpserver_file", MCPSERVER_FILE),
    ]:
        path = Path(p).expanduser().resolve()
        print(f"[check] {label}: {path}")

    # 数据库 & MCP 服务器脚本存在性检查（你的 TaskManager 可能要求 DB 先准备好）
    if not Path(DATABASE_FILE).exists():
        print("[FATAL] 数据库文件不存在，请先准备好 app.sqlite3")
        return
    if not Path(MCPSERVER_FILE).exists():
        print("[FATAL] MCP 服务器脚本不存在，请检查路径")
        return

    # 1) 启动 TaskManager（在脚本内创建，不需要你手动提供）
    tm = AsyncTaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCPSERVER_FILE,
    )
    await tm.astart()
    print("[ok] AsyncTaskManager 启动成功。")

    # 2) 构造 Agent B（使用你的宽松参数校验版本）
    cfg_b = AgentBConfig(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        max_retries=3,
        allowed_tools=None,            # 默认使用 tm.list_tools()
        allowed_datasets=None,         # 如需限制可填集合，例如 {"vision_catsdogs_v1"}
        extra_param_rules=None,
        prompt_tools_limit=20,
    )
    agent_b = TaskCreationAgentB(task_manager=tm, config=cfg_b)

    # 3) 构造 Agent A
    cfg_a = AgentAConfig(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        request_timeout=60.0,
        system_prefix=(
            "你是一个对话编排代理（Agent A）。你只做两类事："
            "1) 若应该直接回复用户，请调用函数 emit_user_reply，并把要说的话放到 content。"
            "2) 若应该创建任务，请调用函数 emit_task_request，并把用于创建任务的自然语言描述放到 description。"
            "禁止输出纯文本回答；你必须调用上面两个函数之一。"
        ),
    )
    agent_a = DialogueAgentA(agent_b=agent_b, config=cfg_a)

    # 4) 可选：完全离线时，打补丁模拟 LLM
    if MOCK_LLM:
        patch_agent_for_mock_llm(agent_a)

    # 5) 打印可用工具（便于确认白名单）
    tools = await tm.list_tools()
    print("\n[tools] 当前 TM 提供的工具（仅 name/description）：")
    for t in tools:
        name = t.get("name")
        desc = (t.get("description") or "")[:100]
        more = "..." if len(t.get("description") or "") > 100 else ""
        print(f" - {name}: {desc}{more}")

    # 6) 用例一：期望直接对话回复
    print("\n[case#1] 期望 LLM 直接回复用户：")
    r1 = await agent_a.handle_user_message(
        user_uid=USER_UID,
        user_input=INPUT_SHOULD_REPLY,
        extra_system_hint="若无需创建任务，请直接回答用户。",
        chat_history=None,
    )
    pprint(r1, width=100)

    # 7) 用例二：期望创建任务
    print("\n[case#2] 期望 LLM 触发任务创建：")
    r2 = await agent_a.handle_user_message(
        user_uid=USER_UID,
        user_input=INPUT_SHOULD_CREATE,
        extra_system_hint="如属批处理/流水线，请优先创建任务（emit_task_request）。",
        chat_history=None,
    )
    pprint(r2, width=100)

    # 若创建了任务，演示查一次简要状态
    if r2.get("type") == "task_created" and r2.get("ok") and r2.get("task_uid"):
        task_uid = r2["task_uid"]
        print(f"\n[step] 查询任务状态 task_uid={task_uid}")
        st = await tm.get_task_status(task_uid)
        pprint(st, width=100)

    # 8) 资源释放
    await tm.aclose()
    print("\n[cleanup] 资源释放完成。")


if __name__ == "__main__":
    asyncio.run(main())
