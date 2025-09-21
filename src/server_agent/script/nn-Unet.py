import shutil
import sys

from script import reg_dir, og_dir

sys.path.append("./nnunet_projects/")
import predict

for patient_dir in reg_dir.iterdir():
    if not patient_dir.is_dir():
        continue

    c2_path = patient_dir / "C2.nii.gz"
    if not c2_path.exists():
        continue

    c2_mask_path = patient_dir / "C2_mask.nii.gz"
    if c2_mask_path.exists():
        continue

    predict.main_worker(c2_path, c2_mask_path)
    shutil.copy2(c2_mask_path, og_dir / patient_dir.name / c2_mask_path.name)
