from radiomics.featureextractor import RadiomicsFeatureExtractor
import SimpleITK as sitk
import numpy as np
import pandas as pd
# from monai.transforms import generate_spatial_bounding_box
from ..utils import generate_spatial_bounding_box
from easydict import EasyDict as edict
from typing import Dict, Any, Union
from loguru import logger
from ..utils import parallel, load_params
from pathlib import Path
import pickle
from copy import deepcopy
import shutil

FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
CFG_DIR = ROOT / "configs/feature_extraction/radiomics"

def radiomics_worker(extractor: RadiomicsFeatureExtractor, 
                     image_path: str, 
                     mask_path: str,
                     ) -> Dict[str, Any]:
    try:
        image_sitk = sitk.ReadImage(image_path)
        mask_sitk = sitk.ReadImage(mask_path)
        image_np = sitk.GetArrayFromImage(image_sitk)
        mask_np = sitk.GetArrayFromImage(mask_sitk)
        if mask_np.sum() == 0:
            logger.warning(f"{mask_path} has no foreground pixels")
            return None

        mask_bin_np = np.where(mask_np > 0, 1, 0)
        # roi_start, roi_end = generate_spatial_bounding_box(mask_bin_np[None], allow_smaller=False, margin=0)
        roi_start, roi_end = generate_spatial_bounding_box(mask_bin_np)
        """ 不能切roi, 这会导致normalization有问题 """
        image_roi_np = image_np[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]
        mask_roi_np = mask_np[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]
        # image_roi_np = image_np
        # mask_roi_np = mask_np

        labels = [_ for _ in np.unique(mask_roi_np) if _ > 0] # only keep non-background labels
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
        return dict(labels=labels, features=features_df, errors=errors)
    except Exception as e:
        import traceback
        logger.error(f"Error in radiomics_worker: {e}")
        logger.error(traceback.format_exc())
        raise e
    
def extract_radiomics_batch(params: str, 
                            df: pd.DataFrame, 
                            n_jobs: int,
                            ) -> edict:
    if not params.endswith(".yaml"):
        logger.error(f"Only yaml is supported for radiomics params")
        raise ValueError(f"Only yaml is supported for radiomics params")
    if not Path(params).exists():
        tmp = CFG_DIR / params
        print(tmp)
        if not tmp.exists():
            logger.error(f"Radiomics config file {params} not found")
            raise FileNotFoundError(f"Radiomics config file {params} not found")
        params = str(tmp)
    extractor = RadiomicsFeatureExtractor(params)
    kwargs_list = []
    for _, row in df.iterrows():
        kwargs_list.append(dict(
            extractor=extractor,
            image_path=row["image_path"],
            mask_path=row["mask_path"],
        ))
    ret = parallel.worker(radiomics_worker, kwargs_list, use_multiprocessing=n_jobs > 1, desc="Radiomics", max_workers=n_jobs, parallel_type="process")
    
    case_indices, feats, labels, errors = [], [], [], []
    for i, d in enumerate(ret):
        if d is None:
            logger.warning(f"No features extracted for {df.iloc[i]['mask_path']}")
            continue
        case_indices.extend([i] * len(d["labels"]))
        feats.append(d["features"])
        labels.extend(d["labels"])
        errors.extend(d["errors"])
    expanded_df = df.iloc[case_indices].reset_index(drop=True).copy()
    expanded_df["sv_id"] = labels
    feat_df = pd.concat(feats, axis=0, ignore_index=True)
    error_df = pd.DataFrame(errors, columns=["Error"])
    new_df = pd.concat([expanded_df, feat_df, error_df], axis=1)
    return edict(df=new_df, feature_columns=feat_df.columns.tolist(), error_columns=error_df.columns.tolist())

def auto_extractor(params: str = None):
    if params is None:
        params = "MR_noshape.yaml"
    if not params.endswith(".yaml"):
        logger.error(f"Only yaml is supported for radiomics params")
        raise ValueError(f"Only yaml is supported for radiomics params")
    if not Path(params).exists():
        tmp = CFG_DIR / params
        if not tmp.exists():
            logger.error(f"Radiomics config file {params} not found")
            raise FileNotFoundError(f"Radiomics config file {params} not found")
        params = str(tmp)
    
    extractor = RadiomicsFeatureExtractor(params)
    return extractor, params

from hiomics.task.step import AbcStep
from hiomics.task.data import FeatureData, PathData

class FeatureExtractorRadiomicsStep(AbcStep):
    def __init__(self, params=None):
        if params is None:
            params = "MR_noshape.yaml"
        if not params.endswith(".yaml"):
            logger.error(f"Only yaml is supported for radiomics params")
            raise ValueError(f"Only yaml is supported for radiomics params")
        if not Path(params).exists():
            tmp = CFG_DIR / params
            if not tmp.exists():
                logger.error(f"Radiomics config file {params} not found")
                raise FileNotFoundError(f"Radiomics config file {params} not found")
            params = str(tmp)
        
        self.extractor = RadiomicsFeatureExtractor(params)
        self.params = params

    def to_kwargs(self):
        return {
            "params": "params.yaml",
        }

    def __eq__(self, other):
        from hashlib import md5
        return md5(self.params.encode()).hexdigest() == md5(other.params.encode()).hexdigest()

    def run(self, step_dir, result_dir, path_data: PathData, force=False, n_jobs=1):
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
        for i in range(len(src_images)):
            kwargs_list.append(dict(
                extractor=deepcopy(self.extractor),
                image_path=src_images[i],
                mask_path=src_masks[i],
            ))
        ret = parallel.worker(radiomics_worker, kwargs_list, use_multiprocessing=n_jobs > 1, desc="Radiomics", max_workers=n_jobs, parallel_type="process")
        
        case_indices, feats, labels, errors = [], [], [], []
        for i, d in enumerate(ret):
            if d is None:
                logger.warning(f"No features extracted for {path_data.df.iloc[i]['mask_path']}")
                continue
            case_indices.extend([i] * len(d["labels"]))
            feats.append(d["features"])
            labels.extend(d["labels"])
            errors.extend(d["errors"])
        expanded_df = path_data.df.iloc[case_indices].reset_index(drop=True).copy()
        expanded_df["sv_id"] = labels
        feat_df = pd.concat(feats, axis=0, ignore_index=True)
        error_df = pd.DataFrame(errors, columns=["Error"])

        error_df = pd.concat([expanded_df, error_df], axis=1, ignore_index=False)
        error_df.to_csv(step_dir / "error.csv", index=False)
        
        new_df = pd.concat([expanded_df, feat_df], axis=1, ignore_index=False)
        new_df.insert(0, "FID", new_df.apply(lambda x: f"{x[path_data.id_column]}_{x['sv_id']}", axis=1))
        new_df.to_csv(step_dir / "data.csv", index=False)
        
        feat_data = FeatureData(csv_path=step_dir / "data.csv", feature_columns=feat_df.columns.tolist(), id_column="FID")
        feat_data.save(result_dir)
        return feat_data

    def save(self, step_dir, input_map, result_dir):
        tmp = {
            "step_obj": self,
            "input_map": input_map,
            "result_dir": result_dir,
        }
        with open(step_dir / "step.pkl", "wb") as f:
            pickle.dump(tmp, f)
            
        shutil.copy2(self.params, step_dir / self.to_kwargs()["params"])
        