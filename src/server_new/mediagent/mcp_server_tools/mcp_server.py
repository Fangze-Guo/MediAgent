# mcp_server.py
from __future__ import annotations
from fastmcp import Server

# 1) 创建 MCP 服务器实例（固定使用 stdio）
server = Server("mediagent-mcp")

# 2) 这里预留工具注册位：以后直接按下面的风格添加即可
# === 新增：注册脚本工具（基于当前文件同级的 tools/ 目录） ===
# mcp_server.py 里添加/替换如下
# mcp_server.py
import asyncio, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE / "tools"

async def _stream_script(pyfile: str, *cli_args: str):
    # 统一使用启动本服务器的解释器（与当前虚拟环境完全一致）
    python_exe = sys.executable

    cmd = [python_exe, "-u", str(TOOLS_DIR / pyfile), *cli_args]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"  # 强制无缓冲，配合 -u 实时输出

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
        cwd=str(HERE),
    )
    assert proc.stdout
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        yield line.decode("utf-8", "replace").rstrip("\n")

    rc = await proc.wait()
    yield {"exit_code": rc}


@server.tool(streaming=True)
async def ingest(source: str, out_dir: str):
    """step1: 采集 -> 写入 out_dir/raw/*"""
    async for out in _stream_script("step1_ingest.py", "--source", source, "--out-dir", out_dir):
        yield out

@server.tool(streaming=True)
async def preprocess(in_dir: str, out_dir: str):
    """step2: 预处理 -> 读 in_dir/raw/* ; 写入 out_dir/clean/*"""
    async for out in _stream_script("step2_preprocess.py", "--in-dir", in_dir, "--out-dir", out_dir):
        yield out

@server.tool(streaming=True)
async def train(in_dir: str, out_dir: str, epochs: int = 5):
    """step3: 训练 -> 读 in_dir/clean/clean.txt ; 写入 out_dir/model/*"""
    async for out in _stream_script("step3_train.py", "--in-dir", in_dir, "--out-dir", out_dir, "--epochs", str(epochs)):
        yield out

@server.tool(streaming=True)
async def evaluate(in_dir: str, out_dir: str):
    """step4: 评估 -> 读 in_dir/model/model.bin ; 写入 out_dir/report.json"""
    async for out in _stream_script("step4_evaluate.py", "--in-dir", in_dir, "--out-dir", out_dir):
        yield out



# 3) 启动（stdio 传输层）
if __name__ == "__main__":
# 以子进程方式被其他模块连接：client 会通过 stdin/stdout 与本进程通信
    server.run_stdio()
