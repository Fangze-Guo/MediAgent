import numpy as np
import SimpleITK as sitk
from pathlib import Path
from typing import Union
import torch


def get_optimal_dtype(array: np.ndarray) -> np.dtype:
    """
    Automatically determine the optimal integer dtype based on array's value range.
    """
    if not np.issubdtype(array.dtype, np.integer):
        # If not integer, keep original dtype
        return array.dtype
    
    min_val = array.min()
    max_val = array.max()
    
    # Choose the smallest dtype that can hold the range
    if min_val >= 0:  # unsigned integers
        if max_val <= 255:
            return np.uint8
        elif max_val <= 65535:
            return np.uint16
        elif max_val <= 4294967295:
            return np.uint32
        else:
            return np.uint64
    else:  # signed integers
        if min_val >= -128 and max_val <= 127:
            return np.int8
        elif min_val >= -32768 and max_val <= 32767:
            return np.int16
        elif min_val >= -2147483648 and max_val <= 2147483647:
            return np.int32
        else:
            return np.int64

def as_numpy(image: Union[str, Path, sitk.Image, np.ndarray]) -> np.ndarray:
    if isinstance(image, (str, Path)):
        image = sitk.ReadImage(image)
    if isinstance(image, sitk.Image):
        image = sitk.GetArrayFromImage(image)
    if not isinstance(image, np.ndarray):
        raise ValueError("Image must be a string, path, sitk.Image, or numpy.ndarray")
    return image

def write_mask_nii(mask: np.ndarray, path: Union[str, Path]):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(mask, torch.Tensor):
        mask = mask.detach().cpu().numpy()
    sitk.WriteImage(sitk.GetImageFromArray(mask.astype(get_optimal_dtype(mask))), str(path))

def write_image_nii(image: np.ndarray, path: Union[str, Path]):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(image, torch.Tensor):
        image = image.detach().cpu().numpy()
    sitk.WriteImage(sitk.GetImageFromArray(image.astype(get_optimal_dtype(image))), str(path))