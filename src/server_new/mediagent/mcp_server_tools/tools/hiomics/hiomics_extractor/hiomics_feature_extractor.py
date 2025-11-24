import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Union
from loguru import logger
import pickle
from copy import deepcopy

from hiomics.task.step import AbcStep
from hiomics.task.data import PathData, FeatureData
from hiomics.utils import load_params
from .ghsd import HiomicsGHSD
from .lhcp.radiomics_lhcp import HiomicsRadiomicsLHCP


class HiomicsFeatureExtractor:
    """Hiomics特征提取器主类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.feature_classes = config.get("featureClass", {})
        self.settings = config.get("settings", {})
        
    def extract_features(self, input_image_paths: List[str], input_mask_paths: List[str], **kwargs) -> Dict[str, Any]:
        """提取特征的主方法"""
        results = {}
        
        for extractor_name, extractor_config in self.feature_classes.items():
            logger.info(f"Extracting features using {extractor_name}")
            
            if extractor_name == "GHSD":
                # GHSD特征提取
                extractor = HiomicsGHSD(
                    input_image_paths=input_image_paths,
                    input_mask_paths=input_mask_paths,
                    **kwargs
                )
                features_df = extractor.get_all_features(enabled_features=extractor_config)
                results[extractor_name] = features_df
                
            elif extractor_name == "RadiomicsLHCP":
                # RadiomicsLHCP特征提取
                extractor_params = extractor_config.copy()
                extractor_params.update(kwargs)
                
                extractor = HiomicsRadiomicsLHCP(
                    input_image_paths=input_image_paths,
                    input_mask_paths=input_mask_paths,
                    **extractor_params
                )
                
                # 提取基础radiomics特征
                base_features = extractor.get_radiomics()
                
                # 如果配置了primary特征，则提取
                if "primary_params" in extractor_params:
                    primary_features = extractor.get_radiomics_primary()
                    results[extractor_name] = {"radiomics": base_features, "primary": primary_features}
                else:
                    results[extractor_name] = {"radiomics": base_features}
                    
            else:
                logger.warning(f"Unknown extractor: {extractor_name}")
                
        return results


class HiomicsFeatureExtractorStep(AbcStep):
    """Hiomics特征提取步骤类"""
    
    def __init__(self, params=None):
        if params is None:
            params = {}
        self.params = params
        self.extractor = HiomicsFeatureExtractor(params)
        
    def to_kwargs(self):
        return {"params": self.params}
        
    def __eq__(self, other):
        return self.params == other.params
        
    def save(self, step_dir, input_map, result_dir):
        """保存步骤信息（已经在run方法中保存了实际数据）"""
        pass
        
    def run(self, step_dir, result_dir, path_data: PathData, force=False, n_jobs=1, **kwargs):
        """运行特征提取步骤"""
        step_dir = Path(step_dir)
        result_dir = Path(result_dir)
        
        # 检查是否需要重新运行
        if not force:
            step_pkl = step_dir / "step.pkl"
            data_pkl = result_dir / "data.pkl"
            if step_pkl.exists() and data_pkl.exists():
                with open(data_pkl, "rb") as f:
                    data_obj = pickle.load(f)
                    logger.info(f"Loaded from {data_pkl}")
                    return data_obj
        
        # 获取输入数据路径
        image_paths = path_data.get_images()
        mask_paths = path_data.get_masks()
        
        logger.info(f"Processing {len(image_paths)} cases")
        
        try:
            # 提取特征
            extractor_results = self.extractor.extract_features(
                input_image_paths=image_paths,
                input_mask_paths=mask_paths,
                n_jobs=n_jobs
            )
            
            # 处理结果为每个extractor创建单独的特征数据
            all_features = []
            feature_columns = []
            
            for extractor_name, result in extractor_results.items():
                if extractor_name == "GHSD":
                    # GHSD返回单个DataFrame
                    df = result
                    # 重命名特征列，添加GHSD@前缀
                    feature_cols = [col for col in df.columns if col != "unique_id"]
                    renamed_df = df.copy()
                    for col in feature_cols:
                        renamed_df.rename(columns={col: f"GHSD@{col}"}, inplace=True)
                    
                    # 添加原始数据信息
                    df_with_info = pd.concat([
                        path_data.df.reset_index(drop=True),
                        renamed_df.drop(columns=["unique_id"]).reset_index(drop=True)
                    ], axis=1)
                    all_features.append(df_with_info)
                    feature_columns.extend([f"GHSD@{col}" for col in feature_cols])
                    
                elif extractor_name == "RadiomicsLHCP":
                    # RadiomicsLHCP返回字典，包含多个方法的结果
                    for method_name, method_df in result.items():
                        if not method_df.empty:
                            # 识别ID列（可能是unique_id或其他名称）
                            id_cols_to_drop = [col for col in method_df.columns 
                                             if col in ["unique_id", path_data.id_column]]
                            
                            # 获取特征列（排除ID列）
                            feature_cols = [col for col in method_df.columns if col not in id_cols_to_drop]
                            
                            # 添加原始数据信息
                            if feature_cols:  # 确保有特征列
                                # 重命名特征列，添加RadiomicsLHCP@前缀
                                renamed_df = method_df[feature_cols].copy()
                                for col in feature_cols:
                                    renamed_df.rename(columns={col: f"RadiomicsLHCP@{col}"}, inplace=True)
                                
                                df_with_info = pd.concat([
                                    path_data.df.reset_index(drop=True),
                                    renamed_df.reset_index(drop=True)
                                ], axis=1)
                                all_features.append(df_with_info)
                                feature_columns.extend([f"RadiomicsLHCP@{col}" for col in feature_cols])
            
            # 合并所有特征
            if all_features:
                # 使用第一个DataFrame作为基础，然后添加其他特征
                final_df = all_features[0].copy()
                for i in range(1, len(all_features)):
                    # 只添加特征列，避免重复信息列
                    feature_cols = [col for col in all_features[i].columns 
                                  if col not in final_df.columns]
                    if feature_cols:
                        final_df = pd.concat([final_df, all_features[i][feature_cols]], axis=1)
                
                # 更新feature_columns为实际存在的列
                feature_columns = [col for col in final_df.columns 
                                 if col not in path_data.df.columns]
            else:
                final_df = path_data.df.copy()
                feature_columns = []
            
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
            
            logger.info(f"Feature extraction completed - Features: {len(feature_columns)}, Samples: {len(final_df)}")
            
            return feature_data
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {str(e)}")
            raise