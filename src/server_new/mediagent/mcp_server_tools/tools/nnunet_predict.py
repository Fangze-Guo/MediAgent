#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/nnunet_predict.py

功能：
- 从 --in-dir（配准输出）批量读取病人目录，要求每例同时存在 C0.nii.gz 与 C2.nii.gz；
- 调用 nnunet_projects.predict.main_worker(C2 -> C2_mask) 完成推理；
- 在 --out-dir 下仅输出病人子目录和三件文件：C0.nii.gz、C2.nii.gz、C2_mask.nii.gz；
- 中间产物统一放在 --out-dir/_workspace/<Patient>/，不污染病人目录；
- 跳过输入中的 "_logs" 目录；
- 进程内打印的每一行会被 MCP 包装成 ndjson 存到 out_dir/_logs 中（见 mcp_server.py 的 _launch_and_capture）。

用法：
python tools/nnunet_predict.py --in-dir <reg_dir> --out-dir <nnunet_out> [--overwrite-mask]
"""
from __future__ import annotations
import argparse
import sys
import shutil
from pathlib import Path
from datetime import datetime

# ========== 动态定位 nnunet_projects 包 ==========
HERE = Path(__file__).resolve().parent
# 你可以在这里添加更多候选位置（例如项目根、上级目录）
NNUNET_PKG_CANDIDATES = [
    HERE.parent / "nnunet_projects",    # <repo_root>/nnunet_projects
    HERE / "nnunet_projects",           # tools/nnunet_projects（如放在 tools 同级）
]

for cand in NNUNET_PKG_CANDIDATES:
    if cand.exists() and str(cand.parent) not in sys.path:
        sys.path.insert(0, str(cand.parent))

try:
    from nnunet_projects import predict
    print(f"[import] predict at: {Path(predict.__file__).resolve()}", flush=True)
except Exception as e:
    raise ImportError(f"无法导入 nnunet_projects.predict：{e}")

# ========== 常量 ==========
IMAGE_NAME_C0    = "C0.nii.gz"
IMAGE_NAME_C2    = "C2.nii.gz"
OUTPUT_MASK_NAME = "C2_mask.nii.gz"

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def copy_if_needed(src: Path, dst: Path) -> None:
    """如果目标不存在则复制；存在则保留（不覆盖）"""
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在：{src}")
    if not dst.exists():
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)

def run_once(patient_dir: Path, out_root: Path, work_root: Path, overwrite_mask: bool) -> tuple[bool, str]:
    """处理单个病人；返回 (ok, message)"""
    pname = patient_dir.name
    c0 = patient_dir / IMAGE_NAME_C0
    c2 = patient_dir / IMAGE_NAME_C2
    if not (c0.exists() and c2.exists()):
        miss = []
        if not c0.exists(): miss.append(IMAGE_NAME_C0)
        if not c2.exists(): miss.append(IMAGE_NAME_C2)
        return False, f"[{pname}] 跳过：缺少 {', '.join(miss)}"

    out_patient = out_root / pname
    ensure_dir(out_patient)
    work_dir = work_root / pname
    ensure_dir(work_dir)

    mask_out = out_patient / OUTPUT_MASK_NAME
    if mask_out.exists() and not overwrite_mask:
        # 不重跑推理，但补齐 C0/C2
        try:
            copy_if_needed(c0, out_patient / IMAGE_NAME_C0)
            copy_if_needed(c2, out_patient / IMAGE_NAME_C2)
        except Exception as e:
            return False, f"[{pname}] 复制 C0/C2 失败：{e}"
        return True, f"[{pname}] 已存在 mask，未覆盖；已确保 C0/C2 就位"

    # 执行推理
    log(f"[{pname}] 开始推理：{IMAGE_NAME_C2} -> {OUTPUT_MASK_NAME}")
    predict.main_worker(c2, mask_out, work_dir=work_dir)
    if not mask_out.exists():
        return False, f"[{pname}] 失败：推理后未找到输出 {mask_out}"

    # 补齐 C0 / C2
    copy_if_needed(c0, out_patient / IMAGE_NAME_C0)
    copy_if_needed(c2, out_patient / IMAGE_NAME_C2)

    return True, f"[{pname}] 完成"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir",  required=True, help="配准输出根目录（含病人子目录）")
    ap.add_argument("--out-dir", required=True, help="本步输出根目录（只包含病人目录与三件文件）")
    ap.add_argument("--overwrite-mask", action="store_true", help="若已存在 C2_mask.nii.gz，是否覆盖重算")
    args = ap.parse_args()

    reg_dir = Path(args.in_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    work_root = out_dir / "_workspace"

    if not reg_dir.exists():
        raise FileNotFoundError(f"输入目录不存在：{reg_dir}")
    ensure_dir(out_dir)
    ensure_dir(work_root)

    log(f"输入目录：{reg_dir}")
    log(f"输出目录：{out_dir}")
    log(f"工作根目录：{work_root}")
    log(f"覆盖已存在 mask：{bool(args.overwrite_mask)}")

    total = 0; done = 0; skipped = 0; errors = 0

    for patient_dir in sorted(reg_dir.iterdir()):
        if not patient_dir.is_dir():
            continue
        if patient_dir.name == "_logs":
            continue  # 跳过日志目录
        total += 1
        ok, msg = run_once(patient_dir, out_dir, work_root, args.overwrite_mask)
        log(msg)
        if ok:
            if "已存在 mask" in msg:
                skipped += 1
            else:
                done += 1
        else:
            errors += 1

    log("==== nnUNet 推理完成 ====")
    log(f"总病人数：{total} | 成功：{done} | 跳过（已存在且未覆盖）：{skipped} | 失败：{errors}")

if __name__ == "__main__":
    main()
