#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
QC 可视化（最大掩膜切片 + 全卷强度分布）——多日期健壮版：
- 同时兼容：
  1) 病人根目录含 c2(.nii.gz)/c2_mask(.nii.gz)
  2) 病人目录下一层含多个“日期文件夹”（YYYYMMDD 或 D0/D1…），每个子文件夹内含 c2/c2_mask
- 为每个命中的“时间点”各自输出 PNG 和 JSON：
  <out_dir>/<patient>/<date>/C2_qc.png 和 C2_qc.json
  若使用根目录那对，则输出到 <out_dir>/<patient>/C2_qc.*
- 默认不覆盖；跳过以“_”开头的目录；实时日志 + summary
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Optional
import argparse
import json
import time

import numpy as np
import SimpleITK as sitk
from tqdm import tqdm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

OVERWRITE = False
SKIP_UNDERSCORE = True

def _log(msg: str) -> None:
    print(msg, flush=True)

def _case_insensitive(path_dir: Path, name: str) -> Optional[Path]:
    """在目录下大小写不敏感地寻找文件名 name（如 'c2.nii.gz'）。找不到返回 None。"""
    target_lower = name.lower()
    for p in path_dir.iterdir():
        if p.is_file() and p.name.lower() == target_lower:
            return p
    return None

def _enumerate_timepoints(patient_dir: Path) -> List[Tuple[Optional[str], Path, Path]]:
    """
    返回 [(date_label, c2_path, c2_mask_path), ...]
    - date_label 为 None 表示来自“病人根目录”的一对
    - 其余为子目录名（日期文件夹）
    """
    pairs: List[Tuple[Optional[str], Path, Path]] = []

    # 1) 先尝试病人根目录的一对
    c2_root  = _case_insensitive(patient_dir, "c2.nii.gz")
    c2m_root = _case_insensitive(patient_dir, "c2_mask.nii.gz")
    if c2_root and c2m_root:
        pairs.append((None, c2_root, c2m_root))

    # 2) 再找下一层日期文件夹中的一对
    for sub in sorted([p for p in patient_dir.iterdir() if p.is_dir()]):
        if SKIP_UNDERSCORE and sub.name.startswith("_"):
            continue
        c2  = _case_insensitive(sub, "c2.nii.gz")
        c2m = _case_insensitive(sub, "c2_mask.nii.gz")
        if c2 and c2m:
            pairs.append((sub.name, c2, c2m))

    return pairs

def _get_max_mask_slice_figure(
    image_path: Path,
    mask_path: Path,
    vmin=None,
    vmax=None,
    figsize=(6, 6),
    bins=256,
):
    """读取 image/mask，按 mask 面积最大的 z 切片可视化，并叠加整卷强度分布（KDE 或直方图）。"""
    img_sitk = sitk.ReadImage(str(image_path))
    msk_sitk = sitk.ReadImage(str(mask_path))

    img = sitk.GetArrayFromImage(img_sitk)  # [Z, Y, X]
    msk = sitk.GetArrayFromImage(msk_sitk)  # [Z, Y, X]

    if img.shape != msk.shape:
        raise ValueError(f"Image and mask shapes do not match: {img.shape} vs {msk.shape}")

    mask_binary = msk > 0
    areas = mask_binary.sum(axis=(1, 2))
    z_idx = int(np.argmax(areas)) if int(areas.max()) > 0 else img.shape[0] // 2

    image_slice = img[z_idx]

    fig = plt.figure(figsize=figsize)
    ax_main = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax_main.imshow(image_slice, cmap="gray", vmin=vmin, vmax=vmax)
    ax_main.axis("off")

    # 元信息
    size = img_sitk.GetSize()
    spacing = img_sitk.GetSpacing()
    origin = img_sitk.GetOrigin()
    info_text = (
        f"Size: {size[0]}×{size[1]}×{size[2]}\n"
        f"Spacing: ({spacing[0]:.2f}, {spacing[1]:.2f}, {spacing[2]:.2f})\n"
        f"Origin: ({origin[0]:.1f}, {origin[1]:.1f}, {origin[2]:.1f})\n"
        f"Direction: LPS"
    )
    ax_main.text(
        0.02, 0.98, info_text,
        transform=ax_main.transAxes,
        fontsize=12, color="white", va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7, edgecolor="none"),
    )

    # 直方图 / KDE
    ax_hist = fig.add_axes([0.15, 0.10, 0.75, 0.22])
    values = img.ravel()
    hist_counts, bin_edges = np.histogram(values, bins=bins)
    intensity_min, intensity_max = values.min(), values.max()
    if vmin is not None:
        intensity_min = max(intensity_min, vmin)
    if vmax is not None:
        intensity_max = min(intensity_max, vmax)

    try:
        sample_values = values if values.size <= 50000 else values[np.random.choice(values.size, 50000, replace=False)]
        kde = stats.gaussian_kde(sample_values)
        x_range = np.linspace(intensity_min, intensity_max, 200)
        density = kde(x_range)
        ax_hist.plot(x_range, density, linewidth=1.8, alpha=0.9)
        ax_hist.fill_between(x_range, density, alpha=0.5)
    except Exception:
        # 回退：线形直方图
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        valid = (bin_centers >= intensity_min) & (bin_centers <= intensity_max)
        ax_hist.plot(bin_centers[valid], hist_counts[valid], linewidth=1.8, alpha=0.9)
        ax_hist.fill_between(bin_centers[valid], hist_counts[valid], alpha=0.5)

    ax_hist.set_xlabel("Intensity", fontsize=12, color="white")
    ax_hist.set_ylabel("Count", fontsize=12, color="white")
    ax_hist.tick_params(labelsize=10, colors="white", labelleft=False)
    ax_hist.grid(True, alpha=0.3, color="white")
    ax_hist.patch.set_facecolor("none")
    ax_hist.patch.set_alpha(0.0)
    for spine in ax_hist.spines.values():
        spine.set_edgecolor("white")
        spine.set_linewidth(1.0)
        spine.set_alpha(0.7)

    return fig, z_idx

def main() -> int:
    parser = argparse.ArgumentParser(description="QC plot: max mask slice + whole-volume intensity KDE (multi-date aware)")
    parser.add_argument("--in-dir", required=True, help="输入根目录（含病人子目录）")
    parser.add_argument("--out-dir", required=True, help="输出根目录")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)

    if not in_dir.exists():
        _log(f"[QC] ERROR: in_dir not exists: {in_dir}")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    patients = [p for p in in_dir.iterdir() if p.is_dir()]
    if SKIP_UNDERSCORE:
        patients = [p for p in patients if not p.name.startswith("_")]

    ok: List[str] = []
    skipped: List[str] = []
    failed: List[Tuple[str, str]] = []

    _log(f"[QC] start: src={in_dir} -> dst={out_dir} | overwrite={OVERWRITE} | skip_underscore={SKIP_UNDERSCORE}")

    t0 = time.time()
    for patient in tqdm(patients, desc="QC plotting", unit="case"):
        name = patient.name
        # 列举该病人的所有“时间点”
        timepoints = _enumerate_timepoints(patient)
        if not timepoints:
            _log(f"[QC] skip {name}: no C2/C2_mask found in root or subfolders")
            skipped.append(name)
            continue

        for date_label, c2, c2m in timepoints:
            # 输出目录：根对 -> <out>/<patient>/；日期对 -> <out>/<patient>/<date>/
            out_patient = out_dir / name if date_label is None else out_dir / name / date_label
            out_patient.mkdir(parents=True, exist_ok=True)
            png_path = out_patient / "C2_qc.png"
            json_path = out_patient / "C2_qc.json"

            if png_path.exists() and not OVERWRITE:
                _log(f"[QC] skip {name}{'@'+date_label if date_label else ''}: output exists")
                skipped.append(f"{name}@{date_label or 'ROOT'}")
                continue

            try:
                _log(f"[QC] processing {name}{'@'+date_label if date_label else ''}")
                fig, z_idx = _get_max_mask_slice_figure(c2, c2m, vmin=None, vmax=None, figsize=(6, 6), bins=256)
                fig.savefig(str(png_path), dpi=150, bbox_inches="tight", pad_inches=0.05)
                plt.close(fig)

                with json_path.open("w", encoding="utf-8") as f:
                    json.dump({"z_index": int(z_idx)}, f, ensure_ascii=False, indent=2)

                ok.append(f"{name}@{date_label or 'ROOT'}")
                _log(f"[QC] done {name}{'@'+date_label if date_label else ''} -> {png_path}")
            except Exception as e:
                _log(f"[QC] fail {name}{'@'+date_label if date_label else ''}: {e}")
                failed.append((f"{name}@{date_label or 'ROOT'}", str(e)))

    summary = {
        "ok": ok,
        "skipped": skipped,
        "failed": [{"patient": p, "error": err} for p, err in failed],
        "counts": {"ok": len(ok), "skipped": len(skipped), "failed": len(failed), "total_cases": len(patients)},
        "out_dir": str(out_dir),
    }
    _log("[QC] summary: " + json.dumps(summary, ensure_ascii=False))
    _log(f"[QC] total time: {time.time() - t0:.2f}s")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
