#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tm_test_dataset_convert_ref_debug.py
- 使用 `$ref` + dataset_id=8173837876 测试 convert_dicom_to_nifti
- 在提交任务前，先在测试脚本内“模拟解析”所有 $ref，并打印解析结果（最终路径）
"""

from __future__ import annotations

import asyncio
import time
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any

# ======== 路径 & AsyncTaskManager 引入（根据你目前工程结构自适应） ========
try:
    from src.server_new.mediagent.paths import in_data, in_mediagent
except ImportError:
    from mediagent.paths import in_data, in_mediagent

try:
    from src.server_new.mediagent.modules.tm_test import AsyncTaskManager
except ImportError:
    from mediagent.modules.tm_test import AsyncTaskManager


# ======== 常量配置（与你之前的 e2e 脚本保持一致） ========
PUBLIC_DATASETS_SOURCE_ROOT = in_data("files")
WORKSPACE_ROOT              = in_data("files", "private")
DATABASE_FILE               = in_data("db", "app.sqlite3")
MCP_SERVER_FILE             = in_mediagent("mcp_server_tools", "mcp_server.py")

USER_UID = "7272895950"          # 按需修改
DATASET_ID_FOR_TEST = 8173837876 # 你要测试的数据集 id


# ======== 基础工具函数 ========
def ensure_dirs():
    PUBLIC_DATASETS_SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def open_ro_conn(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ======== 构造 steps（使用 $ref 版本） ========
def build_steps_with_ref():
    """
    构造一个只有 1 个 step 的任务，直接对数据集 8173837876 做 DICOM → NIfTI 转换。

    参数结构对齐你之前给我的示例：
    {
      "step_number": 1,
      "tool_name": "convert_dicom_to_nifti",
      "args": {
        "in_dir": {
          "$ref": {
            "kind": "dataset",
            "id": 8173837876,
            "relative": "0_DICOM"
          }
        }
      }
    }
    """
    return [
        {
            "step_number": 1,
            "tool_name": "convert_dicom_to_nifti",
            "args": {
                "in_dir": {
                    "$ref": {
                        "kind": "dataset",
                        "id": DATASET_ID_FOR_TEST,
                        # 如果不需要 0_DICOM 这层子目录，你改成 None 或直接删掉这个键
                        "relative": "0_DICOM"
                    }
                }
            },
        }
    ]


# ======== 测试脚本内：模拟解析 $ref ========
def debug_lookup_dataset_root(
    conn: sqlite3.Connection,
    dataset_id: int,
) -> Optional[Path]:
    """
    直接访问 dataset_catalog 表，模拟 TaskManager 对 dataset 的解析：
    - 查 id = dataset_id 的记录
    - 取 data_path
    - 返回 PUBLIC_DATASETS_SOURCE_ROOT / data_path
    """
    row = conn.execute(
        "SELECT id, user_id, has_data, data_path "
        "FROM dataset_catalog WHERE id = ? LIMIT 1",
        (dataset_id,),
    ).fetchone()

    if not row:
        print(f"[debug] dataset_catalog 中未找到 id={dataset_id}")
        return None

    user_id = row["user_id"]
    has_data = row["has_data"]
    data_path = row["data_path"]

    print(
        f"[debug] dataset id={dataset_id} -> "
        f"user_id={user_id}, has_data={has_data}, data_path={data_path}"
    )

    if not data_path:
        print(f"[debug] data_path 为空，无法解析目录")
        return None

    base = (PUBLIC_DATASETS_SOURCE_ROOT / str(data_path)).expanduser().resolve()
    print(f"[debug] dataset 根目录解析为: {base} (exists={base.exists()}, is_dir={base.is_dir()})")
    return base if base.exists() and base.is_dir() else None


def debug_resolve_ref_value(
    conn: sqlite3.Connection,
    value: Any,
) -> Any:
    """
    在测试脚本里模拟解析单个值：
    - 若是 {$ref: {...}}，根据 kind/id/relative 解析成真实路径
    - 若是 list/dict，递归解析
    - 否则原样返回
    """
    # 1) 非 dict/list，直接返回
    if not isinstance(value, (dict, list)):
        return value

    # 2) list：递归
    if isinstance(value, list):
        return [debug_resolve_ref_value(conn, v) for v in value]

    # 3) dict：可能是 {$ref: ...}，也可能是普通 dict
    if "$ref" in value and isinstance(value["$ref"], dict):
        ref_obj = value["$ref"]
        kind = ref_obj.get("kind")
        # dataset / job_output / config 这里只实现 dataset，其它先按“未实现”打印出来
        if kind == "dataset":
            ds_id_raw = ref_obj.get("id")
            try:
                ds_id = int(ds_id_raw)
            except Exception:
                print(f"[debug] dataset.$ref 中 id 非整数: {ds_id_raw!r}")
                return value

            base = debug_lookup_dataset_root(conn, ds_id)
            if base is None:
                return value

            rel = ref_obj.get("relative")
            if rel is None:
                final = base
            else:
                final = (base / str(rel)).resolve()
            print(f"[debug] dataset-ref 解析结果: kind=dataset id={ds_id} relative={rel!r} -> {final} (exists={final.exists()})")
            return str(final)

        else:
            # 其它 kind 暂时只打印出来，不做解析
            print(f"[debug] 暂不支持的 $ref.kind={kind!r}，保持原样: {value}")
            return value

    # 普通 dict：递归解析其键值
    out = {}
    for k, v in value.items():
        out[k] = debug_resolve_ref_value(conn, v)
    return out


def debug_resolve_args_for_step(
    conn: sqlite3.Connection,
    step: Dict[str, Any],
) -> Dict[str, Any]:
    """
    对单个 step 的 args 做完整解析，返回“解析后”的 args。
    同时在控制台打印解析过程。
    """
    tool_name = step.get("tool_name")
    args = step.get("args") or {}
    print(f"\n[debug] === 解析 step#{step.get('step_number')} tool={tool_name} 的 args ===")
    print("[debug] 原始 args:")
    print(json.dumps(args, ensure_ascii=False, indent=2))

    resolved_args = debug_resolve_ref_value(conn, args)

    print("\n[debug] 解析后的 args:")
    print(json.dumps(resolved_args, ensure_ascii=False, indent=2))
    print("[debug] === 解析结束 ===\n")
    return resolved_args


# ======== DB 异步封装（与原 e2e 测试保持一致） ========
async def db_fetchone(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...],
) -> Optional[sqlite3.Row]:
    def _run():
        cur = conn.execute(sql, params)
        return cur.fetchone()
    return await asyncio.to_thread(_run)


async def db_fetchall(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    def _run():
        cur = conn.execute(sql, params)
        return cur.fetchall()
    return await asyncio.to_thread(_run)


# ======== 打印任务快照 ========
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
        (task_uid,),
    )
    for s in rows:
        print(
            f"       └─ step#{s['step_number']} uid={s['step_uid']} "
            f"status={s['status']} tool={s['tool_name']} run_id={s['run_id']}"
        )


# ======== 推断当前 step 的 out_dir 路径 ========
async def expected_out_dir(
    conn: sqlite3.Connection,
    workspace_root: Path,
    task_uid: str,
) -> Optional[Path]:
    row = await db_fetchone(
        conn,
        "SELECT user_uid, current_step_uid FROM tasks WHERE task_uid=?",
        (task_uid,),
    )
    if not row or not row["current_step_uid"]:
        return None
    user_uid = str(row["user_uid"])
    step_uid = str(row["current_step_uid"])
    return workspace_root / user_uid / "workspace" / task_uid / step_uid


# ======== 拉取日志（poll_logs） ========
async def stream_logs_while_running(
    tm: AsyncTaskManager,
    conn_ro: sqlite3.Connection,
    task_uid: str,
    run_offsets: Dict[str, int],
):
    row = await db_fetchone(
        conn_ro,
        "SELECT step_uid, step_number, run_id FROM steps "
        "WHERE task_uid=? AND status='running' "
        "ORDER BY rowid DESC LIMIT 1",
        (task_uid,),
    )
    if not row:
        return
    run_id = row["run_id"]
    if not run_id:
        return

    offset = run_offsets.get(run_id, 0)
    try:
        res = await tm.call_tool("poll_logs", {"run_id": run_id, "offset": offset})
        if not isinstance(res, dict):
            return
        items = res.get("items", []) or []
        for it in items:
            line = it.get("line") if isinstance(it, dict) else str(it)
            if line is not None:
                print(f"[log][run={run_id}] {line}")
        run_offsets[run_id] = res.get("offset", offset)
    except Exception:
        pass


# ======== 等待任务结束 ========
async def wait_until_done_with_logs(
    tm: AsyncTaskManager,
    db_path: Path,
    task_uid: str,
    poll: float = 0.25,
    timeout: Optional[float] = None,
):
    conn_ro = open_ro_conn(db_path)
    try:
        t0 = time.time()
        last_status = None
        run_offsets: Dict[str, int] = {}

        await asyncio.sleep(1.0)  # 给 TaskManager 主循环一些时间

        while True:
            await stream_logs_while_running(tm, conn_ro, task_uid, run_offsets)

            row = await db_fetchone(
                conn_ro,
                "SELECT status FROM tasks WHERE task_uid=?",
                (task_uid,),
            )
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
                print(f"[probe] expected out_dir: {out_dir} exists={exists}")

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


# ======== 主流程 ========
async def main():
    ensure_dirs()

    # 先在测试脚本内解析一次 $ref，看看 dataset_id + relative 实际落到哪个目录
    conn_ro = open_ro_conn(DATABASE_FILE)
    try:
        steps = build_steps_with_ref()
        print("[info] 原始 steps（含 $ref）:")
        print(json.dumps(steps, ensure_ascii=False, indent=2))

        # 只解析第一个 step 的 args，打印结果
        debug_resolve_args_for_step(conn_ro, steps[0])
    finally:
        conn_ro.close()

    tm = AsyncTaskManager(
        public_datasets_source_root=PUBLIC_DATASETS_SOURCE_ROOT,
        workspace_root=WORKSPACE_ROOT,
        database_file=DATABASE_FILE,
        mcpserver_file=MCP_SERVER_FILE,
    )
    await tm.astart()
    print("[ok] AsyncTaskManager 启动成功。")

    created = await tm.create_task(
        user_uid=USER_UID,
        steps=steps,
        check_tools=True,
    )
    print("[create_task] ->")
    print(json.dumps(created, ensure_ascii=False, indent=2))
    task_uid = created["task_uid"]

    await wait_until_done_with_logs(tm, DATABASE_FILE, task_uid, poll=0.25, timeout=None)

    await tm.aclose()
    print("[cleanup] AsyncTaskManager 关闭完成。")


if __name__ == "__main__":
    asyncio.run(main())
