#!/usr/bin/env python3
import os
# os.environ['OMP_NUM_THREADS'] = '1'
# os.environ['OPENBLAS_NUM_THREADS'] = '1'
# os.environ['MKL_NUM_THREADS'] = '1'
# os.environ['BLIS_NUM_THREADS'] = '1'
# os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
# os.environ['NUMEXPR_NUM_THREADS'] = '1'

import argparse
import SimpleITK as sitk
from pathlib import Path
import os
import tempfile
import shutil
import sys

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from utils import my_breast, my_nnunet

def main_worker(input_path: Path, output_path: Path):
    # img = sitk.ReadImage(input_path)
    # print("=> Input image loaded: ", input_path)

    print(f"input_path: {input_path}")
    print(f"output_path: {output_path}")

    remove_small_components_min_pixels = 100

    img = sitk.ReadImage(input_path)
    print(f"img.GetSize(): {img.GetSize()}")
    print(f"img.GetSpacing(): {img.GetSpacing()}")
    print(f"img.GetDirection(): {img.GetDirection()}")
    print(f"img.GetOrigin(): {img.GetOrigin()}")

    # 使用script目录下的临时文件夹
    script_temp_dir = Path(__file__).parent.parent / "temp"
    script_temp_dir.mkdir(exist_ok=True)
    
    with tempfile.TemporaryDirectory(dir=str(script_temp_dir)) as tmpdir:
        import time
        # tmpdir = Path("/media/wzt/wdc18t/ToOthers/20250819-WangQianting-preprocessing_workflow/debug")
        output_dir = Path(tmpdir)
        original_image_dir = output_dir / "input"
        original_image_dir.mkdir(parents=True, exist_ok=True)
        sym_path = original_image_dir / input_path.name
        # sym_path.symlink_to(input_path)
        shutil.copy2(input_path, sym_path)

        denoise_image_dir = output_dir / "denoise_image"
        pred_breast_mask_dir = output_dir / "pred_breast_mask"
        cor_breast_mask_dir = output_dir / "breast_mask"
        breast_region_dir = output_dir / "breast_region"
        pure_breast_region_dir = output_dir / "pure_breast_region"
        various_mask_dir = output_dir / "various_mask"
        pred_gland_mask_dir = output_dir / "pred_gland_mask"
        pred_tumor_mask_dir = output_dir / "pred_tumor_mask"

        # denoise_image_dir.mkdir(parents=True, exist_ok=True)
        # my_breast.run_denoising(original_image_dir, denoise_image_dir, use_multiprocessing=False)
        # print("=> Denoised image saved: ", denoise_image_dir)

        # my_nnunet.run_predict_breast_mask(denoise_image_dir, pred_breast_mask_dir, "*.nii.gz", use_rglob=True)
        print(list(original_image_dir.rglob("*.nii.gz")))
        my_nnunet.run_predict_breast_mask(original_image_dir, pred_breast_mask_dir, "*.nii.gz", use_rglob=True)
        print("=> Predicted breast mask saved: ", pred_breast_mask_dir)

        my_breast.run_correct_breast_mask(pred_breast_mask_dir, cor_breast_mask_dir)
        print("=> Corrected breast mask saved: ", cor_breast_mask_dir)

        my_breast.run_various_mask(cor_breast_mask_dir, various_mask_dir)
        print("=> Various mask saved: ", various_mask_dir)

        my_breast.run_generate_breast_region_v2(original_image_dir, cor_breast_mask_dir, breast_region_dir)
        print("=> Breast region saved: ", breast_region_dir)

        # 检查乳房区域文件是否存在
        breast_region_files = list(breast_region_dir.glob("*.nii.gz"))
        print(f"乳房区域文件数量: {len(breast_region_files)}")
        for file in breast_region_files:
            print(f"  - {file.name}")

        if not breast_region_files:
            print("⚠️ 乳房区域文件为空，跳过肿瘤预测")
            # 创建一个空的掩码文件
            empty_mask = sitk.Image(img.GetSize(), sitk.sitkUInt8)
            empty_mask.SetSpacing(img.GetSpacing())
            empty_mask.SetDirection(img.GetDirection())
            empty_mask.SetOrigin(img.GetOrigin())
            sitk.WriteImage(empty_mask, output_path)
            print("=> 空掩码已保存: ", output_path)
            return

        my_nnunet.run_predict_tumor_mask(breast_region_dir, pred_tumor_mask_dir, "*.nii.gz", use_rglob=True)
        print("=> Predicted tumor mask saved: ", pred_tumor_mask_dir)

        if remove_small_components_min_pixels > 0:
            print("    → Remove small components")
            for nii_path in pred_tumor_mask_dir.glob("*.nii.gz"):
                my_breast.remove_small_components(nii_path, nii_path, min_pixels=remove_small_components_min_pixels)


        print("=> Copying mask...")
        
        # 检查输出目录是否存在
        if not pred_tumor_mask_dir.exists():
            print(f"⚠️ 输出目录不存在: {pred_tumor_mask_dir}")
            print("肿瘤预测可能失败，尝试查找其他可能的输出位置...")
            
            # 查找可能的输出文件
            possible_outputs = [
                tmpdir / "pred_tumor_mask",
                tmpdir / "tumor_mask", 
                tmpdir / "pred_mask",
                tmpdir
            ]
            
            output_files = []
            for possible_dir in possible_outputs:
                if possible_dir.exists():
                    files = list(possible_dir.glob("*.nii.gz"))
                    if files:
                        output_files.extend(files)
                        print(f"在 {possible_dir} 中找到 {len(files)} 个文件")
            
            if not output_files:
                raise FileNotFoundError(f"未找到任何肿瘤预测输出文件")
            
            pred_mask_file = output_files[0]
            print(f"使用找到的输出文件: {pred_mask_file}")
        else:
            # 调试：列出输出目录中的所有文件
            print(f"输出目录内容: {pred_tumor_mask_dir}")
            try:
                for item in pred_tumor_mask_dir.iterdir():
                    print(f"  - {item.name}")
            except FileNotFoundError:
                print("  - 目录为空或无法访问")
            
            # nnUNet输出文件名可能与输入文件名不同，需要查找实际输出文件
            output_files = list(pred_tumor_mask_dir.glob("*.nii.gz"))
            if not output_files:
                raise FileNotFoundError(f"在 {pred_tumor_mask_dir} 中未找到.nii.gz文件")
            
            # 使用第一个找到的.nii.gz文件
            pred_mask_file = output_files[0]
            print(f"找到输出文件: {pred_mask_file}")
        
        pred_mask = sitk.ReadImage(str(pred_mask_file))
        
        pred_mask.SetSpacing(img.GetSpacing())
        pred_mask.SetDirection(img.GetDirection())
        pred_mask.SetOrigin(img.GetOrigin())

        sitk.WriteImage(pred_mask, output_path)
        print("=> Predicted mask saved: ", output_path)

def main():
    parser = argparse.ArgumentParser(description='Demo')
    parser.add_argument('-i', '--input', required=True, help='Input image path')
    parser.add_argument('-o', '--output', required=True, help='Output result path')
    args = parser.parse_args()
    print(args)

    main_worker(args.input, args.output)

if __name__ == "__main__":
    main()