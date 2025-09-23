# test_init_task_manager_async.py
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from pprint import pprint
from mediagent.paths import in_data, in_mediagent

# ======== 需要你自己填写的变量（用绝对路径更稳）========
PUBLIC_DATASETS_ROOT = in_data("files", "public")     # 例如：r"D:\datasets\public"
WORKSPACE_ROOT       = in_data("files", "private")    # 例如：r"D:\projects\MediAgent\workspace"
DATABASE_FILE        = in_data("db", "app.sqlite3")   # 例如：r"D:\projects\MediAgent\data\app.sqlite3" (必须已存在)
MCPSERVER_FILE       = in_mediagent("mcp_server_tools", "mcp_server.py")  # 例如：r"...\mcp_server.py" (必须已存在)

# ======== 导入你的 AsyncTaskManager 类 ========
try:
    # 按你的工程实际路径修改这一行
    from mediagent.modules.task_manager import AsyncTaskManager
except Exception as e:
    print("[FATAL] 无法导入 AsyncTaskManager，请检查模块路径。")
    print("示例：from mediagent.task_manager import AsyncTaskManager")
    print("错误信息：", e)
    sys.exit(1)


def check_path(label: str, p: str | Path) -> Path:
    path = Path(p).expanduser().resolve()
    print(f"[check] {label}: {path}")
    return path


async def main():
    # 0) 基础输入检查（便于尽早发现路径问题）
    if not DATABASE_FILE or not Path(DATABASE_FILE).exists():
        print("[FATAL] 请正确填写 DATABASE_FILE（必须已存在的 sqlite 文件）。")
        return
    if not MCPSERVER_FILE or not Path(MCPSERVER_FILE).exists():
        print("[FATAL] 请正确填写 MCPSERVER_FILE（必须已存在的 mcp 服务器脚本）。")
        return

    pub_root = check_path("public_datasets_source_root", PUBLIC_DATASETS_ROOT) if PUBLIC_DATASETS_ROOT else None
    ws_root  = check_path("workspace_root", WORKSPACE_ROOT) if WORKSPACE_ROOT else None
    db_path  = check_path("database_file", DATABASE_FILE)
    mcp_path = check_path("mcpserver_file", MCPSERVER_FILE)

    print("\n[step] 开始执行异步初始化…\n")

    tm = None
    try:
        tm = AsyncTaskManager(
            public_datasets_source_root=pub_root or ".",
            workspace_root=ws_root or ".",
            database_file=db_path,
            mcpserver_file=mcp_path,
        )
        await tm.astart()
        print("[ok] AsyncTaskManager 启动成功。")

        # 1) MCP 工具列表（验证会话就绪）
        tools = await tm.list_tools()
        print(f"[check] 已加载工具数量：{len(tools)}")
        if tools:
            print("[preview] 工具名（最多列出前10个）：")
            for name in [t["name"] for t in tools][:10]:
                print("  -", name)

        # 2) 数据库连通性与简要结构探测（通过底层同步实例执行到线程池）
        async def _peek_tables():
            def _run():
                cur = tm.sync.db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 10;"
                )
                return [r[0] for r in cur.fetchall()]
            return await asyncio.to_thread(_run)

        try:
            tables = await _peek_tables()
            print(f"[check] 数据库连接正常，示例表：{tables or '（未发现表，若你还没建表可以忽略）'}")
        except Exception as e:
            print("[warn] 数据库简单查询失败，但连接已建立。错误：", repr(e))

        # 3) 队列与运行状态（通过底层同步实例读取）
        async def _peek_runtime():
            def _run():
                return tm.sync.task_queue.empty(), tm.sync.task_running
            return await asyncio.to_thread(_run)

        is_empty, running = await _peek_runtime()
        print(f"[check] task_queue 为空：{is_empty}")
        print(f"[check] task_running = {running}")

        print("\n[RESULT] 异步版本初始化路径、DB 连接、MCP 会话、工具加载均已完成。")

    except Exception as e:
        print("\n[ERROR] 初始化失败：", repr(e))
    finally:
        if tm is not None:
            try:
                await tm.aclose()
                print("[cleanup] 资源释放完成。")
            except Exception as e:
                print("[cleanup-warn] 释放资源时出错：", repr(e))


if __name__ == "__main__":
    asyncio.run(main())
