from pathlib import Path

import SimpleITK as sitk
from tqdm import tqdm

from script import n4_dir, res_dir


def resample(in_path, out_path, out_spacing=[1.0, 1.0, 1.0], is_mask=False):
    image_3d = sitk.ReadImage(str(in_path))

    """ 1. spacing """
    original_size = image_3d.GetSize()
    original_spacing = image_3d.GetSpacing()
    same_spacing = True
    for i in range(len(original_spacing)):
        if original_spacing[i] != out_spacing[i]:
            same_spacing = False
            break
    if not same_spacing:
        out_size = [int(round(osz * ospc / nspc)) for osz, ospc, nspc in
                    zip(original_size, original_spacing, out_spacing)]
        resample_filter = sitk.ResampleImageFilter()
        resample_filter.SetOutputSpacing(out_spacing)
        resample_filter.SetSize(out_size)
        resample_filter.SetOutputDirection(image_3d.GetDirection())
        resample_filter.SetOutputOrigin(image_3d.GetOrigin())
        resample_filter.SetTransform(sitk.Transform())
        # resample.SetDefaultPixelValue(itk_image.GetPixelIDValue())

        if is_mask:  # 如果是mask图像，就选择sitkNearestNeighbor这种插值
            resample_filter.SetInterpolator(sitk.sitkNearestNeighbor)
        else:  # 如果是普通图像，就采用sitkBSpline插值法
            resample_filter.SetInterpolator(sitk.sitkBSpline)

        image_3d = resample_filter.Execute(image_3d)

    """ 2. direction """
    original_direction = image_3d.GetDirection()
    out_direction = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    same_direction = True
    for i in range(len(original_direction)):
        if original_direction[i] != out_direction[i]:
            same_direction = False
            break
    image_3d = sitk.DICOMOrient(image_3d, "LPS")
    image_3d.SetDirection(out_direction)

    """ 3. origin """
    original_origin = image_3d.GetOrigin()
    out_origin = (0.0, 0.0, 0.0)
    same_origin = True
    for i in range(len(original_origin)):
        if original_origin[i] != out_origin[i]:
            same_origin = False
    image_3d.SetOrigin(out_origin)

    """ 4. write """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(image_3d, str(out_path))


for patient_dir in tqdm(list(n4_dir.iterdir())):
    if not patient_dir.is_dir():
        continue

    c2_path = patient_dir / "C2.nii.gz"
    c2_mask_path = patient_dir / "C2_mask.nii.gz"
    if not c2_path.exists() or not c2_mask_path.exists():
        continue

    dst_c2_path = res_dir / patient_dir.name / "C2.nii.gz"
    dst_c2_mask_path = res_dir / patient_dir.name / "C2_mask.nii.gz"
    dst_c2_path.parent.mkdir(parents=True, exist_ok=True)
    dst_c2_mask_path.parent.mkdir(parents=True, exist_ok=True)

    if not dst_c2_path.exists():
        resample(c2_path, dst_c2_path, out_spacing=[1.0, 1.0, 1.0], is_mask=False)
        resample(c2_mask_path, dst_c2_mask_path, out_spacing=[1.0, 1.0, 1.0], is_mask=True)
