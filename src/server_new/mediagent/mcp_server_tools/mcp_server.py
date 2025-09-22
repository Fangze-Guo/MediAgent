from __future__ import annotations
import asyncio, os, sys, json, contextlib, time, uuid
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from fastmcp import FastMCP, Context

# 目录定位
HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE / "tools"

# MCP 实例
server = FastMCP("mediagent-mcp")

# ------------------------------- 运行管理器 ---------------------------------
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
    同时写入一个 status.json 记录完成状态。
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
                # 每一行按 ndjson 写出；保持原样（脚本里打印什么就写什么）
                f.write(json.dumps({"ts": time.time(), "line": text}, ensure_ascii=False) + "\n")
                f.flush()
        rc = await proc.wait()
        ri.done = True
        ri.exit_code = int(rc or 0)
        with status_path.open("w", encoding="utf-8") as sf:
            json.dump({"run_id": run_id, "done": True, "exit_code": ri.exit_code}, sf, ensure_ascii=False)

    # 后台抽取日志（不阻塞工具返回）
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

# ------------------------------- 工具定义 -----------------------------------

@server.tool()
async def ping(ctx: Context) -> dict:
    return {"ok": True}

@server.tool()
async def start_ingest(ctx: Context, in_dir: str, out_dir: str) -> dict:
    """
    启动 step1_ingest.py（后台运行），立即返回 run_id / log_path；
    客户端可轮询 poll_logs(get_status) 获取实时日志/状态。
    """
    ri = await _launch_and_capture("step1_ingest.py", "--source", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {
        "run_id": ri.run_id,
        "log_path": str(ri.log_path),
        "status_path": str(ri.status_path),
        "out_dir": out_dir,
        "started": True,
    }

@server.tool()
async def start_preprocess(ctx: Context, in_dir: str, out_dir: str) -> dict:
    ri = await _launch_and_capture("step2_preprocess.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path), "out_dir": out_dir, "started": True}

@server.tool()
async def start_train(ctx: Context, in_dir: str, out_dir: str, epochs: int = 5) -> dict:
    ri = await _launch_and_capture("step3_train.py", "--in-dir", in_dir, "--out-dir", out_dir, "--epochs", str(epochs), out_dir=out_dir)
    return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path), "out_dir": out_dir, "started": True}

@server.tool()
async def start_evaluate(ctx: Context, in_dir: str, out_dir: str) -> dict:
    ri = await _launch_and_capture("step4_evaluate.py", "--in-dir", in_dir, "--out-dir", out_dir, out_dir=out_dir)
    return {"run_id": ri.run_id, "log_path": str(ri.log_path), "status_path": str(ri.status_path), "out_dir": out_dir, "started": True}

@server.tool()
async def poll_logs(ctx: Context, run_id: str, offset: int = 0, limit: int = 2000) -> dict:
    """
    读取本次运行的日志（ndjson），从 offset 开始返回若干行（最多 limit），并返回新的 offset。
    """
    ri = RUNS.get(run_id)
    if not ri:
        return {"error": f"run_id not found: {run_id}"}
    items, new_off = _read_ndjson_from(ri.log_path, offset)
    if limit and len(items) > limit:
        items = items[-limit:]
    return {"run_id": run_id, "items": items, "offset": new_off}

@server.tool()
async def get_status(ctx: Context, run_id: str) -> dict:
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
    ri = RUNS.get(run_id)
    if not ri:
        return {"error": f"run_id not found: {run_id}"}
    with contextlib.suppress(ProcessLookupError):
        ri.proc.terminate()
    return {"run_id": run_id, "terminated": True}

# 启动
if __name__ == "__main__":
    server.run()
