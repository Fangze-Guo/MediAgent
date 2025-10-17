# -*- coding: utf-8 -*-
"""
utils/base.py —— Windows/Linux 通用基础工具

公开函数（保持你原来的接口）：
- rglob(path, pattern) -> Iterable[Path]
- pid_dx_cx_parser(s, pid_default="#", dx_default="#", cx_default="#") -> Tuple[str, str, str]
- search(path, pattern, tgt_cx: Union[str, int] = "C2", dst_dir=None) -> List[Path]

改进要点：
- search(dst_dir=...) 不再用符号链接，改为“硬链接优先，失败则复制”
- pid/dx/cx 解析大小写兼容（dx: 'd\\d+'；cx: 'C\\d+'）
"""

from __future__ import annotations

import os
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Tuple, Union, Dict, Optional
import shutil


# ----------------------------- 基础文件遍历 -----------------------------

def rglob(path: Union[str, Path], pattern: str) -> Iterable[Path]:
    """
    递归遍历 path，使用 shell 风格的 fnmatch 过滤文件名（不含目录）。
    followlinks=True 可遍历符号链接的目录，但不会创建新的符号链接。
    """
    root = Path(path)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        for filename in filenames:
            if fnmatch(filename, pattern):
                yield Path(dirpath) / filename


# ----------------------------- 名称解析工具 -----------------------------

_re_pid = re.compile(r"\d+")
_re_dx  = re.compile(r"[dD]\d+")
_re_cx  = re.compile(r"[cC]\d+")

def pid_dx_cx_parser(
    s: str,
    pid_default: str = "#",
    dx_default: str = "#",
    cx_default: str = "#",
) -> Tuple[str, str, str]:
    """
    从文件名中提取 pid、dx、cx：
      - pid: 连续数字中“位数最长”的那段
      - dx: 出现次数最多的 'd\\d+'（不区分大小写），返回统一小写前缀 'd'
      - cx: 出现次数最多的 'C\\d+'（不区分大小写），返回统一大写前缀 'C'
    若未匹配到，对应项返回默认值（'#'）
    """
    # pid：选长度最长的数字串
    pid_matches = _re_pid.findall(s)
    pid = max(pid_matches, key=len) if pid_matches else pid_default

    # dx/cx：选“出现次数最多”的那一个（与原逻辑一致），忽略大小写
    dx_matches = _re_dx.findall(s)
    cx_matches = _re_cx.findall(s)

    if dx_matches:
        # 统计出现次数，选择次数最多的；同频任选第一个
        counts: Dict[str, int] = {}
        for m in dx_matches:
            key = m.lower()  # 统一小写统计
            counts[key] = counts.get(key, 0) + 1
        dx_key = max(counts.items(), key=lambda kv: kv[1])[0]  # 'd\d+'
        dx = dx_key.lower()  # 统一返回小写 d 前缀
    else:
        dx = dx_default

    if cx_matches:
        counts: Dict[str, int] = {}
        for m in cx_matches:
            key = m.upper()  # 统一大写统计
            counts[key] = counts.get(key, 0) + 1
        cx_key = max(counts.items(), key=lambda kv: kv[1])[0]  # 'C\d+'
        cx = cx_key.upper()  # 统一返回大写 C 前缀
    else:
        cx = cx_default

    return pid, dx, cx


# ----------------------------- 链接/复制工具 -----------------------------

def _link_or_copy(src: Path, dst: Path) -> None:
    """
    Windows 友好：优先创建硬链接（同盘且允许时更快），失败则回退为复制。
    从不创建符号链接（symlink），避免权限问题。
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        if hasattr(os, "link"):
            os.link(src, dst)
            return
    except Exception:
        pass
    shutil.copy2(src, dst)


# ----------------------------- 高层搜索与选择 -----------------------------

def search(
    path: Union[str, Path],
    pattern: str,
    tgt_cx: Union[str, int] = "C2",
    dst_dir: Optional[Union[str, Path]] = None,
) -> List[Path]:
    """
    在 path 下递归匹配 pattern，按 (pid, dx) 分组，并为每组挑选一个目标 cx：
      - 若 tgt_cx 是字符串（如 "C2"），优先选择与该 cx 完全匹配的条目
      - 若 tgt_cx 是整数 n，则按 cx 的字典序排序后取第 n 个（例如 -1 取最后一个）
    返回选中的 Path 列表；若传入 dst_dir，则把选中的文件链接/复制到该目录下并返回其原始路径列表。

    与原实现保持一致，但：
      - 目标目录不再创建符号链接，改为“硬链接优先、否则复制”，更适配 Windows。
    """
    root = Path(path)
    all_paths = list(rglob(root, pattern))

    # 聚合：data[pid][dx] -> List[(cx, Path)]
    data: Dict[str, Dict[str, List[Tuple[str, Path]]]] = {}
    for p in all_paths:
        name = p.name
        pid, dx, cx = pid_dx_cx_parser(name)
        data.setdefault(pid, {}).setdefault(dx, []).append((cx, p))

    picked: List[Path] = []
    for pid, dxs in data.items():
        for dx, cx_paths in dxs.items():
            # 目标选择
            if isinstance(tgt_cx, str):
                # 期望精确匹配（如 "C2"），若无则跳过该组
                for cx, p in cx_paths:
                    if cx == tgt_cx:
                        picked.append(p)
                        break
            else:
                # 按 cx 字典序排序后选第 n 个
                cx_paths_sorted = sorted(cx_paths, key=lambda x: x[0])
                if not cx_paths_sorted:
                    continue
                # 支持负索引
                idx = tgt_cx
                try:
                    picked.append(cx_paths_sorted[idx][1])
                except Exception:
                    # 索引越界则跳过
                    continue

    if dst_dir is not None:
        dst_dir = Path(dst_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        for p in picked:
            dst_path = dst_dir / p.name
            if not dst_path.exists():
                _link_or_copy(p, dst_path)

    return picked
