# mcp_test_test_hiomics.py
# 直接对接 MCP server（stdio）测试 test_hiomics_pipeline

from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ===========================
# 你需要改的地方（仿照训练测试脚本）
# ===========================

# 1) mcp_server.py 的路径（Windows 路径）
SERVER = Path(r"D:\projects\MediAgent2\src\server_new\mediagent\mcp_server_tools\mcp_server.py")

# 2) 训练产物目录（Windows 路径）
#    也就是你 train_hiomics_pipeline 输出的 out_dir（TrainTask task_dir）
TRAIN_TASK_DIR_WIN = r"D:\hio_test\ISPY2"   # <- 改成你的真实训练输出目录

# 3) 待测试数据集顶层目录列表（Windows 路径）
TEST_DATASETS_WIN = [
    r"D:\projects\MediAgent2\src\server_new\data\files\private\7272895950\dataset\XJ",
    r"D:\projects\MediAgent2\src\server_new\data\files\private\7272895950\dataset\YN",
]

# 4) out_dir（Windows 路径），随便给一个空目录用于测试
OUT_DIR_WIN = r"D:\hio_test_out"


# ===========================
# MCP 调用辅助（和训练测试脚本一致）
# ===========================

def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


async def call_tool(sess: ClientSession, name: str, **kwargs) -> Dict[str, Any]:
    """兼容 MCP TextContent 返回"""
    result = await sess.call_tool(name, kwargs)
    content = getattr(result, "content", None) or []
    for part in content:
        text = getattr(part, "text", None)
        if not text:
            continue
        try:
            return json.loads(text)
        except Exception:
            return {"raw_text": text}
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}


async def poll_until_done(
    sess: ClientSession,
    run_id: str,
    poll_interval: float = 0.5,
    tail_lines: int = 80,
) -> Dict[str, Any]:
    """循环 poll_logs/get_status 直到 done"""
    offset = -1  # 从尾部追
    last_items: List[Dict[str, Any]] = []

    while True:
        logs = await call_tool(sess, "poll_logs", run_id=run_id, offset=offset)
        if "error" in logs:
            print("[poll_logs error]", logs["error"])
            break

        items = logs.get("items", []) or []
        offset = logs.get("offset", offset)

        if items:
            last_items.extend(items)
            if len(last_items) > tail_lines:
                last_items = last_items[-tail_lines:]

            for it in items:
                line = it.get("line", "")
                if line:
                    print(line, end="" if line.endswith("\n") else "\n")

        status = await call_tool(sess, "get_status", run_id=run_id)
        if "error" in status:
            print("[get_status error]", status["error"])
            break

        if status.get("done", False):
            return {"status": status, "last_items": last_items}

        await asyncio.sleep(poll_interval)


# ===========================
# 主测试流程
# ===========================

async def main():
    assert SERVER.exists(), f"SERVER not found: {SERVER}"
    assert Path(TRAIN_TASK_DIR_WIN).exists(), f"TRAIN_TASK_DIR not found: {TRAIN_TASK_DIR_WIN}"

    server_params = StdioServerParameters(
        command="python",
        args=[str(SERVER)],
        cwd=str(SERVER.parent),
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as sess:
            await sess.initialize()

            # 1) ping
            print("\n=== ping ===")
            ping_res = await call_tool(sess, "ping")
            print(pretty(ping_res))

            # 2) list_job_tools
            print("\n=== list_job_tools ===")
            tools_res = await call_tool(sess, "list_job_tools")
            print(pretty(tools_res))

            # 3) call test tool
            print("\n=== test_hiomics_pipeline call ===")
            test_res = await call_tool(
                sess,
                "test_hiomics_pipeline",
                train_task_dir=TRAIN_TASK_DIR_WIN,
                test_datasets=TEST_DATASETS_WIN,
                out_dir=OUT_DIR_WIN,
            )
            print(pretty(test_res))

            if "error" in test_res:
                print("\n[test start error]", test_res["error"])
                return

            run_id = test_res["run_id"]
            print(f"\n[run_id] {run_id}")

            # 4) poll logs until done
            print("\n=== polling logs ===")
            final = await poll_until_done(sess, run_id=run_id)

            status = final.get("status", {})
            last_items = final.get("last_items", [])

            print("\n=== FINAL STATUS ===")
            print(pretty(status))

            print("\n=== LAST LOG TAIL ===")
            for it in last_items:
                line = it.get("line", "")
                if line:
                    print(line, end="" if line.endswith("\n") else "\n")

            exit_code = status.get("exit_code")
            print(f"\n[exit_code] {exit_code}")


if __name__ == "__main__":
    asyncio.run(main())
