import pandas as pd
from pathlib import Path
from hiomics.utils import load_params
import hiomics.preprocessing as preprocessing
import hiomics.decomposition as decomposition
from easydict import EasyDict as edict
from copy import deepcopy

from loguru import logger
from hiomics.utils import parallel
import numpy as np
import SimpleITK as sitk
import pickle
import shutil

from radiomics.featureextractor import RadiomicsFeatureExtractor

# Import HiomicsFeatureExtractor classes
from .hiomics_feature_extractor import HiomicsFeatureExtractor, HiomicsFeatureExtractorStep
from .ghsd import HiomicsGHSD, GHSDStep
from .lhcp.radiomics_lhcp import HiomicsRadiomicsLHCP, RadiomicsLHCPStep

FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
CFG_DIR = ROOT / "configs/hiomics"
DEFAULT_CFG = load_params(CFG_DIR / "default.yaml")

def extract_hi_radiomics_batch(args, sr_clu_res, output_dir, n_jobs, is_train=False):
    # Import here to avoid circular dependency
    from hiomics.feature_extractor import run as run_feature_extractor
    from hiomics.feature_extractor.radiomics_wrapper import auto_extractor, radiomics_worker
    
    if args is None:
        args = {}
    pkl_dir = output_dir / "pkl/hi_radiomics"
    hi_dir = output_dir / "hiomics"

    hi_feat1_df = sr_clu_res.df.copy()
    hi_feat1_df.drop(columns=["image_path", "mask_path",], inplace=True)
    # hi_feat1_df.rename(columns={"n_sr": "global_tumor_ecological_indices"}, inplace=True)
    hi_feat1 = edict(df=hi_feat1_df, feature_columns=["n_sr"])

    fe_args = args.get("subregion_feature_extraction", None)
    if fe_args is None:
        fe_args = deepcopy(DEFAULT_CFG["subregion_feature_extraction"])
        if not (fe_args["params"].endswith(".yaml") or fe_args["params"].endswith(".json")):
            logger.error(f"Only yaml and json are supported for feature extraction params")
            raise ValueError(f"Only yaml and json are supported for feature extraction params")
        tmp = Path(fe_args["params"])
        if not tmp.exists():
            tmp = ROOT / "configs/feature_extraction" / fe_args["method"] / fe_args["params"]
            if not tmp.exists():
                logger.error(f"Feature extraction config file {fe_args['params']} not found")
                raise FileNotFoundError(f"Feature extraction config file {fe_args['params']} not found")
        fe_args["params"] = str(tmp)
        logger.info(f"Using default feature extraction args: {fe_args}")
    sr_feat = run_feature_extractor(method=fe_args["method"], params=fe_args["params"], df=sr_clu_res.df, n_jobs=n_jobs)
    hi_feat2 = sr_feat

    decomp_pkl_path = pkl_dir / "decomp_model.pkl"
    if decomp_pkl_path.exists() and not is_train:
        decomp_model = decomposition.sklearn_wrapper.SklearnDecompositionWrapper.load(decomp_pkl_path)
        logger.info(f"Loaded decomp_model from {decomp_pkl_path}")
    else:
        decomp_args = args.get("decomposition", None)
        if decomp_args is None:
            decomp_args = deepcopy(DEFAULT_CFG["decomposition"])
            logger.info(f"Using default decomposition args: {decomp_args}")
        decomp_model = decomposition.get_method(decomp_args["method"])(params=decomp_args["params"])
        decomp_model.fit(hi_feat2.df[hi_feat2.feature_columns])
        decomp_model.save(decomp_pkl_path)
    decomp_feat_df = decomp_model.predict(hi_feat2.df[hi_feat2.feature_columns])
    df = hi_feat2.df.copy().drop(columns=hi_feat2.feature_columns)
    df = pd.concat([df, decomp_feat_df], axis=1)
    hi_feat3 = edict(df=df, feature_columns=decomp_feat_df.columns.tolist())

    return [hi_feat1, hi_feat2, hi_feat3]


from hiomics.task.step import AbcStep
from hiomics.task.data import PathData, FeatureData

def calc_ITED(mask_path: str):
    try:
        mask = sitk.GetArrayFromImage(sitk.ReadImage(mask_path))
        return len(np.unique(mask)) - 1, ""
    except Exception as e:
        return 0, str(e)

def transform_to_wide_format(df, id_column, sr_id_column, feature_columns):
    feat_df = df[[id_column, sr_id_column] + feature_columns]
    melted = feat_df.melt(id_vars=[id_column, sr_id_column], 
                         var_name='feature_name', 
                         value_name='feature_value')
    melted.sort_values(by=[id_column, sr_id_column], inplace=True)
    melted['new_col'] = melted[sr_id_column].astype(str) + '@' + melted['feature_name']

    # result = melted.groupby(id_column).apply(
    #     lambda x: pd.Series(x['feature_value'].values, index=x['new_col'].values)
    # ).reset_index()

    result = melted.pivot_table(
        index=id_column, 
        columns='new_col', 
        values='feature_value',
        aggfunc='first'
    ).reset_index()
    result.fillna(0, inplace=True)
    new_feature_columns = result.columns.tolist()[1:]
    return result, new_feature_columns

    # info_df = df.drop_duplicates(subset=[id_column]).copy().reset_index(drop=True)
    # assert len(info_df) == len(result), "Length of info_df and result is not the same"
    # merged_df = pd.merge(info_df, result, on=id_column, how='left', indicator=True)
    # assert merged_df["_merge"].value_counts()["both"] == len(info_df), "Length of info_df and result is not the same"
    # merged_df.drop(columns=["_merge"], inplace=True)

    # return merged_df, new_feature_columns

class HiomicsStep(AbcStep):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "default.yaml"
        self.params = load_params(params)
        self.prep_model = None
        self.decomp_model = None
        self.extractor = None

    def to_kwargs(self):
        return {
            "params": self.params,
        }

    def run(self, step_dir, result_dir, original_path_data: PathData, path_data: PathData, force=False, n_jobs=1, **kwargs):
        args = self.params
        step_dir = Path(step_dir)
        result_dir = Path(result_dir)

        if not force:
            step_pkl = step_dir / "step.pkl"
            data_pkl = result_dir / "data.pkl"
            if step_pkl.exists():
                with open(step_pkl, "rb") as f:
                    tmp = pickle.load(f)
                    step_obj = tmp["step_obj"]
                self = deepcopy(step_obj)
                assert step_obj == self, "Step object is not the same"
            
                if data_pkl.exists():
                    with open(data_pkl, "rb") as f:
                        data_obj = pickle.load(f)
                        logger.info(f"Loaded from {data_pkl}")
                        return data_obj

        src_images = path_data.get_images()
        src_masks = path_data.get_masks()

        kwargs_list = []
        for i, src_mask_path in enumerate(src_masks):
            kwargs_list.append({
                "mask_path": src_mask_path,
                "__name__": f"{i}",
            })
        ret = parallel.worker(calc_ITED, kwargs_list, use_multiprocessing=n_jobs > 1, desc="Calculating ITED", max_workers=n_jobs, parallel_type="process")
        ited_columns = ["ITED"]
        ited_feat_df = pd.DataFrame([r[0] for r in ret], columns=ited_columns) # case level
        ited_feat_df = pd.concat([path_data.df[[path_data.id_column]], ited_feat_df], axis=1, ignore_index=False)
        ited_feat_df.to_csv(step_dir / "ited_feat.csv", index=False)

        ited_error_df = pd.DataFrame([r[1] for r in ret], columns=["Error"]) # case level
        ited_error_df = pd.concat([path_data.df, ited_error_df], axis=1, ignore_index=False)
        ited_error_df.to_csv(step_dir / "ited_error.csv", index=False)

        # rad_params = args.get("subregion_feature_extraction", None)
        # assert rad_params is not None, "subregion_feature_extraction is not set"
        # assert rad_params["method"] == "radiomics", "subregion_feature_extraction method must be radiomics"
        
        # from hiomics.feature_extractor.radiomics_wrapper import auto_extractor, radiomics_worker
        # extractor, rad_params = auto_extractor(rad_params.get("params", None))
        # self.extractor = extractor
        # self.params["subregion_feature_extraction"]["params"] = Path(rad_params).name
        # shutil.copy(rad_params, step_dir / Path(rad_params).name)

        # kwargs_list = []
        # for i in range(len(src_images)):
        #     kwargs_list.append(dict(
        #         extractor=deepcopy(self.extractor),
        #         image_path=src_images[i],
        #         mask_path=src_masks[i],
        #     ))
        # ret = parallel.worker(radiomics_worker, kwargs_list, use_multiprocessing=n_jobs > 1, desc="Radiomics", max_workers=n_jobs, parallel_type="process")
        
        # case_indices, feats, labels, errors = [], [], [], []
        # for i, d in enumerate(ret):
        #     case_indices.extend([i] * len(d["labels"]))
        #     feats.append(d["features"])
        #     labels.extend(d["labels"])
        #     errors.extend(d["errors"])
        # expanded_df = path_data.df.iloc[case_indices].reset_index(drop=True).copy()
        # expanded_df["sr_id"] = labels
        # sr_rad_feat_df = pd.concat(feats, axis=0, ignore_index=True) # sr level
        # sr_rad_error_df = pd.DataFrame(errors, columns=["Error"]) # sr level
        # sr_rad_error_df = pd.concat([expanded_df, sr_rad_error_df], axis=1, ignore_index=False)
        # sr_rad_error_df.to_csv(step_dir / "rad_error.csv", index=False)

        # # sr level -> case level
        # df = pd.concat([expanded_df, sr_rad_feat_df], axis=1, ignore_index=False)
        # df.to_csv(step_dir / "sr_rad_feat.csv", index=False)
        # rad_feat_df, rad_feat_columns = transform_to_wide_format(df, path_data.id_column, 'sr_id', sr_rad_feat_df.columns.tolist())

        # rad_feat_df.to_csv(step_dir / "rad_feat.csv", index=False)

        # prep_pkl_path = step_dir / "prep_model.pkl"
        # if prep_pkl_path.exists() and not force:
        #     prep_model = preprocessing.sklearn_wrapper.SklearnPreprocessingWrapper.load(prep_pkl_path)
        #     logger.info(f"Loaded prep_model from {prep_pkl_path}")
        # else:
        #     prep_args = args.get("preprocessing", None)
        #     if prep_args is None:
        #         prep_args = deepcopy(DEFAULT_CFG["preprocessing"])
        #         logger.info(f"Using default preprocessing args: {prep_args}")
        #     prep_model = preprocessing.get_method(prep_args["method"])(params=prep_args["params"])
        #     prep_model.fit(rad_feat_df[rad_feat_columns])
        #     prep_model.save(prep_pkl_path) 
        # self.prep_model = prep_model
        # norm_feat_df = pd.DataFrame(prep_model.predict(rad_feat_df[rad_feat_columns]), columns=rad_feat_columns)
        # norm_feat_df = pd.concat([rad_feat_df[[path_data.id_column]], norm_feat_df], axis=1, ignore_index=False)
        # norm_feat_df.to_csv(step_dir / "norm_feat.csv", index=False)

        # decomp_pkl_path = step_dir / "decomp_model.pkl"
        # if decomp_pkl_path.exists() and not force:
        #     decomp_model = decomposition.sklearn_wrapper.SklearnDecompositionWrapper.load(decomp_pkl_path)
        #     logger.info(f"Loaded decomp_model from {decomp_pkl_path}")
        # else:
        #     decomp_args = args.get("decomposition", None)
        #     if decomp_args is None:
        #         decomp_args = deepcopy(DEFAULT_CFG["decomposition"])
        #         logger.info(f"Using default decomposition args: {decomp_args}")
        #     decomp_model = decomposition.get_method(decomp_args["method"])(params=decomp_args["params"])
        #     decomp_model.fit(norm_feat_df[rad_feat_columns])
        #     decomp_model.save(decomp_pkl_path)
        # self.decomp_model = decomp_model

        # sr_decomp_feat_df = decomp_model.predict(norm_feat_df[rad_feat_columns]) # sr level
        # # sr level -> case level
        # df = pd.concat([expanded_df, sr_decomp_feat_df], axis=1, ignore_index=False)
        # decomp_feat_df, decomp_feat_columns = transform_to_wide_format(df, path_data.id_column, 'sr_id', sr_decomp_feat_df.columns.tolist())
        # decomp_feat_df.to_csv(step_dir / "decomp_feat.csv", index=False)
        
        # ited_feat_df.set_index(path_data.id_column, inplace=True)
        # rad_feat_df.set_index(path_data.id_column, inplace=True)
        # decomp_feat_df.set_index(path_data.id_column, inplace=True)
        
        # # ited_feat_df, rad_feat_df, decomp_feat_df -> all_feat_df, 并且添加给各自的列添加前缀
        # ited_feat_df.columns = [f"ited@{c}" for c in ited_feat_df.columns]
        # rad_feat_df.columns = [f"rad@{c}" for c in rad_feat_df.columns]
        # decomp_feat_df.columns = [f"decomp@{c}" for c in decomp_feat_df.columns]
        # all_feat_df = pd.concat([ited_feat_df, rad_feat_df, decomp_feat_df], axis=1, ignore_index=False)
        # all_feat_df.reset_index(inplace=True, drop=False)
        # all_feat_df.to_csv(step_dir / "all_feat.csv", index=False)


        



# Export public API
__all__ = [
    "HiomicsFeatureExtractor",
    "HiomicsFeatureExtractorStep", 
    "HiomicsGHSD",
    "GHSDStep",
    "HiomicsRadiomicsLHCP",
    "RadiomicsLHCPStep",
    "HiomicsStep",
    "extract_hi_radiomics_batch",
    "transform_to_wide_format",
    "calc_ITED"
]

if __name__ == '__main__':
    args = {}
    decomp_args = args.get("decomposition", None)
    if decomp_args is None:
        decomp_args = DEFAULT_CFG["decomposition"]
        logger.info(f"Using default decomposition args: {decomp_args}")
    decomp_model = decomposition.get_method(decomp_args["method"])(params=decomp_args["params"])

