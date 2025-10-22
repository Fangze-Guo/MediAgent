#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
强度归一化（基于 MONAI NormalizeIntensity）：
- 对每个病人目录的 C2.nii.gz 做归一化；保持空间信息（CopyInformation）
- C2_mask.nii.gz 原样复制（不做插值/变换）
- ★ 若存在 C0.nii.gz，则原样复制到输出（无覆盖；即使该例被 skip 也尽量 passthrough）
- 默认不覆盖（目标存在则跳过）
- 自动跳过以下划线开头的目录（_logs/_workspace 等）
- 实时日志输出，结束时打印 summary
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import argparse
import json
import time
import shutil

import SimpleITK as sitk
from tqdm import tqdm

# 依赖：pip install monai
try:
    import monai
except Exception as e:
    raise RuntimeError("MONAI is required. Please `pip install monai`.") from e

OVERWRITE = False              # 固定不覆盖
SKIP_UNDERSCORE = True         # 固定跳过以下划线目录

def _log(msg: str) -> None:
    print(msg, flush=True)

def _try_copy_c0(c0_src: Path, c0_dst: Path, overwrite: bool, tag: str, name: str) -> None:
    """尽力把 C0 原样传递；不覆盖已有文件（除非 overwrite=True）。"""
    if not c0_src.exists():
        return
    try:
        c0_dst.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or (not c0_dst.exists()):
            shutil.copy2(c0_src, c0_dst)
            _log(f"[NORM] copy C0 {tag} for {name} -> {c0_dst}")
        else:
            _log(f"[NORM] skip C0 {tag} for {name}: dst exists")
    except Exception as e:
        _log(f"[NORM] warn {name}: C0 {tag} failed: {e}")

def _normalize_c2(c2_in: Path, c2_out: Path) -> None:
    """SimpleITK -> numpy [1,C,Z,Y,X] → MONAI NormalizeIntensity → SimpleITK（保留空间信息）"""
    img = sitk.ReadImage(str(c2_in))
    arr = sitk.GetArrayFromImage(img)          # [Z, Y, X]
    arr = arr[None, ...]                       # [1, Z, Y, X]

    trans = monai.transforms.NormalizeIntensity()
    arr_norm = trans(arr)

    import numpy as np
    arr_norm = np.asarray(arr_norm[0], dtype=np.float32)  # 去通道、定为 float32
    img_norm = sitk.GetImageFromArray(arr_norm, isVector=False)
    img_norm.CopyInformation(img)

    c2_out.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(img_norm, str(c2_out))

def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize intensity for C2; passthrough C2_mask & C0.")
    parser.add_argument("--in-dir", required=True, help="输入根目录（含病人子目录）")
    parser.add_argument("--out-dir", required=True, help="输出根目录")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    if not in_dir.exists():
        _log(f"[NORM] ERROR: in_dir not exists: {in_dir}")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    patients = [p for p in in_dir.iterdir() if p.is_dir()]
    if SKIP_UNDERSCORE:
        patients = [p for p in patients if not p.name.startswith("_")]

    ok: List[str] = []
    skipped: List[str] = []
    failed: List[Tuple[str, str]] = []

    _log(f"[NORM] start: src={in_dir} -> dst={out_dir} | overwrite={OVERWRITE} | skip_underscore={SKIP_UNDERSCORE}")

    t0 = time.time()
    for patient in tqdm(patients, desc="Normalizing", unit="case"):
        name = patient.name
        c2  = patient / "C2.nii.gz"
        c2m = patient / "C2_mask.nii.gz"
        c0  = patient / "C0.nii.gz"           # ★ 可能存在

        out_patient = out_dir / name
        dst_c2  = out_patient / "C2.nii.gz"
        dst_c2m = out_patient / "C2_mask.nii.gz"
        dst_c0  = out_patient / "C0.nii.gz"

        # 必备：C2 + C2_mask
        if not c2.exists() or not c2m.exists():
            _log(f"[NORM] skip {name}: missing C2 or C2_mask")
            # 即便 skip，也尽力传递 C0（passthrough）
            _try_copy_c0(c0, dst_c0, overwrite=False, tag="passthrough", name=name)
            skipped.append(name)
            continue

        # 幂等：C2 已存在且不覆盖 -> 整例跳过；但仍尽力传递 C0
        if dst_c2.exists() and not OVERWRITE:
            if not dst_c2m.exists():
                _log(f"[NORM] warn {name}: dst C2 exists but C2_mask missing; incomplete case (overwrite disabled).")
            _try_copy_c0(c0, dst_c0, overwrite=False, tag="passthrough", name=name)
            _log(f"[NORM] skip {name}: output exists")
            skipped.append(name)
            continue

        try:
            _log(f"[NORM] processing {name}")
            _normalize_c2(c2, dst_c2)

            # 掩膜原样复制（不覆盖）
            dst_c2m.parent.mkdir(parents=True, exist_ok=True)
            if (not dst_c2m.exists()) or OVERWRITE:
                shutil.copy2(c2m, dst_c2m)
            else:
                _log(f"[NORM] skip mask for {name}: dst exists")

            # ★ 同步传递 C0（原样复制）
            _try_copy_c0(c0, dst_c0, overwrite=OVERWRITE, tag="copy", name=name)

            _log(f"[NORM] done {name} -> {dst_c2}")
            ok.append(name)
        except Exception as e:
            _log(f"[NORM] fail {name}: {e}")
            failed.append((name, str(e)))

    summary = {
        "ok": ok,
        "skipped": skipped,
        "failed": [{"patient": p, "error": err} for p, err in failed],
        "counts": {"ok": len(ok), "skipped": len(skipped), "failed": len(failed), "total": len(patients)},
        "out_dir": str(out_dir),
    }
    _log("[NORM] summary: " + json.dumps(summary, ensure_ascii=False))
    _log(f"[NORM] total time: {time.time() - t0:.2f}s")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
