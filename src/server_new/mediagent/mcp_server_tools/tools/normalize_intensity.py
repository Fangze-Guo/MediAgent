#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
强度归一化（基于 MONAI NormalizeIntensity）——兼容两种结构，并按日期逐一处理：
A) <patient>/C2.nii.gz, C2_mask.nii.gz [, C0.nii.gz]                 → 输出到 <out>/<patient>/
B) <patient>/<date>/C2.nii.gz, C2_mask.nii.gz [, C0.nii.gz] (多组)   → 输出到 <out>/<patient>/<date>/

- 先在病例根目录找一组；然后下探一层子目录，逐一查找所有可处理的日期文件夹
- 兼容大小写：C2/c2、C2_mask/c2_mask、C0/c0
- C0 优先取同层，没有则回退到病例根目录
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Optional, Iterable
import argparse
import json
import time
import shutil

import numpy as np
import SimpleITK as sitk
from tqdm import tqdm

# 依赖：pip install monai
try:
    import monai
except Exception as e:
    raise RuntimeError("MONAI is required. Please `pip install monai`.") from e

OVERWRITE = False
SKIP_UNDERSCORE = True

def _log(msg: str) -> None:
    print(msg, flush=True)

def _try_copy_c0(c0_src: Optional[Path], c0_dst: Path, overwrite: bool, tag: str, case_name: str) -> None:
    """尽力把 C0 原样传递；不覆盖已有文件（除非 overwrite=True）。"""
    if not c0_src or not c0_src.exists():
        return
    try:
        c0_dst.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or (not c0_dst.exists()):
            shutil.copy2(c0_src, c0_dst)
            _log(f"[NORM] copy C0 {tag} for {case_name} -> {c0_dst}")
        else:
            _log(f"[NORM] skip C0 {tag} for {case_name}: dst exists")
    except Exception as e:
        _log(f"[NORM] warn {case_name}: C0 {tag} failed: {e}")

def _normalize_c2(c2_in: Path, c2_out: Path) -> None:
    """SimpleITK -> numpy [1,Z,Y,X] → MONAI NormalizeIntensity → SimpleITK（保留空间信息）"""
    img = sitk.ReadImage(str(c2_in))
    arr = sitk.GetArrayFromImage(img)   # [Z, Y, X]
    arr = arr[None, ...]                # [1, Z, Y, X]

    trans = monai.transforms.NormalizeIntensity()
    arr_norm = trans(arr)

    arr_norm = np.asarray(arr_norm[0], dtype=np.float32)  # 去通道、定为 float32
    img_norm = sitk.GetImageFromArray(arr_norm, isVector=False)
    img_norm.CopyInformation(img)

    c2_out.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(img_norm, str(c2_out))

# ---------- 枚举病例下的所有可处理“日期用例” ----------
_C2_NAMES  = ("C2.nii.gz", "c2.nii.gz")
_MSK_NAMES = ("C2_mask.nii.gz", "c2_mask.nii.gz")
_C0_NAMES  = ("C0.nii.gz", "c0.nii.gz")

def _pick_existing(base: Path, names: Iterable[str]) -> Optional[Path]:
    for n in names:
        p = base / n
        if p.exists():
            return p
    return None

def enumerate_cases(patient_dir: Path) -> List[Tuple[Optional[str], Path, Path, Optional[Path]]]:
    """
    返回一组列表：[(date_name, c2, c2_mask, c0), ...]
    - date_name 为 None 表示根目录直接有一组 C2/C2_mask
    - 之后遍历一层子目录（跳过 _ 开头），每个目录若有 C2/C2_mask 则作为一个 case
    - 每个子目录的 C0 优先取本目录；没有则回退到病例根目录
    """
    cases: List[Tuple[Optional[str], Path, Path, Optional[Path]]] = []

    # 根目录一组（可选）
    c2_root  = _pick_existing(patient_dir, _C2_NAMES)
    msk_root = _pick_existing(patient_dir, _MSK_NAMES)
    if c2_root and msk_root:
        c0_root = _pick_existing(patient_dir, _C0_NAMES)
        cases.append((None, c2_root, msk_root, c0_root))

    # 一层子目录多组
    subdirs = [d for d in patient_dir.iterdir() if d.is_dir()]
    if SKIP_UNDERSCORE:
        subdirs = [d for d in subdirs if not d.name.startswith("_")]

    # 避免与根目录同名或重复：依次检测每个子目录
    for sd in sorted(subdirs):
        c2  = _pick_existing(sd, _C2_NAMES)
        msk = _pick_existing(sd, _MSK_NAMES)
        if c2 and msk:
            c0 = _pick_existing(sd, _C0_NAMES) or _pick_existing(patient_dir, _C0_NAMES)
            cases.append((sd.name, c2, msk, c0))

    return cases
# -----------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize intensity for C2; passthrough C2_mask & C0. (handles multiple date subfolders)")
    parser.add_argument("--in-dir", required=True, help="输入根目录（含病人子目录）")
    parser.add_argument("--out-dir", required=True, help="输出根目录")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    if not in_dir.exists():
        _log(f("[NORM] ERROR: in_dir not exists: {in_dir}"))
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
        patient_name = patient.name

        # 列出该病例所有可处理的 (date_name, c2, c2m, c0)
        cases = enumerate_cases(patient)
        if not cases:
            _log(f"[NORM] skip {patient_name}: no C2/C2_mask found (root and one-level subfolders)")
            skipped.append(patient_name)
            continue

        for date_name, c2_path, c2m_path, c0_path in cases:
            # 输出路径：带日期则进入日期子目录；根目录则直接在病例根
            out_patient = out_dir / patient_name
            out_case_dir = out_patient if (date_name is None) else (out_patient / date_name)

            dst_c2  = out_case_dir / "C2.nii.gz"
            dst_c2m = out_case_dir / "C2_mask.nii.gz"
            dst_c0  = out_case_dir / "C0.nii.gz"

            case_tag = f"{patient_name}" if date_name is None else f"{patient_name}/{date_name}"

            # 幂等：已存在且不覆盖 -> 跳过；但仍尽力透传 C0
            if dst_c2.exists() and not OVERWRITE:
                if not dst_c2m.exists():
                    _log(f"[NORM] warn {case_tag}: dst C2 exists but C2_mask missing; incomplete case (overwrite disabled).")
                _try_copy_c0(c0_path, dst_c0, overwrite=False, tag="passthrough", case_name=case_tag)
                _log(f"[NORM] skip {case_tag}: output exists")
                skipped.append(case_tag)
                continue

            try:
                _log(f"[NORM] processing {case_tag}")
                _normalize_c2(c2_path, dst_c2)

                # 掩膜原样复制（不覆盖）
                dst_c2m.parent.mkdir(parents=True, exist_ok=True)
                if (not dst_c2m.exists()) or OVERWRITE:
                    shutil.copy2(c2m_path, dst_c2m)
                else:
                    _log(f"[NORM] skip mask for {case_tag}: dst exists")

                # 传递 C0（若存在）
                _try_copy_c0(c0_path, dst_c0, overwrite=OVERWRITE, tag="copy", case_name=case_tag)

                _log(f"[NORM] done {case_tag} -> {dst_c2}")
                ok.append(case_tag)
            except Exception as e:
                _log(f"[NORM] fail {case_tag}: {e}")
                failed.append((case_tag, str(e)))

    summary = {
        "ok": ok,
        "skipped": skipped,
        "failed": [{"case": p, "error": err} for p, err in failed],
        "counts": {"ok": len(ok), "skipped": len(skipped), "failed": len(failed), "total_cases": len(ok)+len(skipped)+len(failed)},
        "out_dir": str(out_dir),
    }
    _log("[NORM] summary: " + json.dumps(summary, ensure_ascii=False))
    _log(f"[NORM] total time: {time.time() - t0:.2f}s")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
