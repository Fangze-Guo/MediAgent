# -*- coding: utf-8 -*-
"""
utils/my_breast.py —— Windows/Linux 通用与路径安全版

改动要点：
- 相对导入：from . import base
- 统一使用 pathlib.Path；给 SimpleITK 传 str(path)
- 去除 split('/')，改为 Path(...).name
- 进程池在 Windows 无 main 守卫时自动降级为串行执行（避免崩溃）
- 写文件前确保父目录存在
"""

from __future__ import annotations

import os
import re
import numpy as np
from pathlib import Path
from typing import Dict, Iterable, Tuple, Optional

import SimpleITK as sitk
from scipy.ndimage import binary_fill_holes
from skimage import measure
from skimage.morphology import dilation, erosion
import cv2
import torch  # rot90 用得到
from skimage.measure import label, regionprops
from tqdm.auto import tqdm

# 包内相对导入（保证可移植）
from . import base

# 并行
from concurrent.futures import ProcessPoolExecutor, as_completed


# ============== 基础工具 ==============

def _ensure_parent(p: Path) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)


# ============== I/O 与公共处理 ==============

def read_images(file_path: Path) -> Tuple[sitk.Image, Dict[str, str]]:
    """
    读取 DICOM 序列为 sitk.Image，并从任意一帧读出简单元信息。
    """
    file_path = Path(file_path)
    series_reader = sitk.ImageSeriesReader()
    series_files_path = series_reader.GetGDCMSeriesFileNames(str(file_path))
    series_reader.SetFileNames(series_files_path)
    images = series_reader.Execute()

    file_reader = sitk.ImageFileReader()
    # 安全地取一个文件（若第 6 个不存在则取第一个）
    pick_index = 6 if len(series_files_path) > 6 else 0
    file_reader.SetFileName(series_files_path[pick_index])
    file_reader.ReadImageInformation()
    patient_id = file_reader.GetMetaData("0010|0020") if file_reader.HasMetaDataKey("0010|0020") else "unknown"
    study_date = file_reader.GetMetaData("0008|0020") if file_reader.HasMetaDataKey("0008|0020") else "unknown"
    manufacturer = file_reader.GetMetaData("0008|0070") if file_reader.HasMetaDataKey("0008|0070") else "unknown"
    meta_data = {"id": patient_id, "date": study_date, "model": manufacturer}
    return images, meta_data


def make_dirs(path: Path | str) -> Path:
    """
    兼容旧接口；返回 Path。
    """
    p = Path(path)
    if not p.exists():
        print(f" [*] Make directories : {p}")
        p.mkdir(parents=True, exist_ok=True)
    return p


def morph_iter(slices: np.ndarray, op, kernel: np.ndarray, iter_num: int) -> np.ndarray:
    oped_mask = None
    for i in range(iter_num):
        if i == 0:
            oped_mask = op(slices, kernel)
        else:
            oped_mask = op(oped_mask, kernel)
    return oped_mask


def get_corrected_region(mask_path: Path) -> Tuple[np.ndarray, Tuple[slice, slice, slice]]:
    mask_arr = sitk.GetArrayFromImage(sitk.ReadImage(str(mask_path)))
    mask_arr[mask_arr > 0] = 1
    # 保留最大连通域
    cor_mask_np = max_connected_domain_process(origin_img_nparr=mask_arr)
    # 计算 3D bbox
    b_box = get_breast_box_3d(cor_mask_np, if_64=True)
    return cor_mask_np, b_box


# ============== 最大连通域等形态处理 ==============

def max_connected_domain_process(origin_img_nparr: np.ndarray, output: Optional[Path] = None) -> np.ndarray:
    d, w, h = origin_img_nparr.shape
    layer_nparr = np.zeros((d, w, h)).astype(np.int16)

    # 填充内部小孔
    for i in range(d):
        slices = origin_img_nparr[i, :, :]
        fillholes = binary_fill_holes(slices)
        layer_nparr[i, :, :] = fillholes

    # 保留最大联通域
    [region_labels, num] = measure.label(layer_nparr, return_num=True)
    region_prop = measure.regionprops(region_labels)

    if num == 0:
        max_connected_domain_img = np.zeros_like(layer_nparr, dtype=np.int8)
    else:
        area_box = [rp.area for rp in region_prop]
        max_region_label = area_box.index(max(area_box)) + 1
        region_labels[region_labels != max_region_label] = 0
        region_labels[region_labels == max_region_label] = 1
        max_connected_domain_img = np.array(region_labels, dtype=np.int8)

    if output is not None:
        _ensure_parent(output)
        max_connected_domain_sitk_img = sitk.GetImageFromArray(max_connected_domain_img)
        sitk.WriteImage(max_connected_domain_sitk_img, str(output))

    return max_connected_domain_img


def get_breast_box_3d(mask_array: np.ndarray, if_64: bool = False) -> Tuple[slice, slice, slice]:
    mask_voxel_coords = np.where(mask_array)
    mindidx = int(np.min(mask_voxel_coords[0]))
    maxdidx = int(np.max(mask_voxel_coords[0])) + 1
    minhidx = int(np.min(mask_voxel_coords[1]))
    maxhidx = int(np.max(mask_voxel_coords[1])) + 1
    minwidx = int(np.min(mask_voxel_coords[2]))
    maxwidx = int(np.max(mask_voxel_coords[2])) + 1

    # 保证 y 轴尺寸 >= 64
    if if_64:
        diff = maxhidx - minhidx
        if diff <= 64:
            print(f"[H] -> ({diff})")
            ep = int((64 - diff) / 2 + 2)
            maxhidx += ep
            minhidx -= ep
            print(f"Corrected [H] -> ({maxhidx - minhidx})")

    resizer = (slice(mindidx, maxdidx), slice(minhidx, maxhidx), slice(minwidx, maxwidx))
    return resizer


# ============== 去噪（可选） ==============

def denoising(image: Path | str, dst_image: Path | str) -> None:
    image = Path(image)
    dst_image = Path(dst_image)
    raw_image_sitk = sitk.ReadImage(str(image))
    raw_image = sitk.GetArrayFromImage(raw_image_sitk)

    max_value = np.percentile(raw_image, 99.8)
    raw_image[raw_image > max_value] = max_value
    raw_image = raw_image.astype(np.float32)

    denoising_raw_stack = []
    raw_image[raw_image < 0] = 0
    for s2dm in raw_image:
        if s2dm.max() <= 0:
            print("Invalid Slice", image.name)
            denoising_raw_stack.append(s2dm)
        else:
            s2dm *= (255.0 / s2dm.max())  # 归一化到 0~255
            s2dm = np.uint8(s2dm)
            dn_s2d = cv2.fastNlMeansDenoising(s2dm, None, 27, 7, 21)
            denoising_raw_stack.append(dn_s2d)

    dn_3d_raw = np.stack(denoising_raw_stack, axis=0)
    dn_3d_raw_img = sitk.GetImageFromArray(dn_3d_raw.astype(np.float32))
    dn_3d_raw_img.CopyInformation(raw_image_sitk)
    _ensure_parent(dst_image)
    sitk.WriteImage(dn_3d_raw_img, str(dst_image))


def run_denoising(src_dir: Path | str, dst_dir: Path | str, use_multiprocessing: bool = False) -> None:
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    image_paths = [p for p in src_dir.iterdir() if p.is_file()]

    # Windows 下没有 main 守卫时，进程池容易出问题；这里自动降级为串行
    if use_multiprocessing and os.name == "nt":
        print("[my_breast] Windows 环境未确保 main 守卫，已自动降级为串行去噪。")
        use_multiprocessing = False

    if use_multiprocessing:
        pbar = tqdm(image_paths, desc="Denoising with Multiprocessing")
        with ProcessPoolExecutor() as executor:
            futures = []
            futures_dict = {}
            for image in image_paths:
                out_path = dst_dir / image.name
                f = executor.submit(denoising, image, out_path)
                futures.append(f)
                futures_dict[f] = image.name
            for f in as_completed(futures):
                image_name = futures_dict[f]
                pbar.set_postfix_str(f"{image_name} is finished")
                pbar.update(1)
    else:
        pbar = tqdm(image_paths, desc="Denoising")
        for image in pbar:
            pbar.set_postfix_str(f"Denoising {image.name}")
            denoising(image, dst_dir / image.name)


# ============== 旋转（厂商差异处理） ==============

def rotate180(images, models: str):
    import torchio as tio
    if bool(re.search("GE", models, re.I)):
        tio_image_tensor = torch.rot90(images.data, k=-2, dims=[1, 2])
        tio_new_image = tio.ScalarImage(tensor=tio_image_tensor)
    else:
        tio_new_image = images
    return tio_new_image


# ============== N4 偏置场校正（可选） ==============

def n4_trans(image_in: np.ndarray, mask_in: np.ndarray, out: Optional[Path] = None) -> np.ndarray:
    image_ = sitk.Cast(sitk.GetImageFromArray(image_in), sitk.sitkFloat32)
    mask_  = sitk.Cast(sitk.GetImageFromArray(mask_in),  sitk.sitkUInt8)
    print(image_.GetSize(), mask_.GetSize())
    n4_corrector = sitk.N4BiasFieldCorrectionImageFilter()
    n4_corrector.SetMaximumNumberOfIterations((4, 100))
    res = n4_corrector.Execute(image_, mask_)
    if out is not None:
        _ensure_parent(out)
        sitk.WriteImage(res, str(out))
    print("N4 Done...")
    return sitk.GetArrayFromImage(res)


# ============== mask 后处理与派生区域 ==============

def mcd(raw_mask_np: np.ndarray, is_mirrored_mask: bool = False) -> np.ndarray:
    # 二值化
    raw_mask_np = (raw_mask_np > 0).astype(np.uint8)

    # 裁掉最前/最后 10% 的切片
    d = raw_mask_np.shape[0]
    raw_mask_np[: int(d * 0.1), :, :] = 0
    raw_mask_np[int(d * 0.9) :, :, :] = 0

    cor_mask_np = max_connected_domain_process(raw_mask_np)

    if is_mirrored_mask:
        xx = np.split(cor_mask_np, 2, axis=2)
        xx[1] = np.flip(xx[1], axis=2)
        xmax = np.stack(xx, axis=0).max(axis=0)
        xx = np.concatenate((xmax, np.flip(xmax, axis=2)), axis=2)
        cor_mask_np = xx
    return cor_mask_np


def various_mask(cor_mask_np: np.ndarray) -> Dict[str, np.ndarray]:
    skin_iter = 4
    chest_wall_iter = 16

    skin_op_kernel = np.array([[1, 1, 1],
                               [0, 1, 0],
                               [0, 0, 0]])
    wall_op_kernel = np.array([[0, 1, 0],
                               [0, 1, 0],
                               [0, 0, 0]])

    skin_stack, wall_stack, pbr_stack, out_stack, entire_stack = [], [], [], [], []
    for s2dm in cor_mask_np:
        # skin: erosion
        s2d_ero_skin = morph_iter(s2dm, erosion, skin_op_kernel, skin_iter)
        s2d_skin = s2dm - s2d_ero_skin

        # chest wall: dilation
        s2d_dila_wall = morph_iter(s2dm, dilation, wall_op_kernel, chest_wall_iter)
        s2d_wall = s2d_dila_wall - s2dm
        s2d_wall[s2d_wall > 0] = 2

        # pure breast
        s2d_pure = s2dm - s2d_skin
        s2d_pure[s2d_pure > 0] = 4

        # outside + entire
        s2d_outside = s2d_skin + s2d_wall
        s2d_entire_struct = s2d_outside + s2d_pure

        skin_stack.append(s2d_skin)
        wall_stack.append(s2d_wall)
        pbr_stack.append(s2d_pure)
        out_stack.append(s2d_outside)
        entire_stack.append(s2d_entire_struct)

    b3d_skin   = np.stack(skin_stack, axis=0)
    b3d_wall   = np.stack(wall_stack, axis=0)
    b3d_pbr    = np.stack(pbr_stack, axis=0)
    b3d_out    = np.stack(out_stack, axis=0)
    b3d_entire = np.stack(entire_stack, axis=0)

    return dict(skin=b3d_skin, chest_wall=b3d_wall, pure_breast=b3d_pbr, outside=b3d_out, entire=b3d_entire)


def run_correct_breast_mask(raw_mask_dir: Path, mcd_mask_dir: Path,
                            pattern: str = "*.nii.gz", use_rglob: bool = False,
                            is_mirrored_mask: bool = False) -> None:
    raw_mask_dir = Path(raw_mask_dir)
    mcd_mask_dir = Path(mcd_mask_dir)
    glob_iter = base.rglob(raw_mask_dir, pattern) if use_rglob else raw_mask_dir.glob(pattern)

    for nii_path in glob_iter:
        nii_path = Path(nii_path)
        try:
            raw_mask_sitk = sitk.ReadImage(str(nii_path))
            raw_mask_np = sitk.GetArrayFromImage(raw_mask_sitk)
            cor_mask_np = mcd(raw_mask_np, is_mirrored_mask=is_mirrored_mask)

            D, H, W = cor_mask_np.shape
            left_cor = cor_mask_np[:, :, W // 2 : W]
            right_cor = cor_mask_np[:, :, 0 : W // 2]
            # 简单阈值：一侧极小则分别对左右半区重新做 mcd，再拼回
            if left_cor.sum() < 30 or right_cor.sum() < 30:
                left_cor  = mcd(raw_mask_np[:, :, W // 2 : W], is_mirrored_mask=is_mirrored_mask)
                right_cor = mcd(raw_mask_np[:, :, 0 : W // 2], is_mirrored_mask=is_mirrored_mask)
                cor_mask_np = np.concatenate((right_cor, left_cor), axis=2)

            dst_nii_path = mcd_mask_dir / nii_path.name
            _ensure_parent(dst_nii_path)
            dst_nii_sitk = sitk.GetImageFromArray(cor_mask_np)
            dst_nii_sitk.CopyInformation(raw_mask_sitk)
            sitk.WriteImage(dst_nii_sitk, str(dst_nii_path))
        except Exception as e:
            print(f"Failed in {nii_path}: {e}")


def run_various_mask(cor_mask_dir: Path, dst_mask_root: Path,
                     pattern: str = "*.nii.gz", use_rglob: bool = False) -> None:
    cor_mask_dir = Path(cor_mask_dir)
    dst_mask_root = Path(dst_mask_root)

    glob_iter = base.rglob(cor_mask_dir, pattern) if use_rglob else cor_mask_dir.glob(pattern)
    for nii_path in glob_iter:
        nii_path = Path(nii_path)
        cor_mask_sitk = sitk.ReadImage(str(nii_path))
        cor_mask_np = sitk.GetArrayFromImage(cor_mask_sitk)
        res = various_mask(cor_mask_np)
        for k, v in res.items():
            dst_nii_path = dst_mask_root / k / nii_path.name
            _ensure_parent(dst_nii_path)
            dst_nii_sitk = sitk.GetImageFromArray(v)
            dst_nii_sitk.CopyInformation(cor_mask_sitk)
            sitk.WriteImage(dst_nii_sitk, str(dst_nii_path))


def run_generate_breast_region(img_dir: Path, mask_dir: Path, dst_dir: Path,
                               pattern: str = "*.nii.gz", use_rglob: bool = False,
                               is_N4: bool = False) -> None:
    img_dir = Path(img_dir)
    mask_dir = Path(mask_dir)
    dst_dir = Path(dst_dir)

    glob_iter = base.rglob(img_dir, pattern) if use_rglob else img_dir.glob(pattern)
    path_dict = {}
    for path in glob_iter:
        path = Path(path)
        pid, dx, cx = base.pid_dx_cx_parser(path.name)
        for key in [f"{pid}_{dx}_{cx}", f"{pid}_{dx}", f"{pid}"]:
            path_dict[key] = path

    glob_iter = base.rglob(mask_dir, pattern) if use_rglob else mask_dir.glob(pattern)
    for mask_path in tqdm(list(glob_iter)):
        mask_path = Path(mask_path)
        pid, dx, cx = base.pid_dx_cx_parser(mask_path.name)

        img_path = None
        for key in [f"{pid}_{dx}_{cx}", f"{pid}_{dx}", f"{pid}"]:
            if key in path_dict:
                img_path = path_dict[key]
                break
        if img_path is None:
            print(f"Can't find image path for {mask_path.name}")
            continue

        img_sitk  = sitk.ReadImage(str(img_path))
        mask_sitk = sitk.ReadImage(str(mask_path))
        img_arr  = sitk.GetArrayFromImage(img_sitk)
        mask_arr = sitk.GetArrayFromImage(mask_sitk)
        if img_arr.shape != mask_arr.shape:
            print(pid, dx, "wrong shape: ", img_path, mask_path)
            continue

        region_arr = img_arr * mask_arr
        if is_N4:
            region_arr = n4_trans(region_arr, mask_arr)

        breast_region_path = dst_dir / img_path.name
        _ensure_parent(breast_region_path)
        region_img = sitk.GetImageFromArray(region_arr)
        region_img.CopyInformation(img_sitk)
        sitk.WriteImage(region_img, str(breast_region_path))


def run_generate_breast_region_v2(img_dir: Path, mask_dir: Path, dst_dir: Path,
                                  pattern: str = "*.nii.gz", use_rglob: bool = False,
                                  is_N4: bool = False) -> None:
    img_dir = Path(img_dir)
    mask_dir = Path(mask_dir)
    dst_dir = Path(dst_dir)

    img_path_list  = list(sorted(base.rglob(img_dir, pattern)  if use_rglob else img_dir.glob(pattern)))
    mask_path_list = list(sorted(base.rglob(mask_dir, pattern) if use_rglob else mask_dir.glob(pattern)))

    for img_path, mask_path in tqdm(list(zip(img_path_list, mask_path_list))):
        img_path  = Path(img_path)
        mask_path = Path(mask_path)
        assert img_path.name == mask_path.name, f"name mismatch: {img_path.name} vs {mask_path.name}"

        img_sitk = sitk.ReadImage(str(img_path))
        img_arr  = sitk.GetArrayFromImage(img_sitk)
        mask_arr = sitk.GetArrayFromImage(sitk.ReadImage(str(mask_path)))
        region_arr = img_arr * mask_arr
        if is_N4:
            region_arr = n4_trans(region_arr, mask_arr)

        breast_region_path = dst_dir / img_path.name
        _ensure_parent(breast_region_path)
        region_img = sitk.GetImageFromArray(region_arr)
        region_img.CopyInformation(img_sitk)
        sitk.WriteImage(region_img, str(breast_region_path))


# ============== 小连通域移除（统计信息返回） ==============

def remove_small_components(src_path: Path | str, dst_path: Path | str, min_pixels: int = 10) -> Dict[str, int]:
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    mask_sitk = sitk.ReadImage(str(src_path))
    mask_np = sitk.GetArrayFromImage(mask_sitk).astype(np.uint8)

    # 统计原始信息
    original_foreground_pixels = int(np.sum(mask_np > 0))

    # 先二值化再连通域
    labeled_mask = label(mask_np > 0)
    regions = regionprops(labeled_mask)

    original_components = len(regions)
    small_components_count = 0
    removed_pixels = 0

    for region in regions:
        if region.area < min_pixels:
            small_components_count += 1
            removed_pixels += int(region.area)
            labeled_mask[labeled_mask == region.label] = 0

    # 最终连通域数
    final_labeled_mask = label(labeled_mask > 0)
    final_regions = regionprops(final_labeled_mask)
    final_components = len(final_regions)
    final_foreground_pixels = int(np.sum(labeled_mask > 0))

    # 输出
    dst_sitk = sitk.GetImageFromArray((labeled_mask > 0).astype(np.uint8))
    dst_sitk.SetOrigin(mask_sitk.GetOrigin())
    dst_sitk.SetSpacing(mask_sitk.GetSpacing())
    dst_sitk.SetDirection(mask_sitk.GetDirection())

    _ensure_parent(dst_path)
    sitk.WriteImage(dst_sitk, str(dst_path))

    return {
        "original_components": original_components,
        "original_pixels": original_foreground_pixels,
        "final_components": final_components,
        "final_pixels": final_foreground_pixels,
        "removed_components": small_components_count,
        "removed_pixels": removed_pixels,
        "min_pixels_threshold": min_pixels,
    }
