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
    同时写入一个 status.json 记录完成状态；立即返回 RunInfo（后台任务持续抽取日志）。
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
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

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

    async def _pump():
        with log_path.open("w", encoding="utf-8") as f:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace").rstrip("\n")
                f.write(json.dumps({"ts": time.time(), "line": text}, ensure_ascii=False) + "\n")
                f.flush()

        rc = await proc.wait()
        ri.done = True
        ri.exit_code = int(rc or 0)
        with status_path.open("w", encoding="utf-8") as sf:
            json.dump({"run_id": run_id, "done": True, "exit_code": ri.exit_code}, sf, ensure_ascii=False)

    asyncio.create_task(_pump())
    return ri


def _read_ndjson_from(path: Path, offset: int) -> Tuple[List[dict], int]:
    """从给定 offset（字节偏移）读取新的 ndjson 行，返回对象列表和新的偏移。"""
    if not path.exists():
        return [], offset
    items: List[dict] = []
    with path.open("rb") as f:
        f.seek(offset)
        for raw in f:
            try:
                obj = json.loads(raw.decode("utf-8", "replace"))
                items.append(obj)
            except Exception:
                pass
        new_off = f.tell()
    return items, new_off


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
    print("[list_job_tools] tools=", json.dumps(tools, ensure_ascii=False)[:500])
    return {"tools": tools}



# ============================ 基础工具 ============================
@server.tool()
async def ping(ctx: Context) -> dict:
    """健康检查：返回 ok=True"""
    return {"ok": True}


# ============================ 作业工具（描述已对齐 PLAN_JSON_SCHEMA） ============================
@job_tool(
    name="start_ingest",
    description=(
        "数据导入（step1_ingest.py）。用于将外部数据引入工作空间。\n\n"
        "【用于 LLM 产出 steps[*] 的规则】\n"
        "1) 固定字段：必须包含 step_number / tool_name / source_kind / source / additional_params；relative 可选。\n"
        "2) tool_name 必须为 'start_ingest'。\n"
        "3) 推荐的 source_kind：\n"
        "   - 'dataset'：source=数据集编号（字符串），例如 'ds001'。\n"
        "   - 'direct'：source=输入目录路径或自定义 scheme（字符串），例如 'file:///mnt/raw'。\n"
        "4) relative：可选，指定子路径或模式（字符串），由任务管理器解析。\n"
        "5) additional_params：本工具无业务参数 → 必须是空对象 {}。\n"
        "6) 禁止在 additional_params 中出现 in_dir/out_dir（执行时由系统注入）。\n\n"
        "【最小示例】\n"
        "{\n"
        "  \"step_number\": 1,\n"
        "  \"tool_name\": \"start_ingest\",\n"
        "  \"source_kind\": \"dataset\",\n"
        "  \"source\": \"ds001\",\n"
        "  \"relative\": null,\n"
        "  \"additional_params\": {}\n"
        "}"
    )
)
async def start_ingest(ctx: Context, in_dir: str, out_dir: str) -> dict:
    ri = await _launch_and_capture("step1_ingest.py", "--source", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
            "out_dir": out_dir, "started": True}


@job_tool(
    name="start_preprocess",
    description=(
        "数据预处理（step2_preprocess.py）。对上一步导入的数据进行清洗/转换。\n\n"
        "【用于 LLM 产出 steps[*] 的规则】\n"
        "1) tool_name='start_preprocess'。\n"
        "2) 常用 source_kind='step'，source=前置步骤号（整数或数字字符串），且必须小于当前步骤号。\n"
        "3) relative：可选，用于选择上一步产物中的子目录/文件模式。\n"
        "4) additional_params：无业务参数 → 必须是 {}。\n"
        "5) 禁止 additional_params 出现 in_dir/out_dir。\n\n"
        "【最小示例】\n"
        "{\n"
        "  \"step_number\": 2,\n"
        "  \"tool_name\": \"start_preprocess\",\n"
        "  \"source_kind\": \"step\",\n"
        "  \"source\": 1,\n"
        "  \"relative\": null,\n"
        "  \"additional_params\": {}\n"
        "}"
    )
)
async def start_preprocess(ctx: Context, in_dir: str, out_dir: str) -> dict:
    ri = await _launch_and_capture("step2_preprocess.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
            "out_dir": out_dir, "started": True}


@job_tool(
    name="start_train",
    description=(
        "模型训练（step3_train.py）。从预处理产物中训练模型。\n\n"
        "【用于 LLM 产出 steps[*] 的规则】\n"
        "1) tool_name='start_train'。\n"
        "2) 常用 source_kind='step'，source=预处理步骤号。\n"
        "3) relative：可选。\n"
        "4) additional_params：可包含业务参数，例如 epochs（整数，默认 5）。\n"
        "5) 禁止 additional_params 出现 in_dir/out_dir。\n\n"
        "【最小示例】\n"
        "{\n"
        "  \"step_number\": 3,\n"
        "  \"tool_name\": \"start_train\",\n"
        "  \"source_kind\": \"step\",\n"
        "  \"source\": 2,\n"
        "  \"relative\": null,\n"
        "  \"additional_params\": {\"epochs\": 20}\n"
        "}"
    )
)
async def start_train(ctx: Context, in_dir: str, out_dir: str, epochs: int = 5) -> dict:
    ri = await _launch_and_capture(
        "step3_train.py", "--in-dir", in_dir, "--out-dir", out_dir, "--epochs", str(epochs), out_dir=out_dir
    )
    return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
            "out_dir": out_dir, "started": True}


@job_tool(
    name="start_evaluate",
    description=(
        "模型评估（step4_evaluate.py）。对训练好的模型或结果进行评估。\n\n"
        "【用于 LLM 产出 steps[*] 的规则】\n"
        "1) tool_name='start_evaluate'。\n"
        "2) 常用 source_kind='step'，source=训练步骤号。\n"
        "3) relative：可选。\n"
        "4) additional_params：无业务参数 → 必须是 {}。\n"
        "5) 禁止 additional_params 出现 in_dir/out_dir。\n\n"
        "【最小示例】\n"
        "{\n"
        "  \"step_number\": 4,\n"
        "  \"tool_name\": \"start_evaluate\",\n"
        "  \"source_kind\": \"step\",\n"
        "  \"source\": 3,\n"
        "  \"relative\": null,\n"
        "  \"additional_params\": {}\n"
        "}"
    )
)
async def start_evaluate(ctx: Context, in_dir: str, out_dir: str) -> dict:
    ri = await _launch_and_capture("step4_evaluate.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path),
            "out_dir": out_dir, "started": True}

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
        "使用 linearBCV + deedsBCV 将每个病人目录中的 C2.nii.gz 配准到 C0.nii.gz。\n"
        "输入目录可为根目录（含多个病人）或单病人目录；输出结构与输入一致。\n"
        "二进制文件 linearBCV / deedsBCV 需放在本工具脚本同级的 bin/ 文件夹内。\n"
        "参数：in_dir, out_dir。"
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





# ============================ 内部辅助工具（执行层用） ============================
@server.tool()
async def poll_logs(ctx: Context, run_id: str, offset: int = 0, limit: int = 2000) -> dict:
    """读取日志 ndjson，返回若干行与新的 offset。"""
    ri = RUNS.get(run_id)
    if not ri:
        return {"error": f"run_id not found: {run_id}"}
    items, new_off = _read_ndjson_from(ri.log_path, offset)
    if limit and len(items) > limit:
        items = items[-limit:]
    return {"run_id": run_id, "items": items, "offset": new_off}


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
