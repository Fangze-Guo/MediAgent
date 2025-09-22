from pathlib import Path

dcm_dir = Path("../data/0_DICOM")
og_dir = Path("../data/1_NII")
reg_dir = Path("../data/2_Reg")
n4_dir = Path("../data/3_N4")
res_dir = Path("../data/4_Res")
norm_dir = Path("../data/5_Norm")

__all__ = [
    "dcm_dir",
    "og_dir",
    "reg_dir",
    "n4_dir",
    "res_dir",
    "norm_dir"
]
