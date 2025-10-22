#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对每个病人目录中的 C2.nii.gz / C2_mask.nii.gz 做规则化：
- 重采样到 1.0×1.0×1.0 mm
- DICOMOrient 到 LPS
- direction 设为 identity
- origin 设为 (0,0,0)
- 图像插值：B-Spline；掩膜插值：最近邻
- 默认不覆盖（若输出 C2 已存在则整例跳过）
- 自动跳过以下划线开头的目录（_logs/_workspace 等）
- 额外：若发现 C0.nii.gz，原样复制到输出目录（无覆盖），即使该例被 skip 也尽力传递（passthrough）
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


OUT_SPACING = (1.0, 1.0, 1.0)  # 固定 1mm
ORIENTATION = "LPS"            # 固定 LPS
IDENTITY_3X3 = (1.0, 0.0, 0.0,
                0.0, 1.0, 0.0,
                0.0, 0.0, 1.0)
ZERO_ORIGIN = (0.0, 0.0, 0.0)
OVERWRITE = False              # 固定不覆盖
SKIP_UNDERSCORE = True         # 固定跳过以 _ 开头的目录
EPS = 1e-6                     # spacing 比较容差


def _log(msg: str) -> None:
    print(msg, flush=True)


def _need_resample_spacing(orig_spacing: Tuple[float, float, float]) -> bool:
    return any(abs(os - ns) > EPS for os, ns in zip(orig_spacing, OUT_SPACING))


def _resample_one(
    src_img_path: Path,
    dst_img_path: Path,
    is_mask: bool,
) -> None:
    img = sitk.ReadImage(str(src_img_path))
    dim = img.GetDimension()
    if dim != 3:
        raise ValueError(f"Only 3D supported, got dim={dim} for {src_img_path}")

    # 1) spacing 归一化到 1mm
    orig_size = img.GetSize()
    orig_spacing = img.GetSpacing()

    if _need_resample_spacing(orig_spacing):
        out_size = [
            int(round(osz * osp / nsp))
            for osz, osp, nsp in zip(orig_size, orig_spacing, OUT_SPACING)
        ]

        res = sitk.ResampleImageFilter()
        res.SetOutputSpacing(OUT_SPACING)
        res.SetSize(out_size)
        res.SetOutputDirection(img.GetDirection())
        res.SetOutputOrigin(img.GetOrigin())
        res.SetTransform(sitk.Transform())

        if is_mask:
            res.SetInterpolator(sitk.sitkNearestNeighbor)
        else:
            res.SetInterpolator(sitk.sitkBSpline)

        img = res.Execute(img)

    # 2) 坐标系规范化：先变换到 LPS
    img = sitk.DICOMOrient(img, ORIENTATION)
    # 3) direction 设为 identity
    img.SetDirection(IDENTITY_3X3)
    # 4) origin 设为 (0,0,0)
    img.SetOrigin(ZERO_ORIGIN)

    # 5) 写出
    dst_img_path.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(img, str(dst_img_path))


def _try_copy_c0(c0_src: Path, c0_dst: Path, overwrite: bool, tag: str, name: str) -> None:
    """尽力把 C0 原样传递；不覆盖已有文件（除非 overwrite=True）。"""
    if not c0_src.exists():
        return
    try:
        c0_dst.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or (not c0_dst.exists()):
            shutil.copy2(c0_src, c0_dst)
            _log(f"[RESAMPLE] copy C0 {tag} for {name} -> {c0_dst}")
        else:
            _log(f"[RESAMPLE] skip C0 {tag} for {name}: dst exists")
    except Exception as e:
        _log(f"[RESAMPLE] warn {name}: C0 {tag} failed: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resample C2 & C2_mask to 1mm LPS/identity/zero-origin (and passthrough C0)")
    parser.add_argument("--in-dir", required=True, help="输入根目录（含病人子目录）")
    parser.add_argument("--out-dir", required=True, help="输出根目录")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    if not in_dir.exists():
        _log(f"[RESAMPLE] ERROR: in_dir not exists: {in_dir}")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    patients = [p for p in in_dir.iterdir() if p.is_dir()]
    if SKIP_UNDERSCORE:
        patients = [p for p in patients if not p.name.startswith("_")]

    ok: List[str] = []
    skipped: List[str] = []
    failed: List[Tuple[str, str]] = []

    _log(f"[RESAMPLE] start: src={in_dir} -> dst={out_dir} | spacing={OUT_SPACING} | overwrite={OVERWRITE} | skip_underscore={SKIP_UNDERSCORE}")

    t0 = time.time()
    for patient in tqdm(patients, desc="Resampling", unit="case"):
        name = patient.name
        c2  = patient / "C2.nii.gz"
        c2m = patient / "C2_mask.nii.gz"
        c0  = patient / "C0.nii.gz"  # ★ 可能存在的 C0

        out_patient = out_dir / name
        dst_c2  = out_patient / "C2.nii.gz"
        dst_c2m = out_patient / "C2_mask.nii.gz"
        dst_c0  = out_patient / "C0.nii.gz"

        if not c2.exists() or not c2m.exists():
            _log(f"[RESAMPLE] skip {name}: missing C2 or C2_mask")
            # 即便整例被跳过，也尽力传递 C0（passthrough）
            _try_copy_c0(c0, dst_c0, overwrite=False, tag="passthrough", name=name)
            skipped.append(name)
            continue

        if dst_c2.exists() and not OVERWRITE:
            # 若目标 C2 已存在，不做重采样；但仍尝试传递 C0
            if not dst_c2m.exists():
                _log(f"[RESAMPLE] warn {name}: dst C2 exists but C2_mask missing; this case will be left incomplete (overwrite disabled).")
            _try_copy_c0(c0, dst_c0, overwrite=False, tag="passthrough", name=name)
            _log(f"[RESAMPLE] skip {name}: output exists")
            skipped.append(name)
            continue

        try:
            _log(f"[RESAMPLE] processing {name}")
            _resample_one(c2,  dst_c2,  is_mask=False)
            _resample_one(c2m, dst_c2m, is_mask=True)
            # 同步传递 C0（原样复制）
            _try_copy_c0(c0, dst_c0, overwrite=OVERWRITE, tag="copy", name=name)

            _log(f"[RESAMPLE] done {name} -> {dst_c2}")
            ok.append(name)
        except Exception as e:
            _log(f"[RESAMPLE] fail {name}: {e}")
            failed.append((name, str(e)))

    summary = {
        "ok": ok,
        "skipped": skipped,
        "failed": [{"patient": p, "error": err} for p, err in failed],
        "counts": {"ok": len(ok), "skipped": len(skipped), "failed": len(failed), "total": len(patients)},
        "out_dir": str(out_dir),
    }
    _log("[RESAMPLE] summary: " + json.dumps(summary, ensure_ascii=False))
    _log(f"[RESAMPLE] total time: {time.time() - t0:.2f}s")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
