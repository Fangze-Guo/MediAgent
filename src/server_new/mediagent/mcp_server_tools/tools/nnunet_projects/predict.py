#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
import shutil
import re
from pathlib import Path
from datetime import datetime
import SimpleITK as sitk

# ------------- log -------------
def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def _remove_trailing_mod_suffix(stem: str) -> str:
    return re.sub(r'(_\d{4})+$', '', stem)

from .utils import my_breast as _breast
from .utils import my_nnunet as _nn
log(f"[import] using my_nnunet at: {Path(_nn.__file__).resolve()}")
log(f"[import] my_nnunet exports: {', '.join(sorted([n for n in dir(_nn) if not n.startswith('_')])[:30])} ...")

if not hasattr(_nn, "run_predict_breast_mask") or not hasattr(_nn, "run_predict_tumor_mask"):
    raise ImportError(
        "my_nnunet 中缺少 run_predict_breast_mask / run_predict_tumor_mask。"
        f"\n实际文件：{Path(_nn.__file__).resolve()}"
    )

run_predict_breast_mask = _nn.run_predict_breast_mask
run_predict_tumor_mask  = _nn.run_predict_tumor_mask
run_correct_breast_mask = _breast.run_correct_breast_mask
run_various_mask        = _breast.run_various_mask
run_generate_breast_region_v2 = _breast.run_generate_breast_region_v2
remove_small_components = _breast.remove_small_components

def main_worker(input_path: Path, output_path: Path, work_dir: Path | None = None) -> None:
    """
    注意：
    - 只把最终 mask 写入 `output_path`
    - 所有中间产物都写入 `work_dir`（由外层 run_predict.py 传入到 <OG_DIR>/_workspace/<Patient>/）
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    remove_small_components_min_pixels = 100

    log(f"input_path: {input_path}")
    log(f"output_path: {output_path}")

    img = sitk.ReadImage(str(input_path))
    log(f"img.GetSize(): {img.GetSize()}")
    log(f"img.GetSpacing(): {img.GetSpacing()}")
    log(f"img.GetDirection(): {img.GetDirection()}")
    log(f"img.GetOrigin(): {img.GetOrigin()}")

    if work_dir is None:
        # 若外层未提供，则默认在源所在目录旁新建，这种情况下仍不会影响最终输出目录
        work_dir = input_path.parent / "_predict_work"
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    log(f"使用工作目录：{work_dir}")

    _run_in_dir(work_dir, input_path, output_path, img, remove_small_components_min_pixels)

def _run_in_dir(output_dir: Path,
                input_path: Path,
                output_path: Path,
                ref_img: "sitk.Image",
                remove_small_components_min_pixels: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    original_image_dir   = output_dir / "input"
    pred_breast_mask_dir = output_dir / "pred_breast_mask"
    cor_breast_mask_dir  = output_dir / "breast_mask"
    breast_region_dir    = output_dir / "breast_region"
    various_mask_dir     = output_dir / "various_mask"
    pred_tumor_mask_dir  = output_dir / "pred_tumor_mask"
    for d in (original_image_dir, pred_breast_mask_dir, cor_breast_mask_dir,
              breast_region_dir, various_mask_dir, pred_tumor_mask_dir):
        d.mkdir(parents=True, exist_ok=True)

    in_name = input_path.name
    if in_name.endswith(".nii.gz"):
        stem = in_name[:-7]
    elif in_name.endswith(".nii"):
        stem = in_name[:-4]
    else:
        raise ValueError(f"输入文件必须是 NIfTI：{input_path}")

    stem = _remove_trailing_mod_suffix(stem)
    nn_name = f"{stem}_0000.nii.gz"

    staged_path = original_image_dir / nn_name
    shutil.copy2(input_path, staged_path)
    log(f"=> Copied input to nnU-Net input: {staged_path}")

    log("=> Run breast mask prediction...")
    run_predict_breast_mask(original_image_dir, pred_breast_mask_dir, "*.nii.gz", use_rglob=True)
    log(f"=> Predicted breast mask saved: {pred_breast_mask_dir}")

    run_correct_breast_mask(pred_breast_mask_dir, cor_breast_mask_dir)
    run_various_mask(cor_breast_mask_dir, various_mask_dir)
    run_generate_breast_region_v2(original_image_dir, cor_breast_mask_dir, breast_region_dir)

    log("=> Run tumor mask prediction...")
    run_predict_tumor_mask(breast_region_dir, pred_tumor_mask_dir, "*.nii.gz", use_rglob=True)

    if remove_small_components_min_pixels > 0:
        for nii_path in pred_tumor_mask_dir.glob("*.nii.gz"):
            remove_small_components(nii_path, nii_path, min_pixels=remove_small_components_min_pixels)

    base_case = _remove_trailing_mod_suffix(stem)
    src_mask_path = pred_tumor_mask_dir / f"{base_case}.nii.gz"
    log(f"=> Expect nnU-Net tumor output: {src_mask_path}")
    if not src_mask_path.exists():
        alt = pred_tumor_mask_dir / f"{base_case}_0000.nii.gz"
        if alt.exists():
            src_mask_path = alt
        else:
            raise FileNotFoundError(f"未找到预测 mask: {src_mask_path} 或 {alt}")

    pred_mask = sitk.ReadImage(str(src_mask_path))
    pred_mask.SetSpacing(ref_img.GetSpacing())
    pred_mask.SetDirection(ref_img.GetDirection())
    pred_mask.SetOrigin(ref_img.GetOrigin())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(pred_mask, str(output_path))
    log(f"=> Write mask to: {output_path}")

# CLI 保持不变
def _parse_args() -> argparse.Namespace:
    import argparse as _ap
    p = _ap.ArgumentParser(description="Breast/Tumor mask prediction wrapper")
    p.add_argument("-i", "--input", required=True, help="Input NIfTI path")
    p.add_argument("-o", "--output", required=True, help="Output mask NIfTI path")
    p.add_argument("--work-dir", default=None, help="Optional working directory")
    return p.parse_args()

def main() -> None:
    args = _parse_args()
    in_p  = Path(args.input)
    out_p = Path(args.output)
    wk_p  = Path(args.work_dir).resolve() if args.work_dir else None
    main_worker(in_p, out_p, wk_p)

if __name__ == "__main__":
    main()
