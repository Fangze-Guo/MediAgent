import shutil

import SimpleITK as sitk
import monai
from tqdm import tqdm

from script import res_dir, norm_dir

trans = monai.transforms.NormalizeIntensity()

for patient_dir in tqdm(list(res_dir.iterdir())):
    if not patient_dir.is_dir():
        continue

    c0_path = patient_dir / "C0.nii.gz"
    c0_mask_path = patient_dir / "C0_mask.nii.gz"
    if not c0_path.exists() or not c0_mask_path.exists():
        continue

    dst_c0_path = norm_dir / patient_dir.name / "C0.nii.gz"
    dst_c0_mask_path = norm_dir / patient_dir.name / "C0_mask.nii.gz"
    dst_c0_path.parent.mkdir(parents=True, exist_ok=True)
    dst_c0_mask_path.parent.mkdir(parents=True, exist_ok=True)

    if not dst_c0_path.exists():
        img = sitk.ReadImage(str(c0_path))
        img_arr = sitk.GetArrayFromImage(img)[None]
        img_norm = trans(img_arr)
        img_norm = img_norm[0]
        img_norm = sitk.GetImageFromArray(img_norm)
        img_norm.CopyInformation(img)
        sitk.WriteImage(img_norm, str(dst_c0_path))

    if not dst_c0_mask_path.exists():
        shutil.copy2(c0_mask_path, dst_c0_mask_path)
