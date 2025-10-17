# mcp_test_poll.py —— 放在 server_new/test_scripts/ 下
import asyncio, sys, json, time
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

HERE   = Path(__file__).resolve().parent
SERVER = HERE.parent / "mediagent" / "mcp_server_tools" / "mcp_server.py"
CWD    = SERVER.parent

# === 新增：超时阈值（秒） ===
POLL_TIMEOUT_SEC = 5.0
STATUS_TIMEOUT_SEC = 5.0

def parse_json(result):
    """
    更健壮的解析：
    - 遍历所有 TextContent 段，找出第一个能 json.loads 的；
    - 优先返回包含 'items' 或 'run_id' 的对象；
    - 若都不是 JSON，最后退回 {'text': <最后一个文本段>}。
    """
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
                    # 优先包含关键信息的对象
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

# === 新增：带超时的 call_tool 包装（静默失败，下一轮重试） ===
async def call_tool_with_timeout(session: ClientSession, tool: str, payload: dict, timeout: float):
    try:
        return await asyncio.wait_for(session.call_tool(tool, payload), timeout=timeout)
    except Exception:
        return None  # 超时或异常：返回 None，调用方按原有循环逻辑重试

async def tail(session, run_id):
    """
    从 0 开始增量读取；如长时间无新增，自动触发一次“从末尾追新”（offset=-1）。
    加入 seq 去重，避免重复行。
    """
    offset = 0
    empty_rounds = 0
    MAX_EMPTY_ROUNDS_BEFORE_TAIL = 20  # ~5 秒（配合下面 sleep 0.25s）

    last_seq_printed = -1  # 关键：记录最后一次已输出的 seq

    while True:
        # 常规增量拉取（加超时）
        r = await call_tool_with_timeout(
            session, "poll_logs", {"run_id": run_id, "offset": offset, "limit": 200}, POLL_TIMEOUT_SEC
        )
        if r is None:
            await asyncio.sleep(0.25)
            continue
        obj = parse_json(r)

        items = obj.get("items", [])
        new_offset = obj.get("offset", offset)

        if items:
            for it in items:
                seq = it.get("seq")
                line = it.get("line")
                # 仅打印“未打印过”的新序号
                if isinstance(seq, int) and seq > last_seq_printed:
                    if line is None:
                        print(f"[log] seq={seq} off={new_offset} {json.dumps(it, ensure_ascii=False)}")
                    else:
                        print(f"[log] seq={seq} off={new_offset} {line}")
                    last_seq_printed = seq
            offset = new_offset
            empty_rounds = 0
        else:
            empty_rounds += 1
            # 连续多轮无新增：触发一次“从当前末尾追新”（加超时）
            if empty_rounds >= MAX_EMPTY_ROUNDS_BEFORE_TAIL:
                r_tail = await call_tool_with_timeout(
                    session, "poll_logs", {"run_id": run_id, "offset": -1}, POLL_TIMEOUT_SEC
                )
                if r_tail is not None:
                    obj_tail = parse_json(r_tail)
                    tail_items = obj_tail.get("items", [])
                    tail_offset = obj_tail.get("offset", offset)
                    if tail_items:
                        for it in tail_items:
                            seq = it.get("seq")
                            line = it.get("line")
                            if isinstance(seq, int) and seq > last_seq_printed:
                                if line is None:
                                    print(f"[log] seq={seq} off={tail_offset} {json.dumps(it, ensure_ascii=False)}")
                                else:
                                    print(f"[log] seq={seq} off={tail_offset} {line}")
                                last_seq_printed = seq
                        offset = tail_offset
                    empty_rounds = 0  # 重置

        # 查询一次状态（加超时）
        s_resp = await call_tool_with_timeout(session, "get_status", {"run_id": run_id}, STATUS_TIMEOUT_SEC)
        if s_resp is not None:
            s = parse_json(s_resp)
            if s.get("done"):
                print(f"[done] exit_code={s.get('exit_code')}")
                break

        await asyncio.sleep(0.25)


async def main():
    out_root = HERE.parent / "data" / "test" / "stream_test"
    s1 = out_root / "task_demo" / "s1_ingest"
    s2 = out_root / "task_demo" / "s2_pre"
    s3 = out_root / "task_demo" / "s3_train"
    s4 = out_root / "task_demo" / "s4_eval"

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        cwd=str(CWD),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # # 1) ingest
            # r = await session.call_tool("start_ingest", {"in_dir": "dummy://source", "out_dir": str(s1)})
            # j = parse_json(r); run_id = j["run_id"]; print("ingest run:", run_id)
            # await tail(session, run_id)
            #
            # # 2) preprocess
            # r = await session.call_tool("start_preprocess", {"in_dir": str(s1), "out_dir": str(s2)})
            # j = parse_json(r); run_id = j["run_id"]; print("preprocess run:", run_id)
            # await tail(session, run_id)
            #
            # # 3) train
            # r = await session.call_tool("start_train", {"in_dir": str(s2), "out_dir": str(s3), "epochs": 3})
            # j = parse_json(r); run_id = j["run_id"]; print("train run:", run_id)
            # await tail(session, run_id)
            #
            # # 4) evaluate
            # r = await session.call_tool("start_evaluate", {"in_dir": str(s3), "out_dir": str(s4)})
            # j = parse_json(r); run_id = j["run_id"]; print("evaluate run:", run_id)
            # await tail(session, run_id)

            # r= await session.call_tool("convert_dicom_to_nifti",{"in_dir": r"D:\mcp_test\0_DICOM", "out_dir": r"D:\mcp_test\dicom2nii"})
            # j = parse_json(r)
            # run_id = j["run_id"]
            # print("ingest run:", run_id)
            # await tail(session, run_id)

            # r = await session.call_tool("register_deeds", {
            #     "in_dir": r"D:\mcp_test\dicom2nii",
            #     "out_dir": r"D:\mcp_test\reg_out",
            # })
            # j = parse_json(r)
            # print("SERVER RESP:", j)  # ← 关键打印
            # run_id = j.get("run_id")
            # if not run_id:
            #     raise RuntimeError(f"tool failed, no run_id. server returned: {j}")
            # print("register run:", run_id)
            # await tail(session, run_id)

            # ------------- 5) nnU-Net 批量分割：复制 reg_out → 在拷贝里生成 C2_mask.nii.gz -------------
            r = await session.call_tool("start_nnunet_predict", {
                "in_dir":  r"D:\mcp_test\reg_out",      # 上一步 register_deeds 的输出
                "out_dir": r"D:\mcp_test\nnunet_out",   # 本步输出目录（会先整体复制 in_dir）
            })
            j = parse_json(r)
            print("SERVER RESP (nnunet):", j)
            run_id = j.get("run_id")
            if not run_id:
                raise RuntimeError(f"tool failed, no run_id. server returned: {j}")
            print("nnunet run:", run_id)
            await tail(session, run_id)

if __name__ == "__main__":
    asyncio.run(main())
