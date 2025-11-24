# mcp_test_train_hiomics.py
# 直接对接 MCP server（stdio）测试 train_hiomics_pipeline

from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ===========================
# 你需要改的 3 个地方
# ===========================

# 1) mcp_server.py 的路径（Windows 路径）
SERVER = Path(r"D:\projects\MediAgent2\src\server_new\mediagent\mcp_server_tools\mcp_server.py")

# 2) 训练数据集顶层目录列表（Windows 路径）
TRAIN_DATASETS_WIN = [
    r"D:\projects\MediAgent2\src\server_new\data\files\private\7272895950\dataset\CMU",
    r"D:\projects\MediAgent2\src\server_new\data\files\private\7272895950\dataset\GDPH",
]

# 3) out_dir（Windows 路径），随便给一个空目录用于测试
OUT_DIR_WIN = r"D:\hio_test"


# ===========================
# MCP 调用辅助
# ===========================

def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


async def call_tool(sess: ClientSession, name: str, **kwargs) -> Dict[str, Any]:
    """兼容 MCP TextContent 返回"""
    result = await sess.call_tool(name, kwargs)
    content = getattr(result, "content", None) or []
    # FastMCP 通常在 content 里塞一个 TextContent
    # 取第一个能解析成 json 的文本
    for part in content:
        text = getattr(part, "text", None)
        if not text:
            continue
        try:
            return json.loads(text)
        except Exception:
            # 某些工具直接返回纯文本
            return {"raw_text": text}
    # 兜底：如果 result 直接是 dict
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}


async def poll_until_done(
    sess: ClientSession,
    run_id: str,
    poll_interval: float = 0.5,
    tail_lines: int = 50,
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
            # 只保留最后 tail_lines 行
            if len(last_items) > tail_lines:
                last_items = last_items[-tail_lines:]

            # 实时打印新日志
            for it in items:
                line = it.get("line", "")
                if line:
                    print(line, end="" if line.endswith("\n") else "\n")

        status = await call_tool(sess, "get_status", run_id=run_id)
        if "error" in status:
            print("[get_status error]", status["error"])
            break

        if status.get("done", False):
            return {
                "status": status,
                "last_items": last_items,
            }

        await asyncio.sleep(poll_interval)


async def main():
    assert SERVER.exists(), f"SERVER not found: {SERVER}"

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

            # 3) call train tool
            print("\n=== train_hiomics_pipeline call ===")
            train_res = await call_tool(
                sess,
                "train_hiomics_pipeline",
                train_datasets=TRAIN_DATASETS_WIN,
                out_dir=OUT_DIR_WIN,
            )
            print(pretty(train_res))

            if "error" in train_res:
                print("\n[train start error]", train_res["error"])
                return

            run_id = train_res["run_id"]
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
