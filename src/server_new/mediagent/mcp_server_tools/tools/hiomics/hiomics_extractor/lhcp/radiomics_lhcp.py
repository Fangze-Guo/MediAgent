from radiomics.featureextractor import RadiomicsFeatureExtractor
import SimpleITK as sitk
import numpy as np
import pandas as pd
from typing import Dict, Any
from loguru import logger
from pathlib import Path
import pickle
from copy import deepcopy

from hiomics.utils import parallel, generate_spatial_bounding_box, load_params
import hiomics.preprocessing as preprocessing
import hiomics.decomposition as decomposition
from hiomics.task.step import AbcStep
from hiomics.task.data import PathData, FeatureData


def transform_to_wide_format(df, id_column, sr_id_column, feature_columns):
    feat_df = df[[id_column, sr_id_column] + feature_columns]
    melted = feat_df.melt(id_vars=[id_column, sr_id_column], 
                         var_name='feature_name', 
                         value_name='feature_value')
    melted.sort_values(by=[id_column, sr_id_column], inplace=True)
    melted['new_col'] = melted[sr_id_column].astype(str) + '@' + melted['feature_name']

    result = melted.pivot_table(
        index=id_column, 
        columns='new_col', 
        values='feature_value',
        aggfunc='first'
    ).reset_index()
    # result.fillna(0, inplace=True)
    
    new_feature_columns = result.columns.tolist()[1:]
    return result, new_feature_columns

def radiomics_worker(extractor: RadiomicsFeatureExtractor, 
                     image_path: str, 
                     mask_path: str,
                     ) -> Dict[str, Any]:
    image_sitk = sitk.ReadImage(image_path)
    mask_sitk = sitk.ReadImage(mask_path)
    image_np = sitk.GetArrayFromImage(image_sitk)
    mask_np = sitk.GetArrayFromImage(mask_sitk)
    if mask_np.sum() == 0:
        logger.warning(f"{mask_path} has no foreground pixels")
        return None, None
    mask_bin_np = np.where(mask_np > 0, 1, 0)

    roi_start, roi_end = generate_spatial_bounding_box(mask_bin_np)
    """ 不能切roi, 这会导致normalization有问题 """
    # image_roi_np = image_np[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]
    # mask_roi_np = mask_np[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]
    image_roi_np = image_np
    mask_roi_np = mask_np

    labels = [int(_) for _ in np.unique(mask_roi_np) if _ > 0] # only keep non-background labels
    features = []
    errors = []
    for i in labels:
        mask_roi_i_np = np.where(mask_roi_np == i, 1, 0)
        if mask_roi_i_np.sum() < 5:
            logger.warning(f"{mask_path} has less than 5 pixels for label {i}, filling with zeros")
            errors.append(f"Label {i} has less than 5 pixels")
            features.append({})
            continue
        features_i_raw = extractor.execute(sitk.GetImageFromArray(image_roi_np), sitk.GetImageFromArray(mask_roi_i_np))
        features_i = {key: features_i_raw[key] for key in features_i_raw.keys() if not key.startswith("diagnostics_")}
        features.append(features_i)
        errors.append(None)

    features_df = pd.DataFrame(features)
    feature_columns = features_df.columns.tolist()
    label_df = pd.DataFrame(labels, columns=["sr_id"])
    label_df["sr_id"] = label_df["sr_id"].apply(lambda x: f"SR_{x}")
    error_df = pd.DataFrame(errors, columns=["Error"])
    ret_df = pd.concat([label_df, error_df, features_df], axis=1)
    return ret_df, feature_columns

class HiomicsRadiomicsLHCP:
    def __init__(self, input_image_paths, input_mask_paths, **kwargs):
        self.input_image_paths = input_image_paths
        self.input_mask_paths = input_mask_paths
        self.params = kwargs

        self.sr_features_df = None
        self.sr_feature_columns = None
        self.case_features_df = None
        self.case_feature_columns = None
        self.sr_features_df_before_fillna = None
        self.sr_features_df_after_fillna = None

    def debug_pkl(self):
        data = {
            "input_image_paths": self.input_image_paths,
            "input_mask_paths": self.input_mask_paths,
            "params": self.params,
            "sr_features_df": self.sr_features_df,
            "sr_feature_columns": self.sr_feature_columns,
            "case_features_df": self.case_features_df,
            "case_feature_columns": self.case_feature_columns,
            "sr_features_df_before_fillna": self.sr_features_df_before_fillna,
            "sr_features_df_after_fillna": self.sr_features_df_after_fillna,
        }
        with open("radiomics_lhcp.pkl", "wb") as f:
            pickle.dump(data, f)

    def load_pkl(self):
        with open("radiomics_lhcp.pkl", "rb") as f:
            data = pickle.load(f)
        for k, v in data.items():
            setattr(self, k, v)


    def get_radiomics(self):
        assert self.params.get("radiomics_params", None) is not None, "radiomics_params is not set"
        n_jobs = self.params.get("n_jobs", 1)

        extractor = RadiomicsFeatureExtractor(self.params.get("radiomics_params"))
        kwargs_list = []
        for idx, (image_path, mask_path) in enumerate(zip(self.input_image_paths, self.input_mask_paths)):
            kwargs_list.append(dict(
                extractor=extractor,
                image_path=image_path,
                mask_path=mask_path,
            ))
        ret = parallel.worker(radiomics_worker, kwargs_list, use_multiprocessing=n_jobs > 1, desc="Hiomics Radiomics", max_workers=n_jobs, parallel_type="process")

        feats = []
        for i, (df, feature_columns) in enumerate(ret):
            if df is None:
                logger.warning(f"No features extracted for {self.input_mask_paths[i]}")
                continue
            self.sr_feature_columns = feature_columns
            df.insert(0, "unique_id", f"{i}")
            feats.append(df)
        self.sr_features_df = pd.concat(feats, axis=0, ignore_index=True)
        # self.sr_features_df.fillna(self.sr_features_df.mean(numeric_only=True), inplace=True)
        # self.sr_features_df.fillna(0, inplace=True)

        """
        @WZT: case_features_df 不是每个case都有，因为有的case是没有tumor的，所以 len(case_features_df) < len(self.input_image_paths)
        """
        self.case_features_df, self.case_feature_columns = transform_to_wide_format(self.sr_features_df, "unique_id", "sr_id", self.sr_feature_columns)
        self.case_features_df["unique_id"] = self.case_features_df["unique_id"].astype(int)
        self.case_features_df.sort_values(by="unique_id", inplace=True)
        # self.case_features_df.fillna(self.case_features_df.mean(numeric_only=True), inplace=True)
        # self.case_features_df.fillna(0, inplace=True)

        case_info_df = pd.DataFrame(range(len(self.input_image_paths)), columns=["unique_id"])
        logger.debug(f"case_info_df: {len(case_info_df)}, case_features_df: {len(self.case_features_df)}")
        self.case_features_df = pd.merge(case_info_df, self.case_features_df, on="unique_id", how="left")

        # from IPython import embed; embed()

        return self.case_features_df[self.case_feature_columns].copy()

    def get_base(self):
        """获取基础radiomics特征（base features）"""
        return self.get_radiomics()
    
    def get_primary(self):

        if self.sr_feature_columns is None:
            self.get_radiomics()

        # Get primary params first
        primary_params = self.params.get("primary_params", {})
        
        # Get preprocessing and decomposition parameters
        prep_args = primary_params.get("preprocessing", {"method": "StandardScaler", "params": None})
        decomp_args = primary_params.get("decomposition", {"method": "PCA", "params": {"random_state": 42}})
        
        # Work with SR level features
        sr_features_filled = self.sr_features_df.copy()
        
        # Store data before fillna
        self.sr_features_df_before_fillna = sr_features_filled.copy()
        
        # sr_features_filled[self.sr_feature_columns] = sr_features_filled[self.sr_feature_columns].fillna(
        #     sr_features_filled[self.sr_feature_columns].mean(numeric_only=True)
        # )
        sr_features_filled[self.sr_feature_columns] = sr_features_filled[self.sr_feature_columns].fillna(0)
        
        # Store data after fillna
        self.sr_features_df_after_fillna = sr_features_filled.copy()
        
        # 检查是否应该使用已有模型(基于force参数传递的逻辑)
        should_train_new = self.params.get("should_train_new", True)
        
        if should_train_new:
            # 训练新模型
            
            # Preprocessing model - fit on all SR features
            prep_model = preprocessing.get_method(prep_args["method"])(params=prep_args["params"])
            prep_model.fit(sr_features_filled[self.sr_feature_columns])
            
            # Save preprocessing model if path is provided
            if "preprocessing_pkl_path" in primary_params:
                prep_model.save(primary_params["preprocessing_pkl_path"])
                logger.info(f"Saved preprocessing model to {primary_params['preprocessing_pkl_path']}")
            
            # Apply preprocessing
            norm_feat_np = prep_model.predict(sr_features_filled[self.sr_feature_columns])
            norm_sr_feat_df = pd.DataFrame(norm_feat_np, columns=self.sr_feature_columns)
            
            # Get unique SR IDs
            unique_sr_ids = sr_features_filled["sr_id"].unique()
            
            # Create decomposition models for each SR
            decomp_models = {}
            decomp_features_list = []
            
            for sr_id in unique_sr_ids:
                # Get features for this SR
                sr_mask = sr_features_filled["sr_id"] == sr_id
                sr_specific_features = norm_sr_feat_df[sr_mask]
                
                # Create and fit decomposition model for this SR
                decomp_model = decomposition.get_method(decomp_args["method"])(params=decomp_args["params"])
                decomp_model.fit(sr_specific_features)
                decomp_models[sr_id] = decomp_model
                
                # Apply decomposition
                decomp_feat = decomp_model.predict(sr_specific_features)
                
                # Add SR ID and unique ID back
                decomp_feat_with_ids = pd.concat([
                    sr_features_filled[sr_mask][["unique_id", "sr_id"]].reset_index(drop=True),
                    decomp_feat.reset_index(drop=True)
                ], axis=1) # 都是基于 sr_mask 的，所以可以concat
                decomp_features_list.append(decomp_feat_with_ids)
            
            # Combine all SR decomposed features
            all_decomp_features = pd.concat(decomp_features_list, axis=0, ignore_index=True)
            
            # Save decomposition models if path is provided
            if "decomposition_pkl_path" in primary_params:
                with open(primary_params["decomposition_pkl_path"], "wb") as f:
                    pickle.dump(decomp_models, f)
                logger.info(f"Saved decomposition models to {primary_params['decomposition_pkl_path']}")
            
            # Store models for potential later use
            self.prep_model = prep_model
            self.decomp_models = decomp_models
            
            # Transform to wide format
            decomp_columns = [col for col in all_decomp_features.columns if col not in ["unique_id", "sr_id"]]
            result_df, _ = transform_to_wide_format(all_decomp_features, "unique_id", "sr_id", decomp_columns)
            
            # return result_df
            
        else:
            # 加载并使用已有模型
            
            # Load preprocessing model
            assert "preprocessing_pkl_path" in primary_params, "preprocessing_pkl_path is required when using existing models"
            try:
                prep_model = preprocessing.sklearn_wrapper.SklearnPreprocessingWrapper.load(primary_params["preprocessing_pkl_path"])
                logger.debug(f"✅ Successfully loaded preprocessing model from {primary_params['preprocessing_pkl_path']}")
                # 简单记录模型信息
                model_info = f"Preprocessing model: {type(prep_model.model).__name__}"
                if hasattr(prep_model.model, 'get_params'):
                    model_info += f", params: {prep_model.model.get_params()}"
                logger.debug(f"📊 {model_info}")
                logger.info(f"Using existing preprocessing model from {primary_params['preprocessing_pkl_path']}")
            except Exception as e:
                logger.error(f"❌ Failed to load preprocessing model from {primary_params['preprocessing_pkl_path']}: {e}")
                raise
            
            # Apply preprocessing
            norm_feat_np = prep_model.predict(sr_features_filled[self.sr_feature_columns])
            norm_sr_feat_df = pd.DataFrame(norm_feat_np, columns=self.sr_feature_columns)
            
            # Load decomposition models
            assert "decomposition_pkl_path" in primary_params, "decomposition_pkl_path is required when using existing models"
            try:
                with open(primary_params["decomposition_pkl_path"], "rb") as f:
                    decomp_models = pickle.load(f)
                logger.debug(f"✅ Successfully loaded decomposition models from {primary_params['decomposition_pkl_path']}")
                # 简单记录模型信息
                sr_ids = list(decomp_models.keys())
                model_types = [type(model.model).__name__ for model in decomp_models.values()]
                logger.debug(f"📊 Decomposition models: {len(sr_ids)} SR regions ({sr_ids}), model types: {set(model_types)}")
                # 记录第一个模型的参数作为示例
                if sr_ids:
                    first_model = decomp_models[sr_ids[0]]
                    if hasattr(first_model.model, 'get_params'):
                        logger.debug(f"📊 Sample model params: {first_model.model.get_params()}")
                logger.info(f"Using existing decomposition models from {primary_params['decomposition_pkl_path']}")
            except Exception as e:
                logger.error(f"❌ Failed to load decomposition models from {primary_params['decomposition_pkl_path']}: {e}")
                raise
            
            # Apply decomposition for each SR
            decomp_features_list = []
            for sr_id in sr_features_filled["sr_id"].unique():
                if sr_id not in decomp_models:
                    logger.warning(f"No decomposition model found for SR ID {sr_id}, skipping")
                    continue
                
                # Get features for this SR
                sr_mask = sr_features_filled["sr_id"] == sr_id
                sr_specific_features = norm_sr_feat_df[sr_mask]
                
                # Apply decomposition
                decomp_feat = decomp_models[sr_id].predict(sr_specific_features)
                
                # Add SR ID and unique ID back
                decomp_feat_with_ids = pd.concat([
                    sr_features_filled[sr_mask][["unique_id", "sr_id"]].reset_index(drop=True),
                    decomp_feat.reset_index(drop=True)
                ], axis=1)
                decomp_features_list.append(decomp_feat_with_ids)
            
            # Combine all SR decomposed features
            all_decomp_features = pd.concat(decomp_features_list, axis=0, ignore_index=True)
            
            # Transform to wide format
            decomp_columns = [col for col in all_decomp_features.columns if col not in ["unique_id", "sr_id"]]
            result_df, _ = transform_to_wide_format(all_decomp_features, "unique_id", "sr_id", decomp_columns)
            
        result_df["unique_id"] = result_df["unique_id"].astype(int)
        result_df.sort_values(by="unique_id", inplace=True)
        case_info_df = pd.DataFrame(range(len(self.input_image_paths)), columns=["unique_id"])
        result_df = pd.merge(case_info_df, result_df, on="unique_id", how="left")
        return result_df
            
        # This should not happen due to the assert at the beginning, but just in case
        # The logic above handles both cases based on use_existing_models flag


# class RadiomicsLHCPTester:
#     """规范化的Radiomics LHCP测试类"""
    
#     def __init__(self, config: Dict[str, Any]):
#         """
#         初始化测试器
        
#         Args:
#             config: 配置字典，包含所有必要的路径和参数
#         """
#         self.config = config
#         self.output_dir = Path(config.get("output_dir", "./test_output"))
#         self.output_dir.mkdir(parents=True, exist_ok=True)
        
#         # 设置日志
#         logger.info(f"RadiomicsLHCPTester initialized with output dir: {self.output_dir}")
        
#     def load_and_prepare_data(self):
#         """加载并准备数据"""
#         logger.info("Loading and preparing data...")
        
#         # 加载数据
#         data_csv_path = self.config["data_csv_path"]
#         base_dir = Path(self.config["base_dir"])
        
#         df = pd.read_csv(data_csv_path)
#         df["abs_image_path"] = df["image_path"].apply(lambda x: base_dir / x)
#         df["abs_mask_path"] = df["mask_path"].apply(lambda x: base_dir / x)
        
#         # 数据分割
#         train_size = self.config.get("train_size", 20)
#         test_size = self.config.get("test_size", 20)
        
#         df_train = df.iloc[:train_size]
#         df_test = df.iloc[train_size:train_size + test_size]
        
#         logger.info(f"Data prepared - Total: {len(df)}, Train: {len(df_train)}, Test: {len(df_test)}")
        
#         return df_train, df_test
    
#     def create_base_params(self):
#         """创建基础参数配置"""
#         model_dir = self.output_dir / "models"
#         model_dir.mkdir(exist_ok=True)
        
#         return {
#             "radiomics_params": self.config["radiomics_params"],
#             "n_jobs": self.config.get("n_jobs", 24),
#             "primary_params": {
#                 "preprocessing_pkl_path": str(model_dir / "preprocessing_model.pkl"),
#                 "decomposition_pkl_path": str(model_dir / "decomposition_model.pkl"),
#                 "preprocessing": self.config.get("preprocessing", {
#                     "method": "StandardScaler",
#                     "params": None
#                 }),
#                 "decomposition": self.config.get("decomposition", {
#                     "method": "PCA", 
#                     "params": {"n_components": 10}
#                 })
#             }
#         }
    
    # def run_training_phase(self, df_train):
    #     """执行训练阶段"""
    #     logger.info("=== Training Phase ===")
        
    #     params = self.create_base_params()
    #     params["use_existing_models"] = False  # Train new models
        
    #     try:
    #         extractor = HiomicsRadiomicsLHCP(
    #             df_train["abs_image_path"].tolist(), 
    #             df_train["abs_mask_path"].tolist(), 
    #             **params
    #         )
            
    #         # 提取特征
    #         extractor.get_radiomics()
    #         primary_features_df = extractor.get_radiomics_primary()
            
    #         # 保存结果
    #         results_dir = self.output_dir / "results"
    #         results_dir.mkdir(exist_ok=True)
            
    #         # 只保存核心结果文件
            
    #         # 1. 保存主要特征（最终结果 - 用户最需要的）
    #         train_results_path = results_dir / "primary_features_train.csv"
    #         primary_features_df.to_csv(train_results_path, index=False)
            
    #         # 2. 保存训练数据信息（便于追溯）
    #         train_info_path = results_dir / "train_info.csv"
    #         df_train[["abs_image_path", "abs_mask_path"]].to_csv(train_info_path, index=False)
            
    #         logger.info(f"Training completed - Features: {primary_features_df.shape[1]-1}, Samples: {primary_features_df.shape[0]}")
    #         logger.info(f"✅ 主要特征文件: {train_results_path}")
    #         logger.info(f"📋 训练数据信息: {train_info_path}")
            
    #         return primary_features_df, extractor
            
    #     except Exception as e:
    #         logger.error(f"Training phase failed: {str(e)}")
    #         raise
    
    # def run_testing_phase(self, df_test):
    #     """执行测试阶段"""
    #     logger.info("=== Testing Phase ===")
        
    #     params = self.create_base_params()
    #     params["use_existing_models"] = True  # Use existing models
    #     # 使用已有模型只需要模型路径
    #     params["primary_params"] = {
    #         "preprocessing_pkl_path": params["primary_params"]["preprocessing_pkl_path"],
    #         "decomposition_pkl_path": params["primary_params"]["decomposition_pkl_path"]
    #     }
        
    #     try:
    #         extractor = HiomicsRadiomicsLHCP(
    #             df_test["abs_image_path"].tolist(), 
    #             df_test["abs_mask_path"].tolist(), 
    #             **params
    #         )
            
    #         # 提取特征
    #         extractor.get_radiomics()
    #         primary_features_df = extractor.get_radiomics_primary()
            
    #         # 保存结果
    #         results_dir = self.output_dir / "results"
    #         results_dir.mkdir(exist_ok=True)
            
    #         # 只保存核心结果文件
            
    #         # 1. 保存主要特征（最终结果 - 用户最需要的）
    #         test_results_path = results_dir / "primary_features_test.csv"
    #         primary_features_df.to_csv(test_results_path, index=False)
            
    #         # 2. 保存测试数据信息（便于追溯）
    #         test_info_path = results_dir / "test_info.csv"
    #         df_test[["abs_image_path", "abs_mask_path"]].to_csv(test_info_path, index=False)
            
    #         logger.info(f"Testing completed - Features: {primary_features_df.shape[1]-1}, Samples: {primary_features_df.shape[0]}")
    #         logger.info(f"✅ 主要特征文件: {test_results_path}")
    #         logger.info(f"📋 测试数据信息: {test_info_path}")
            
    #         return primary_features_df
            
    #     except Exception as e:
    #         logger.error(f"Testing phase failed: {str(e)}")
    #         raise
    
    # def compare_results(self, train_df, test_df):
    #     """比较训练和测试结果"""
    #     logger.info("=== Feature Statistics Comparison ===")
        
    #     try:
    #         # 计算统计信息
    #         train_features = train_df.iloc[:, 1:]  # 排除unique_id列
    #         test_features = test_df.iloc[:, 1:]    # 排除unique_id列
            
    #         train_stats = {
    #             "mean": train_features.mean().mean(),
    #             "std": train_features.std().mean(),
    #             "min": train_features.min().min(),
    #             "max": train_features.max().max()
    #         }
            
    #         test_stats = {
    #             "mean": test_features.mean().mean(),
    #             "std": test_features.std().mean(),
    #             "min": test_features.min().min(),
    #             "max": test_features.max().max()
    #         }
            
    #         # 记录统计信息
    #         logger.info(f"Train Stats - Mean: {train_stats['mean']:.4f}, Std: {train_stats['std']:.4f}, "
    #                    f"Min: {train_stats['min']:.4f}, Max: {train_stats['max']:.4f}")
    #         logger.info(f"Test Stats  - Mean: {test_stats['mean']:.4f}, Std: {test_stats['std']:.4f}, "
    #                    f"Min: {test_stats['min']:.4f}, Max: {test_stats['max']:.4f}")
            
    #         # 保存统计信息
    #         stats_df = pd.DataFrame({
    #             "phase": ["train", "test"],
    #             "mean": [train_stats["mean"], test_stats["mean"]],
    #             "std": [train_stats["std"], test_stats["std"]],
    #             "min": [train_stats["min"], test_stats["min"]],
    #             "max": [train_stats["max"], test_stats["max"]]
    #         })
            
    #         stats_path = self.output_dir / "results" / "feature_statistics.csv"
    #         stats_df.to_csv(stats_path, index=False)
    #         logger.info(f"Statistics saved to: {stats_path}")
            
    #     except Exception as e:
    #         logger.error(f"Statistics comparison failed: {str(e)}")
    
    # def run_full_test(self):
    #     """执行完整的测试流程"""
    #     logger.info("Starting full Radiomics LHCP test...")
        
    #     try:
    #         # 加载数据
    #         df_train, df_test = self.load_and_prepare_data()
            
    #         # 训练阶段
    #         train_results, _ = self.run_training_phase(df_train)
            
    #         # 测试阶段
    #         test_results = self.run_testing_phase(df_test)
            
    #         # 比较结果
    #         self.compare_results(train_results, test_results)
            
    #         # 清晰总结最终输出文件
    #         logger.info("="*60)
    #         logger.info("🎉 完整测试完成！最终输出文件总结：")
    #         logger.info("="*60)
    #         logger.info("📁 核心结果文件 (用户主要关注):")
    #         logger.info(f"   ✅ 训练集特征: {self.output_dir}/results/primary_features_train.csv")
    #         logger.info(f"   ✅ 测试集特征: {self.output_dir}/results/primary_features_test.csv")
    #         logger.info("")
    #         logger.info("📁 数据信息文件 (便于追溯):")
    #         logger.info(f"   📋 训练数据信息: {self.output_dir}/results/train_info.csv")
    #         logger.info(f"   📋 测试数据信息: {self.output_dir}/results/test_info.csv")
    #         logger.info("")
    #         logger.info("📁 统计分析文件:")
    #         logger.info(f"   📊 特征统计比较: {self.output_dir}/results/feature_statistics.csv")
    #         logger.info("")
    #         logger.info("📁 模型文件:")
    #         logger.info(f"   🔧 预处理模型: {self.output_dir}/models/preprocessing_model.pkl")
    #         logger.info(f"   🔧 降维模型: {self.output_dir}/models/decomposition_model.pkl")
    #         logger.info("="*60)
    #         logger.info("💡 建议: 主要查看 primary_features_train.csv 和 primary_features_test.csv")
    #         logger.info("="*60)
            
    #     except Exception as e:
    #         logger.error(f"Full test failed: {str(e)}")
    #         raise


# def create_default_test_config():
#     """创建默认的测试配置"""
#     return {
#         "data_csv_path": "/media/wzt/plum14t/PyHiomics/exp/pCR/04_Clu_Rad/output/val/data/04_Clu_Rad/data.csv",
#         "base_dir": "/media/wzt/plum14t/PyHiomics/exp/pCR/04_Clu_Rad/output/val/data/04_Clu_Rad",
#         "radiomics_params": "/media/wzt/plum14t/PyHiomics/exp/pCR/03_FE_Rad/MR_noshape.yaml",
#         "output_dir": "./radiomics_lhcp_test_output",
#         "n_jobs": 24,
#         "train_size": 20,
#         "test_size": 20,
#         "preprocessing": {
#             "method": "StandardScaler",
#             "params": None
#         },
#         "decomposition": {
#             "method": "PCA", 
#             "params": {"n_components": 1}
#         }
#     }


# if __name__ == "__main__":
#     # 创建测试配置
#     config = create_default_test_config()
    
#     # 创建测试器并运行
#     tester = RadiomicsLHCPTester(config)
#     tester.run_full_test()


class RadiomicsLHCPStep(AbcStep):
    """RadiomicsLHCP特征提取步骤类"""
    
    def __init__(self, params=None):
        if params is None:
            params = "RadiomicsLHCP.yaml"
            logger.info(f"Using default params for RadiomicsLHCP: {params}")
        self.params = load_params(params)
        self.enabled_features = self.params.get("enabled_features", ["base", "primary"])
        self.radiomics_params = self.params.get("radiomics_params")
        self.primary_params = self.params.get("primary_params", {})
        
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
        # logger.debug("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        # path_data.df = path_data.df.head(10)

        """运行RadiomicsLHCP特征提取步骤"""
        step_dir = Path(step_dir)
        result_dir = Path(result_dir)
        
        # 检查是否需要重新运行
        if not force:
            step_pkl = step_dir / "step.pkl"
            data_pkl = result_dir / "data.pkl"
            if step_pkl.exists() and data_pkl.exists():
                with open(data_pkl, "rb") as f:
                    data_obj = pickle.load(f)
                    # 简单记录加载的数据信息
                    if hasattr(data_obj, 'feature_columns') and data_obj.feature_columns:
                        logger.debug(f"📊 Loaded feature data: {len(data_obj.feature_columns)} features")
                        logger.debug(f"📊 Sample features: {data_obj.feature_columns[:5]}..." if len(data_obj.feature_columns) > 5 else f"📊 Features: {data_obj.feature_columns}")
                    logger.info(f"Loaded RadiomicsLHCP from {data_pkl}")
                    return data_obj
        
        # 获取输入数据路径
        image_paths = path_data.get_images()
        mask_paths = path_data.get_masks()
        
        logger.info(f"Processing {len(image_paths)} cases with RadiomicsLHCP")
        
        try:
            # 动态设置模型保存路径
            primary_params = self.primary_params.copy() if self.primary_params else {}
            if primary_params.get("preprocessing_pkl_path") is None:
                primary_params["preprocessing_pkl_path"] = str(step_dir / "preprocessing_model.pkl")
            if primary_params.get("decomposition_pkl_path") is None:
                primary_params["decomposition_pkl_path"] = str(step_dir / "decomposition_model.pkl")
            
            # 动态决定是否使用已有模型：基于pkl文件存在与否和force参数
            preprocessing_pkl_path = Path(primary_params["preprocessing_pkl_path"])
            decomposition_pkl_path = Path(primary_params["decomposition_pkl_path"])
            
            # 如果pkl文件存在且不强制重新训练，使用已有模型；否则训练新模型
            if (preprocessing_pkl_path.exists() and decomposition_pkl_path.exists() and not force):
                should_train_new = False
                logger.info(f"🔄 Found existing models, will load and reuse - preprocessing: {preprocessing_pkl_path}, decomposition: {decomposition_pkl_path}")
            else:
                should_train_new = True
                logger.info(f"🏗️ Will train new models - force={force}, prep_exists={preprocessing_pkl_path.exists()}, decomp_exists={decomposition_pkl_path.exists()}")
            
            # 创建参数字典
            extractor_params = {
                "radiomics_params": self.radiomics_params,
                "should_train_new": should_train_new,
                "n_jobs": n_jobs
            }
            
            # 如果有primary_params，添加到参数中
            if primary_params:
                extractor_params["primary_params"] = primary_params
            
            # 创建RadiomicsLHCP提取器
            extractor = HiomicsRadiomicsLHCP(
                input_image_paths=image_paths,
                input_mask_paths=mask_paths,
                **extractor_params
            )
            
            results = {}
            all_features = []
            feature_columns = []
            
            # 根据enabled_features来决定提取哪些特征
            if "base" in self.enabled_features:
                base_features = extractor.get_base()
                results["base"] = base_features
            
            if "primary" in self.enabled_features and self.primary_params:
                primary_features = extractor.get_primary()
                results["primary"] = primary_features
            
            # 处理结果
            for method_name, method_df in results.items():
                if not method_df.empty:
                    # 识别ID列（可能是unique_id或其他名称）
                    id_cols_to_drop = [col for col in method_df.columns 
                                     if col in ["unique_id", path_data.id_column]]
                    
                    # 获取特征列（排除ID列）
                    feature_cols = [col for col in method_df.columns if col not in id_cols_to_drop]
                    
                    # 添加原始数据信息
                    if feature_cols:  # 确保有特征列
                        # 重命名特征列，添加RadLHCP@前缀
                        renamed_df = method_df[feature_cols].copy()
                        for col in feature_cols:
                            renamed_df.rename(columns={col: f"RadLHCP@{method_name}@{col}"}, inplace=True)
                        
                        df_with_info = pd.concat([
                            path_data.df.reset_index(drop=True),
                            renamed_df.reset_index(drop=True)
                        ], axis=1)
                        all_features.append(df_with_info)
                        feature_columns.extend([f"RadLHCP@{method_name}@{col}" for col in feature_cols])
            
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
            
            # 备份radiomics参数文件到step_dir
            if self.radiomics_params and Path(self.radiomics_params).exists():
                import shutil
                radiomics_param_file = Path(self.radiomics_params)
                backup_param_file = step_dir / f"radiomics_params_{radiomics_param_file.name}"
                shutil.copy2(self.radiomics_params, backup_param_file)
                logger.debug(f"📋 Backed up radiomics params to {backup_param_file}")
            
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
            
            logger.info(f"RadiomicsLHCP extraction completed - Features: {len(feature_columns)}, Samples: {len(final_df)}")
            
            return feature_data
            
        except Exception as e:
            logger.error(f"RadiomicsLHCP extraction failed: {str(e)}")
            raise