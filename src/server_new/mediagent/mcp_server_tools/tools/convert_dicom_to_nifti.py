#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_dicom_to_nifti.py —— 批量将 DICOM 序列转换为 NIfTI
输入：
    --in-dir   : 包含多个病人子文件夹的 DICOM 根目录
    --out-dir  : 输出目录（每个病人一个子目录，生成 C0.nii.gz 和 C2.nii.gz）
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
import SimpleITK as sitk

def log(o):
    print(json.dumps(o, ensure_ascii=False), flush=True)

def ensure_line_buffer():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

def read_dicom_series(series_directory: Path) -> sitk.Image:
    reader = sitk.ImageSeriesReader()
    series_ids = reader.GetGDCMSeriesIDs(str(series_directory))
    if not series_ids:
        raise FileNotFoundError(f"No DICOM series found in {series_directory}")

    # 选择包含文件最多的序列
    best_file_names = []
    for series_id in series_ids:
        file_names = reader.GetGDCMSeriesFileNames(str(series_directory), series_id)
        if len(file_names) > len(best_file_names):
            best_file_names = file_names

    reader.SetFileNames(best_file_names)
    image = reader.Execute()
    return image

def main():
    ensure_line_buffer()
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, help="输入 DICOM 根目录")
    ap.add_argument("--out-dir", required=True, help="输出 NIfTI 根目录")
    args = ap.parse_args()

    dcm_dir = Path(args.in_dir).expanduser().resolve()
    og_dir = Path(args.out_dir).expanduser().resolve()
    og_dir.mkdir(parents=True, exist_ok=True)

    log({"event": "start", "in_dir": str(dcm_dir), "out_dir": str(og_dir)})

    try:
        patient_dirs = [p for p in dcm_dir.iterdir() if p.is_dir()]
        total = len(patient_dirs)
        done = 0

        for patient_dir in patient_dirs:
            c0_dir = patient_dir / "C0"
            c2_dir = patient_dir / "C2"
            if not c0_dir.exists() or not c2_dir.exists():
                continue

            c0_img_sitk = read_dicom_series(c0_dir)
            c2_img_sitk = read_dicom_series(c2_dir)

            dst_dir = og_dir / patient_dir.name
            dst_dir.mkdir(parents=True, exist_ok=True)
            sitk.WriteImage(c0_img_sitk, str(dst_dir / "C0.nii.gz"))
            sitk.WriteImage(c2_img_sitk, str(dst_dir / "C2.nii.gz"))

            log({
                "event": "converted",
                "patient": patient_dir.name,
                "C0_size": c0_img_sitk.GetSize(),
                "C0_spacing": c0_img_sitk.GetSpacing(),
                "C2_size": c2_img_sitk.GetSize(),
                "C2_spacing": c2_img_sitk.GetSpacing(),
            })

            done += 1
            pct = int(done / total * 100)
            log({"event": "progress", "pct": pct})

        log({"event": "done", "ok": True, "out_dir": str(og_dir)})
    except Exception as e:
        log({"event": "error", "msg": str(e)})
        sys.exit(2)

if __name__ == "__main__":
    main()
