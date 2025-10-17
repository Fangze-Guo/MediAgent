# mcp_server.py —— 极简：仅向 Agent 返回 {name, description}，不返回 inputSchema
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Set, Any

from fastmcp import FastMCP, Context

import re
_ANSI_RE   = re.compile(r"\x1B\[[0-9;?]*[ -/]*[@-~]")        # CSI … m 等
_OSC_RE    = re.compile(r"\x1B\][^\a]*\x07")                 # OSC … BEL
_CTRL_RE   = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")     # 除 \t \n 外的控制字节


def _sanitize_json_line(s: str, max_len: int = 16384) -> str:
    # 1) 统一编码，替换非法码点
    s = s.encode("utf-8", "replace").decode("utf-8", "replace")
    # 2) 去掉 ANSI/OSC 终端控制序列
    s = _ANSI_RE.sub("", s)
    s = _OSC_RE.sub("", s)
    # 3) 去掉裸回车，再去除除 \t \n 外的控制字节
    s = s.replace("\r", "")
    s = _CTRL_RE.sub("", s)
    # 4) 限长（避免极端超长一行撑爆单帧）
    if len(s) > max_len:
        s = s[: max_len - 15] + " ...[truncated]"
    return s

# ============================ 目录定位 ============================
HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE / "tools"

# ============================ MCP 实例 ============================
server = FastMCP("mediagent-mcp")

# ============================ 运行管理器（执行用） ============================
class RunInfo:
    __slots__ = ("run_id", "proc", "log_path", "status_path", "start_ts", "done", "exit_code")

    def __init__(self, run_id: str, proc: asyncio.subprocess.Process, log_path: Path, status_path: Path):
        self.run_id = run_id
        self.proc = proc
        self.log_path = log_path
        self.status_path = status_path
        self.start_ts = time.time()
        self.done = False
        self.exit_code: Optional[int] = None


RUNS: Dict[str, RunInfo] = {}





async def _launch_and_capture(pyfile: str, *cli_args: str, out_dir: str) -> RunInfo:
    """
    启动 tools/<pyfile> 子进程，把 stdout/stderr 写入 run 专属的 .ndjson 文件；
    —— 编码与落盘改进：
       • 强制子进程 Python 使用 UTF-8：PYTHONIOENCODING=utf-8
       • 设置 UTF-8 本地化：LANG/LC_ALL=C.UTF-8
       • 读取端智能解码：UTF-8 优先，含大量替换符时回退 GBK
       • 提高刷盘频率：BATCH_INTERVAL=0.02，减少半行窗口
    """
    run_id = uuid.uuid4().hex[:12]
    work_dir = Path(out_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = work_dir / "_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{Path(pyfile).stem}-{run_id}.ndjson"
    status_path = logs_dir / f"{Path(pyfile).stem}-{run_id}.status.json"

    python_exe = sys.executable
    script_path = TOOLS_DIR / pyfile
    cmd = [python_exe, "-u", str(script_path), *cli_args]

    # === 关键：统一子进程输出为 UTF-8 ===
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"   # 强制 Python 子进程 stdout/stderr 用 UTF-8
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("LC_ALL", "C.UTF-8")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(HERE),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None

    ri = RunInfo(run_id, proc, log_path, status_path)
    RUNS[run_id] = ri

    # --- 批量写配置 ---
    BATCH_LINES = 200
    BATCH_INTERVAL = 0.02
    MAX_LINE_LEN = 65536

    def _sanitize(s: str) -> str:
        # 轻量清洗：去 \r 与非常规控制符，限长
        s = s.replace("\r", "")
        s = "".join(ch for ch in s if (ch == "\n" or ch == "\t" or ord(ch) >= 32))
        if len(s) > MAX_LINE_LEN:
            s = s[: MAX_LINE_LEN - 15] + " ...[truncated]"
        return s

    def _decode_best(raw: bytes) -> str:
        """优先 UTF-8；若替换符过多则回退 GBK（适配部分 Windows/WSL 场景）。"""
        try:
            s = raw.decode("utf-8", "replace")
            # 如果出现很多替换符（�），说明不是正经 UTF-8，尝试 GBK 一次
            if s.count("�") >= 3:
                try:
                    s2 = raw.decode("gbk", "replace")
                    # 选替换符更少的那个版本
                    if s2.count("�") < s.count("�"):
                        s = s2
                except Exception:
                    pass
            return s
        except Exception:
            # 极端兜底
            try:
                return raw.decode("gbk", "replace")
            except Exception:
                return raw.decode("utf-8", "replace")

    async def _pump():
        f = log_path.open("a", encoding="utf-8")
        try:
            batch = []
            loop = asyncio.get_event_loop()
            last_flush = loop.time()
            seq = 0

            async def _flush_batch():
                nonlocal batch
                if not batch:
                    return
                lines = batch
                batch = []

                def _write_lines():
                    for obj in lines:
                        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    f.flush()
                return await asyncio.to_thread(_write_lines)

            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    await _flush_batch()
                    break

                s = _sanitize(_decode_best(raw))
                seq += 1
                batch.append({"ts": time.time(), "seq": seq, "line": s})

                now = loop.time()
                if len(batch) >= BATCH_LINES or (now - last_flush) >= BATCH_INTERVAL:
                    await _flush_batch()
                    last_flush = now

            rc = await proc.wait()
            ri.done = True
            ri.exit_code = int(rc or 0)

            def _write_status():
                with status_path.open("w", encoding="utf-8") as sf:
                    json.dump({"run_id": ri.run_id, "done": True, "exit_code": ri.exit_code}, sf, ensure_ascii=False)

            await asyncio.to_thread(_write_status)

        finally:
            with contextlib.suppress(Exception):
                f.close()

    asyncio.create_task(_pump())
    return ri



def _read_ndjson_from(path: Path, offset: int) -> Tuple[List[dict], int]:
    """
    从给定 offset（字节偏移）读取 .ndjson。关键点：
    - 返回 offset 为“最后一条成功返回的行”的行尾偏移（不是文件当前位置）；
    - 若文件截断（size < offset），将 offset 自愈到文件尾窗口；
    - 加入读时限、行数/字节上限，避免一次读太多。
    """
    import time
    HARD_MAX_LINES = 200               # 单次最多拿 200 行
    HARD_MAX_BYTES = 256 * 1024        # 单次最多 256KB
    HARD_MAX_TIME  = 0.050             # 单次最多 50ms
    SAFE_TAIL_BYTES = 512 * 1024       # 截断自愈时，回到末尾这个窗口

    if not path.exists():
        return [], offset

    try:
        size = path.stat().st_size
    except Exception:
        return [], offset

    # 自愈：负数表示“从末尾追”
    if offset < 0:
        offset = max(0, size - SAFE_TAIL_BYTES)
    # 自愈：文件被截断或轮转了
    if offset > size:
        offset = max(0, size - SAFE_TAIL_BYTES)

    items: List[dict] = []
    last_returned_offset = offset
    total_bytes = 0
    t0 = time.perf_counter()

    with path.open("rb") as f:
        try:
            f.seek(offset)
        except Exception:
            f.seek(0)

        while True:
            line_start = f.tell()
            raw = f.readline()
            line_end = f.tell()  # 这一行（包含换行）的结束偏移

            if not raw:
                break

            # 轻量限流，避免一次读太多
            total_bytes += len(raw)
            if (time.perf_counter() - t0) >= HARD_MAX_TIME:
                break
            if total_bytes > HARD_MAX_BYTES or len(items) >= HARD_MAX_LINES:
                break

            try:
                obj = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                # 坏行：不返回，也不推进 offset，下一轮再读
                continue

            # 只有“真正返回给客户端的行”才推进 offset
            items.append(obj)
            last_returned_offset = line_end

    return items, last_returned_offset



# ============================ “作业工具 → 仅对 Agent 的元信息” ============================
JOB_TOOLS: Set[str] = set()
# 仅存给 Agent 的元数据：name -> {"description": str}
JOB_TOOL_META: Dict[str, Dict[str, Any]] = {}

# 只把“name”传给 FastMCP（避免未知 kw 报错）
_FASTMCP_TOOL_KW_WHITELIST = {"name"}


def job_tool(_fn=None, **tool_kwargs):
    """
    注册“可编排作业工具”（返回 run_id）。
    仅向 Agent 暴露：name / description。**不返回 inputSchema**。
    """
    def _decorator(fn):
        tool_name = tool_kwargs.get("name") or fn.__name__
        JOB_TOOLS.add(tool_name)

        desc = tool_kwargs.get("description") or (fn.__doc__ or "").strip() or ""
        JOB_TOOL_META[tool_name] = {"description": desc}

        mcp_kwargs = {k: v for k, v in tool_kwargs.items() if k in _FASTMCP_TOOL_KW_WHITELIST}
        mcp_kwargs["name"] = tool_name
        return server.tool(**mcp_kwargs)(fn)

    if callable(_fn):
        return _decorator(_fn)
    return _decorator


@server.tool()
async def list_job_tools(ctx: Context) -> dict:
    """
    返回给 Agent 的工具能力（name / description）。不含任何参数 schema。
    """
    tools = []
    for name in sorted(JOB_TOOLS):
        meta = JOB_TOOL_META.get(name, {})
        desc = meta.get("description", "") or ""
        # 关键：一定返回对象，且 description 为字符串
        tools.append({"name": name, "description": str(desc)})
    # 可选：在服务器控制台打日志，便于核对
    return {"tools": tools}



# ============================ 基础工具 ============================
@server.tool()
async def ping(ctx: Context) -> dict:
    """健康检查：返回 ok=True"""
    return {"ok": True}


# ============================ 作业工具（描述已对齐 PLAN_JSON_SCHEMA） ============================
# @job_tool(
#     name="start_ingest",
#     description=(
#         "数据导入（step1_ingest.py）。用于将外部数据引入工作空间。\n\n"
#         "【用于 LLM 产出 steps[*] 的规则】\n"
#         "1) 固定字段：必须包含 step_number / tool_name / source_kind / source / additional_params；relative 可选。\n"
#         "2) tool_name 必须为 'start_ingest'。\n"
#         "3) 推荐的 source_kind：\n"
#         "   - 'dataset'：source=数据集编号（字符串），例如 'ds001'。\n"
#         "   - 'direct'：source=输入目录路径或自定义 scheme（字符串），例如 'file:///mnt/raw'。\n"
#         "4) relative：可选，指定子路径或模式（字符串），由任务管理器解析。\n"
#         "5) additional_params：本工具无业务参数 → 必须是空对象 {}。\n"
#         "6) 禁止在 additional_params 中出现 in_dir/out_dir（执行时由系统注入）。\n\n"
#         "【最小示例】\n"
#         "{\n"
#         "  \"step_number\": 1,\n"
#         "  \"tool_name\": \"start_ingest\",\n"
#         "  \"source_kind\": \"dataset\",\n"
#         "  \"source\": \"ds001\",\n"
#         "  \"relative\": null,\n"
#         "  \"additional_params\": {}\n"
#         "}"
#     )
# )
# async def start_ingest(ctx: Context, in_dir: str, out_dir: str) -> dict:
#     ri = await _launch_and_capture("step1_ingest.py", "--source", in_dir, "--out-dir", out_dir, out_dir=out_dir)
#     return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
#             "out_dir": out_dir, "started": True}
#
#
# @job_tool(
#     name="start_preprocess",
#     description=(
#         "数据预处理（step2_preprocess.py）。对上一步导入的数据进行清洗/转换。\n\n"
#         "【用于 LLM 产出 steps[*] 的规则】\n"
#         "1) tool_name='start_preprocess'。\n"
#         "2) 常用 source_kind='step'，source=前置步骤号（整数或数字字符串），且必须小于当前步骤号。\n"
#         "3) relative：可选，用于选择上一步产物中的子目录/文件模式。\n"
#         "4) additional_params：无业务参数 → 必须是 {}。\n"
#         "5) 禁止 additional_params 出现 in_dir/out_dir。\n\n"
#         "【最小示例】\n"
#         "{\n"
#         "  \"step_number\": 2,\n"
#         "  \"tool_name\": \"start_preprocess\",\n"
#         "  \"source_kind\": \"step\",\n"
#         "  \"source\": 1,\n"
#         "  \"relative\": null,\n"
#         "  \"additional_params\": {}\n"
#         "}"
#     )
# )
# async def start_preprocess(ctx: Context, in_dir: str, out_dir: str) -> dict:
#     ri = await _launch_and_capture("step2_preprocess.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
#     return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
#             "out_dir": out_dir, "started": True}
#
#
# @job_tool(
#     name="start_train",
#     description=(
#         "模型训练（step3_train.py）。从预处理产物中训练模型。\n\n"
#         "【用于 LLM 产出 steps[*] 的规则】\n"
#         "1) tool_name='start_train'。\n"
#         "2) 常用 source_kind='step'，source=预处理步骤号。\n"
#         "3) relative：可选。\n"
#         "4) additional_params：可包含业务参数，例如 epochs（整数，默认 5）。\n"
#         "5) 禁止 additional_params 出现 in_dir/out_dir。\n\n"
#         "【最小示例】\n"
#         "{\n"
#         "  \"step_number\": 3,\n"
#         "  \"tool_name\": \"start_train\",\n"
#         "  \"source_kind\": \"step\",\n"
#         "  \"source\": 2,\n"
#         "  \"relative\": null,\n"
#         "  \"additional_params\": {\"epochs\": 20}\n"
#         "}"
#     )
# )
# async def start_train(ctx: Context, in_dir: str, out_dir: str, epochs: int = 5) -> dict:
#     ri = await _launch_and_capture(
#         "step3_train.py", "--in-dir", in_dir, "--out-dir", out_dir, "--epochs", str(epochs), out_dir=out_dir
#     )
#     return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
#             "out_dir": out_dir, "started": True}
#
#
# @job_tool(
#     name="start_evaluate",
#     description=(
#         "模型评估（step4_evaluate.py）。对训练好的模型或结果进行评估。\n\n"
#         "【用于 LLM 产出 steps[*] 的规则】\n"
#         "1) tool_name='start_evaluate'。\n"
#         "2) 常用 source_kind='step'，source=训练步骤号。\n"
#         "3) relative：可选。\n"
#         "4) additional_params：无业务参数 → 必须是 {}。\n"
#         "5) 禁止 additional_params 出现 in_dir/out_dir。\n\n"
#         "【最小示例】\n"
#         "{\n"
#         "  \"step_number\": 4,\n"
#         "  \"tool_name\": \"start_evaluate\",\n"
#         "  \"source_kind\": \"step\",\n"
#         "  \"source\": 3,\n"
#         "  \"relative\": null,\n"
#         "  \"additional_params\": {}\n"
#         "}"
#     )
# )
# async def start_evaluate(ctx: Context, in_dir: str, out_dir: str) -> dict:
#     ri = await _launch_and_capture("step4_evaluate.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
#     return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
#             "out_dir": out_dir, "started": True}

@job_tool(
    name="convert_dicom_to_nifti",
    description=(
        "将 DICOM 序列批量转换为 NIfTI 文件。\n\n"
        "输入目录结构示例：\n"
        "  ├─ Patient001\n"
        "  │   ├─ C0\n"
        "  │   └─ C2\n"
        "  ├─ Patient002\n"
        "  │   ├─ C0\n"
        "  │   └─ C2\n"
        "输出目录将生成对应的 NIfTI 文件：C0.nii.gz, C2.nii.gz。\n\n"
        "【用于 LLM 产出 steps[*] 的规则】\n"
        "1) tool_name='convert_dicom_to_nifti'。\n"
        "2) source_kind='step' 或 'direct' 均可。\n"
        "3) additional_params 必须为 {}。\n"
        "4) 禁止 additional_params 出现 in_dir/out_dir。\n"
        "【示例】\n"
        "{\n"
        "  \"step_number\": 5,\n"
        "  \"tool_name\": \"convert_dicom_to_nifti\",\n"
        "  \"source_kind\": \"direct\",\n"
        "  \"source\": \"file:///mnt/data/dicoms\",\n"
        "  \"additional_params\": {}\n"
        "}"
    )
)
async def convert_dicom_to_nifti(ctx: Context, in_dir: str, out_dir: str) -> dict:
    ri = await _launch_and_capture("convert_dicom_to_nifti.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {
        "run_id": ri.run_id,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
        "out_dir": out_dir,
        "started": True,
    }

@job_tool(
    name="register_deeds",
    description=(
        "基于 linearBCV + deedsBCV 的批量配准工具：将每个病人目录中的 C2.nii.gz 配准到 C0.nii.gz。\n"
        "输入目录既可为“包含多个病人的根目录”，也可为“单一病人目录”。输出目录的层级结构将与输入保持一致。\n"
        "输入要求：每个病人目录下必须至少包含 C0.nii.gz 与 C2.nii.gz 两个文件。\n"
        "运行依赖：linearBCV / deedsBCV 可执行文件需放置在本工具脚本同级的 bin/ 目录内。\n\n"
        "【用于 LLM 产出 steps[*] 的规则】\n"
        "1) tool_name 必须为 'register_deeds'。\n"
        "2) 常用 source_kind='step'（例如上一转换步骤 convert_dicom_to_nifti 的产物），也可使用 'direct'。\n"
        "3) relative：可选，字符串，表示在输入目录下选择子目录/模式（由任务管理器解析）。\n"
        "4) additional_params：本工具无业务可配置参数 → 必须是空对象 {}。\n"
        "5) 禁止在 additional_params 中出现 in_dir/out_dir（执行时由系统注入）。\n\n"
        "【最小示例】\n"
        "{\n"
        "  \"step_number\": 9,\n"
        "  \"tool_name\": \"register_deeds\",\n"
        "  \"source_kind\": \"step\",\n"
        "  \"source\": 8,\n"
        "  \"relative\": null,\n"
        "  \"additional_params\": {}\n"
        "}\n"
    )
)
async def register_deeds(ctx: Context, in_dir: str, out_dir: str) -> dict:
    try:
        ri = await _launch_and_capture(
            "register_deeds.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir
        )
        return {
            "run_id": ri.run_id,
            "log_path": str(ri.log_path),
            "status_path": str(ri.status_path),
            "out_dir": out_dir,
            "started": True,
        }
    except Exception as e:
        # 关键：失败也明确告诉客户端
        return {"error": f"failed to start register_deeds: {e}"}



@job_tool(
    name="start_nnunet_predict",
    description=(
        "nnUNet 推理（批量）。\n"
        "输入目录结构：根目录下为病人文件夹；每个病人包含 C0.nii.gz 与 C2.nii.gz。\n"
        "输出目录：仅包含病人子目录，每个病人目录下三件文件：C0.nii.gz、C2.nii.gz、C2_mask.nii.gz。\n"
        "【用于 LLM 产出 steps[*] 的规则】\n"
        "1) tool_name='start_nnunet_predict'。\n"
        "2) 常用 source_kind='step'（例如上一配准步骤的产物）。\n"
        "3) additional_params 可选：{\"overwrite_mask\": true/false}（默认 false）。\n"
        "4) 禁止 additional_params 出现 in_dir/out_dir（由系统注入）。\n"
        "【最小示例】\n"
        "{\n"
        "  \"step_number\": 10,\n"
        "  \"tool_name\": \"start_nnunet_predict\",\n"
        "  \"source_kind\": \"step\",\n"
        "  \"source\": 9,\n"
        "  \"relative\": null,\n"
        "  \"additional_params\": {\"overwrite_mask\": false}\n"
        "}"
    )
)
async def start_nnunet_predict(ctx: Context, in_dir: str, out_dir: str, overwrite_mask: bool = False) -> dict:
    args = ["--in-dir", in_dir, "--out-dir", out_dir]
    if overwrite_mask:
        args.append("--overwrite-mask")
    ri = await _launch_and_capture("nnunet_predict.py", *args, out_dir=out_dir)
    return {
        "run_id": ri.run_id,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
        "out_dir": out_dir,
        "started": True,
    }


# ============================ 内部辅助工具（执行层用） ============================
@server.tool()
async def poll_logs(ctx: Context, run_id: str, offset: int = 0, limit: int = 2000) -> dict:
    """
    极简版：仅从 ndjson 读取并返回 {run_id, items, offset}。
    - 不写任何调试文件
    - 不附带额外字段
    - 不做原始尾部兜底
    """
    ri = RUNS.get(run_id)
    if not ri:
        return {"error": f"run_id not found: {run_id}"}

    items, new_off = _read_ndjson_from(ri.log_path, offset)

    if limit and len(items) > limit:
        items = items[-limit:]

    return {
        "run_id": run_id,
        "items": items,
        "offset": (new_off if isinstance(new_off, int) else offset),
    }



@server.tool()
async def get_status(ctx: Context, run_id: str) -> dict:
    """查询运行状态。"""
    ri = RUNS.get(run_id)
    if not ri:
        return {"error": f"run_id not found: {run_id}"}
    return {"run_id": run_id, "done": ri.done, "exit_code": ri.exit_code,
            "log_path": str(ri.log_path), "status_path": str(ri.status_path)}


@server.tool()
async def cancel(ctx: Context, run_id: str) -> dict:
    """终止某次运行（best-effort）。"""
    ri = RUNS.get(run_id)
    if not ri:
        return {"error": f"run_id not found: {run_id}"}
    with contextlib.suppress(ProcessLookupError):
        ri.proc.terminate()
    return {"run_id": run_id, "terminated": True}


# ============================ 启动 ============================
if __name__ == "__main__":
    server.run()
