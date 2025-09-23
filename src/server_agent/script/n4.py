import shutil
import traceback
from pathlib import Path

import SimpleITK as sitk
from loguru import logger
from tqdm import tqdm

from script import reg_dir, n4_dir


def N4(src_image_path, src_mask_path, dst_image_path, dst_mask_path, kernel_radius=None):
    try:
        image = sitk.Cast(sitk.ReadImage(str(src_image_path)), sitk.sitkFloat32)
        mask = sitk.Cast(sitk.ReadImage(str(src_mask_path)), sitk.sitkUInt8)
        if kernel_radius:
            mask = sitk.Cast(sitk.BinaryDilate(mask, kernelRadius=kernel_radius, foregroundValue=1, backgroundValue=0),
                             sitk.sitkUInt8)

        n4_corrector = sitk.N4BiasFieldCorrectionImageFilter()
        res = n4_corrector.Execute(image, mask)

        Path(dst_image_path).parent.mkdir(parents=True, exist_ok=True)
        sitk.WriteImage(res, str(dst_image_path))

        Path(dst_mask_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_mask_path, dst_mask_path)
    except Exception as e:
        logger.error(traceback.format_exc())
        raise e


for patient_dir in tqdm(list(reg_dir.iterdir())):
    if not patient_dir.is_dir():
        continue

    c0_path = patient_dir / "C0.nii.gz"
    c0_mask_path = patient_dir / "C0_mask.nii.gz"
    if not c0_path.exists() or not c0_mask_path.exists():
        continue

    dst_c0_path = n4_dir / patient_dir.name / "C0.nii.gz"
    dst_c0_mask_path = n4_dir / patient_dir.name / "C0_mask.nii.gz"
    dst_c0_path.parent.mkdir(parents=True, exist_ok=True)
    dst_c0_mask_path.parent.mkdir(parents=True, exist_ok=True)

    if not dst_c0_path.exists():
        N4(c0_path, c0_mask_path, dst_c0_path, dst_c0_mask_path)
        shutil.copy2(c0_mask_path, dst_c0_mask_path)
