import os
import shutil
import subprocess
from pathlib import Path

from tqdm import tqdm

from script import reg_dir, og_dir


def run_registration(fixed_nii_path: Path, moving_nii_path: Path, dst_nii_path: Path,
                     mask_nii_path: Path = None, dst_mask_nii_path: Path = None):
    """
    执行图像配准流程，包括线性配准和非线性配准，并保存结果。

    参数:
        fixed_nii_path (Path): 固定图像的路径（目标图像）。
        moving_nii_path (Path): 移动图像的路径（待配准图像）。
        dst_nii_path (Path): 配准后图像的输出路径。
        mask_nii_path (Path, optional): 固定图像的掩膜路径，用于约束配准区域。默认为 None。
        dst_mask_nii_path (Path, optional): 掩膜配准后的输出路径。默认为 None。

    返回值:
        无返回值。配准结果将写入指定的输出路径。
    """

    # 创建输出目录（如果不存在）
    dst_nii_path.parent.mkdir(parents=True, exist_ok=True)

    affine_matrix_path = str(dst_nii_path)

    # 打开日志文件，记录命令执行过程
    with open("registration.log", "a") as f:
        new_affine_matrix_path = affine_matrix_path + "_matrix.txt"
        # 如果矩阵文件已存在则删除，避免旧数据干扰
        if Path(new_affine_matrix_path).exists():
            os.remove(new_affine_matrix_path)

        # 构建并执行线性配准命令
        cmd_1 = ["./bin/linearBCV", "-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O",
                 str(affine_matrix_path)]
        subprocess.run(cmd_1, stdout=f, stderr=f)

        # 检查线性配准是否成功生成矩阵文件
        if not Path(new_affine_matrix_path).exists():
            msg = ' '.join(cmd_1) + " failed"
            raise Exception(msg)

        # 根据是否提供掩膜路径，构建并执行非线性配准命令
        if mask_nii_path is None:
            cmd_2 = ["./bin/deedsBCV", "-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O", str(dst_nii_path),
                     "-A", str(new_affine_matrix_path)]
        else:
            cmd_2 = ["./bin/deedsBCV", "-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O", str(dst_nii_path),
                     "-A", str(new_affine_matrix_path), "-S", str(mask_nii_path)]
        subprocess.run(cmd_2, stdout=f, stderr=f)

    # deedsBCV 输出的变形图像路径，需移动到用户指定路径
    new_dst_nii_path = dst_nii_path.parent / (dst_nii_path.name + "_deformed.nii.gz")
    if not new_dst_nii_path.exists():
        msg = ' '.join(cmd_2) + " failed"
        raise Exception(msg)

    # 将变形图像移动到目标路径
    shutil.move(new_dst_nii_path, dst_nii_path)

    # 如果指定了掩膜输出路径，则处理掩膜配准结果
    if dst_mask_nii_path:
        dst_mask_nii_path.parent.mkdir(parents=True, exist_ok=True)
        new_dst_mask_nii_path = dst_nii_path.parent / (dst_nii_path.name + "_deformed_seg.nii.gz")
        shutil.move(new_dst_mask_nii_path, dst_mask_nii_path)

    # 清理中间文件
    os.remove(new_affine_matrix_path)
    os.remove(dst_nii_path.parent / (dst_nii_path.name + "_displacements.dat"))


for patient_dir in tqdm(list(Path(og_dir).iterdir())):
    if not patient_dir.is_dir():
        continue

    c0_path = patient_dir / "C0.nii.gz"
    # c2_path = patient_dir / "C2.nii.gz"
    # if not c0_path.exists() or not c2_path.exists():
    if not c0_path.exists():
        continue

    dst_c0_path = reg_dir / patient_dir.name / "C0.nii.gz"
    # dst_c2_path = reg_dir / patient_dir.name / "C2.nii.gz"
    dst_c0_path.parent.mkdir(parents=True, exist_ok=True)
    # dst_c2_path.parent.mkdir(parents=True, exist_ok=True)

    if not dst_c0_path.exists():
        shutil.copy2(c0_path, dst_c0_path)

    # if not dst_c2_path.exists():
    #     run_registration(c0_path, c2_path, dst_c2_path)
