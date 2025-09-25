from pathlib import Path

# 获取当前文件所在目录（script目录）
script_dir = Path(__file__).parent

# 数据目录相对于script目录的位置
data_dir = script_dir / "data"

dcm_dir = data_dir / "0_DICOM"
og_dir = data_dir / "1_NII"
reg_dir = data_dir / "2_Reg"
n4_dir = data_dir / "3_N4"
res_dir = data_dir / "4_Res"
norm_dir = data_dir / "5_Norm"

__all__ = [
    "dcm_dir",
    "og_dir",
    "reg_dir",
    "n4_dir",
    "res_dir",
    "norm_dir"
]
