# tools_server.py
from typing import Annotated
from mcp.server.fastmcp import FastMCP
import subprocess, json, sys, pathlib, shlex, os, time, logging
from logging.handlers import TimedRotatingFileHandler

# ========== 日志到文件（按日滚动） ==========
LOG_DIR = pathlib.Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_handler = TimedRotatingFileHandler(LOG_DIR / "tools_server.log", when="D", interval=1, backupCount=7, encoding="utf-8")
logging.basicConfig(level=logging.DEBUG, handlers=[_handler], format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tools_server").debug

log("=== tools_server start ===")
log(f"sys.executable = {sys.executable}")

mcp = FastMCP("local-tools")
SCRIPTS_ROOT = pathlib.Path(__file__).parent / "scripts"

# 统一返回结构
def _json(code:int, out:str, err:str, extra:dict|None=None) -> str:
    payload = {"code": code, "stdout": out or "", "stderr": err or ""}
    if extra: payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)

def run_script(cmd: list[str], timeout_sec: int = 60) -> tuple[int, str, str, float, int]:
    start = time.time()
    log(f"[run_script] exec: {shlex.join(cmd)}")
    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,   # 防止子进程意外读 stdin 挂起
            text=True,
        )
        log(f"[run_script] pid={p.pid}")
        out, err = p.communicate(timeout=timeout_sec)
        dur = time.time() - start
        log(f"[run_script] rc={p.returncode} duration={dur:.2f}s")
        if err: log(f"[run_script][stderr]\n{err}")
        if out: log(f"[run_script][stdout]\n{out[:1000]}")
        return p.returncode, out, err, dur, p.pid
    except subprocess.TimeoutExpired:
        try:
            log(f"[run_script][TIMEOUT] kill pid={p.pid}")
            p.kill()
            out, err = p.communicate(timeout=5)
        except Exception as e:
            out, err = "", f"[kill-exception]{e!r}"
        dur = time.time() - start
        return 124, out or "", (err or "") + f"\nTimeout after {timeout_sec}s", dur, p.pid
    except Exception as e:
        dur = time.time() - start
        log(f"[run_script][EXCEPTION] {e!r} duration={dur:.2f}s")
        return 1, "", f"[EXCEPTION] {e!r}", dur, 0

@mcp.tool()
def resize_image(
    input_path: Annotated[str, "输入图片路径（绝对或相对）"],
    output_path: Annotated[str, "输出图片路径"],
    width: Annotated[int, "目标宽度，像素"],
    height: Annotated[int, "目标高度，像素"],
    timeout: Annotated[int, "超时时间(秒)"] = 60
) -> str:
    try:
        inp = pathlib.Path(input_path)
        outp = pathlib.Path(output_path)
        if not inp.exists():
            return _json(2, "", f"[ERROR] input not found: {inp}", {"args": {"input_path": input_path}})
        outp.parent.mkdir(parents=True, exist_ok=True)
        script = SCRIPTS_ROOT / "resize_image.py"
        code, out, err, dur, pid = run_script(
            [sys.executable, str(script), str(inp), str(outp), str(width), str(height)],
            timeout
        )
        return _json(code, out, err, {"duration_sec": dur, "cwd": os.getcwd(), "pid": pid, "args": {
            "input_path": input_path, "output_path": output_path, "width": width, "height": height
        }})
    except Exception as e:
        return _json(1, "", f"[EXCEPTION] {e!r}")

@mcp.tool()
def csv_summary(
    csv_path: Annotated[str, "CSV 文件路径"],
    delimiter: Annotated[str, "分隔符，默认逗号"] = ",",
    max_rows: Annotated[int, "最多抽样行数"] = 5000,
    timeout: Annotated[int, "超时时间(秒)"] = 60
) -> str:
    try:
        csvp = pathlib.Path(csv_path)
        if not csvp.exists():
            return _json(2, "", f"[ERROR] csv not found: {csvp}", {"args": {"csv_path": csv_path}})
        script = SCRIPTS_ROOT / "csv_summary.py"
        code, out, err, dur, pid = run_script(
            [sys.executable, str(script), str(csvp), delimiter, str(max_rows)],
            timeout
        )
        return _json(code, out, err, {"duration_sec": dur, "pid": pid, "args": {
            "csv_path": csv_path, "delimiter": delimiter, "max_rows": max_rows
        }})
    except Exception as e:
        return _json(1, "", f"[EXCEPTION] {e!r}")

if __name__ == "__main__":
    # 通过 stdio 运行（不要向 stdout 打印日志）
    mcp.run(transport="stdio")
