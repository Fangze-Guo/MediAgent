#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_agent_b_create_task.py —— 测试新版 AgentB + TaskManager + MCP 全链路创建任务

建议路径：src/server_new/test_scripts/test_agent_b_create_task.py

运行方式（在 src/server_new 目录下）：
    (P310) python -m test_scripts.test_agent_b_create_task
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

# ====== 项目内部模块导入（按你之前的约定） ======
from mediagent.modules.tm_test import AsyncTaskManager
from mediagent.agents.B_test import TaskCreationAgentB, AgentBConfig
from mediagent.paths import in_data,in_mediagent


# ======================================================================
# 一、根据你目前的 TaskManager 代码，补齐 4 个必选参数
# ======================================================================

# 1) 公共数据集根目录（_lookup_dataset_path_for_task 会用到）：
#    DB 中 dataset_catalog.data_path 是相对路径，会拼在这个 public_root 后面。
PUBLIC_DATASETS_ROOT: Path = in_data("files")

# 2) 工作区根目录：TaskManager 会在下面创建
#    workspace_root / user_uid / "workspace" / task_uid / step_uid / ...
WORKSPACE_ROOT: Path = in_data("files", "private")

# 3) SQLite 数据库文件：里边要有 tasks / steps / dataset_catalog 等表
DATABASE_FILE: Path = in_data("db", "app.sqlite3")   # ⚠ 如果你叫别的名，改这里

# 4) MCP 服务器脚本：也就是你之前一直在用的 mcp_server.py           # .../src/server_new/test_scripts
MCP_SERVER_FILE: Path = in_mediagent("mcp_server_tools", "mcp_server.py")


# ======================================================================
# 二、AgentB 的 LLM 配置（按你 LM Studio / 网关实际情况改）
# ======================================================================

AGENTB_MODEL = "deepseek-chat"        # 你在 LM Studio 里配置的模型名
AGENTB_BASE_URL = "https://api.deepseek.com/v1"   # LM Studio 默认 /v1 网关
AGENTB_API_KEY = "sk-d0e27c4c590a454e8284309067c03f04"

MAX_RETRIES = 2
PROMPT_TOOLS_LIMIT = 10

# 测试用 user_uid 随便给一个
TEST_USER_UID = "7272895950"

# 限制 AgentB 可用工具（None 表示用 TaskManager.list_tools() 返回的全部白名单）
ALLOWED_TOOLS = None          # 例如：{"convert_dicom_to_nifti", "register_deeds"}

# 限制可用的数据集 ID（None 表示完全交给 TaskManager 校验）
ALLOWED_DATASETS = None       # 例如：{8842777993}


# ======================================================================
# 三、给 AgentB 的自然语言任务说明（模拟 AgentA 传进来的 plan_text）
# ======================================================================

SAMPLE_PLAN_TEXT = """
我有一个MR数据集，dataset_id = 8173837876。
该数据集下有一个0_DICOM文件夹，该文件夹内包含原始dicom文件

现在需要你帮我规划一个自动化处理流水线：

1. 第一步：调用 DICOM→NIfTI 的转换工具，把 dataset_id=8173837876这个数据集
   下的 0_DICOM 中的 C0/C2 序列批量转换成 NIfTI，并输出到一个中间结果目录。

2. 第二步：调用基于 linearBCV + deedsBCV 的批量配准工具，将每个病人的 C2.nii.gz
   配准到 C0.nii.gz，输入来自上一步的输出目录，输出到新的结果目录。

"""


# ======================================================================
# 四、初始化 / 关闭 AsyncTaskManager 的辅助函数
# ======================================================================

async def init_task_manager() -> AsyncTaskManager:
    """
    按当前 task_manager.AsyncTaskManager 的签名：

        AsyncTaskManager(
            public_datasets_source_root: str | Path,
            workspace_root: str | Path,
            database_file: str | Path,
            mcpserver_file: str | Path,
        )

    来创建并启动一个实例。
    """
    tm = AsyncTaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCP_SERVER_FILE,
    )

    # 你的 AsyncTaskManager 里已经有 astart() 方法
    await tm.astart()
    return tm


async def shutdown_task_manager(tm: AsyncTaskManager) -> None:
    """优雅关闭 AsyncTaskManager。"""
    if tm is None:
        return
    # 你的实现里有 aclose()
    if hasattr(tm, "aclose"):
        await tm.aclose()
    elif hasattr(tm, "astop"):
        await tm.astop()
    elif hasattr(tm, "close"):
        tm.close()


# ======================================================================
# 五、主测试流程
# ======================================================================

async def main() -> None:
    tm: AsyncTaskManager | None = None
    try:
        # 1) 启动 TaskManager（内部会连 DB、启动 MCPExecutor、扫描工具白名单等等）
        print(">>> 初始化 AsyncTaskManager ...")
        tm = await init_task_manager()
        print(">>> AsyncTaskManager 已启动。")

        # 2) 构造 AgentB 配置（外部接口和你原来的一样）
        cfg = AgentBConfig(
            model=AGENTB_MODEL,
            max_retries=MAX_RETRIES,
            allowed_tools=ALLOWED_TOOLS,
            allowed_datasets=ALLOWED_DATASETS,
            api_key=AGENTB_API_KEY,        # 对 LM Studio 来说内容无所谓，有字符串就行
            base_url=AGENTB_BASE_URL,
            prompt_tools_limit=PROMPT_TOOLS_LIMIT,
        )

        agent_b = TaskCreationAgentB(task_manager=tm, config=cfg)

        # 3) 调用 AgentB.create_task（用自然语言 plan_text）
        print("\n>>> 调用 AgentB.create_task() ...")
        result = await agent_b.create_task(
            user_uid=TEST_USER_UID,
            plan_text=SAMPLE_PLAN_TEXT,
        )

        print("\n=== AgentB.create_task 返回结果 ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if result.get("ok"):
            print("\n✅ 任务创建成功，task_uid =", result.get("task_uid"))
        else:
            print("\n❌ 任务创建失败，可查看 errors 字段进行排查。")

    finally:
        # 4) 关闭 TaskManager
        if tm is not None:
            print("\n>>> 关闭 AsyncTaskManager ...")
            await shutdown_task_manager(tm)
            print(">>> AsyncTaskManager 已关闭。")


if __name__ == "__main__":
    asyncio.run(main())
