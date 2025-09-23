import os
import shutil
import platform
import sys
from pathlib import Path
import subprocess
import tempfile

# 添加当前目录到Python路径，以便导入utils.base
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from base import rglob


NNUNET_ROOT = Path("/home/wzt/src/nnunet_projects")


def init_env(nnunet_root=NNUNET_ROOT):
    nnunet_raw_data_base = os.environ.get("nnUNet_raw_data_base", nnunet_root / "nnUNet_raw")
    nnunet_preprocessed = os.environ.get("nnUNet_preprocessed", nnunet_root / "nnUNet_preprocessed")
    results_folder = os.environ.get("RESULTS_FOLDER", nnunet_root / "nnUNet_trained_models")

    os.putenv("nnUNet_raw_data_base", str(nnunet_raw_data_base))
    os.putenv("nnUNet_preprocessed", str(nnunet_preprocessed))
    os.putenv("RESULTS_FOLDER", str(results_folder))
    return dict(nnUNet_raw_data_base=nnunet_raw_data_base, nnUNet_preprocessed=nnunet_preprocessed, RESULTS_FOLDER=results_folder)

def _create_file_link(source_path, target_path):
    """
    创建文件链接或复制文件
    在Windows系统上使用文件复制，其他系统使用符号链接
    """
    if platform.system() == "Windows":
        try:
            # Windows系统优先使用文件复制
            shutil.copy2(source_path, target_path)
            print(f"复制文件: {source_path} -> {target_path}")
            return True
        except Exception as e:
            print(f"复制文件失败: {e}")
            # 如果复制失败，尝试创建符号链接（需要管理员权限）
            try:
                target_path.symlink_to(source_path)
                print(f"创建符号链接: {source_path} -> {target_path}")
                return True
            except OSError as symlink_error:
                print(f"符号链接创建失败: {symlink_error}")
                print("提示: 在Windows上创建符号链接需要管理员权限")
                raise symlink_error
    else:
        # Linux/Unix系统使用符号链接
        target_path.symlink_to(source_path)
        print(f"创建符号链接: {source_path} -> {target_path}")
        return True

def predict(to_pred_dir, output_dir, task_name, model, folds):
    cmd = ["nnUNet_predict",
           "-i", to_pred_dir, 
           "-o", output_dir, 
           "-t", task_name, 
           "-m", model, 
           "-f", folds]
    print(" ".join([str(_) for _ in cmd]))
    with open('nnunet_run.log', 'w+') as f:
        subprocess.run(cmd, stdout=f, stderr=f)
    # subprocess.run(cmd)

def run_predict(to_pred_dir, output_dir, task_name, model, folds, pattern, use_rglob=False):
    init_env()
    
    # 使用script目录下的临时文件夹
    script_temp_dir = Path(__file__).parent.parent.parent / "temp"
    script_temp_dir.mkdir(exist_ok=True)
    
    with tempfile.TemporaryDirectory(dir=str(script_temp_dir)) as tmpdirname:
        temp_dir = Path(tmpdirname)
        glob_iter = rglob(to_pred_dir, pattern) if use_rglob else to_pred_dir.glob(pattern)
        for nii_path in glob_iter:
            nnunet_nii_name = nii_path.name.replace(".nii.gz", "_0000.nii.gz")
            nnunet_nii_path = temp_dir / nnunet_nii_name
            
            # 使用统一的文件链接/复制函数
            _create_file_link(nii_path, nnunet_nii_path)
        
        print(f"{to_pred_dir} --> {temp_dir}")
        predict(temp_dir, output_dir, task_name, model, folds)

def run_predict_breast_mask(to_pred_dir, output_dir, pattern="*.nii.gz", use_rglob=False):
    run_predict(to_pred_dir, output_dir, task_name="52", model="3d_fullres", folds="4", pattern=pattern, use_rglob=use_rglob)

def run_predict_gland_mask(to_pred_dir, output_dir, pattern="*.nii.gz", use_rglob=False):
    run_predict(to_pred_dir, output_dir, task_name="86", model="2d", folds="0", pattern=pattern, use_rglob=use_rglob)

def run_predict_tumor_mask(to_pred_dir, output_dir, pattern="*.nii.gz", use_rglob=False):
    run_predict(to_pred_dir, output_dir, task_name="88", model="3d_fullres", folds="0", pattern=pattern, use_rglob=use_rglob)

def run_predict_benign_tumor_mask(to_pred_dir, output_dir, pattern="*.nii.gz", use_rglob=False):
    run_predict(to_pred_dir, output_dir, task_name="34", model="3d_fullres", folds="0", pattern=pattern, use_rglob=use_rglob)

