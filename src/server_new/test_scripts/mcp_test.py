# mcp_test_poll.py —— 放在 server_new/test_scripts/ 下
import asyncio, sys, json, time
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

HERE   = Path(__file__).resolve().parent
SERVER = HERE.parent / "mediagent" / "mcp_server_tools" / "mcp_server.py"
CWD    = SERVER.parent

def parse_json(result):
    for part in result.content:
        if isinstance(part, TextContent):
            try:
                return json.loads(part.text)
            except Exception:
                return {"text": part.text}
    return {}

async def tail(session, run_id):
    offset = 0
    while True:
        r = await session.call_tool("poll_logs", {"run_id": run_id, "offset": offset})
        obj = parse_json(r)
        for it in obj.get("items", []):
            print(f"[log] {it.get('line')}")
        offset = obj.get("offset", offset)

        s = parse_json(await session.call_tool("get_status", {"run_id": run_id}))
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
            r = await session.call_tool("segment_c2_with_nnunet", {
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
