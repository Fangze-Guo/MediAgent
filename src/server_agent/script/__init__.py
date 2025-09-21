from pathlib import Path

dcm_dir = Path("./0_DICOM")
og_dir = Path("./1_NII")
reg_dir = Path("./2_Reg")
n4_dir = Path("./3_N4")
res_dir = Path("./4_Res")
norm_dir = Path("./5_Norm")

__all__ = [
    "dcm_dir",
    "og_dir",
    "reg_dir",
    "n4_dir",
    "res_dir",
    "norm_dir"
]
