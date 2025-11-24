import SimpleITK as sitk
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Union
from pathlib import Path
from loguru import logger
import pickle

from scipy.stats import entropy
from scipy.spatial import distance_matrix
from scipy import ndimage
from hiomics.utils import parallel, generate_spatial_bounding_box, load_params
from hiomics.task.step import AbcStep
from hiomics.task.data import PathData, FeatureData


class HiomicsGHSDSingle:
    """单个图像的GHSD特征提取器"""
    def __init__(self, input_image, input_mask, **kwargs):
        if input_image is None or input_mask is None:
            msg = "Missing input image or mask"
            raise ValueError(msg)
        
        self.input_image = input_image
        self.input_mask = input_mask
        self._image = None
        self._mask = None
        self.params = kwargs

    @property
    def mask(self):
        if self._mask is None:
            self._mask = sitk.GetArrayFromImage(self.input_mask)
        return self._mask
    
    @property
    def image(self):
        if self._image is None:
            self._image = sitk.GetArrayFromImage(self.input_image)
        return self._image
        
    def get_tumoral_ecological_diversity(self):
        mask = sitk.GetArrayFromImage(self.input_mask)
        return len(np.unique(mask)) - 1

    def get_entropy(self):
        mask = sitk.GetArrayFromImage(self.input_mask)
        counts = np.bincount(mask.flatten())[1:]  # 排除背景(0)
        prob = counts / counts.sum()  
        return entropy(prob, base=2)

    def get_spatial_dispersion_index(self):
        """
        计算habitats的空间分散指数 (Spatial Dispersion Index, SDI)
        返回:
            sdi: 空间分散指数
        """
        # 获取mask数组和spacing信息
        mask = self.mask
        spacing = self.input_mask.GetSpacing()  # (x, y, z) spacing in mm
        
        # 获取所有非背景的label
        unique_labels = np.unique(mask)
        unique_labels = unique_labels[unique_labels > 0]  # 排除背景0
        
        if len(unique_labels) < 2:
            # 至少需要2个habitat才能计算SDI
            return 0.0
        
        # 计算每个label的质心坐标
        habitat_centroids = []
        for label in unique_labels:
            # 找到该label的所有体素坐标 (z, y, x)
            coords = np.argwhere(mask == label)
            if len(coords) > 0:
                # 计算质心 (z, y, x)
                centroid = np.mean(coords, axis=0)
                # 转换为物理坐标 (x, y, z) in mm
                centroid_mm = [centroid[2] * spacing[0], 
                              centroid[1] * spacing[1], 
                              centroid[0] * spacing[2]]
                habitat_centroids.append(centroid_mm)
        
        if len(habitat_centroids) < 2:
            return 0.0
            
        habitat_centroids = np.array(habitat_centroids)
        
        # 计算肿瘤总体积 (mm³)
        voxel_volume = spacing[0] * spacing[1] * spacing[2]  # mm³ per voxel
        tumor_volume = np.sum(mask > 0) * voxel_volume
        
        # 计算实际平均最近邻距离
        dists = distance_matrix(habitat_centroids, habitat_centroids)
        np.fill_diagonal(dists, np.inf)  # 忽略自身距离
        mean_observed = np.mean(np.min(dists, axis=1))
        
        # 计算随机分布预期距离 (球体模型)
        n = len(habitat_centroids)
        expected_random = 0.5 * (3 * tumor_volume / (4 * np.pi * n)) ** (1/3)
        
        # 避免除零错误
        if expected_random == 0:
            return 0.0
            
        return mean_observed / expected_random

    def get_variation_coefficient(self):
        """Calculate the coefficient of variation (CV) of intensity values."""
        image = self.image
        mask = self.mask
        values = image[mask > 0]
        mean_val = np.mean(values)
        if mean_val == 0:
            return 0.0
        return np.std(values) / mean_val


    def get_simpson_diversity_index(self):
        mask = self.mask
        counts = np.bincount(mask.flatten())[1:]
        total = counts.sum()
        if total == 0:
            return 0.0
        proportions = counts / total
        return float(1.0 - np.sum(proportions * proportions))

    def get_pielou_evenness(self):
        mask = self.mask
        unique_labels = np.unique(mask)
        unique_labels = unique_labels[unique_labels > 0]
        S = len(unique_labels)
        if S <= 1:
            return 0.0
        H = self.get_entropy()
        denom = np.log2(S)
        if denom == 0:
            return 0.0
        return float(H / denom)

    def get_berger_parker_dominance(self):
        mask = self.mask
        counts = np.bincount(mask.flatten())[1:]
        total = counts.sum()
        if total == 0:
            return 0.0
        proportions = counts / total
        return float(proportions.max())

    def get_habitat_size_cv(self):
        mask = self.mask
        counts = np.bincount(mask.flatten())[1:]
        total = counts.sum()
        if total == 0:
            return 0.0
        proportions = counts / total
        mean_val = proportions.mean()
        if mean_val == 0:
            return 0.0
        return float(proportions.std() / mean_val)

    def get_habitat_fragmentation_index(self):
        mask = self.mask
        tumor = mask > 0
        if not np.any(tumor):
            return 0.0
        unique_labels = np.unique(mask)
        unique_labels = unique_labels[unique_labels > 0]
        if len(unique_labels) == 0:
            return 0.0
        counts = np.bincount(mask.flatten())[1:]
        total = counts.sum()
        proportions = counts / total if total > 0 else np.array([])
        structure = ndimage.generate_binary_structure(rank=3, connectivity=1)
        value = 0.0
        for idx, label in enumerate(range(1, len(counts) + 1)):
            if counts[idx] == 0:
                continue
            labeled, num_comp = ndimage.label(mask == label, structure=structure)
            value += float(proportions[idx] * max(num_comp - 1, 0))
        return value

    def get_interface_area_density(self):
        mask = self.mask
        spacing = self.input_mask.GetSpacing()
        dx, dy, dz = float(spacing[0]), float(spacing[1]), float(spacing[2])
        tumor = mask > 0
        if not np.any(tumor):
            return 0.0

        # x-direction adjacencies (faces orthogonal to x => area dy*dz)
        a = mask[:, :, :-1]
        b = mask[:, :, 1:]
        valid = (a > 0) & (b > 0) & (a != b)
        area_x = float(valid.sum()) * (dy * dz)

        # y-direction adjacencies (faces orthogonal to y => area dx*dz)
        a = mask[:, :-1, :]
        b = mask[:, 1:, :]
        valid = (a > 0) & (b > 0) & (a != b)
        area_y = float(valid.sum()) * (dx * dz)

        # z-direction adjacencies (faces orthogonal to z => area dx*dy)
        a = mask[:-1, :, :]
        b = mask[1:, :, :]
        valid = (a > 0) & (b > 0) & (a != b)
        area_z = float(valid.sum()) * (dx * dy)

        A_interface = area_x + area_y + area_z
        V = float(tumor.sum()) * (dx * dy * dz)
        if V <= 0.0:
            return 0.0
        return float(A_interface / (V ** (2.0 / 3.0)))

    def get_label_transition_fraction(self):
        mask = self.mask
        tumor = mask > 0
        if not np.any(tumor):
            return 0.0

        # x-direction
        a = mask[:, :, :-1]
        b = mask[:, :, 1:]
        both = (a > 0) & (b > 0)
        diff = both & (a != b)
        total_pairs = int(both.sum())
        diff_pairs = int(diff.sum())

        # y-direction
        a = mask[:, :-1, :]
        b = mask[:, 1:, :]
        both = (a > 0) & (b > 0)
        diff = both & (a != b)
        total_pairs += int(both.sum())
        diff_pairs += int(diff.sum())

        # z-direction
        a = mask[:-1, :, :]
        b = mask[1:, :, :]
        both = (a > 0) & (b > 0)
        diff = both & (a != b)
        total_pairs += int(both.sum())
        diff_pairs += int(diff.sum())

        if total_pairs == 0:
            return 0.0
        return float(diff_pairs / total_pairs)

    def get_label_adjacency_entropy(self):
        mask = self.mask
        tumor = mask > 0
        if not np.any(tumor):
            return 0.0
        max_label = int(mask.max())
        if max_label <= 1:
            return 0.0
        base = max_label + 1

        def _pair_indices(a, b):
            both = (a > 0) & (b > 0)
            diff = both & (a != b)
            if not np.any(diff):
                return np.empty((0,), dtype=np.int64)
            v1 = a[diff].astype(np.int64)
            v2 = b[diff].astype(np.int64)
            pmin = np.minimum(v1, v2)
            pmax = np.maximum(v1, v2)
            return pmin * base + pmax

        idx_x = _pair_indices(mask[:, :, :-1], mask[:, :, 1:])
        idx_y = _pair_indices(mask[:, :-1, :], mask[:, 1:, :])
        idx_z = _pair_indices(mask[:-1, :, :], mask[1:, :, :])
        all_idx = np.concatenate([idx_x, idx_y, idx_z]) if (idx_x.size + idx_y.size + idx_z.size) > 0 else np.empty((0,), dtype=np.int64)
        if all_idx.size == 0:
            return 0.0
        _, counts = np.unique(all_idx, return_counts=True)
        probs = counts.astype(np.float64)
        probs /= probs.sum()
        return float(-np.sum(probs * np.log2(probs)))

    def get_radial_separation_index(self):
        mask = self.mask
        tumor = mask > 0
        if not np.any(tumor):
            return 0.0
        spacing = self.input_mask.GetSpacing()
        sampling = (float(spacing[2]), float(spacing[1]), float(spacing[0]))
        dt = ndimage.distance_transform_edt(tumor, sampling=sampling)
        dt_max = float(dt.max())
        if dt_max <= 0.0:
            return 0.0
        dt_norm = dt / dt_max
        total = tumor.sum()
        if total == 0:
            return 0.0
        unique_labels = np.unique(mask)
        unique_labels = unique_labels[unique_labels > 0]
        if len(unique_labels) == 0:
            return 0.0
        mu_global = float(dt_norm[tumor].mean())
        value = 0.0
        counts = np.bincount(mask.flatten())[1:]
        total_counts = counts.sum()
        if total_counts == 0:
            return 0.0
        for idx, label in enumerate(range(1, len(counts) + 1)):
            if counts[idx] == 0:
                continue
            p_i = counts[idx] / total_counts
            mu_i = float(dt_norm[mask == label].mean())
            value += float(p_i * (mu_i - mu_global) * (mu_i - mu_global))
        return value * 1000




def ghsd_worker(image_path: str, mask_path: str, enabled_features: List[str]) -> Dict[str, Any]:
    """Worker function for parallel GHSD feature extraction."""
    try:
        image_sitk = sitk.ReadImage(image_path)
        mask_sitk = sitk.ReadImage(mask_path)
        image_np = sitk.GetArrayFromImage(image_sitk)
        mask_np = sitk.GetArrayFromImage(mask_sitk)
        # Convert mask to integer type to avoid float casting issues
        mask_np = mask_np.astype(np.int32)
        mask_bin_np = np.where(mask_np > 0, 1, 0)
        
        # Get ROI
        roi_start, roi_end = generate_spatial_bounding_box(mask_bin_np)
        image_roi_np = image_np[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]
        mask_roi_np = mask_np[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]
        
        # Create ROI image and mask with proper spacing/origin
        image_roi_sitk = sitk.GetImageFromArray(image_roi_np)
        mask_roi_sitk = sitk.GetImageFromArray(mask_roi_np)
        image_roi_sitk.SetSpacing(image_sitk.GetSpacing())
        image_roi_sitk.SetOrigin(image_sitk.GetOrigin())
        mask_roi_sitk.SetSpacing(mask_sitk.GetSpacing())
        mask_roi_sitk.SetOrigin(mask_sitk.GetOrigin())
        
        # Check if mask has enough pixels
        if mask_roi_np.sum() < 5:
            logger.warning(f"{mask_path} has less than 5 pixels, filling with NaN")
            feat_dict = {feature: np.nan for feature in enabled_features}
            return {"features": feat_dict, "error": "Insufficient pixels"}
        
        # Extract GHSD features for the entire clustered mask
        extractor = HiomicsGHSDSingle(image_roi_sitk, mask_roi_sitk)
        feat_dict = {}
        
        for feature in enabled_features:
            method_name = f"get_{feature}"
            if hasattr(extractor, method_name):
                feat_dict[feature] = getattr(extractor, method_name)()
            else:
                logger.warning(f"Method {method_name} not found")
                feat_dict[feature] = np.nan
        
        return {"features": feat_dict, "error": None}
        
    except Exception as e:
        logger.error(f"Failed to extract GHSD features for {mask_path}: {e}")
        feat_dict = {feature: np.nan for feature in enabled_features}
        return {"features": feat_dict, "error": str(e)}


class HiomicsGHSD:
    """List形式的GHSD特征提取器，兼容LHCP风格的接口"""
    
    def __init__(self, input_image_paths: List[str], input_mask_paths: List[str], **kwargs):
        self.input_image_paths = input_image_paths
        self.input_mask_paths = input_mask_paths
        self.params = kwargs
        
        # 支持的特征列表
        self.available_features = [
            "tumoral_ecological_diversity",
            "entropy", 
            "spatial_dispersion_index",
            "variation_coefficient",
            "simpson_diversity_index",
            "pielou_evenness",
            "berger_parker_dominance",
            "habitat_size_cv",
            "habitat_fragmentation_index",
            "interface_area_density",
            "label_transition_fraction",
            "label_adjacency_entropy",
            "radial_separation_index"
        ]
        
        # 结果存储
        self.sr_features_df = None
        self.sr_feature_columns = None

    def get_available_features(self) -> List[str]:
        """获取所有可用的特征列表"""
        return self.available_features.copy()

    def get_tumoral_ecological_diversity(self, enabled_features: List[str] = None) -> pd.DataFrame:
        """提取tumoral_ecological_diversity特征"""
        if enabled_features is None:
            enabled_features = ["tumoral_ecological_diversity"]
        return self._extract_features(enabled_features)

    def get_entropy(self, enabled_features: List[str] = None) -> pd.DataFrame:
        """提取entropy特征"""
        if enabled_features is None:
            enabled_features = ["entropy"]
        return self._extract_features(enabled_features)

    def get_spatial_dispersion_index(self, enabled_features: List[str] = None) -> pd.DataFrame:
        """提取spatial_dispersion_index特征"""
        if enabled_features is None:
            enabled_features = ["spatial_dispersion_index"]
        return self._extract_features(enabled_features)

    def get_all_features(self, enabled_features: List[str] = None) -> pd.DataFrame:
        """提取所有或指定的特征"""
        if enabled_features is None:
            enabled_features = self.available_features
        return self._extract_features(enabled_features)

    def _extract_features(self, enabled_features: List[str]) -> pd.DataFrame:
        """内部特征提取方法"""
        n_jobs = self.params.get("n_jobs", 1)
        
        kwargs_list = []
        for idx, (image_path, mask_path) in enumerate(zip(self.input_image_paths, self.input_mask_paths)):
            kwargs_list.append({
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "enabled_features": enabled_features,
            })
        
        # 并行提取特征
        ret = parallel.worker(
            ghsd_worker, 
            kwargs_list, 
            use_multiprocessing=n_jobs > 1, 
            desc="GHSD Features", 
            max_workers=n_jobs, 
            parallel_type="process"
        )
        
        # 处理结果 - 每个case一行特征
        features_list = []
        for i, result in enumerate(ret):
            feat_dict = result["features"].copy()
            feat_dict["unique_id"] = i
            features_list.append(feat_dict)
        
        # 创建DataFrame，每个case一行
        self.sr_features_df = pd.DataFrame(features_list)
        self.sr_feature_columns = enabled_features
        
        # 重新排列列的顺序，把unique_id放在最前面
        cols = ["unique_id"] + enabled_features
        self.sr_features_df = self.sr_features_df[cols]
        
        return self.sr_features_df.copy()


class GHSDStep(AbcStep):
    """GHSD特征提取步骤类"""
    
    def __init__(self, params=None):
        if params is None:
            params = "GHSD.yaml"
            logger.info(f"Using default params for GHSD: {params}")
        self.params = load_params(params)
        self.enabled_features = self.params.get("enabled_features", [
            "tumoral_ecological_diversity", 
            "entropy",
            "spatial_dispersion_index",
            "variation_coefficient"
        ])
        
    def to_kwargs(self):
        return {"params": self.params}
        
    def __eq__(self, other):
        return self.params == other.params
        
    def save(self, step_dir, input_map, result_dir):
        tmp = {
            "step_obj": self,
            "input_map": input_map,
            "result_dir": result_dir,
        }
        with open(step_dir / "step.pkl", "wb") as f:
            pickle.dump(tmp, f)
        
    def run(self, step_dir, result_dir, path_data: PathData, force=False, n_jobs=1, **kwargs):
        """运行GHSD特征提取步骤"""
        step_dir = Path(step_dir)
        result_dir = Path(result_dir)
        
        # 检查是否需要重新运行
        if not force:
            step_pkl = step_dir / "step.pkl"
            data_pkl = result_dir / "data.pkl"
            if step_pkl.exists() and data_pkl.exists():
                with open(data_pkl, "rb") as f:
                    data_obj = pickle.load(f)
                    logger.info(f"Loaded GHSD from {data_pkl}")
                    return data_obj
        
        # 获取输入数据路径
        image_paths = path_data.get_images()
        mask_paths = path_data.get_masks()
        
        logger.info(f"Processing {len(image_paths)} cases with GHSD")
        
        try:
            # 创建GHSD提取器
            extractor = HiomicsGHSD(
                input_image_paths=image_paths,
                input_mask_paths=mask_paths,
                n_jobs=n_jobs
            )
            
            # 提取特征
            features_df = extractor.get_all_features(enabled_features=self.enabled_features)
            
            # 重命名特征列，添加GHSD@前缀
            feature_cols = [col for col in features_df.columns if col != "unique_id"]
            renamed_df = features_df.copy()
            for col in feature_cols:
                renamed_df.rename(columns={col: f"GHSD@{col}"}, inplace=True)
            
            # 添加原始数据信息
            final_df = pd.concat([
                path_data.df.reset_index(drop=True),
                renamed_df.drop(columns=["unique_id"]).reset_index(drop=True)
            ], axis=1)
            
            # 特征列名
            feature_columns = [f"GHSD@{col}" for col in feature_cols]
            
            # 保存结果
            step_dir.mkdir(parents=True, exist_ok=True)
            result_dir.mkdir(parents=True, exist_ok=True)
            
            with open(step_dir / "step.pkl", "wb") as f:
                pickle.dump({"step_obj": self}, f)
                
            # 先保存CSV文件
            csv_path = result_dir / "data.csv"
            final_df.to_csv(csv_path, index=False)
            
            # 创建特征数据对象
            feature_data = FeatureData(
                csv_path=str(csv_path),
                feature_columns=feature_columns,
                id_column=path_data.id_column
            )
                
            with open(result_dir / "data.pkl", "wb") as f:
                pickle.dump(feature_data, f)
            
            logger.info(f"GHSD extraction completed - Features: {len(feature_columns)}, Samples: {len(final_df)}")
            
            return feature_data
            
        except Exception as e:
            logger.error(f"GHSD extraction failed: {str(e)}")
            raise