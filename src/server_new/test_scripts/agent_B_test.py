# test_agent_b.py
# 目的：用自然语言计划测试修改后的 Agent B（先走 Responses API 严格 JSON Schema，失败则回退）
from __future__ import annotations
import os
import asyncio
from pathlib import Path
from pprint import pprint

# --- 你工程里的导入（按你的实际模块路径修改） ---
# 示例来自你前面的脚本：AsyncTaskManager / Agent B
from mediagent.modules.task_manager import AsyncTaskManager
from mediagent.agents.task_create_agent import TaskCreationAgentB, AgentBConfig  # 确保是你刚替换过的版本

# ======== 需要你自己填写/确认的变量（用绝对路径更稳）========
# 这些和你之前 test_init_task_manager_async.py 的用法一致
from mediagent.paths import in_data, in_mediagent
PUBLIC_DATASETS_ROOT = in_data("files", "public")
WORKSPACE_ROOT       = in_data("files", "private")
DATABASE_FILE        = in_data("db", "app.sqlite3")
MCPSERVER_FILE       = in_mediagent("mcp_server_tools", "mcp_server.py")

# OpenAI 连接（建议放到环境变量；也可直接写死）
OPENAI_API_KEY = "NONE"
OPENAI_BASE_URL = "http://127.0.0.1:1234/v1"  # 若走兼容网关就填；官方无需设置
OPENAI_MODEL = "qwen/qwen3-30b-a3b-2507"  # 支持 Responses 结构化输出的模型

# 业务侧：模拟一个用户ID
USER_UID = "6127016735"

# ======== 示例自然语言计划（随便换）========
PLAN_TEXT = """
执行如下计划：
第一步做数据导入，待导入的数据为公共数据集的test_set
第二步做数据预处理，其输入为第一步的产物
第三步做模型训练，其输入为第二步的产物
最后一步做模型评估，其输入为第三步的产物
"""

async def main():
    # 0) 基础检查
    for label, p in [
        ("public_datasets_source_root", PUBLIC_DATASETS_ROOT),
        ("workspace_root", WORKSPACE_ROOT),
        ("database_file", DATABASE_FILE),
        ("mcpserver_file", MCPSERVER_FILE),
    ]:
        path = Path(p).expanduser().resolve()
        print(f"[check] {label}: {path}")

    if not Path(DATABASE_FILE).exists():
        print("[FATAL] 数据库文件不存在，请先准备好 app.sqlite3")
        return
    if not Path(MCPSERVER_FILE).exists():
        print("[FATAL] MCP 服务器脚本不存在，请检查路径")
        return

    if not OPENAI_API_KEY or "<<<填你的API KEY>>>" in OPENAI_API_KEY:
        print("[FATAL] 请设置 OPENAI_API_KEY（环境变量或直接在脚本中填写）")
        return

    # 1) 启动 AsyncTaskManager
    tm = AsyncTaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCPSERVER_FILE,
    )
    await tm.astart()
    print("[ok] AsyncTaskManager 启动成功。")

    # 2) Agent B 配置（注意：我们使用的是你刚修改过的“宽松参数校验”版本）
    cfg = AgentBConfig(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,      # None 表示官方；否则指向你的网关
        max_retries=3,
        allowed_tools=None,            # 默认用 tm.list_tools() 返回的白名单工具
        allowed_datasets=None,         # 如需限制可填集合，例如 {"vision_catsdogs_v1"}
        extra_param_rules=None,        # 可选：对特定工具做互斥/依赖等约束
        prompt_tools_limit=20,
    )
    agent = TaskCreationAgentB(task_manager=tm, config=cfg)

    # 3) 读取当前可用工具（仅 name/description），便于调试
    tools = await tm.list_tools()
    print("\n[tools] 供 LLM 使用的工具（只含 name/description）：")
    for t in tools:
        print(f" - {t.get('name')}: {t.get('description')[:100]}{'...' if len(t.get('description',''))>100 else ''}")

    # 4) 调用 Agent B：它会先尝试 Responses API 的 json_schema(strict)，失败才回退 chat.completions
    print("\n[step] 调用 Agent B.create_task() …")
    result = await agent.create_task(user_uid=USER_UID, plan_text=PLAN_TEXT)

    print("\n[RESULT] Agent B 返回：")
    pprint(result, width=100)

    # 5) 如已创建任务，查询一次状态（不包含日志）
    if result.get("ok") and result.get("task_uid"):
        task_uid = result["task_uid"]
        print(f"\n[step] 查询任务状态 task_uid={task_uid}")
        st = await tm.get_task_status(task_uid)
        print("[status]")
        pprint(st, width=100)

    # 6) 关闭
    await tm.aclose()
    print("\n[cleanup] 资源释放完成。")


if __name__ == "__main__":
    asyncio.run(main())
