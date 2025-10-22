# mcp_test_poll.py —— 测试全流程：DICOM→NIfTI→配准→nnU-Net→N4校正→Resample→Normalize→QC Plot
# 放在 server_new/test_scripts/ 下
import asyncio, sys, json, time
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

HERE   = Path(__file__).resolve().parent
SERVER = HERE.parent / "mediagent" / "mcp_server_tools" / "mcp_server.py"
CWD    = SERVER.parent

# === 超时阈值（秒） ===
POLL_TIMEOUT_SEC = 5.0
STATUS_TIMEOUT_SEC = 5.0


# ============================================================
# 工具函数
# ============================================================

def parse_json(result):
    """健壮解析：尝试从 TextContent 段中提取 JSON。"""
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
    """包装 call_tool：增加超时保护。"""
    try:
        return await asyncio.wait_for(session.call_tool(tool, payload), timeout=timeout)
    except Exception:
        return None


async def tail(session, run_id):
    """实时轮询日志与状态。"""
    offset = 0
    empty_rounds = 0
    MAX_EMPTY_ROUNDS_BEFORE_TAIL = 20
    last_seq_printed = -1

    while True:
        # 拉取日志
        r = await call_tool_with_timeout(session, "poll_logs", {"run_id": run_id, "offset": offset, "limit": 200}, POLL_TIMEOUT_SEC)
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
                if isinstance(seq, int) and seq > last_seq_printed:
                    print(f"[log] seq={seq} off={new_offset} {line}")
                    last_seq_printed = seq
            offset = new_offset
            empty_rounds = 0
        else:
            empty_rounds += 1
            if empty_rounds >= MAX_EMPTY_ROUNDS_BEFORE_TAIL:
                r_tail = await call_tool_with_timeout(session, "poll_logs", {"run_id": run_id, "offset": -1}, POLL_TIMEOUT_SEC)
                if r_tail:
                    obj_tail = parse_json(r_tail)
                    tail_items = obj_tail.get("items", [])
                    tail_offset = obj_tail.get("offset", offset)
                    if tail_items:
                        for it in tail_items:
                            seq = it.get("seq")
                            line = it.get("line")
                            if isinstance(seq, int) and seq > last_seq_printed:
                                print(f"[log] seq={seq} off={tail_offset} {line}")
                                last_seq_printed = seq
                        offset = tail_offset
                    empty_rounds = 0

        # 检查运行状态
        s_resp = await call_tool_with_timeout(session, "get_status", {"run_id": run_id}, STATUS_TIMEOUT_SEC)
        if s_resp:
            s = parse_json(s_resp)
            if s.get("done"):
                print(f"[done] exit_code={s.get('exit_code')}")
                break

        await asyncio.sleep(0.25)


async def run_tool_and_tail(session: ClientSession, tool: str, payload: dict, label: str):
    """调用工具并轮询日志"""
    print(f"\n=== {label}: call {tool} ===")
    r = await session.call_tool(tool, payload)
    j = parse_json(r)
    print(f"SERVER RESP ({tool}):", j)
    run_id = j.get("run_id")
    if not run_id:
        raise RuntimeError(f"{tool} failed, no run_id. server returned: {j}")
    print(f"{label} run_id:", run_id)
    await tail(session, run_id)
    return j


# ============================================================
# 主流程
# ============================================================

async def main():
    # 测试路径，可按需修改
    dicom_dir   = Path(r"D:\mcp_test\0_DICOM")
    dicom2nii   = Path(r"D:\mcp_test\dicom2nii")
    reg_out     = Path(r"D:\mcp_test\reg_out")
    nnunet_out  = Path(r"D:\mcp_test\nnunet_out")  # 含 _logs / _workspace
    n4_out      = Path(r"D:\mcp_test\n4_out")
    res_out     = Path(r"D:\mcp_test\res_out")
    norm_out    = Path(r"D:\mcp_test\norm_out")
    qc_out      = Path(r"D:\mcp_test\qc_out")      # ★ 新增：QC 输出

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        cwd=str(CWD),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ============================================================
            # Step 1: DICOM → NIfTI
            # ============================================================
            print("\n========== STEP 1: DICOM → NIfTI ==========")
            j1 = await run_tool_and_tail(session, "convert_dicom_to_nifti", {
                "in_dir":  str(dicom_dir),
                "out_dir": str(dicom2nii),
            }, label="DICOM2NIfTI")

            # ============================================================
            # Step 2: deeds 配准
            # ============================================================
            print("\n========== STEP 2: Registration (deedsBCV) ==========")
            j2 = await run_tool_and_tail(session, "register_deeds", {
                "in_dir":  str(dicom2nii),
                "out_dir": str(reg_out),
            }, label="REGISTER_DEEDS")

            # ============================================================
            # Step 3: nnU-Net 批量推理
            # ============================================================
            print("\n========== STEP 3: nnU-Net Predict ==========")
            j3 = await run_tool_and_tail(session, "start_nnunet_predict", {
                "in_dir":  str(reg_out),
                "out_dir": str(nnunet_out),
            }, label="NNUNET_PREDICT")

            # ============================================================
            # Step 4: N4 偏置场校正
            # ============================================================
            print("\n========== STEP 4: N4 Bias Correction ==========")
            n4_payload = {
                "in_dir":  str(nnunet_out),
                "out_dir": str(n4_out),
                "kernel_radius": [3, 3, 1],
                "overwrite": False,
                "save_dilated_mask": False,
            }
            j4 = await run_tool_and_tail(session, "start_n4", n4_payload, label="N4_CORRECTION")

            # ============================================================
            # Step 5: Resample 到 1mm + LPS/identity + origin(0)
            # ============================================================
            print("\n========== STEP 5: Resample (1mm LPS identity origin=0) ==========")
            print("[TEST] 期待日志中看到：")
            print("  • '[RESAMPLE] processing <PatientX>' / 'done' / 'skip' / 'fail' 等实时输出")
            print("  • 最后有 '[RESAMPLE] summary: {...}' 与 'total time'")
            res_payload = {
                "in_dir":  str(n4_out),
                "out_dir": str(res_out),
            }
            j5 = await run_tool_and_tail(session, "start_resample", res_payload, label="RESAMPLE")

            # ============================================================
            # Step 6: Normalize intensity (MONAI)
            # ============================================================
            print("\n========== STEP 6: Normalize Intensity (MONAI) ==========")
            print("[TEST] 期待日志中看到：")
            print("  • '[NORM] processing <PatientX>' / 'done' / 'skip' / 'fail' 等实时输出")
            print("  • 最后有 '[NORM] summary: {...}' 与 'total time'")

            norm_payload = {
                "in_dir":  str(res_out),    # 输入：Resample 的输出
                "out_dir": str(norm_out),   # 输出：Normalize 结果目录
            }
            j6 = await run_tool_and_tail(session, "start_normalize", norm_payload, label="NORMALIZE")

            # ============================================================
            # Step 7: QC Plot (Max-slice + KDE)
            # ============================================================
            print("\n========== STEP 7: QC Plot (Max-slice + KDE) ==========")
            print("[TEST] 期待日志中看到：")
            print("  • '[QC] processing <PatientX>' / 'done' / 'skip' / 'fail' 等实时输出")
            print("  • 最后有 '[QC] summary: {...}' 与 'total time'")

            qc_payload = {
                "in_dir":  str(norm_out),   # 建议使用 Normalize 的输出作为输入
                "out_dir": str(qc_out),     # 输出：PNG + z_index JSON
            }
            j7 = await run_tool_and_tail(session, "start_qc_plot", qc_payload, label="QC_PLOT")

            # 可选：汇总输出路径
            # print("\n========== ALL STEPS FINISHED ==========")
            # print("NORMALIZE 输出：", j6.get("out_dir"))
            # print("QC_PLOT   输出：", j7.get("out_dir"))


if __name__ == "__main__":
    asyncio.run(main())
