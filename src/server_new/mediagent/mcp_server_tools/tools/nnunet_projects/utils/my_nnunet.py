# nnunet_projects/utils/my_nnunet.py
from __future__ import annotations
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Union
import re
import shlex
import time

# ================= 日志 =================
def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ================= 路径与环境 =================
def _project_root() -> Path:
    # 本文件在 nnunet_projects/utils/ 下，项目根目录是上上级
    return Path(__file__).resolve().parents[2]

def _nnunet_root() -> Path:
    # 放置 nnUNet_raw / nnUNet_preprocessed / nnUNet_trained_models 的目录
    # 统一放在项目的 nnunet_projects/ 下
    return Path(__file__).resolve().parents[1]

def _ensure_dirs(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _win_to_wsl_path(p: Union[str, Path]) -> str:
    """
    把 Windows 路径转换为 WSL 路径：
      D:\\foo\\bar -> /mnt/d/foo/bar
    对已经是 POSIX 路径的，原样返回。
    """
    s = str(p)
    if s.startswith("/"):  # 已经是 WSL/Posix
        return s
    m = re.match(r"^([a-zA-Z]):\\(.*)$", s)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    # 其他情况：尽量替换反斜杠
    return s.replace("\\", "/")

def _quote(s: str) -> str:
    # 简单安全包裹到双引号（用于 bash -lc 的命令串）
    return f'"{s}"'

def init_env() -> dict:
    """
    设置 nnU-Net v1 必需的环境变量（相对项目路径），并返回这些路径对象。
    - nnUNet_raw_data_base -> <proj>/nnunet_projects/nnUNet_raw
    - nnUNet_preprocessed  -> <proj>/nnunet_projects/nnUNet_preprocessed
    - RESULTS_FOLDER       -> <proj>/nnunet_projects/nnUNet_trained_models
    注意：这里设置的是当前 Windows 进程的 env；稍后我们在 WSL 里也会 export 同样的值（转换为 WSL 路径）
    """
    nnunet_root = _nnunet_root()  # <proj>/nnunet_projects
    raw_base = nnunet_root / "nnUNet_raw"
    preproc  = nnunet_root / "nnUNet_preprocessed"
    results  = nnunet_root / "nnUNet_trained_models"
    for p in (raw_base, preproc, results):
        _ensure_dirs(p)

    os.environ["nnUNet_raw_data_base"] = str(raw_base)
    os.environ["nnUNet_preprocessed"]  = str(preproc)
    os.environ["RESULTS_FOLDER"]       = str(results)

    log("[init_env] nnUNet 环境变量：")
    log(f"  nnUNet_raw_data_base = {raw_base}")
    log(f"  nnUNet_preprocessed  = {preproc}")
    log(f"  RESULTS_FOLDER       = {results}")

    return {
        "raw_base": raw_base,
        "preproc": preproc,
        "results": results,
    }

# ================== 准备 imagesTs ==================
def _prepare_imagesTs(src_dir: Path, dst_imagesTs: Path, pattern: str, use_rglob: bool) -> int:
    """
    把 src_dir 下匹配 pattern 的 NIfTI 复制/重命名为 *_0000.nii.gz 到 dst_imagesTs
    返回复制的病例数
    """
    _ensure_dirs(dst_imagesTs)
    def basename_wo_nii(p: Path) -> str:
        n = p.name
        if n.endswith(".nii.gz"):
            return n[:-7]
        if n.endswith(".nii"):
            return n[:-4]
        return p.stem

    files = list(src_dir.rglob(pattern) if use_rglob else src_dir.glob(pattern))
    count = 0
    for f in files:
        if not f.is_file():
            continue
        base = basename_wo_nii(f)
        dst = dst_imagesTs / f"{base}_0000.nii.gz"
        shutil.copy2(f, dst)
        count += 1

    log(f"[prepare] {count} case(s): {src_dir} -> {dst_imagesTs.parent}")
    if count == 0:
        raise FileNotFoundError(f"未在 {src_dir} 匹配到输入：{pattern}")
    return count

# ============ 生成 v1 所需的 model_output_folder 绝对路径 ============
def _model_output_folder_v1(
    results_folder_win: Path,
    task_name: str,
    model: str = "3d_fullres",
    trainer: str = "nnUNetTrainerV2",
    plans: str = "nnUNetPlansv2.1",
) -> Path:
    """
    v1 的 predict.py 需要传入训练输出目录 (-m/--model_output_folder)，目录结构为：
      <RESULTS_FOLDER>/nnUNet/<model>/<task_name>/<trainer>__<plans>/
    """
    mof = Path(results_folder_win) / "nnUNet" / model / task_name / f"{trainer}__{plans}"
    return mof

# ================== 通过 WSL 运行 nnUNet_predict ==================
def _run_nnunet_predict_in_wsl(
    imagesTs_win: Path,
    out_win: Path,
    task_name: str,
    model: str = "3d_fullres",
    folds: Union[str, Iterable[str]] = "4",
    trainer: str = "nnUNetTrainerV2",
    plans: str = "nnUNetPlansv2.1",
    disable_tta: bool = True,
    wsl_conda_env: str = "nnunet_env",   # 继续使用这个名字
    extra_args: List[str] | None = None,
) -> None:
    env_local = init_env()

    mof_win = _model_output_folder_v1(
        results_folder_win=env_local["results"],
        task_name=task_name, model=model, trainer=trainer, plans=plans
    )
    if not mof_win.exists():
        raise FileNotFoundError(
            f"模型输出目录不存在：{mof_win}\n"
            f"请确认目录结构：<RESULTS_FOLDER>/nnUNet/{model}/{task_name}/{trainer}__{plans}/"
        )

    imagesTs_wsl = _win_to_wsl_path(imagesTs_win)
    out_wsl      = _win_to_wsl_path(out_win)
    raw_wsl      = _win_to_wsl_path(env_local["raw_base"])
    pre_wsl      = _win_to_wsl_path(env_local["preproc"])
    res_wsl      = _win_to_wsl_path(env_local["results"])
    mof_wsl      = _win_to_wsl_path(mof_win)

    if isinstance(folds, str):
        folds_part = [folds]
    else:
        folds_part = [str(f) for f in folds]

    # === 构建在 WSL 内部执行的命令串（尽量简单、可读） ===
    inner_cmd = [
        # 强制行缓冲；python -u 进一步无缓冲输出
        "export", "PYTHONUNBUFFERED=1;",
        f"export nnUNet_raw_data_base={shlex.quote(raw_wsl)};",
        f"export nnUNet_preprocessed={shlex.quote(pre_wsl)};",
        f"export RESULTS_FOLDER={shlex.quote(res_wsl)};",
        "export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1;",
        # 非交互激活 conda 环境
        # 注意：下面两条 source 路径按你的实际 Conda 安装位置选其一或都写，存在则生效
        'if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then source "$HOME/miniconda3/etc/profile.d/conda.sh"; fi;',
        'if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then source "$HOME/anaconda3/etc/profile.d/conda.sh"; fi;',
        f"conda activate {shlex.quote(wsl_conda_env)} >/dev/null 2>&1 || {{ echo '[wsl] conda activate {wsl_conda_env} failed' >&2; exit 127; }};",
        # 执行 nnUNet 预测
        "stdbuf -oL -eL python -u -m nnunet.inference.predict",
        "-i", shlex.quote(imagesTs_wsl),
        "-o", shlex.quote(out_wsl),
        "-m", shlex.quote(mof_wsl),
        "-f", *[shlex.quote(x) for x in folds_part],
        "--tta", "0" if disable_tta else "1",
    ]
    if extra_args:
        inner_cmd += [shlex.quote(a) for a in extra_args]

    inner_str = " ".join(inner_cmd)

    # 关键：用 bash --noprofile --norc，避免加载任何用户 profile，最大化“无副作用”
    # -lc 以登录 shell 方式执行命令串
    cmd = ["wsl", "bash", "--noprofile", "--norc", "-lc", inner_str]

    log("[wsl] executing (no profile, no rc):")
    log("  " + inner_str)

    out_win.mkdir(parents=True, exist_ok=True)
    logs_dir = out_win.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / "nnunet_wsl.log"

    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"\n==== {datetime.now().isoformat()} ====\n{inner_str}\n")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            f.write(line)
            f.flush()
        rc = proc.wait()

    if rc != 0:
        raise RuntimeError(f"WSL nnUNet_predict 退出码 {rc}，详见日志：{logfile}")


# ================== 通用预测入口（Windows->WSL） ==================
def run_predict(
    to_pred_dir: Path,
    output_dir: Path,
    task_name: str,
    model: str,
    folds: Union[str, Iterable[str]],
    pattern: str,
    use_rglob: bool = False,
    wsl_conda_env: str = "nnunet_env",
    num_threads_preprocessing: int = 1,
    num_threads_nifti_save: int = 1,
) -> None:
    """
    Windows 下调用：准备好临时 imagesTs，然后在 WSL 里跑 nnUNet_predict (v1 参数)。
    关键修复：**模型预测结果直接写到传入的 output_dir**（与师兄版行为对齐），
    不再落到 output_dir/workspace/pred_out。
    """
    to_pred_dir = Path(to_pred_dir).resolve()
    output_dir  = Path(output_dir).resolve()
    _ensure_dirs(output_dir)

    # 仍然可以使用一个工作区，但仅用于准备输入；输出就写到 output_dir 根
    workspace = output_dir / "_ws_tmp"   # 临时目录名，预测结束仍会存在于 output_dir 下；如需纯净，可改到系统临时目录
    imagesTs  = workspace / "imagesTs"
    _ensure_dirs(imagesTs)

    # 准备输入（把原始 NIfTI 复制/重命名为 *_0000.nii.gz）
    _prepare_imagesTs(to_pred_dir, imagesTs, pattern, use_rglob)

    # 通过 WSL 执行 nnUNet_predict (v1)：把输出 **直接写到 output_dir**
    extra = ["--num_threads_preprocessing", str(num_threads_preprocessing),
             "--num_threads_nifti_save", str(num_threads_nifti_save)]
    _run_nnunet_predict_in_wsl(
        imagesTs_win=imagesTs,
        out_win=output_dir,   # ★ 关键：改为 output_dir
        task_name=task_name,
        model=model,
        folds=folds,
        trainer="nnUNetTrainerV2",
        plans="nnUNetPlansv2.1",
        disable_tta=True,
        wsl_conda_env=wsl_conda_env,
        extra_args=extra
    )

    log(f"[done] 预测完成，输出目录：{output_dir}")


# ================== 任务封装（与你原来的保持一致的入口名） ==================
def run_predict_breast_mask(to_pred_dir: Path, output_dir: Path, pattern: str = "*.nii.gz", use_rglob: bool = False) -> None:
    # 乳腺分割任务（Task052_SYbreastSeg2），使用 fold_4（你有完整 checkpoint）
    run_predict(
        to_pred_dir=to_pred_dir,
        output_dir=output_dir,
        task_name="Task052_SYbreastSeg2",
        model="3d_fullres",
        folds="4",
        pattern=pattern,
        use_rglob=use_rglob,
    )

def run_predict_gland_mask(to_pred_dir: Path, output_dir: Path, pattern: str = "*.nii.gz", use_rglob: bool = False) -> None:
    run_predict(
        to_pred_dir=to_pred_dir,
        output_dir=output_dir,
        task_name="Task086_xxxGland",  # 如需用到再改真实 Task 名
        model="2d",
        folds="0",
        pattern=pattern,
        use_rglob=use_rglob,
    )

def run_predict_tumor_mask(to_pred_dir: Path, output_dir: Path, pattern: str = "*.nii.gz", use_rglob: bool = False) -> None:
    run_predict(
        to_pred_dir=to_pred_dir,
        output_dir=output_dir,
        task_name="Task088_TumorSeg",
        model="3d_fullres",
        folds="0",
        pattern=pattern,
        use_rglob=use_rglob,
    )

def run_predict_benign_tumor_mask(to_pred_dir: Path, output_dir: Path, pattern: str = "*.nii.gz", use_rglob: bool = False) -> None:
    run_predict(
        to_pred_dir=to_pred_dir,
        output_dir=output_dir,
        task_name="Task034_BenignTumor",
        model="3d_fullres",
        folds="0",
        pattern=pattern,
        use_rglob=use_rglob,
    )

# 兼容你最早的接口命名（如果有其它模块直接 import predict/predict_breast 之类）
def predict(to_pred_dir, output_dir, task_name, model, folds):
    # 这个简单封装用于兼容旧代码，但仍然走 WSL
    run_predict(
        to_pred_dir=Path(to_pred_dir),
        output_dir=Path(output_dir),
        task_name=str(task_name),
        model=str(model),
        folds=str(folds),
        pattern="*.nii.gz",
        use_rglob=False,
    )
