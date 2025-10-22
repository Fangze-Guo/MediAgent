#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from typing import Optional, Sequence, Union, Tuple, List
import argparse
import sys
import json
import time
import shutil

# 依赖：pip install SimpleITK tqdm
import SimpleITK as sitk
from tqdm import tqdm

KernelT = Optional[Union[int, Sequence[int]]]

def _log(msg: str) -> None:
    # 让 MCP 侧的 _launch_and_capture 捕获到 stdout 并写入 .ndjson
    print(msg, flush=True)

def _parse_kernel_radius(s: Optional[str], dim: int = 3) -> Optional[Tuple[int, ...]]:
    if s is None or s == "":
        return None
    s = str(s).strip()
    if "," in s:
        parts = [int(x.strip()) for x in s.split(",") if x.strip() != ""]
        if len(parts) != dim:
            raise ValueError(f"--kernel-radius 需要 {dim} 个整数，如 3,3,1；实际为 {parts}")
        return tuple(parts)
    else:
        v = int(s)
        return (v,) * dim

def _binary01(mask: sitk.Image) -> sitk.Image:
    # 任意非零视为前景，更稳，不受像素类型上界影响
    return sitk.Cast(sitk.NotEqual(mask, 0), sitk.sitkUInt8)


def n4_correct_one(
    src_image_path: Path,
    src_mask_path: Path,
    dst_image_path: Path,
    dst_mask_path: Path,
    kernel_radius: Optional[Tuple[int, ...]] = None,
    save_dilated_mask: bool = False,
) -> None:
    image = sitk.Cast(sitk.ReadImage(str(src_image_path)), sitk.sitkFloat32)
    mask  = sitk.Cast(sitk.ReadImage(str(src_mask_path)),  sitk.sitkUInt8)

    if image.GetSize() != mask.GetSize():
        raise ValueError(f"Image/Mask size mismatch: {image.GetSize()} vs {mask.GetSize()} for {src_image_path}")

    mask = _binary01(mask)

    if kernel_radius is not None:
        mask_for_n4 = sitk.BinaryDilate(mask, kernelRadius=kernel_radius, foregroundValue=1, backgroundValue=0)
    else:
        mask_for_n4 = mask

    n4 = sitk.N4BiasFieldCorrectionImageFilter()
    corrected = n4.Execute(image, mask_for_n4)

    dst_image_path.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(corrected, str(dst_image_path))

    dst_mask_path.parent.mkdir(parents=True, exist_ok=True)
    if save_dilated_mask and (kernel_radius is not None):
        sitk.WriteImage(sitk.Cast(mask_for_n4, sitk.sitkUInt8), str(dst_mask_path))
    else:
        shutil.copy2(src_mask_path, dst_mask_path)


def _try_copy_c0(c0_src: Path, c0_dst: Path, overwrite: bool, tag: str, name: str) -> None:
    """尽力把 C0 原样传递；不覆盖已有文件（除非 overwrite=True）。"""
    if not c0_src.exists():
        return
    try:
        c0_dst.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or (not c0_dst.exists()):
            shutil.copy2(c0_src, c0_dst)
            _log(f"[N4] copy C0 {tag} for {name} -> {c0_dst}")
        else:
            _log(f"[N4] skip C0 {tag} for {name}: dst exists")
    except Exception as e:
        _log(f"[N4] warn {name}: C0 {tag} failed: {e}")


def n4_batch_on_reg_dir(
    reg_dir: Path,
    n4_dir: Path,
    overwrite: bool = False,
    kernel_radius: Optional[Tuple[int, ...]] = None,
    save_dilated_mask: bool = False,
) -> dict:
    reg_dir = Path(reg_dir)
    n4_dir = Path(n4_dir)
    n4_dir.mkdir(parents=True, exist_ok=True)

    # ✅ 只处理“非下划线开头”的子目录
    patients = [p for p in reg_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]

    ok: List[str] = []
    skipped: List[str] = []
    failed: List[Tuple[str, str]] = []

    _log(f"[N4] start batch: src={reg_dir} -> dst={n4_dir} | overwrite={overwrite} | kernel_radius={kernel_radius} | save_dilated_mask={save_dilated_mask}")
    for patient_dir in tqdm(patients, desc="N4 correcting", unit="case"):
        name = patient_dir.name
        c2_path = patient_dir / "C2.nii.gz"
        c2_mask_path = patient_dir / "C2_mask.nii.gz"
        c0_path = patient_dir / "C0.nii.gz"  # ★ C0 输入

        out_patient_dir = n4_dir / name
        dst_c2_path = out_patient_dir / "C2.nii.gz"
        dst_c2_mask_path = out_patient_dir / "C2_mask.nii.gz"
        dst_c0_path = out_patient_dir / "C0.nii.gz"  # ★ C0 输出

        # 必要文件检查（C2 & C2_mask）
        if not c2_path.exists() or not c2_mask_path.exists():
            _log(f"[N4] skip {name}: missing C2 or C2_mask")
            # 即便整例跳过，也尽力传递 C0
            _try_copy_c0(c0_path, dst_c0_path, overwrite=False, tag="passthrough", name=name)
            skipped.append(name)
            continue

        # 幂等：目标已存在且不覆盖 -> 跳过，但仍尝试传递 C0
        if dst_c2_path.exists() and not overwrite:
            _log(f"[N4] skip {name}: output exists")
            _try_copy_c0(c0_path, dst_c0_path, overwrite=False, tag="passthrough", name=name)
            skipped.append(name)
            continue

        try:
            _log(f"[N4] processing {name}")
            n4_correct_one(
                src_image_path=c2_path,
                src_mask_path=c2_mask_path,
                dst_image_path=dst_c2_path,
                dst_mask_path=dst_c2_mask_path,
                kernel_radius=kernel_radius,
                save_dilated_mask=save_dilated_mask,
            )

            # N4 完成后，同步传递 C0（原样复制）
            _try_copy_c0(c0_path, dst_c0_path, overwrite=overwrite, tag="copy", name=name)

            _log(f"[N4] done {name} -> {dst_c2_path}")
            ok.append(name)
        except Exception as e:
            _log(f"[N4] fail {name}: {e}")
            failed.append((name, str(e)))

    summary = {
        "ok": ok,
        "skipped": skipped,
        "failed": [{"patient": p, "error": err} for p, err in failed],
        "counts": {"ok": len(ok), "skipped": len(skipped), "failed": len(failed), "total": len(patients)},
    }
    _log("[N4] summary: " + json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch N4 bias field correction")
    parser.add_argument("--in-dir", required=True, help="输入根目录（含病人子目录）")
    parser.add_argument("--out-dir", required=True, help="输出根目录")
    parser.add_argument("--kernel-radius", default=None, help="掩膜膨胀半径：整数或以逗号分隔的三元组，如 3 或 3,3,1")
    parser.add_argument("--overwrite", action="store_true", help="若目标已存在则重新计算")
    parser.add_argument("--save-dilated-mask", action="store_true", help="输出保存膨胀后的 mask（默认保存原始 mask）")

    args = parser.parse_args()
    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)

    if not in_dir.exists():
        _log(f"[N4] ERROR: in_dir not exists: {in_dir}")
        return 2

    try:
        kr = _parse_kernel_radius(args.kernel_radius, dim=3)
    except Exception as e:
        _log(f"[N4] ERROR: bad --kernel-radius: {e}")
        return 3

    t0 = time.time()
    try:
        _ = n4_batch_on_reg_dir(
            reg_dir=in_dir,
            n4_dir=out_dir,
            overwrite=bool(args.overwrite),
            kernel_radius=kr,
            save_dilated_mask=bool(args.save_dilated_mask),
        )
        _log(f"[N4] total time: {time.time()-t0:.2f}s")
        # 进程退出码：有失败也允许为 0；如需强制失败=> 设定阈值后 return 非 0
        return 0
    except Exception as e:
        _log(f"[N4] FATAL: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
