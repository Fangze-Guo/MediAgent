#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
train_hiomics_pipeline.py
合并版训练脚本：
- 输入多个训练数据集顶层目录（train_datasets）
- 自动找到每个数据集的唯一 csv
- 读取 csv，保留/补齐字段（PID/DX），使用 csv 内的 Center 列
- 将 image_path / mask_path 从相对 dataset_root -> 重写为相对 private_root
- 遇到坏行/坏数据集：写 out_dir/prepare_csv_errors.log 并跳过
- 拼接多个数据集为 train_concat.csv
- hiomics TrainTask 训练，task_name 固定 pCR，task_dir=out_dir
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Any

import pandas as pd

# ==== 引入 hiomics（WSL conda pyhiomics 环境里应当可用） ====
from hiomics.task.task import TrainTask
from hiomics.task.data import PathData
from hiomics.preprocessing.simpleitk_wrapper import N4Step
from hiomics.pre_segmentation.slic import PreSegmentationSLICStep
from hiomics.feature_extractor.radiomics_wrapper import FeatureExtractorRadiomicsStep
from hiomics.subregion_clustering.base import SubregionClusteringStep
from hiomics.hiomics_extractor import RadiomicsLHCPStep, GHSDStep


# =========================
# 小工具
# =========================
def log_error(log_file: Path, msg: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")


def apply_dx(id_: str) -> str:
    # e.g. TCIA-ISPY2_PID_D0 -> D0
    return id_.split("_")[-1]


def load_and_standardize_csv(csv_path: Path, errors_log: Path) -> Optional[pd.DataFrame]:
    """
    按你第一步的逻辑做字段标准化：
    - 保留 ID, PID, PCR, image_path, mask_path (+DX 可选) + Center(必须存在)
    - PID = ID 去掉最后段
    - DX 若不存在则从 ID 末段推
    - 校验 ID 唯一、DX 合法（不合法则记录日志后返回 None）
    """
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        log_error(errors_log, f"[CSV_READ_FAIL] csv={csv_path} err={e}")
        return None

    # Center 必须存在（你已保证）——若不在则该数据集整体跳过
    if "Center" not in df.columns:
        log_error(errors_log, f"[NO_CENTER_COL] csv={csv_path} columns={list(df.columns)} -> skip dataset")
        return None

    keep_cols = ["ID", "PID", "PCR", "image_path", "mask_path", "Center"]
    if "DX" in df.columns:
        keep_cols.append("DX")

    missing_cols = [c for c in keep_cols if c not in df.columns and c != "DX"]  # DX 可补
    if missing_cols:
        log_error(errors_log, f"[MISSING_COLS] csv={csv_path} missing={missing_cols} -> skip dataset")
        return None

    df = df[[c for c in keep_cols if c in df.columns]].copy()

    # PID 重算（与原逻辑一致）
    df["PID"] = df["ID"].apply(lambda x: "_".join(str(x).split("_")[:-1]))

    # DX 若没有则补
    if "DX" not in df.columns:
        df["DX"] = df["ID"].apply(apply_dx)

    # validate
    try:
        assert df.ID.nunique() == df.shape[0], "ID is not unique"
        assert set(df.DX.unique()) in [{"D0", "D3"}, {"D0"}, {"D0", "BS"}], f"DX is not valid {df.DX.unique()}"
    except Exception as e:
        log_error(errors_log, f"[VALIDATION_FAIL] csv={csv_path} err={e} -> skip dataset")
        return None

    return df


def rewrite_paths_to_private(
    df: pd.DataFrame,
    dataset_root: Path,
    private_root: Path,
    errors_log: Path,
) -> pd.DataFrame:
    """
    核心规则：
    - 原 image_path/mask_path 相对 dataset_root
    - 重写为相对 private_root
    遇到问题：写日志并跳过该行
    """
    new_rows = []
    for idx, row in df.iterrows():
        try:
            old_img_rel = Path(str(row["image_path"]))
            old_msk_rel = Path(str(row["mask_path"]))

            real_img = dataset_root / old_img_rel
            real_msk = dataset_root / old_msk_rel

            if not real_img.exists():
                log_error(errors_log, f"[MISSING_IMAGE] dataset={dataset_root} ID={row.get('ID')} img={real_img}")
                continue
            if not real_msk.exists():
                log_error(errors_log, f"[MISSING_MASK] dataset={dataset_root} ID={row.get('ID')} msk={real_msk}")
                continue

            # 改成相对 private_root
            new_img_rel = real_img.relative_to(private_root)
            new_msk_rel = real_msk.relative_to(private_root)

            row = row.copy()
            row["image_path"] = str(new_img_rel).replace("\\", "/")
            row["mask_path"] = str(new_msk_rel).replace("\\", "/")
            new_rows.append(row)
        except Exception as e:
            log_error(errors_log, f"[REWRITE_FAIL] dataset={dataset_root} ID={row.get('ID')} err={e}")
            continue

    if not new_rows:
        return df.iloc[0:0].copy()  # 空 df
    return pd.DataFrame(new_rows)


def find_single_csv(dataset_root: Path, errors_log: Path) -> Optional[Path]:
    csvs = sorted([p for p in dataset_root.iterdir() if p.is_file() and p.suffix.lower() == ".csv"])
    if len(csvs) != 1:
        log_error(errors_log, f"[CSV_COUNT_INVALID] dataset={dataset_root} csvs={csvs} -> skip dataset")
        return None
    return csvs[0]


# =========================
# 主流程
# =========================
def main(train_datasets: List[str], private_root: str, out_dir: str) -> None:
    out_dir_p = Path(out_dir).expanduser().resolve()
    out_dir_p.mkdir(parents=True, exist_ok=True)

    errors_log = out_dir_p / "prepare_csv_errors.log"
    processed_dir = out_dir_p / "processed_csvs"
    processed_dir.mkdir(parents=True, exist_ok=True)

    private_root_p = Path(private_root).expanduser().resolve()

    all_train_dfs = []

    for ds_str in train_datasets:
        dataset_root = Path(ds_str).expanduser().resolve()
        if not dataset_root.exists():
            log_error(errors_log, f"[DATASET_NOT_FOUND] dataset={dataset_root} -> skip dataset")
            continue

        csv_path = find_single_csv(dataset_root, errors_log)
        if csv_path is None:
            continue

        df = load_and_standardize_csv(csv_path, errors_log)
        if df is None or df.empty:
            log_error(errors_log, f"[EMPTY_OR_BAD_CSV] dataset={dataset_root} csv={csv_path} -> skip dataset")
            continue

        df2 = rewrite_paths_to_private(df, dataset_root, private_root_p, errors_log)
        if df2.empty:
            log_error(errors_log, f"[NO_VALID_ROWS] dataset={dataset_root} csv={csv_path} -> skip dataset")
            continue

        # 保存每个中心处理后的 csv（中心名从 Center 列拿）
        center_name = str(df2["Center"].iloc[0])
        per_center_csv = processed_dir / f"{center_name}.csv"
        df2.to_csv(per_center_csv, index=False)

        all_train_dfs.append(df2)

    if not all_train_dfs:
        raise RuntimeError(f"No valid training rows after processing. See log: {errors_log}")

    train_df = pd.concat(all_train_dfs, ignore_index=True)
    train_csv_path = processed_dir / "train_concat.csv"
    train_df.to_csv(train_csv_path, index=False)

    # =========================
    # hiomics 训练
    # =========================
    data = PathData(csv_path=str(train_csv_path), base_dir=private_root_p)

    task = TrainTask(task_name="pCR", task_dir=str(out_dir_p))
    task.add_data("00_Original", data)

    # configs 相对脚本所在目录
    script_dir = Path(__file__).resolve().parent
    cfg_dir = script_dir / "configs"

    pipeline = [
        {
            "step_name": "01_N4",
            "step_obj": N4Step(params=str(cfg_dir / "N4.yaml")),
            "input_map": {"path_data": "00_Original"},
            "force": False
        },
        {
            "step_name": "02_SLIC",
            "step_obj": PreSegmentationSLICStep(params=str(cfg_dir / "SLIC.yaml")),
            "input_map": {"path_data": "01_N4"},
            "force": False
        },
        {
            "step_name": "03_FE_Rad_ROI",
            "step_obj": FeatureExtractorRadiomicsStep(str(cfg_dir / "MR_noshape.yaml")),
            "input_map": {"path_data": "02_SLIC"},
            "force": False
        },
        {
            "step_name": "04_Clu_Rad",
            "step_obj": SubregionClusteringStep(str(cfg_dir / "GMM.yaml")),
            "input_map": {"path_data": "02_SLIC", "feature_data": "03_FE_Rad_ROI"},
            "force": False
        },
        {
            "step_name": "05_HI_RadLHCP",
            "step_obj": RadiomicsLHCPStep(params=str(cfg_dir / "RadiomicsLHCP.yaml")),
            "input_map": {"path_data": "04_Clu_Rad"},
            "force": False
        },
        {
            "step_name": "05_HI_GHSD",
            "step_obj": GHSDStep(params=str(cfg_dir / "GHSD.yaml")),
            "input_map": {"path_data": "04_Clu_Rad"},
            "force": False
        },
    ]

    global_force = False
    for cur_step in pipeline:
        global_force = global_force or cur_step.get("force", False)
        task.add_step(cur_step["step_name"], cur_step["step_obj"], cur_step["input_map"])
        task.run_step(cur_step["step_name"], n_jobs=16, force=global_force)

    task.save()

    print("[DONE] Training completed.")
    print(f"  train_csv: {train_csv_path}")
    print(f"  task_dir: {out_dir_p}")
    print(f"  errors_log: {errors_log}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-datasets", nargs="+", required=True, help="WSL paths of dataset roots")
    parser.add_argument("--private-root", required=True, help="WSL path of private root")
    parser.add_argument("--out-dir", required=True, help="WSL path of step out_dir")
    args = parser.parse_args()

    main(
        train_datasets=args.train_datasets,
        private_root=args.private_root,
        out_dir=args.out_dir,
    )
