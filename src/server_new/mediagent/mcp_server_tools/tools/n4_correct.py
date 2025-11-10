#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from typing import Optional, Sequence, Union, Tuple, List, Dict
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

# -------- 新增：查找 c2/c2_mask 的兼容逻辑（支持向下一层） --------
def _find_cases_one_level(patient_dir: Path) -> List[Dict[str, Path]]:
    """
    返回待处理的条目列表。每条包含：
      - rel: 输出时在病人目录下的相对子路径（"" 表示根层；或子文件夹名）
      - img: c2/c2.nii.gz 的路径
      - mask: c2_mask/C2_mask.nii.gz 的路径
      - c0: 若同层存在 C0 文件则给出其路径，否则可能缺失
    仅向下一层子目录查找（不会更深）。
    """
    entries: List[Dict[str, Path]] = []

    def pick_case(base: Path, rel: str):
        # 支持大小写：c2/C2；c2_mask/C2_mask；c0/C0
        img = None
        mask = None
        c0 = None
        for name in ("c2.nii.gz", "C2.nii.gz"):
            p = base / name
            if p.exists():
                img = p
                break
        for name in ("c2_mask.nii.gz", "C2_mask.nii.gz"):
            p = base / name
            if p.exists():
                mask = p
                break
        for name in ("c0.nii.gz", "C0.nii.gz"):
            p = base / name
            if p.exists():
                c0 = p
                break
        if img and mask:
            d = {"rel": Path(rel), "img": img, "mask": mask}
            if c0 is not None:
                d["c0"] = c0
            entries.append(d)

    # 1) 先尝试根层
    pick_case(patient_dir, "")

    # 2) 若根层没有，就尝试下一层所有子目录
    if not entries:
        for sub in sorted([p for p in patient_dir.iterdir() if p.is_dir()]):
            pick_case(sub, sub.name)

    return entries

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

    patients = [p for p in reg_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]

    ok: List[str] = []
    skipped: List[str] = []
    failed: List[Tuple[str, str]] = []

    _log(f"[N4] start batch: src={reg_dir} -> dst={n4_dir} | overwrite={overwrite} | kernel_radius={kernel_radius} | save_dilated_mask={save_dilated_mask}")
    for patient_dir in tqdm(patients, desc="N4 correcting", unit="case"):
        patient = patient_dir.name

        # 找出该病例需要处理的“层”（根层或下一层日期目录）
        cases = _find_cases_one_level(patient_dir)
        if not cases:
            _log(f"[N4] skip {patient}: missing C2/C2_mask at root and one-level deeper")
            skipped.append(patient)
            continue

        # 逐个层处理（可能是根层，也可能是多个日期文件夹）
        for case in cases:
            rel: Path = case["rel"]
            img: Path = case["img"]
            msk: Path = case["mask"]
            c0_src: Optional[Path] = case.get("c0")

            out_dir = n4_dir / patient / rel
            dst_img = out_dir / img.name  # 保持原大小写（C2 或 c2）
            dst_msk = out_dir / msk.name

            # 幂等控制
            if dst_img.exists() and not overwrite:
                _log(f"[N4] skip {patient}/{rel.as_posix() or '.'}: output exists")
                # 即便跳过，也尽力传递 C0
                if c0_src is not None:
                    _try_copy_c0(c0_src, out_dir / c0_src.name, overwrite=False, tag="passthrough", name=f"{patient}/{rel.as_posix() or '.'}")
                skipped.append(f"{patient}/{rel.as_posix() or '.'}")
                continue

            try:
                _log(f"[N4] processing {patient}/{rel.as_posix() or '.'}")
                n4_correct_one(
                    src_image_path=img,
                    src_mask_path=msk,
                    dst_image_path=dst_img,
                    dst_mask_path=dst_msk,
                    kernel_radius=kernel_radius,
                    save_dilated_mask=save_dilated_mask,
                )
                if c0_src is not None:
                    _try_copy_c0(c0_src, out_dir / c0_src.name, overwrite=overwrite, tag="copy", name=f"{patient}/{rel.as_posix() or '.'}")
                _log(f"[N4] done {patient}/{rel.as_posix() or '.'} -> {dst_img}")
                ok.append(f"{patient}/{rel.as_posix() or '.'}")
            except Exception as e:
                _log(f"[N4] fail {patient}/{rel.as_posix() or '.'}: {e}")
                failed.append((f"{patient}/{rel.as_posix() or '.'}", str(e)))

    summary = {
        "ok": ok,
        "skipped": skipped,
        "failed": [{"patient": p, "error": err} for p, err in failed],
        "counts": {"ok": len(ok), "skipped": len(skipped), "failed": len(failed), "total_patients": len(patients)},
    }
    _log("[N4] summary: " + json.dumps(summary, ensure_ascii=False))
    return summary

def main() -> int:
    parser = argparse.ArgumentParser(description="Batch N4 bias field correction (root or one-level deeper).")
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
        return 0
    except Exception as e:
        _log(f"[N4] FATAL: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
