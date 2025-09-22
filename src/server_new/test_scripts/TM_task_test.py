# tm_e2e_test.py —— 测试脚本（加了 out_dir 探针与启动缓冲）
import sys
import time
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict

from mediagent.paths import in_data, in_mediagent
from mediagent.modules.task_manager import TaskManager

PUBLIC_DATASETS_SOURCE_ROOT = in_data("files", "public")
WORKSPACE_ROOT              = in_data("files", "private")
DATABASE_FILE               = in_data("db", "app.sqlite3")
MCP_SERVER_FILE             = in_mediagent("mcp_server_tools", "mcp_server.py")

USER_UID                    = "6127016735"
REAL_INPUT_DIR_FOR_DIRECT   = PUBLIC_DATASETS_SOURCE_ROOT

def ensure_dirs():
    PUBLIC_DATASETS_SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    REAL_INPUT_DIR_FOR_DIRECT.mkdir(parents=True, exist_ok=True)

def build_steps():
    return [
        {"step_number": 1, "tool_name": "start_ingest",   "source_kind": "direct", "source": str(REAL_INPUT_DIR_FOR_DIRECT), "relative": None, "additional_params": {}},
        {"step_number": 2, "tool_name": "start_preprocess","source_kind": "step",  "source": "1", "relative": None, "additional_params": {}},
        {"step_number": 3, "tool_name": "start_train",    "source_kind": "step",   "source": "2", "relative": None, "additional_params": {"epochs": 3}},
        {"step_number": 4, "tool_name": "start_evaluate", "source_kind": "step",   "source": "3", "relative": None, "additional_params": {}},
    ]

def open_ro_conn(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def print_task_snapshot(conn: sqlite3.Connection, task_uid: str):
    row = conn.execute("SELECT * FROM tasks WHERE task_uid=?", (task_uid,)).fetchone()
    if not row:
        print(f"[task] {task_uid} not found")
        return
    print(
        f"[task] uid={task_uid} status={row['status']} "
        f"last={row['last_completed_step']} / total={row['total_steps']} "
        f"cur=({row['current_step_number']},{row['current_step_uid']}) "
        f"failed=({row['failed_step_number']},{row['failed_step_uid']})"
    )
    cur = conn.execute(
        "SELECT step_number, step_uid, status, tool_name, run_id "
        "FROM steps WHERE task_uid=? ORDER BY step_number ASC, rowid ASC",
        (task_uid,)
    )
    for s in cur.fetchall():
        print(f"       └─ step#{s['step_number']} uid={s['step_uid']} status={s['status']} tool={s['tool_name']} run_id={s['run_id']}")

def expected_out_dir(conn: sqlite3.Connection, workspace_root: Path, task_uid: str) -> Optional[Path]:
    # 根据 tasks.current_step_uid 推断 out_dir：workspace_root/<user_uid>/workspace/<task_uid>/<step_uid>
    row = conn.execute("SELECT user_uid, current_step_uid FROM tasks WHERE task_uid=?", (task_uid,)).fetchone()
    if not row or not row["current_step_uid"]:
        return None
    user_uid = str(row["user_uid"])
    step_uid = str(row["current_step_uid"])
    return (workspace_root / user_uid / "workspace" / task_uid / step_uid)

def stream_logs_while_running(tm: TaskManager, conn_ro: sqlite3.Connection, task_uid: str, run_offsets: Dict[str, int]):
    step_row = conn_ro.execute(
        "SELECT step_uid, step_number, run_id FROM steps WHERE task_uid=? AND status='running' ORDER BY rowid DESC LIMIT 1",
        (task_uid,)
    ).fetchone()
    if not step_row:
        return
    run_id = step_row["run_id"]
    if not run_id:
        return
    offset = run_offsets.get(run_id, 0)
    try:
        res = tm.call_tool("poll_logs", {"run_id": run_id, "offset": offset})
        if isinstance(res, dict):
            items = res.get("items", [])
            for it in items:
                line = it.get("line")
                if line is not None:
                    print(f"[log][run={run_id}] {line}")
            new_offset = res.get("offset", offset)
            run_offsets[run_id] = new_offset
    except Exception:
        pass  # demo：忽略日志拉取异常

def wait_until_done_with_logs(tm: TaskManager, db_path: Path, task_uid: str, poll: float = 0.25, timeout: Optional[float] = None):
    conn_ro = open_ro_conn(db_path)
    try:
        t0 = time.time()
        last_status = None
        run_offsets: Dict[str, int] = {}

        # 启动缓冲：给调度线程一次切换周期
        time.sleep(1.0)

        while True:
            # 实时日志
            stream_logs_while_running(tm, conn_ro, task_uid, run_offsets)

            # 打印状态变化
            row = conn_ro.execute("SELECT status FROM tasks WHERE task_uid=?", (task_uid,)).fetchone()
            if not row:
                print("[wait] task row missing (exit)")
                return
            status = row["status"]
            if status != last_status:
                print_task_snapshot(conn_ro, task_uid)
                last_status = status

            # 探针：当前 out_dir 是否已经创建？
            out_dir = expected_out_dir(conn_ro, WORKSPACE_ROOT, task_uid)
            if out_dir:
                print(f"[probe] expected out_dir: {out_dir}  exists={out_dir.exists()}")

            # 终态
            if status in ("succeeded", "failed", "canceled"):
                print(f"[done] task={task_uid} final_status={status}")
                print_task_snapshot(conn_ro, task_uid)
                return

            if timeout is not None and (time.time() - t0) > timeout:
                print("[wait] timeout reached")
                print_task_snapshot(conn_ro, task_uid)
                return

            time.sleep(poll)
    finally:
        conn_ro.close()

def main():
    ensure_dirs()

    tm = TaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_SOURCE_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCP_SERVER_FILE,
    )

    # 可选：确认 schema
    for t in tm.list_tools():
        if t["name"] == "start_ingest":
            print("start_ingest schema:", t.get("inputSchema"))

    steps = build_steps()
    created = tm.create_task(user_uid=USER_UID, steps=steps, check_tools=True)
    task_uid = created["task_uid"]
    print("[create] ->", created)

    tm.start()
    wait_until_done_with_logs(tm, DATABASE_FILE, task_uid, poll=0.25, timeout=None)
    tm.close()

if __name__ == "__main__":
    main()
