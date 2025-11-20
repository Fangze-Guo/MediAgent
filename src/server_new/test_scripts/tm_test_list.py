#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：打印 TaskManager 从 MCP 拉下来的工具列表

- 第一段：TaskManager.list_tools()  -> 仅白名单工具（AgentB/AgentA 会看到的）
- 第二段：TaskManager.list_all_tools() -> MCP 全量工具 + inputSchema（重点看这个）
"""

import asyncio
import json
from pathlib import Path

# 根据你的实际包结构调整：
# 如果你在 src/server_new 下运行，通常如下导入：
from src.server_new.mediagent.modules.tm_test import AsyncTaskManager
from src.server_new.mediagent.paths import in_data, in_mediagent


# ====== 路径配置（请按自己实际环境修改） ======
# 这些值只在初始化 TaskManager 时用，和 list_tools 本身关系不大，
# 但需要是“存在的路径”，否则初始化会直接抛错。

# 公共数据集根目录（随便给一个真实存在的目录就行）
PUBLIC_DATASETS_ROOT = in_data("files")

# 工作区根目录
WORKSPACE_ROOT = in_data("files","private")

# SQLite 数据库文件
DATABASE_FILE = in_data("db", "app.sqlite3")

# MCP 服务器脚本（就是你现在 TaskManager 里传入的那个 mcp_server.py）
MCP_SERVER_FILE = in_mediagent("mcp_server_tools", "mcp_server.py")


async def main() -> None:
    # 1. 初始化并启动 AsyncTaskManager（内部会启动 MCPExecutor）
    tm = AsyncTaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCP_SERVER_FILE,
    )

    await tm.astart()

    try:
        # 2. 打印“白名单工具”——TaskManager.list_tools()
        print("=" * 80)
        print("【1】TaskManager.list_tools()  —— 暴露给外部的白名单工具")
        print("=" * 80)
        allowed_tools = await tm.list_tools()
        print(json.dumps(allowed_tools, ensure_ascii=False, indent=2))

        # 3. 打印“所有 MCP 工具”——TaskManager.list_all_tools()
        print("\n" + "=" * 80)
        print("【2】TaskManager.list_all_tools() —— MCP 全量工具（含 inputSchema）")
        print("=" * 80)
        all_tools = await tm.list_all_tools()

        # 为了阅读方便：按 name 排序一下
        all_tools_sorted = sorted(
            all_tools, key=lambda t: t.get("name", "")
        )

        for idx, t in enumerate(all_tools_sorted, start=1):
            name = t.get("name", "")
            desc = t.get("description", "")
            schema = t.get("inputSchema")

            print(f"\n---- 工具 #{idx} ----")
            print(f"name        : {name}")
            print(f"description : {desc}")
            print(f"hasSchema   : {schema is not None}")

            # 如果你想重点看 schema，就把下面的注释打开
            if schema is not None:
                print("inputSchema :")
                print(json.dumps(schema, ensure_ascii=False, indent=2))

    finally:
        # 4. 关闭 TaskManager（带 MCP 会话和 DB）
        await tm.aclose()


if __name__ == "__main__":
    asyncio.run(main())
