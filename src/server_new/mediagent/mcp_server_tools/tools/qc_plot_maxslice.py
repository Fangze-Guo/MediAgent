#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
QC 可视化（最大掩膜切片 + 全卷强度分布）：
- 输入：每个病人目录包含 C2.nii.gz 与 C2_mask.nii.gz（同空间）
- 输出：为每个病人生成一张 PNG：C2_qc.png（叠加元信息 + 透明直方图密度曲线）
- 行为：
  • 默认不覆盖（若 PNG 已存在则跳过）
  • 自动跳过以下划线开头的目录（_logs/_workspace 等）
  • 实时日志；结束时打印 summary
- 依赖：numpy, SimpleITK, matplotlib, scipy
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import argparse
import json
import time

import numpy as np
import SimpleITK as sitk
from tqdm import tqdm
import matplotlib
matplotlib.use("Agg")  # 服务器无显示环境
import matplotlib.pyplot as plt
from scipy import stats

OVERWRITE = False
SKIP_UNDERSCORE = True

def _log(msg: str) -> None:
    print(msg, flush=True)

def _get_max_mask_slice_figure(
    image_path: Path,
    mask_path: Path,
    vmin=None,
    vmax=None,
    figsize=(6, 6),
    bins=256,
):
    """
    读取 image/mask (NIfTI)，按 mask 面积最大的 z 切片可视化，并在底部叠加整卷强度分布曲线（KDE）。
    返回 (fig, z_idx)。
    """
    img_sitk = sitk.ReadImage(str(image_path))
    msk_sitk = sitk.ReadImage(str(mask_path))

    img = sitk.GetArrayFromImage(img_sitk)  # [Z, Y, X]
    msk = sitk.GetArrayFromImage(msk_sitk)  # [Z, Y, X]

    if img.shape != msk.shape:
        raise ValueError(f"Image and mask shapes do not match: {img.shape} vs {msk.shape}")

    mask_binary = msk > 0
    areas = mask_binary.sum(axis=(1, 2))
    if int(areas.max()) == 0:
        z_idx = img.shape[0] // 2
    else:
        z_idx = int(np.argmax(areas))

    image_slice = img[z_idx]
    # mask_slice = msk[z_idx]  # 暂未叠加显示，如需可加轮廓

    # figure
    fig = plt.figure(figsize=figsize)
    ax_main = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax_main.imshow(image_slice, cmap="gray", vmin=vmin, vmax=vmax)
    ax_main.axis("off")

    # 元信息
    size = img_sitk.GetSize()
    spacing = img_sitk.GetSpacing()
    origin = img_sitk.GetOrigin()
    # direction 简化显示（你的流程已统一 LPS/identity）
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

    # 直方图 / KDE 区域
    ax_hist = fig.add_axes([0.15, 0.10, 0.75, 0.22])
    values = img.ravel()
    hist_counts, bin_edges = np.histogram(values, bins=bins)
    intensity_min, intensity_max = values.min(), values.max()
    if vmin is not None:
        intensity_min = max(intensity_min, vmin)
    if vmax is not None:
        intensity_max = min(intensity_max, vmax)

    try:
        sample_values = values
        if len(values) > 50000:
            idx = np.random.choice(len(values), 50000, replace=False)
            sample_values = values[idx]
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
    parser = argparse.ArgumentParser(description="QC plot: max mask slice + whole-volume intensity KDE")
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
        c2  = patient / "C2.nii.gz"
        c2m = patient / "C2_mask.nii.gz"

        if not c2.exists() or not c2m.exists():
            _log(f"[QC] skip {name}: missing C2 or C2_mask")
            skipped.append(name)
            continue

        out_patient = out_dir / name
        out_patient.mkdir(parents=True, exist_ok=True)
        png_path = out_patient / "C2_qc.png"
        json_path = out_patient / "C2_qc.json"

        if png_path.exists() and not OVERWRITE:
            _log(f"[QC] skip {name}: output exists")
            skipped.append(name)
            continue

        try:
            _log(f"[QC] processing {name}")
            fig, z_idx = _get_max_mask_slice_figure(c2, c2m, vmin=None, vmax=None, figsize=(6, 6), bins=256)
            fig.savefig(str(png_path), dpi=150, bbox_inches="tight", pad_inches=0.05)
            plt.close(fig)

            # 附带一个小 JSON，记录选中的层号
            with json_path.open("w", encoding="utf-8") as f:
                json.dump({"z_index": int(z_idx)}, f, ensure_ascii=False, indent=2)

            _log(f"[QC] done {name} -> {png_path}")
            ok.append(name)
        except Exception as e:
            _log(f"[QC] fail {name}: {e}")
            failed.append((name, str(e)))

    summary = {
        "ok": ok,
        "skipped": skipped,
        "failed": [{"patient": p, "error": err} for p, err in failed],
        "counts": {"ok": len(ok), "skipped": len(skipped), "failed": len(failed), "total": len(patients)},
        "out_dir": str(out_dir),
    }
    _log("[QC] summary: " + json.dumps(summary, ensure_ascii=False))
    _log(f"[QC] total time: {time.time() - t0:.2f}s")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
