import yaml
from pathlib import Path
import numpy as np
from typing import Tuple

def generate_spatial_bounding_box(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """简单的边界框生成函数"""
    # 移除batch维度
    if mask.ndim == 4:
        mask = mask[0]
    
    # 找到非零像素的坐标
    coords = np.where(mask > 0)
    
    if len(coords[0]) == 0:
        # 如果没有非零像素，返回整个图像范围
        return np.array([0, 0, 0]), np.array(mask.shape)
    
    # 计算每个维度的最小和最大坐标
    roi_start = np.array([np.min(c) for c in coords])
    roi_end = np.array([np.max(c) + 1 for c in coords])  # +1因为是排他的上界
    
    return roi_start, roi_end