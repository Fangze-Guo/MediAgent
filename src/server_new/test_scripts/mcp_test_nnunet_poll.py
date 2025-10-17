# mcp_test_nnunet_poll.py —— 极简静默输出版（仅打印日志行；保留超时重试但不提示）
import asyncio, sys, json
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

HERE   = Path(__file__).resolve().parent
SERVER = HERE.parent / "mediagent" / "mcp_server_tools" / "mcp_server.py"
CWD    = SERVER.parent

POLL_TIMEOUT_SEC = 5.0
STATUS_TIMEOUT_SEC = 5.0

def parse_json(result):
    picked = None
    fallback_text = None
    try:
        parts = getattr(result, "content", []) or []
        for part in parts:
            if isinstance(part, TextContent):
                txt = part.text
                fallback_text = txt
                try:
                    obj = json.loads(txt)
                    if isinstance(obj, dict) and ("items" in obj or "run_id" in obj or "offset" in obj):
                        return obj
                    if picked is None and isinstance(obj, dict):
                        picked = obj
                except Exception:
                    continue
    except Exception:
        pass
    if picked is not None:
        return picked
    if fallback_text is not None:
        return {"text": fallback_text}
    return {}

async def call_tool_with_timeout(session: ClientSession, tool: str, payload: dict, timeout: float):
    try:
        return await asyncio.wait_for(session.call_tool(tool, payload), timeout=timeout)
    except Exception:
        return None  # 静默：不输出任何提示

async def tail(session, run_id):
    offset = 0
    empty_rounds = 0
    MAX_EMPTY_ROUNDS_BEFORE_TAIL = 20

    last_seq_printed = -1  # 新增：按 seq 去重

    while True:
        # (A) 拉取增量
        r = await call_tool_with_timeout(session, "poll_logs", {"run_id": run_id, "offset": offset}, POLL_TIMEOUT_SEC)
        if r is None:
            await asyncio.sleep(0.25)
            continue

        obj = parse_json(r)
        items = obj.get("items", []) or []
        new_offset = obj.get("offset", offset)

        if items:
            for it in items:
                seq = it.get("seq")
                line = it.get("line")
                # 仅打印“未打印过”的新序号；没有 seq 的行全部忽略（可改成打印）
                if isinstance(seq, int) and isinstance(line, str) and line:
                    if seq > last_seq_printed:
                        print(line, flush=True)
                        last_seq_printed = seq
            offset = new_offset
            empty_rounds = 0
        else:
            empty_rounds += 1

        # (B) 可选：关闭“从末尾 tail”，或把阈值调大
        # 建议先注释掉以下整段，以彻底杜绝回退窗口导致的重复。
        # 如果你一定要保留这一招，seq 去重会保证不重复。
        # if empty_rounds >= MAX_EMPTY_ROUNDS_BEFORE_TAIL:
        #     r_tail = await call_tool_with_timeout(session, "poll_logs", {"run_id": run_id, "offset": -1}, POLL_TIMEOUT_SEC)
        #     if r_tail is not None:
        #         obj_tail = parse_json(r_tail)
        #         tail_items = obj_tail.get("items", []) or []
        #         tail_offset = obj_tail.get("offset", offset)
        #         if tail_items:
        #             for it in tail_items:
        #                 seq = it.get("seq")
        #                 line = it.get("line")
        #                 if isinstance(seq, int) and isinstance(line, str) and line and seq > last_seq_printed:
        #                     print(line, flush=True)
        #                     last_seq_printed = seq
        #             offset = tail_offset
        #         empty_rounds = 0

        # (C) 查询状态（静默）
        s_resp = await call_tool_with_timeout(session, "get_status", {"run_id": run_id}, STATUS_TIMEOUT_SEC)
        if s_resp is not None:
            s = parse_json(s_resp)
            if bool(s.get("done")):
                r2 = await call_tool_with_timeout(session, "poll_logs", {"run_id": run_id, "offset": offset}, POLL_TIMEOUT_SEC)
                if r2 is not None:
                    o2 = parse_json(r2)
                    for it in o2.get("items", []) or []:
                        seq = it.get("seq")
                        line = it.get("line")
                        if isinstance(seq, int) and isinstance(line, str) and line and seq > last_seq_printed:
                            print(line, flush=True)
                            last_seq_printed = seq
                break

        await asyncio.sleep(0.25)


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        cwd=str(CWD),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 静默启动，不打印任何启动信息
            r = await session.call_tool("start_nnunet_predict", {
                "in_dir":  r"D:\mcp_test\reg_out",
                "out_dir": r"D:\mcp_test\nnunet_out",
            })
            j = parse_json(r)
            run_id = j.get("run_id")
            if not run_id:
                # 失败走 stderr，避免干扰标准输出日志
                sys.stderr.write("ERROR: start_nnunet_predict failed: no run_id\n")
                sys.exit(1)

            await tail(session, run_id)

if __name__ == "__main__":
    asyncio.run(main())
