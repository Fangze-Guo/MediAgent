# mcp_server.py —— 带标准化 description（HUMAN_DESC + PARAM_SPEC_JSON）
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

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]   # 指到 server_new
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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

import shlex
from pathlib import Path
from typing import List, Optional, Any

def _to_wsl_path(p: Path) -> str:
    """
    Windows Path -> WSL Path
    例：D:\\a\\b -> /mnt/d/a/b
    """
    p = p.resolve()
    drive = p.drive.rstrip(":").lower()
    rest = p.as_posix().split(":", 1)[-1]  # /a/b
    return f"/mnt/{drive}{rest}"

def _get_private_root_win() -> Path:
    """
    TODO: 你项目里有现成函数获取 private 绝对路径。
    请把下面的 import / 调用替换成你的真实实现。

    例如你可能有：
        from mediagent.paths import get_private_root
        return Path(get_private_root())

    我这里先给一个占位写法；你替换后就不用改别处。
    """
    try:
        # ====== 你自己替换这里 ======
        from mediagent.paths import in_data  # type: ignore
        return in_data("files","private").resolve()
        # ============================
    except Exception as e:
        raise RuntimeError(
            "Cannot get private_root automatically. "
            "Please edit _get_private_root_win() to call your project's function."
        ) from e


async def _launch_in_wsl_and_capture(
    pyfile: str,
    cli_args: List[str],
    out_dir: str,
    wsl_conda_env: str = "pyhiomics",
) -> RunInfo:
    """
    在 WSL conda env 中运行 tools/<pyfile>，并沿用 ndjson/status/run_id 机制。
    cli_args/out_dir 均为 WSL 格式路径。
    """
    run_id = uuid.uuid4().hex[:12]
    work_dir = Path(out_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = work_dir / "_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{Path(pyfile).stem}-{run_id}.ndjson"
    status_path = logs_dir / f"{Path(pyfile).stem}-{run_id}.status.json"

    script_path_win = (TOOLS_DIR / pyfile).resolve()
    script_path_wsl = _to_wsl_path(script_path_win)

    # 拼 WSL bash -lc 命令
    quoted_args = " ".join(shlex.quote(a) for a in cli_args)
    bash_cmd = f"""
set -e
source ~/anaconda3/etc/profile.d/conda.sh
conda activate {shlex.quote(wsl_conda_env)}
python -u {shlex.quote(script_path_wsl)} {quoted_args}
""".strip()

    cmd = [
        "wsl", "--", "bash", "-lc", bash_cmd
    ]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
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

    # --- 复用你现有的 pump 逻辑（与 _launch_and_capture 保持一致） ---
    BATCH_LINES = 200
    BATCH_INTERVAL = 0.02
    MAX_LINE_LEN = 65536

    def _sanitize(s: str) -> str:
        s = s.replace("\r", "")
        s = "".join(ch for ch in s if (ch == "\n" or ch == "\t" or ord(ch) >= 32))
        if len(s) > MAX_LINE_LEN:
            s = s[: MAX_LINE_LEN - 15] + " ...[truncated]"
        return s

    def _decode_best(raw: bytes) -> str:
        try:
            s = raw.decode("utf-8", "replace")
            if s.count("�") >= 3:
                try:
                    s2 = raw.decode("gbk", "replace")
                    if s2.count("�") < s.count("�"):
                        s = s2
                except Exception:
                    pass
            return s
        except Exception:
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
    description 采用两段式：
    - 【HUMAN_DESC_BEGIN】...【HUMAN_DESC_END】
    - 【PARAM_SPEC_JSON_BEGIN】{...}【PARAM_SPEC_JSON_END】
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
    返回给 Agent 的工具能力（name / description）。
    description 内部包含：
    - 【HUMAN_DESC_BEGIN】...【HUMAN_DESC_END】：自然语言工具说明
    - 【PARAM_SPEC_JSON_BEGIN】{...}【PARAM_SPEC_JSON_END】：严格 JSON 参数规范
    """
    tools = []
    for name in sorted(JOB_TOOLS):
        meta = JOB_TOOL_META.get(name, {})
        desc = meta.get("description", "") or ""
        tools.append({"name": name, "description": str(desc)})
    return {"tools": tools}


# ============================ 基础工具 ============================
@server.tool()
async def ping(ctx: Context) -> dict:
    """健康检查：返回 ok=True"""
    return {"ok": True}


# ============================ 作业工具（带标准化 description） ============================

@job_tool(
    name="convert_dicom_to_nifti",
    description=(
        '''【HUMAN_DESC_BEGIN】
将 DICOM 序列批量转换为 NIfTI 文件。

- 输入目录（in_dir）通常是“包含多个病例子目录”的根目录：
  - Patient001/C0, Patient001/C2
  - Patient002/C0, Patient002/C2
- 输出目录（out_dir）由任务管理器自动注入，对 AgentB 和 LLM 不可见。
- 对每个病人，工具会生成 C0.nii.gz 与 C2.nii.gz。

【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "convert_dicom_to_nifti",
  "params": [
    {
      "name": "in_dir",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output"],
      "default": null,
      "enum": null,
      "description": "输入根目录，下级为病人子目录，每个子目录内包含 C0/C2 等 DICOM 序列。通常通过 $ref 引用数据集或上一步产物，可以配合 relative 子路径。",
      "examples": [
        {
          "comment": "通过数据集引用 0_DICOM 子目录",
          "value": {
            "$ref": {
              "kind": "dataset",
              "id": 8842777993,
              "relative": "0_DICOM"
            }
          }
        },
        {
          "comment": "引用前一配套步骤输出目录 raw_dicoms",
          "value": {
            "$ref": {
              "kind": "job_output",
              "step": 3,
              "relative": "raw_dicoms"
            }
          }
        },
        {
          "comment": "直接指定一个绝对路径（不推荐，但允许）",
          "value": "/mnt/public_datasets/PROJECT_X/0_DICOM"
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出根目录，由任务管理器在执行时自动设置为当前步骤的工作空间，AgentB 和 LLM 不需要也不能填写。",
      "examples": []
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
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
        '''【HUMAN_DESC_BEGIN】
基于 linearBCV + deedsBCV 的批量配准工具：将每个病人目录中的 C2.nii.gz 配准到 C0.nii.gz。

- 输入目录（in_dir）既可为“包含多个病人的根目录”，也可为“单一病人目录”。
- 输出目录（out_dir）的层级结构与输入保持一致。
- 每个病人目录下必须至少包含 C0.nii.gz 与 C2.nii.gz。
【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "register_deeds",
  "params": [
    {
      "name": "in_dir",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output"],
      "default": null,
      "enum": null,
      "description": "输入根目录，可为包含多个病人子目录的根目录，也可为单一病人目录，通常通过 $ref 引用数据集或上一步产物，可以配合 relative 子路径。",
      "examples": [
        {
          "comment": "直接引用前一步 job_output 的全部输出目录",
          "value": {
            "$ref": {
              "kind": "job_output",
              "step": 5,
              "relative": ""
            }
          }
        },
        {
          "comment": "直接指定一个已经准备好的输入目录",
          "value": "/mnt/workspace/user123/task_abc/step_5_out"
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出根目录，由任务管理器设置为当前步骤的工作目录，层级结构与 in_dir 保持一致。",
      "examples": []
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
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
        return {"error": f"failed to start register_deeds: {e}"}


@job_tool(
    name="start_nnunet_predict",
    description=(
        '''【HUMAN_DESC_BEGIN】
nnUNet 推理（批量）。

- 输入目录（in_dir）：根目录下为病人目录；每个病人至少包含 C0.nii.gz 与 C2.nii.gz。
- 输出目录（out_dir）：仅包含病人子目录，每个病人目录下生成三件文件：
  - C0.nii.gz（可能重用/复制自输入）
  - C2.nii.gz（可能重用/复制自输入）
  - C2_mask.nii.gz（nnUNet 预测的掩膜）

关键参数：
- overwrite_mask：是否允许覆盖已有的 C2_mask.nii.gz。默认 false，已有掩膜时会跳过该病人。

【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "start_nnunet_predict",
  "params": [
    {
      "name": "in_dir",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output", "filesystem"],
      "default": null,
      "enum": null,
      "description": "输入根目录，下面是病人目录集合，通常通过 $ref 引用数据集或上一步产物，可以配合 relative 子路径。",
      "examples": [
        {
          "comment": "引用前一步 job_output 的完整输出目录",
          "value": {
            "$ref": {
              "kind": "job_output",
              "step": 9,
              "relative": ""
            }
          }
        },
        {
          "comment": "直接使用一个已有的输入根目录",
          "value": "/mnt/workspace/user123/task_abc/step_9_out"
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出根目录，由任务管理器自动设置，病人目录层级与 in_dir 保持一致。",
      "examples": []
    },
    {
      "name": "overwrite_mask",
      "type": "boolean",
      "required": false,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": false,
      "enum": [true, false],
      "description": "是否覆盖已有的 C2_mask.nii.gz。默认 false（已有掩膜则跳过该例），当需要重新预测时才设置为 true。",
      "examples": [
        {
          "comment": "默认行为（已有掩膜则跳过）",
          "value": false
        },
        {
          "comment": "强制覆盖所有已有掩膜",
          "value": true
        }
      ]
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
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


@job_tool(
    name="start_n4",
    description=(
        '''【HUMAN_DESC_BEGIN】
N4 偏置场校正（批量）。

- 输入目录（in_dir）：根目录下为病人子目录；每个病人至少包含 C2.nii.gz 与 C2_mask.nii.gz。
- 输出目录（out_dir）：与输入层级一致，写出校正后 C2.nii.gz 与对应 C2_mask.nii.gz。
- 可选地对 C2_mask 进行膨胀，以获得更稳定的偏置场估计。

关键参数：
- kernel_radius：用于 BinaryDilate 的膨胀半径，不设置则不膨胀；
  - 可用整数 3，或列表 3,3,1 表示各向异性半径。
- overwrite：是否覆盖已有结果（默认 false）。
- save_dilated_mask：是否把膨胀后的 mask 另存（默认 false）。

典型使用场景：
- 在配准/分割之后，对图像做偏置场校正，提升后续定量分析或建模的稳定性。
【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "start_n4",
  "params": [
    {
      "name": "in_dir",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output", "filesystem"],
      "default": null,
      "enum": null,
      "description": "输入根目录，下面是病人目录集合；通常通过 $ref 引用数据集或上一步产物，可以配合 relative 子路径。",
      "examples": [
        {
          "comment": "引用前一步 job_output 的完整输出目录",
          "value": {
            "$ref": {
              "kind": "job_output",
              "step": 10,
              "relative": ""
            }
          }
        },
        {
          "comment": "直接指定一个已存在的输入根目录",
          "value": "/mnt/workspace/user123/task_abc/step_10_out"
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出根目录，由任务管理器设置为当前步骤的工作目录，层级结构与 in_dir 保持一致。",
      "examples": []
    },
    {
      "name": "kernel_radius",
      "type": "string",
      "required": false,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "用户没有特殊需求则不填写，用于 BinaryDilate 的膨胀半径，不设置则不膨胀。可以是整数 3，或列表格式 3,3,1 等（内部会解析为半径向量）。",
      "examples": [
        {
          "comment": "各向同性半径 3",
          "value": "3"
        },
        {
          "comment": "各向异性半径 [3,3,1]",
          "value": "3,3,1"
        },
        {
          "comment": "不进行膨胀",
          "value": null
        }
      ]
    },
    {
      "name": "overwrite",
      "type": "boolean",
      "required": false,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": false,
      "enum": [true, false],
      "description": "是否覆盖已有 N4 结果。默认 false，仅在需要强制重跑时设为 true。",
      "examples": [
        {
          "comment": "默认行为：已有结果则跳过",
          "value": false
        },
        {
          "comment": "强制重跑并覆盖已有结果",
          "value": true
        }
      ]
    },
    {
      "name": "save_dilated_mask",
      "type": "boolean",
      "required": false,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": false,
      "enum": [true, false],
      "description": "是否把膨胀后的 mask 单独保存。默认 false，仅在调试或需要对膨胀结果做进一步分析时开启。",
      "examples": [
        {
          "comment": "默认：不另存膨胀 mask",
          "value": false
        },
        {
          "comment": "另存膨胀 mask，便于调试或分析",
          "value": true
        }
      ]
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
    )
)
async def start_n4(
    ctx: Context,
    in_dir: str,
    out_dir: str,
    kernel_radius: Optional[Any] = None,
    overwrite: bool = False,
    save_dilated_mask: bool = False,
) -> dict:
    """
    通过 _launch_and_capture 启动 tools/n4_correct.py 子进程；把参数转为 CLI。
    - kernel_radius 允许 int / list[int] / str("3,3,1")
    """
    args = ["--in-dir", in_dir, "--out-dir", out_dir]
    if kernel_radius is not None:
        if isinstance(kernel_radius, (list, tuple)):
            kr_str = ",".join(str(int(x)) for x in kernel_radius)
        else:
            kr_str = str(kernel_radius)
        args += ["--kernel-radius", kr_str]

    if overwrite:
        args.append("--overwrite")
    if save_dilated_mask:
        args.append("--save-dilated-mask")

    ri = await _launch_and_capture("n4_correct.py", *args, out_dir=out_dir)
    return {
        "run_id": ri.run_id,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
        "out_dir": out_dir,
        "started": True,
    }


@job_tool(
    name="start_resample",
    description=(
        '''【HUMAN_DESC_BEGIN】
重采样与空间规范（批量）。

- 输入目录（in_dir）：根目录为病人目录集合；每个病人目录需包含 C2.nii.gz 与 C2_mask.nii.gz。
- 输出目录（out_dir）：与输入层级一致；每例输出规则化的 C2.nii.gz 和 C2_mask.nii.gz。

固定行为（不可由 Agent 配置）：
1) 体素间距重采样到 1.0×1.0×1.0 mm；图像用 B-Spline，掩膜用最近邻。
2) 统一到 LPS 方向；direction 设为 identity；origin 设为 (0,0,0)。
3) 默认不覆盖已有结果；若目标 C2 已存在则整例跳过。

典型使用场景：
- 在 N4 或分割之后，对图像做空间规范，使得后续量化分析、模型训练具有统一的空间基准。

【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "start_resample",
  "params": [
    {
      "name": "in_dir",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output", "filesystem"],
      "default": null,
      "enum": null,
      "description": "输入根目录，下面为病人目录集合；通常通过 $ref 引用数据集或上一步产物，可以配合 relative 子路径。",
      "examples": [
        {
          "comment": "引用前一步 job_output 的完整输出目录",
          "value": {
            "$ref": {
              "kind": "job_output",
              "step": 11,
              "relative": ""
            }
          }
        },
        {
          "comment": "直接指定 resample 的输入根目录",
          "value": "/mnt/workspace/user123/task_abc/step_11_out"
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出根目录，由任务管理器设置为当前步骤的工作目录，层级结构与 in_dir 保持一致。",
      "examples": []
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
    )
)
async def start_resample(ctx: Context, in_dir: str, out_dir: str) -> dict:
    """
    启动 tools/resample_correct.py 子进程（仅 in_dir/out_dir 两个入参）。
    内部固定：spacing=1mm、overwrite=False、skip_underscore=True。
    """
    ri = await _launch_and_capture("resample_correct.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {
        "run_id": ri.run_id,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
        "out_dir": out_dir,
        "started": True,
    }


@job_tool(
    name="start_normalize",
    description=(
        '''【HUMAN_DESC_BEGIN】
强度归一化（基于 MONAI NormalizeIntensity，批量）。

- 输入目录（in_dir）：根目录为病人目录集合；每个病人目录需包含 C2.nii.gz 与 C2_mask.nii.gz。
- 输出目录（out_dir）：与输入层级一致；输出归一化后的 C2.nii.gz 与原样复制的 C2_mask.nii.gz。
- 若存在 C0.nii.gz，会原样复制到输出目录（不覆盖）。

固定行为：
1) 使用 MONAI NormalizeIntensity 对 C2 做强度归一化（保持空间信息）。
2) C2_mask 原样复制；C0（如存在）原样复制。

典型使用场景：
- 在空间规范之后，对强度分布做标准化，以便不同病例在同一强度尺度上进行建模或统计分析。
【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "start_normalize",
  "params": [
    {
      "name": "in_dir",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output", "filesystem"],
      "default": null,
      "enum": null,
      "description": "输入根目录，下面为病人目录集合；通常通过 $ref 引用数据集或上一步产物，可以配合 relative 子路径。",
      "examples": [
        {
          "comment": "引用前一步 job_output 的完整输出目录",
          "value": {
            "$ref": {
              "kind": "job_output",
              "step": 12,
              "relative": ""
            }
          }
        },
        {
          "comment": "直接指定 normalize 的输入根目录",
          "value": "/mnt/workspace/user123/task_abc/step_12_out"
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出根目录，由任务管理器设置为当前步骤的工作目录，层级结构与 in_dir 保持一致。",
      "examples": []
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
    )
)
async def start_normalize(ctx: Context, in_dir: str, out_dir: str) -> dict:
    """
    启动 tools/normalize_intensity.py 子进程（仅 in_dir/out_dir 两个入参）。
    """
    ri = await _launch_and_capture("normalize_intensity.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {
        "run_id": ri.run_id,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
        "out_dir": out_dir,
        "started": True,
    }


@job_tool(
    name="start_qc_plot",
    description=(
        '''【HUMAN_DESC_BEGIN】
QC 可视化（批量）：为每个病人的 C2/C2_mask 生成“最大掩膜切片 + 全卷强度分布”的 PNG。

- 输入目录（in_dir）：根目录为病人目录集合；每个病人需包含 C2.nii.gz 与 C2_mask.nii.gz。
- 输出目录（out_dir）：与输入层级一致；每例生成：
  - C2_qc.png：展示最大掩膜切片及强度直方图等；
  - C2_qc.json：记录用于可视化的 z_index 等元信息。

固定行为：
- 默认不覆盖已有 QC 结果。
- 自动跳过以下划线开头目录（_logs/_workspace 等）。
- 在日志中输出实时进度与 summary。

典型使用场景：
- 在预处理或训练前后，对数据质量进行快速可视化检查。
【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "start_qc_plot",
  "params": [
    {
      "name": "in_dir",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": false,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output", "filesystem"],
      "default": null,
      "enum": null,
      "description": "输入根目录，下面为病人目录集合；通常通过 $ref 引用数据集或上一步产物，可以配合 relative 子路径。",
      "examples": [
        {
          "comment": "引用前一步 job_output 的完整输出目录",
          "value": {
            "$ref": {
              "kind": "job_output",
              "step": 13,
              "relative": ""
            }
          }
        },
        {
          "comment": "直接指定 qc_plot 的输入根目录",
          "value": "/mnt/workspace/user123/task_abc/step_13_out"
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出根目录，由任务管理器设置为当前步骤的工作目录，层级结构与 in_dir 保持一致。",
      "examples": []
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
    )
)
async def start_qc_plot(ctx: Context, in_dir: str, out_dir: str) -> dict:
    ri = await _launch_and_capture("qc_plot_maxslice.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {
        "run_id": ri.run_id,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
        "out_dir": out_dir,
        "started": True,
    }

@job_tool(
    name="train_hiomics_pipeline",
    description=(
        '''【HUMAN_DESC_BEGIN】
Hiomics 训练（合并 CSV 处理 + 多数据集拼接 + 训练）。
- 输入（train_datasets）：一个或多个“数据集顶层目录”
  每个数据集顶层目录下必须且仅有一个 CSV（*.csv）以及一个数据文件夹。
  CSV 内的 image_path/mask_path 为相对该数据集顶层目录的相对路径。
固定行为：
1) 自动找到每个数据集的 CSV，读取并标准化字段（PID/DX 等）。
2) 将 image_path/mask_path 从相对 dataset_root 重写为相对 private_root。
3) 多数据集拼接为一个训练 CSV。
4) 使用 hiomics pipeline 训练，task_name 固定为 pCR，task_dir=out_dir。
5) 发现单行/单数据集异常：写 prepare_csv_errors.log 并跳过。

【HUMAN_DESC_END】

【PARAM_SPEC_JSON_BEGIN】
{
  "version": 1,
  "tool_name": "train_hiomics_pipeline",
  "params": [
    {
      "name": "train_datasets",
      "type": "path",
      "required": true,
      "filled_by": "agent",
      "is_list": true,
      "allow_ref": true,
      "ref_kinds": ["dataset", "job_output", "filesystem"],
      "default": null,
      "enum": null,
      "description": "训练数据集顶层目录列表（Windows 路径）。每个目录下必须且仅有一个 CSV 文件和一个数据子文件夹。",
      "examples": [
        {
          "comment": "训练用两个数据集",
          "value": [
            {
              "$ref": {"kind": "dataset", "id": 1111111111, "relative": ""}
            },
            {
              "$ref": {"kind": "dataset", "id": 2222222222, "relative": ""}
            }
          ]
        }
      ]
    },
    {
      "name": "out_dir",
      "type": "path",
      "required": true,
      "filled_by": "task_manager",
      "is_list": false,
      "allow_ref": false,
      "ref_kinds": [],
      "default": null,
      "enum": null,
      "description": "输出/工作目录，由任务管理器自动设置，LLM 不填写。",
      "examples": []
    }
  ]
}
【PARAM_SPEC_JSON_END】'''
    )
)
async def train_hiomics_pipeline(ctx: Context, train_datasets: List[str], out_dir: str) -> dict:
    # 1) MCP server 在 Windows 环境自动获取 private_root
    private_root_win = _get_private_root_win()

    # 2) 把所有 Windows 路径转成 WSL 路径
    out_dir_wsl = _to_wsl_path(Path(out_dir))
    private_root_wsl = _to_wsl_path(private_root_win)

    train_datasets_wsl = [_to_wsl_path(Path(p)) for p in (train_datasets or [])]

    # 3) 启动 WSL 子进程运行真实脚本
    cli_args = [
        "--train-datasets", *train_datasets_wsl,
        "--private-root", private_root_wsl,
        "--out-dir", out_dir_wsl,
    ]

    ri = await _launch_in_wsl_and_capture(
        "train_hiomics_pipeline.py",
        cli_args=cli_args,
        out_dir=out_dir_wsl,
        wsl_conda_env="pyhiomics",
    )

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
    return {
        "run_id": run_id,
        "done": ri.done,
        "exit_code": ri.exit_code,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
    }


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
