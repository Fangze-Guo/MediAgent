#用来定位data文件夹
from __future__ import annotations
from pathlib import Path
import os

# 以当前文件（在 mediagent 包内）为基准，向上一级就是 server_new/
_SERVER_ROOT = Path(__file__).resolve().parents[1]

# 默认 data 在 server_new/ 下；可用环境变量覆盖
DATA_DIR = Path(os.getenv("MEDIAGENT_DATA_DIR", str(_SERVER_ROOT / "data"))).resolve()

def in_data(*parts: str | os.PathLike) -> Path:
    """在 data/ 下拼路径，例如 in_data('db', 'app.sqlite3')。"""
    return DATA_DIR.joinpath(*parts).resolve()

def ensure_data_dirs(*subdirs: str) -> None:
    """可选：启动时创建常用子目录。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for sd in subdirs:
        (DATA_DIR / sd).mkdir(parents=True, exist_ok=True)
