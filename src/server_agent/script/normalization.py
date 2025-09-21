import shutil

import SimpleITK as sitk
import monai
from tqdm import tqdm

from script import res_dir, norm_dir

trans = monai.transforms.NormalizeIntensity()

for patient_dir in tqdm(list(res_dir.iterdir())):
    if not patient_dir.is_dir():
        continue

    c2_path = patient_dir / "C2.nii.gz"
    c2_mask_path = patient_dir / "C2_mask.nii.gz"
    if not c2_path.exists() or not c2_mask_path.exists():
        continue

    dst_c2_path = norm_dir / patient_dir.name / "C2.nii.gz"
    dst_c2_mask_path = norm_dir / patient_dir.name / "C2_mask.nii.gz"
    dst_c2_path.parent.mkdir(parents=True, exist_ok=True)
    dst_c2_mask_path.parent.mkdir(parents=True, exist_ok=True)

    if not dst_c2_path.exists():
        img = sitk.ReadImage(str(c2_path))
        img_arr = sitk.GetArrayFromImage(img)[None]
        img_norm = trans(img_arr)
        img_norm = img_norm[0]
        img_norm = sitk.GetImageFromArray(img_norm)
        img_norm.CopyInformation(img)
        sitk.WriteImage(img_norm, str(dst_c2_path))

    if not dst_c2_mask_path.exists():
        shutil.copy2(c2_mask_path, dst_c2_mask_path)
