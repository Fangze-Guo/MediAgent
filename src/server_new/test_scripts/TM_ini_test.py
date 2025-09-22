# test_init_task_manager.py
from __future__ import annotations
import os
import sys
from pathlib import Path
from pprint import pprint
from mediagent.paths import in_data
from mediagent.paths import in_mediagent

# ======== 需要你自己填写的变量（用绝对路径更稳）========
PUBLIC_DATASETS_ROOT = in_data("files","public")   # 例如：r"D:\datasets\public"
WORKSPACE_ROOT       = in_data("files","private")   # 例如：r"D:\projects\MediAgent\workspace"
DATABASE_FILE        = in_data("db","app.sqlite3")   # 例如：r"D:\projects\MediAgent\data\app.sqlite3"  (必须已存在)
MCPSERVER_FILE       = in_mediagent("mcp_server_tools","mcp_server.py")   # 例如：r"D:\projects\MediAgent\server\mcp_server.py"  (必须已存在)

# ======== 导入你的 TaskManager 类 ========
try:
    # 按你的工程实际路径修改这一行
    from mediagent.modules.task_manager import TaskManager
except Exception as e:
    print("[FATAL] 无法导入 TaskManager，请检查模块路径。")
    print("示例：from mediagent.task_manager import TaskManager")
    print("错误信息：", e)
    sys.exit(1)


def check_path(label: str, p: str) -> Path:
    path = Path(p).expanduser().resolve()
    print(f"[check] {label}: {path}")
    return path


def main():
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

    print("\n[step] 开始执行初始化…\n")

    mgr = None
    try:
        mgr = TaskManager(
            public_datasets_source_root=pub_root or ".",
            workspace_root=ws_root or ".",
            database_file=db_path,
            mcpserver_file=mcp_path,
        )
        print("[ok] 任务管理器初始化成功。")

        # 1) MCP 服务器进程情况
        proc = getattr(mgr, "_mcp_proc", None)
        if proc is None:
            print("[warn] 未找到 _mcp_proc 句柄。")
        else:
            alive = (proc.poll() is None)
            print(f"[check] MCP 进程 PID={getattr(proc, 'pid', 'N/A')}, alive={alive}")

        # 2) MCP 工具列表
        tools_index = getattr(mgr, "tools_index", {})
        print(f"[check] 已加载工具数量：{len(tools_index)}")
        if tools_index:
            print("[preview] 工具名（最多列出前10个）：")
            for name in list(tools_index.keys())[:10]:
                print("  -", name)

        # 3) 数据库连通性与简要结构探测（不会修改你的库）
        try:
            cur = mgr.db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 10;")
            tables = [r[0] for r in cur.fetchall()]
            print(f"[check] 数据库连接正常，示例表：{tables or '（未发现表，若你还没建表可以忽略）'}")
        except Exception as e:
            print("[warn] 数据库简单查询失败，但连接已建立。错误：", repr(e))

        # 4) 队列与运行状态
        print(f"[check] task_queue 为空：{mgr.task_queue.empty()}")
        print(f"[check] task_running = {mgr.task_running}")

        print("\n[RESULT] 初始化路径、DB 连接、MCP 启动、工具加载均已完成。")

    except Exception as e:
        print("\n[ERROR] 初始化失败：", repr(e))
    finally:
        # 简单清理，避免子进程残留锁定
        if mgr is not None:
            try:
                mgr.close()
                print("[cleanup] 资源释放完成。")
            except Exception as e:
                print("[cleanup-warn] 释放资源时出错：", repr(e))


if __name__ == "__main__":
    main()
