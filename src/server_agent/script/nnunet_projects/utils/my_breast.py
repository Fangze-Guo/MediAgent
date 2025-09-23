import os
import re
from os.path import exists
from pathlib import Path

import SimpleITK as sitk
import cv2
import numpy as np
import torch
from scipy.ndimage import binary_fill_holes
from skimage import measure
from skimage.measure import label, regionprops
from skimage.morphology import dilation, erosion
from tqdm.auto import tqdm

from utils import base


def read_images(file_path):
    series_reader = sitk.ImageSeriesReader()
    series_files_path = series_reader.GetGDCMSeriesFileNames(file_path)
    series_reader.SetFileNames(series_files_path)
    images = series_reader.Execute()

    file_reader = sitk.ImageFileReader()
    file_reader.SetFileName(series_files_path[6])
    file_reader.ReadImageInformation()
    patient_id = file_reader.GetMetaData("0010|0020") if file_reader.HasMetaDataKey("0010|0020") else "unknown"
    study_date = file_reader.GetMetaData("0008|0020") if file_reader.HasMetaDataKey("0008|0020") else "unknown"
    manufacturer = file_reader.GetMetaData("0008|0070") if file_reader.HasMetaDataKey("0008|0070") else "unknown"
    meta_data = {'id': patient_id, 'date': study_date, 'model': manufacturer}

    return images, meta_data


def make_dirs(path):
    if not exists(path):
        print(" [*] Make directories : {}".format(path))
        os.makedirs(path)
    return path


def morph_iter(slices, op, kernel, iter_num):
    oped_mask = None
    for i in range(0, iter_num):
        if i == 0:
            oped_mask = op(slices, kernel)
        else:
            oped_mask = op(oped_mask, kernel)
    return oped_mask


def get_corrected_region(mask_path):
    mask_arr = sitk.GetArrayFromImage(sitk.ReadImage(mask_path))
    mask_arr[mask_arr > 0] = 1
    # ! breast maybe hasn't only one connection domain
    cor_mask_np = max_connected_domain_process(origin_img_nparr=mask_arr)
    # :: bounding box
    b_box = get_breast_box_3d(cor_mask_np, if_64=True)
    return cor_mask_np, b_box


def max_connected_domain_process(origin_img_nparr, output=None):
    d, w, h = origin_img_nparr.shape
    layer_nparr = np.zeros((d, w, h)).astype(np.int16)

    # 填充内部小孔
    for i in range(d):
        slices = origin_img_nparr[i, :, :]
        fillholes = binary_fill_holes(slices)
        layer_nparr[i, :, :] = fillholes

    # 保留最大联通域
    area_box = []
    [region_labels, num] = measure.label(layer_nparr, return_num=True)
    region_prop = measure.regionprops(region_labels)

    for r in range(num):
        area_box.append(region_prop[r].area)

    max_region_label = area_box.index(max(area_box)) + 1

    region_labels[region_labels != max_region_label] = 0
    region_labels[region_labels == max_region_label] = 1
    max_connected_domain_img = np.array(region_labels, dtype=np.int8)

    if output is not None:
        max_connected_domain_sitk_img = sitk.GetImageFromArray(max_connected_domain_img)
        sitk.WriteImage(max_connected_domain_sitk_img, output)

    return max_connected_domain_img


def get_breast_box_3d(mask_array, if_64=False):
    mask_voxel_coords = np.where(mask_array)
    mindidx = int(np.min(mask_voxel_coords[0]))
    maxdidx = int(np.max(mask_voxel_coords[0])) + 1
    minhidx = int(np.min(mask_voxel_coords[1]))
    maxhidx = int(np.max(mask_voxel_coords[1])) + 1
    minwidx = int(np.min(mask_voxel_coords[2]))
    maxwidx = int(np.max(mask_voxel_coords[2])) + 1

    # ! 保证 y轴尺寸 大于 patch-size(64)
    if if_64:
        diff = maxhidx - minhidx
        if diff <= 64:
            print(f'[H] -> ({diff})')
            ep = int((64 - diff) / 2 + 2)
            maxhidx += ep
            minhidx -= ep
            print(f'Corrected [H] -> ({maxhidx - minhidx})')
    bbox = [[mindidx, maxdidx], [minhidx, maxhidx], [minwidx, maxwidx]]
    resizer = (slice(bbox[0][0], bbox[0][1]), slice(bbox[1][0], bbox[1][1]), slice(bbox[2][0], bbox[2][1]))
    return resizer


# 2024-03-08
def denoising(image, dst_image):
    raw_image_sitk = sitk.ReadImage(image)
    raw_image = sitk.GetArrayFromImage(raw_image_sitk)
    # :: 取CI
    max_value = np.percentile(raw_image, 99.8)
    # min_value = np.percentile(raw_image, 5)

    raw_image[raw_image > max_value] = max_value
    # raw_image[raw_image < min_value] = min_value
    raw_image = raw_image.astype(np.float32)
    # :: 在slice 2d 上操作denoising
    denoising_raw_stack = []
    # print(image.split('/')[-1],'Denoising...')
    raw_image[raw_image < 0] = 0
    for s2dm in raw_image:
        if s2dm.max() <= 0:
            # print('Invalid Slice')
            print('Invalid Slice', image.split('/')[-1])
            denoising_raw_stack.append(s2dm)
        else:
            s2dm *= (255.0 / s2dm.max())  # ! raw MRI 需要normalization到 0 ~ 255
            s2dm = np.uint8(s2dm)
            dn_s2d = cv2.fastNlMeansDenoising(s2dm, None, 27, 7, 21)  # ? 15倍denoise
            denoising_raw_stack.append(dn_s2d)
            pass

    dn_3d_raw = np.stack(denoising_raw_stack, axis=0)
    # print('Denoising RAW-MRI <* Get! *>')

    dn_3d_raw_img = sitk.GetImageFromArray(dn_3d_raw.astype(np.float32))
    dn_3d_raw_img.CopyInformation(raw_image_sitk)
    sitk.WriteImage(dn_3d_raw_img, dst_image)


def run_denoising(src_dir, dst_dir, use_multiprocessing=False):
    image_paths = [os.path.join(src_dir, img) for img in os.listdir(src_dir)]

    if use_multiprocessing:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        pbar = tqdm(image_paths, desc='Denoising with Multiprocessing')
        with ProcessPoolExecutor() as executor:
            futures = []
            futures_dict = {}
            for image in image_paths:
                f = executor.submit(denoising, image, os.path.join(dst_dir, image.split('/')[-1]))
                futures.append(f)
                futures_dict[f] = image.split('/')[-1]
            for f in as_completed(futures):
                image_name = futures_dict[f]
                pbar.set_postfix_str(f'{image_name} is finished')  # 并行时，tqdm只能显示完成的名字，不能显示正在处理的名字
                pbar.update(1)
    else:
        pbar = tqdm(image_paths, desc='Denoising')
        for image in pbar:
            pbar.set_postfix_str(f'Denoising {image.split("/")[-1]}')
            denoising(image, os.path.join(dst_dir, image.split('/')[-1]))


def rotate180(images, models: str):
    import torchio as tio
    tio_new_image = None
    if bool(re.search('GE', models, re.I)):
        tio_image_tensor = torch.rot90(images.data, k=-2, dims=[1, 2])
        tio_new_image = tio.ScalarImage(tensor=tio_image_tensor)
    else:
        tio_new_image = images

    return tio_new_image


def n4_trans(image_in, mask_in, out=None):
    image_ = sitk.Cast(sitk.GetImageFromArray(image_in), sitk.sitkFloat32)
    mask_ = sitk.Cast(sitk.GetImageFromArray(mask_in), sitk.sitkUInt8)
    print(image_.GetSize(), mask_.GetSize())
    n4_corrector = sitk.N4BiasFieldCorrectionImageFilter()
    n4_corrector.SetMaximumNumberOfIterations((4, 100))
    res = n4_corrector.Execute(image_, mask_)
    if out is not None:
        sitk.WriteImage(res, out)
    print(f'N4 Done...')
    return sitk.GetArrayFromImage(res)


def mcd(raw_mask_np, is_mirrored_mask=False):
    # *:: 最大连通域处理
    raw_mask_np[raw_mask_np > 0] = 1

    # *:: 裁减保留80%slices
    raw_mask_np[:int(raw_mask_np.shape[0] * 0.1), :, :] = 0
    raw_mask_np[int(raw_mask_np.shape[0] * 0.9):, :, :] = 0

    # ! 推理的原始乳腺mask 必须做 最大连通域处理
    cor_mask_np = max_connected_domain_process(raw_mask_np)

    if is_mirrored_mask:
        xx = np.split(cor_mask_np, 2, axis=2)
        xx[1] = np.flip(xx[1], axis=2)
        xmax = np.stack(xx, axis=0).max(axis=0)
        xx = np.concatenate((xmax, np.flip(xmax, axis=2)), axis=2)
        cor_mask_np = xx
    return cor_mask_np


def various_mask(cor_mask_np):
    skin_iter = 4
    chest_wall_iter = 16

    skin_op_kernel = np.array([[1, 1, 1],
                               [0, 1, 0],
                               [0, 0, 0]])

    wall_op_kernel = np.array([[0, 1, 0],
                               [0, 1, 0],
                               [0, 0, 0]])
    # *:: 分slice在2D上进行操作
    skin_stack = []
    wall_stack = []  # ? wall => chest wall
    pbr_stack = []  # ? pb => pure breast region
    out_stack = []
    entire_stack = []
    for s2dm in cor_mask_np:
        # * skin op => erosion
        s2d_ero_skin = morph_iter(s2dm, erosion, skin_op_kernel, skin_iter)
        s2d_skin = s2dm - s2d_ero_skin

        # * chest wall op => dilation
        s2d_dila_wall = morph_iter(s2dm, dilation, wall_op_kernel, chest_wall_iter)
        s2d_wall = s2d_dila_wall - s2dm
        s2d_wall[s2d_wall > 0] = 2

        # * pure breast region
        s2d_pure = s2dm - s2d_skin
        s2d_pure[s2d_pure > 0] = 4

        # * skin + chest wall
        s2d_outside = s2d_skin + s2d_wall
        s2d_entire_struct = s2d_outside + s2d_pure

        skin_stack.append(s2d_skin)
        wall_stack.append(s2d_wall)
        pbr_stack.append(s2d_pure)
        out_stack.append(s2d_outside)
        entire_stack.append(s2d_entire_struct)
        pass

    # :: 2d -->stack--> 3d
    b3d_skin = np.stack(skin_stack, axis=0)
    b3d_wall = np.stack(wall_stack, axis=0)
    b3d_pbr = np.stack(pbr_stack, axis=0)
    b3d_out = np.stack(out_stack, axis=0)
    b3d_entire = np.stack(entire_stack, axis=0)

    return dict(skin=b3d_skin, chest_wall=b3d_wall, pure_breast=b3d_pbr, outside=b3d_out, entire=b3d_entire)


def run_correct_breast_mask(raw_mask_dir, mcd_mask_dir, pattern="*.nii.gz", use_rglob=False, is_mirrored_mask=False):
    glob_iter = base.rglob(raw_mask_dir, pattern) if use_rglob else raw_mask_dir.glob(pattern)
    for nii_path in glob_iter:

        # 2025-05-24
        try:
            raw_mask_sitk = sitk.ReadImage(nii_path)
            raw_mask_np = sitk.GetArrayFromImage(raw_mask_sitk)
            cor_mask_np = mcd(raw_mask_np, is_mirrored_mask=is_mirrored_mask)
            D, H, W = cor_mask_np.shape
            left_cor_mask_np = cor_mask_np[:, :, W // 2:W]
            right_cor_mask_np = cor_mask_np[:, :, 0:W // 2]
            if left_cor_mask_np.sum() < 30 or right_cor_mask_np.sum() < 30:  # 一个乳房区域不可能小于30吧？
                left_cor_mask_np = mcd(raw_mask_np[:, :, W // 2:W], is_mirrored_mask=is_mirrored_mask)
                right_cor_mask_np = mcd(raw_mask_np[:, :, 0:W // 2], is_mirrored_mask=is_mirrored_mask)
                cor_mask_np = np.concatenate((right_cor_mask_np, left_cor_mask_np), axis=2)

            dst_nii_path = mcd_mask_dir / nii_path.name
            dst_nii_path.parent.mkdir(parents=True, exist_ok=True)
            dst_nii_sitk = sitk.GetImageFromArray(cor_mask_np)
            dst_nii_sitk.CopyInformation(raw_mask_sitk)
            sitk.WriteImage(dst_nii_sitk, dst_nii_path)
        except Exception as e:
            print(f"Failed in {nii_path}", e)


def run_various_mask(cor_mask_dir, dst_mask_root, pattern="*.nii.gz", use_rglob=False):
    glob_iter = base.rglob(cor_mask_dir, pattern) if use_rglob else cor_mask_dir.glob(pattern)
    for nii_path in glob_iter:
        cor_mask_sitk = sitk.ReadImage(nii_path)
        cor_mask_np = sitk.GetArrayFromImage(cor_mask_sitk)
        res = various_mask(cor_mask_np)
        for k, v in res.items():
            dst_nii_path = dst_mask_root / k / nii_path.name
            dst_nii_path.parent.mkdir(parents=True, exist_ok=True)
            dst_nii_sitk = sitk.GetImageFromArray(v)
            dst_nii_sitk.CopyInformation(cor_mask_sitk)
            sitk.WriteImage(dst_nii_sitk, dst_nii_path)


def run_generate_breast_region(img_dir, mask_dir, dst_dir, pattern="*.nii.gz", use_rglob=False, is_N4=False):
    glob_iter = base.rglob(img_dir, pattern) if use_rglob else img_dir.glob(pattern)
    path_dict = {}
    for path in glob_iter:
        pid, dx, cx = base.pid_dx_cx_parser(path.name)
        for key in [f"{pid}_{dx}_{cx}", f"{pid}_{dx}", f"{pid}"]:
            path_dict[key] = path

    glob_iter = base.rglob(mask_dir, pattern) if use_rglob else mask_dir.glob(pattern)
    for mask_path in tqdm(list(glob_iter)):
        pid, dx, cx = base.pid_dx_cx_parser(mask_path.name)

        img_path = None
        for key in [f"{pid}_{dx}_{cx}", f"{pid}_{dx}", f"{pid}"]:
            if key in path_dict:
                img_path = path_dict[key]
                break
        if img_path is None:
            print(f"Can't find image path for {mask_path.name}")
            continue

        img_sitk = sitk.ReadImage(img_path)
        mask_sitk = sitk.ReadImage(mask_path)
        img_arr = sitk.GetArrayFromImage(img_sitk)
        mask_arr = sitk.GetArrayFromImage(mask_sitk)
        # mask_arr[mask_arr != 1] = 0
        if img_arr.shape != mask_arr.shape:
            print(pid, dx, "wrong shape: ", img_path, mask_path)
            continue
        region_arr = img_arr * mask_arr

        breast_region_path = dst_dir / img_path.name
        breast_region_path.parent.mkdir(parents=True, exist_ok=True)
        if is_N4:
            region_arr = n4_trans(region_arr, mask_arr)
        region_img = sitk.GetImageFromArray(region_arr)
        region_img.CopyInformation(img_sitk)
        sitk.WriteImage(region_img, str(breast_region_path))


def run_generate_breast_region_v2(img_dir, mask_dir, dst_dir, pattern="*.nii.gz", use_rglob=False, is_N4=False):
    # 需要名字相同
    img_path_list = list(sorted(base.rglob(img_dir, pattern) if use_rglob else img_dir.glob(pattern)))
    mask_path_list = list(sorted(base.rglob(mask_dir, pattern) if use_rglob else mask_dir.glob(pattern)))

    for img_path, mask_path in tqdm(zip(img_path_list, mask_path_list)):
        assert img_path.name == mask_path.name
        img_sitk = sitk.ReadImage(img_path)
        img_arr = sitk.GetArrayFromImage(img_sitk)
        mask_arr = sitk.GetArrayFromImage(sitk.ReadImage(mask_path))
        region_arr = img_arr * mask_arr
        region_img = sitk.GetImageFromArray(region_arr)

        breast_region_path = dst_dir / img_path.name
        breast_region_path.parent.mkdir(parents=True, exist_ok=True)
        if is_N4:
            region_arr = n4_trans(region_arr, mask_arr)
        region_img = sitk.GetImageFromArray(region_arr)
        region_img.CopyInformation(img_sitk)
        sitk.WriteImage(region_img, str(breast_region_path))


# 2025-07-11
def remove_small_components(src_path, dst_path, min_pixels=10):
    mask_sitk = sitk.ReadImage(str(src_path))
    mask_np = sitk.GetArrayFromImage(mask_sitk).astype(np.uint8)

    # 统计原始信息
    original_foreground_pixels = np.sum(mask_np > 0)

    # 关键修改：先二值化再进行连通域分析
    labeled_mask = label(mask_np > 0)  # 添加二值化操作
    regions = regionprops(labeled_mask)

    original_components = len(regions)
    small_components_count = 0
    removed_pixels = 0

    # 记录要移除的小连通域信息
    for region in regions:
        if region.area < min_pixels:
            small_components_count += 1
            removed_pixels += region.area
            labeled_mask[labeled_mask == region.label] = 0

    # 重新标记处理后的连通域以获取准确的最终连通域数量
    final_labeled_mask = label(labeled_mask > 0)
    final_regions = regionprops(final_labeled_mask)
    final_components = len(final_regions)
    final_foreground_pixels = np.sum(labeled_mask > 0)

    # 创建输出图像
    dst_sitk = sitk.GetImageFromArray((labeled_mask > 0).astype(np.uint8))
    # copy information
    dst_sitk.SetOrigin(mask_sitk.GetOrigin())
    dst_sitk.SetSpacing(mask_sitk.GetSpacing())
    dst_sitk.SetDirection(mask_sitk.GetDirection())

    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(dst_sitk, str(dst_path))

    # 返回统计信息
    stats = {
        'original_components': original_components,
        'original_pixels': int(original_foreground_pixels),
        'final_components': final_components,
        'final_pixels': int(final_foreground_pixels),
        'removed_components': small_components_count,
        'removed_pixels': int(removed_pixels),
        'min_pixels_threshold': min_pixels,
    }

    return stats
