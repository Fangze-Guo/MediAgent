#用来定位data文件夹
from __future__ import annotations
from pathlib import Path
import os

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 数据目录：优先读环境变量 MEDIAGENT_DATA_DIR，默认使用 src/server_new/data（实际数据所在位置）
DATA_DIR = Path(os.getenv("MEDIAGENT_DATA_DIR", str(_PROJECT_ROOT / "src" / "server_new" / "data"))).resolve()

def in_data(*parts: str | os.PathLike) -> Path:
    """在 data/ 下拼路径，例如 in_data('db', 'app.sqlite3')。"""
    return DATA_DIR.joinpath(*parts).resolve()

def ensure_data_dirs(*subdirs: str) -> None:
    """可选：启动时创建常用子目录。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for sd in subdirs:
        (DATA_DIR / sd).mkdir(parents=True, exist_ok=True)

def get_db_path() -> Path:
    """获取数据库文件路径。"""
    return in_data("db", "app.sqlite3")