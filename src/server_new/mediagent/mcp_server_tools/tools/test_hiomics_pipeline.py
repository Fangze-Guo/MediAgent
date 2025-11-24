#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_hiomics_pipeline.py
合并版测试脚本（融合第一步 + 第三步）：
- 输入训练产物目录（train_task_dir）
- 输入多个测试数据集顶层目录（test_datasets）
- 自动找到每个数据集的唯一 csv
- 读取 csv，保留/补齐字段（PID/DX），使用 csv 内的 Center 列
- 将 image_path / mask_path 从相对 dataset_root -> 重写为相对 private_root
- 遇到坏行/坏数据集：写 out_dir/prepare_csv_errors.log 并跳过
- 每个 <dataset_root.name>__<Center> 生成一个 processed csv
- 对每个 processed csv 建立一个 TestTask：
    task_dir = out_dir/<dataset_root.name>__<Center>
    clone_steps(train_task_dir)
    逐步 run_step
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Any, Tuple

import pandas as pd

# ==== 引入 hiomics（WSL conda pyhiomics 环境里应当可用） ====
from hiomics.task.task import TestTask
from hiomics.task.data import PathData


# =========================
# 小工具区（复用训练脚本）
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
    字段标准化：
    - 保留 ID, PID, PCR, image_path, mask_path (+DX 可选) + Center(必须存在)
    - PID = ID 去掉最后段
    - DX 若不存在则从 ID 末段推
    - 校验 ID 唯一、DX 合法
    """
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        log_error(errors_log, f"[CSV_READ_FAIL] csv={csv_path} err={e}")
        return None

    if "Center" not in df.columns:
        log_error(errors_log, f"[NO_CENTER_COL] csv={csv_path} columns={list(df.columns)} -> skip dataset")
        return None

    keep_cols = ["ID", "PID", "PCR", "image_path", "mask_path", "Center"]
    if "DX" in df.columns:
        keep_cols.append("DX")

    missing_cols = [c for c in keep_cols if c not in df.columns and c != "DX"]
    if missing_cols:
        log_error(errors_log, f"[MISSING_COLS] csv={csv_path} missing={missing_cols} -> skip dataset")
        return None

    df = df[[c for c in keep_cols if c in df.columns]].copy()

    df["PID"] = df["ID"].apply(lambda x: "_".join(str(x).split("_")[:-1]))

    if "DX" not in df.columns:
        df["DX"] = df["ID"].apply(apply_dx)

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
    遇到异常：记录并跳过该行
    """
    new_rows = []
    for _, row in df.iterrows():
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
        return df.iloc[0:0].copy()
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
def main(train_task_dir: str, test_datasets: List[str], private_root: str, out_dir: str) -> None:
    out_dir_p = Path(out_dir).expanduser().resolve()
    out_dir_p.mkdir(parents=True, exist_ok=True)

    errors_log = out_dir_p / "prepare_csv_errors.log"
    processed_dir = out_dir_p / "processed_csvs"
    processed_dir.mkdir(parents=True, exist_ok=True)

    private_root_p = Path(private_root).expanduser().resolve()
    train_task_dir_p = Path(train_task_dir).expanduser().resolve()

    # 保存每个“dataset__center”的 (tag, csv_path)
    processed_items: List[Tuple[str, Path]] = []

    # ---------- 1) prepare（第一步逻辑 + 路径重写） ----------
    for ds_str in test_datasets:
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

        center_name = str(df2["Center"].iloc[0])
        ds_tag = dataset_root.name
        tag = f"{ds_tag}__{center_name}"   # <-- 防冲突命名

        per_csv = processed_dir / f"{tag}.csv"
        df2.to_csv(per_csv, index=False)

        processed_items.append((tag, per_csv))

    if not processed_items:
        raise RuntimeError(f"No valid testing rows after processing. See log: {errors_log}")

    # ---------- 2) hiomics TestTask（第三步逻辑迁移） ----------
    for tag, csv_p in processed_items:
        center_out_dir = out_dir_p / tag
        center_out_dir.mkdir(parents=True, exist_ok=True)

        data = PathData(csv_path=str(csv_p), base_dir=private_root_p)

        task = TestTask(task_name="pCR", task_dir=str(center_out_dir))
        task.clone_steps(train_task_dir=str(train_task_dir_p))

        task.add_data("00_Original", data)

        # 逐步骤执行（顺序保持 clone 后的顺序）
        for step_name, step_item in task._steps.items():
            step_obj, input_map = step_item
            task.run_step(step_name, n_jobs=16, force=False)

        task.save()

        print(f"[DONE] Test completed for: {tag}")
        print(f"  csv: {csv_p}")
        print(f"  task_dir: {center_out_dir}")

    print("[ALL DONE] Testing finished.")
    print(f"  train_task_dir: {train_task_dir_p}")
    print(f"  out_dir: {out_dir_p}")
    print(f"  errors_log: {errors_log}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-task-dir", required=True, help="WSL path of train task dir (output of TrainTask)")
    parser.add_argument("--test-datasets", nargs="+", required=True, help="WSL paths of test dataset roots")
    parser.add_argument("--private-root", required=True, help="WSL path of private root")
    parser.add_argument("--out-dir", required=True, help="WSL path of step out_dir")
    args = parser.parse_args()

    main(
        train_task_dir=args.train_task_dir,
        test_datasets=args.test_datasets,
        private_root=args.private_root,
        out_dir=args.out_dir,
    )
