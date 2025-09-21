import os
import shutil
import subprocess
from pathlib import Path

from tqdm import tqdm

from script import reg_dir


def run_registration(fixed_nii_path: Path, moving_nii_path: Path, dst_nii_path: Path, mask_nii_path: Path = None,
                     dst_mask_nii_path: Path = None):
    dst_nii_path.parent.mkdir(parents=True, exist_ok=True)

    affine_matrix_path = str(dst_nii_path)

    with open("registration.log", "a") as f:
        new_affine_matrix_path = affine_matrix_path + "_matrix.txt"
        if Path(new_affine_matrix_path).exists():
            os.remove(new_affine_matrix_path)

        cmd_1 = ["./bin/linearBCV", "-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O",
                 str(affine_matrix_path)]
        subprocess.run(cmd_1, stdout=f, stderr=f)

        if not Path(new_affine_matrix_path).exists():
            msg = ' '.join(cmd_1) + " failed"
            raise Exception(msg)

        if mask_nii_path is None:
            cmd_2 = ["./bin/deedsBCV", "-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O", str(dst_nii_path),
                     "-A", str(new_affine_matrix_path)]
        else:
            cmd_2 = ["./bin/deedsBCV", "-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O", str(dst_nii_path),
                     "-A", str(new_affine_matrix_path), "-S", str(mask_nii_path)]
        subprocess.run(cmd_2, stdout=f, stderr=f)

    # new_xx_path 是deedsBCV的输出, 需要move to参数里的path
    new_dst_nii_path = dst_nii_path.parent / (dst_nii_path.name + "_deformed.nii.gz")
    if not new_dst_nii_path.exists():
        msg = ' '.join(cmd_2) + " failed"
        raise Exception(msg)

    shutil.move(new_dst_nii_path, dst_nii_path)

    if dst_mask_nii_path:
        dst_mask_nii_path.parent.mkdir(parents=True, exist_ok=True)
        new_dst_mask_nii_path = dst_nii_path.parent / (dst_nii_path.name + "_deformed_seg.nii.gz")
        shutil.move(new_dst_mask_nii_path, dst_mask_nii_path)

    # clean
    os.remove(new_affine_matrix_path)
    os.remove(dst_nii_path.parent / (dst_nii_path.name + "_displacements.dat"))


for patient_dir in tqdm(list(Path("./1_NII").iterdir())):
    if not patient_dir.is_dir():
        continue

    c0_path = patient_dir / "C0.nii.gz"
    c2_path = patient_dir / "C2.nii.gz"
    if not c0_path.exists() or not c2_path.exists():
        continue

    dst_c0_path = reg_dir / patient_dir.name / "C0.nii.gz"
    dst_c2_path = reg_dir / patient_dir.name / "C2.nii.gz"
    dst_c0_path.parent.mkdir(parents=True, exist_ok=True)
    dst_c2_path.parent.mkdir(parents=True, exist_ok=True)

    if not dst_c0_path.exists():
        shutil.copy2(c0_path, dst_c0_path)

    if not dst_c2_path.exists():
        run_registration(c0_path, c2_path, dst_c2_path)
