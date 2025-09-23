# tm_e2e_test_async.py —— 异步版 E2E 测试（适配 AsyncTaskManager）
import asyncio
import time
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any

from mediagent.paths import in_data, in_mediagent

# ======== 路径与常量 ========
PUBLIC_DATASETS_SOURCE_ROOT = in_data("files", "public")
WORKSPACE_ROOT              = in_data("files", "private")
DATABASE_FILE               = in_data("db", "app.sqlite3")
MCP_SERVER_FILE             = in_mediagent("mcp_server_tools", "mcp_server.py")

USER_UID                    = "6127016735"
REAL_INPUT_DIR_FOR_DIRECT   = PUBLIC_DATASETS_SOURCE_ROOT

# ======== 导入异步任务管理器 ========
try:
    from mediagent.modules.task_manager import AsyncTaskManager
except Exception as e:
    print("[FATAL] 无法导入 AsyncTaskManager，请检查模块路径。")
    print("示例：from mediagent.modules.task_manager import AsyncTaskManager")
    print("错误信息：", e)
    raise

# ======== 工具函数 ========
def ensure_dirs():
    PUBLIC_DATASETS_SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    REAL_INPUT_DIR_FOR_DIRECT.mkdir(parents=True, exist_ok=True)

def build_steps():
    return [
        {"step_number": 1, "tool_name": "start_ingest",    "source_kind": "direct", "source": str(REAL_INPUT_DIR_FOR_DIRECT), "relative": None, "additional_params": {}},
        {"step_number": 2, "tool_name": "start_preprocess","source_kind": "step",   "source": "1", "relative": None, "additional_params": {}},
        {"step_number": 3, "tool_name": "start_train",     "source_kind": "step",   "source": "2", "relative": None, "additional_params": {"epochs": 3}},
        {"step_number": 4, "tool_name": "start_evaluate",  "source_kind": "step",   "source": "3", "relative": None, "additional_params": {}},
    ]

def open_ro_conn(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- DB 访问（放到线程池，避免阻塞事件循环） ---
async def db_fetchone(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> Optional[sqlite3.Row]:
    def _run():
        cur = conn.execute(sql, params)
        return cur.fetchone()
    return await asyncio.to_thread(_run)

async def db_fetchall(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    def _run():
        cur = conn.execute(sql, params)
        return cur.fetchall()
    return await asyncio.to_thread(_run)

# --- 打印任务快照 ---
async def print_task_snapshot(conn: sqlite3.Connection, task_uid: str):
    row = await db_fetchone(conn, "SELECT * FROM tasks WHERE task_uid=?", (task_uid,))
    if not row:
        print(f"[task] {task_uid} not found")
        return
    print(
        f"[task] uid={task_uid} status={row['status']} "
        f"last={row['last_completed_step']} / total={row['total_steps']} "
        f"cur=({row['current_step_number']},{row['current_step_uid']}) "
        f"failed=({row['failed_step_number']},{row['failed_step_uid']})"
    )
    rows = await db_fetchall(
        conn,
        "SELECT step_number, step_uid, status, tool_name, run_id "
        "FROM steps WHERE task_uid=? ORDER BY step_number ASC, rowid ASC",
        (task_uid,)
    )
    for s in rows:
        print(f"       └─ step#{s['step_number']} uid={s['step_uid']} status={s['status']} tool={s['tool_name']} run_id={s['run_id']}")

# --- 计算当前步骤 out_dir 期望路径 ---
async def expected_out_dir(conn: sqlite3.Connection, workspace_root: Path, task_uid: str) -> Optional[Path]:
    row = await db_fetchone(conn, "SELECT user_uid, current_step_uid FROM tasks WHERE task_uid=?", (task_uid,))
    if not row or not row["current_step_uid"]:
        return None
    user_uid = str(row["user_uid"])
    step_uid = str(row["current_step_uid"])
    return (workspace_root / user_uid / "workspace" / task_uid / step_uid)

# --- 拉流日志（运行中） ---
async def stream_logs_while_running(tm: AsyncTaskManager, conn_ro: sqlite3.Connection, task_uid: str, run_offsets: Dict[str, int]):
    step_row = await db_fetchone(
        conn_ro,
        "SELECT step_uid, step_number, run_id FROM steps WHERE task_uid=? AND status='running' ORDER BY rowid DESC LIMIT 1",
        (task_uid,)
    )
    if not step_row:
        return
    run_id = step_row["run_id"]
    if not run_id:
        return
    offset = run_offsets.get(run_id, 0)
    try:
        res = await tm.call_tool("poll_logs", {"run_id": run_id, "offset": offset})
        if isinstance(res, dict):
            items = res.get("items", []) or []
            for it in items:
                # 兼容 {"line": "..."} 或直接对象
                line = it.get("line") if isinstance(it, dict) else str(it)
                if line is not None:
                    print(f"[log][run={run_id}] {line}")
            new_offset = res.get("offset", offset)
            run_offsets[run_id] = new_offset
    except Exception:
        # demo：忽略日志拉取异常
        pass

# --- 等待任务结束，并持续输出状态与少量日志 ---
async def wait_until_done_with_logs(tm: AsyncTaskManager, db_path: Path, task_uid: str, poll: float = 0.25, timeout: Optional[float] = None):
    conn_ro = open_ro_conn(db_path)
    try:
        t0 = time.time()
        last_status = None
        run_offsets: Dict[str, int] = {}

        # 启动缓冲：给调度线程一次切换周期
        await asyncio.sleep(1.0)

        while True:
            await stream_logs_while_running(tm, conn_ro, task_uid, run_offsets)

            row = await db_fetchone(conn_ro, "SELECT status FROM tasks WHERE task_uid=?", (task_uid,))
            if not row:
                print("[wait] task row missing (exit)")
                return
            status = row["status"]
            if status != last_status:
                await print_task_snapshot(conn_ro, task_uid)
                last_status = status

            out_dir = await expected_out_dir(conn_ro, WORKSPACE_ROOT, task_uid)
            if out_dir:
                exists = await asyncio.to_thread(out_dir.exists)
                print(f"[probe] expected out_dir: {out_dir}  exists={exists}")

            if status in ("succeeded", "failed", "canceled"):
                print(f"[done] task={task_uid} final_status={status}")
                await print_task_snapshot(conn_ro, task_uid)
                return

            if timeout is not None and (time.time() - t0) > timeout:
                print("[wait] timeout reached")
                await print_task_snapshot(conn_ro, task_uid)
                return

            await asyncio.sleep(poll)
    finally:
        conn_ro.close()

# ======== 主流程（异步） ========
async def main():
    ensure_dirs()

    tm = AsyncTaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_SOURCE_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCP_SERVER_FILE,
    )

    await tm.astart()
    print("[ok] AsyncTaskManager 启动成功。")

    # 可选：确认某工具的 schema
    tools = await tm.list_tools()
    for t in tools:
        if t["name"] == "start_ingest":
            print("start_ingest schema:", t.get("inputSchema"))
            break

    steps = build_steps()
    created = await tm.create_task(user_uid=USER_UID, steps=steps, check_tools=True)
    task_uid = created["task_uid"]
    print("[create] ->", created)

    await wait_until_done_with_logs(tm, DATABASE_FILE, task_uid, poll=0.25, timeout=None)

    await tm.aclose()
    print("[cleanup] 资源释放完成。")

if __name__ == "__main__":
    asyncio.run(main())
