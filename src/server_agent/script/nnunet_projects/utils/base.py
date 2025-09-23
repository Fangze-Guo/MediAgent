import os
from pathlib import Path
from fnmatch import fnmatch
import re
from typing import Union


def rglob(path, pattern):
    for root, dirs, files in os.walk(path, followlinks=True):
        for filename in files:
            if fnmatch(filename, pattern):
                yield Path(os.path.join(root, filename))


def pid_dx_cx_parser(s, pid_default="#", dx_default="#", cx_default="#"):
    pid = max(re.findall(r'\d+', s), key=len) if re.findall(r'\d+', s) else pid_default
    dx = max(re.findall(r'd\d+', s), key=s.count) if re.findall(r'd\d+', s) else dx_default
    cx = max(re.findall(r'C\d+', s), key=s.count) if re.findall(r'C\d+', s) else cx_default
    return pid, dx, cx


def search(path, pattern, tgt_cx: Union[str, int] = "C2", dst_dir=None):
    all_path = list(rglob(path, pattern))
    data = {}
    for path in all_path:
        pid, dx, cx = pid_dx_cx_parser(str(path.name))
        if pid not in data:
            data[pid] = {}
        if dx not in data[pid]:
            data[pid][dx] = []
        data[pid][dx].append((cx, path))
    
    new_path = []
    for pid, dxs in data.items():
        for dx, cx_paths in dxs.items():
            if isinstance(tgt_cx, str):
                for cx, path in cx_paths:
                    if cx == tgt_cx:
                        new_path.append(path)
                        break
            else:
                cx_paths.sort(key=lambda x: x[0])
                new_path.append(cx_paths[tgt_cx][1])
    
    if dst_dir is not None:
        dst_dir = Path(dst_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        for path in new_path:
            dst_path = dst_dir / path.name
            if not dst_path.exists():
                dst_path.symlink_to(path)
    
    return new_path




# search(Path("/mnt/tmp/1016/og_5"), "*.nii.gz", tgt_cx=-1, dst_dir="/mnt/tmp/1016/b5")
# search("/media/wzt/plum14t/wzt/nnUNetData/20231019/registration_99#SYM#/", "*.nii.gz", tgt_cx="C0", dst_dir="/media/wzt/plum14t/wzt/nnUNetData/20231019/tmp")