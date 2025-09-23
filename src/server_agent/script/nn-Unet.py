import shutil
import sys
from pathlib import Path

from script import reg_dir, og_dir

# 添加nnunet_projects目录到Python路径
nnunet_projects_dir = Path(__file__).parent / "nnunet_projects"
sys.path.insert(0, str(nnunet_projects_dir))

from predict import main_worker

for patient_dir in reg_dir.iterdir():
    if not patient_dir.is_dir():
        continue

    c0_path = patient_dir / "C0.nii.gz"
    if not c0_path.exists():
        continue

    c0_mask_path = patient_dir / "C0_mask.nii.gz"
    if c0_mask_path.exists():
        continue

    main_worker(c0_path, c0_mask_path)
    shutil.copy2(c0_mask_path, og_dir / patient_dir.name / c0_mask_path.name)
