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

# —— 新增：定位 mediagent 目录，并在其下拼路径 ——
def _find_mediagent_dir(pkg_name: str = "mediagent") -> Path:
    """
    从当前文件起始，向上寻找名为 pkg_name 的目录。
    优先返回环境变量 MEDIAGENT_DIR，若未设置则从 __file__ 向上匹配目录名。
    """
    # # 1) 环境变量优先
    # env = os.getenv("MEDIAGENT_DIR")
    # if env:
    #     return Path(env).resolve()

    # 2) 以当前文件为起点向上找目录名为 mediagent 的层级
    here = Path(__file__).resolve()
    for anc in (here, *here.parents):
        if anc.name == pkg_name:
            return anc

    # 3) 兜底：通常当前文件就在 mediagent 包内，parent 即 mediagent/
    return here.parent


# mediagent 包根目录（可被环境变量 MEDIAGENT_DIR 覆盖）
MEDIAGENT_DIR = _find_mediagent_dir()

def in_mediagent(*parts: str | os.PathLike) -> Path:
    """
    在 mediagent/ 下拼接路径，例如 in_mediagent('configs', 'default.yaml')。
    """
    return MEDIAGENT_DIR.joinpath(*parts).resolve()

