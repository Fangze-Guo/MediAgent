import pandas as pd
from pathlib import Path
from hiomics.utils import load_params, io, parallel
import hiomics.preprocessing as preprocessing
import hiomics.decomposition as decomposition
import hiomics.cluster as cluster
import SimpleITK as sitk
import numpy as np
import shutil
from tqdm import tqdm
from easydict import EasyDict as edict
import pickle
from copy import deepcopy

from loguru import logger

FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
CFG_DIR = ROOT / "configs/subregion_clustering"
DEFAULT_CFG = load_params(CFG_DIR / "default.yaml")

def _image_mask_worker(group, image_path, mask_path, out_image_path, out_mask_path):
    sv_mask_sitk = sitk.ReadImage(mask_path)
    sv_mask_np = sitk.GetArrayFromImage(sv_mask_sitk)
    sr_mask_np = np.zeros_like(sv_mask_np)

    for sr_id, subgroup in group.groupby("sr_id"):
        for _, row in subgroup.iterrows():
            sr_mask_np[sv_mask_np == int(row["sv_id"])] = int(sr_id)

    sr_mask_sitk = sitk.GetImageFromArray(sr_mask_np)
    sr_mask_sitk.CopyInformation(sv_mask_sitk)

    out_image_path.parent.mkdir(parents=True, exist_ok=True)
    debug_mode = False and Path.home().name in ["zhenwei", "wzt"]
    if not debug_mode:
        shutil.copy2(image_path, out_image_path)
    else:
        # logger.warning(f"ATTENTION: Using symlink!!!\n" * 100)
        if out_image_path.exists():
            import os
            os.remove(out_image_path)
        Path(out_image_path).symlink_to(image_path.resolve())
    io.write_mask_nii(sr_mask_np, out_mask_path)

def subregion_clustering(args, sv_feat, output_dir, is_train=False, n_jobs=2):
    if args is None:
        args = {}
    pkl_dir = output_dir / "pkl/subregion_clustering"
    sr_dir = output_dir / "subregion_clustering"
    
    feat_df = sv_feat.df[sv_feat.feature_columns].copy()

    prep_pkl_path = pkl_dir / "prep_model.pkl"
    if prep_pkl_path.exists() and not is_train:
        prep_model = preprocessing.sklearn_wrapper.SklearnPreprocessingWrapper.load(prep_pkl_path)
        logger.info(f"Loaded prep_model from {prep_pkl_path}")
    else:
        prep_args = args.get("preprocessing", None)
        if prep_args is None:
            prep_args = deepcopy(DEFAULT_CFG["preprocessing"])
            logger.info(f"Using default preprocessing args: {prep_args}")
        prep_model = preprocessing.get_method(prep_args["method"])(params=prep_args["params"])
        prep_model.fit(feat_df)
        prep_model.save(prep_pkl_path)    
    norm_feat_df = pd.DataFrame(prep_model.predict(feat_df), columns=feat_df.columns)

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
        decomp_model.fit(norm_feat_df)
        decomp_model.save(decomp_pkl_path)
    decomp_feat_df = decomp_model.predict(norm_feat_df)

    cluster_pkl_path = pkl_dir / "cluster_model.pkl"
    if cluster_pkl_path.exists() and not is_train:
        cluster_model = cluster.sklearn_wrapper.SklearnClusterWrapper.load(cluster_pkl_path)
        logger.info(f"Loaded cluster_model from {cluster_pkl_path}")
    else:
        cluster_args = args.get("cluster", None)
        if cluster_args is None:
            cluster_args = deepcopy(DEFAULT_CFG["cluster"])
            logger.info(f"Using default cluster args: {cluster_args}")
        cluster_model = cluster.get_method(cluster_args["method"])(params=cluster_args["params"])
        cluster_model.fit(decomp_feat_df)
        cluster_model.save(cluster_pkl_path)
    sr_labels = cluster_model.predict(decomp_feat_df)
    logger.info(f"Subregion clustering done, {len(np.unique(sr_labels))} subregions found")
    # logger.debug(np.unique(sr_labels))
    
    df = sv_feat.df.drop(columns=sv_feat.feature_columns)
    df["sr_id"] = sr_labels

    id_dfs, sr_dfs = [], []
    logger.info(f"Saving subregion images and masks")
    kwargs_list = []
    for id_, group in df.groupby("ID"):
        assert group["mask_path"].nunique() == 1, "mask_path should be unique for each ID"
        assert group["image_path"].nunique() == 1, "image_path should be unique for each ID"

        image_path = group["image_path"].iloc[0]
        mask_path = group["mask_path"].iloc[0]
        
        out_image_path = sr_dir / f"image/{id_}_SR@IMG.nii.gz"
        out_mask_path = sr_dir / f"mask/{id_}_SR@MASK.nii.gz"

        kwargs_list.append({
            "group": group,
            "image_path": image_path,
            "mask_path": mask_path,
            "out_image_path": out_image_path,
            "out_mask_path": out_mask_path,
            "__name__": "_image_mask_worker",
        })

        sr_df = group.copy()
        sr_df["n_sr"] = sr_df["sr_id"].nunique()
        sr_df["n_sv"] = sr_df.groupby("sr_id")["sv_id"].transform("nunique")
        
        id_df = sr_df.drop_duplicates(subset=["ID"]).copy().reset_index(drop=True)
        id_df["image_path"] = out_image_path
        id_df["mask_path"] = out_mask_path

        sr_df.drop(columns=["sv_id", ], inplace=True) 
        id_df.drop(columns=["sv_id", "sr_id", "n_sv"], inplace=True)
        sr_dfs.append(sr_df)
        id_dfs.append(id_df)
    parallel.worker(_image_mask_worker, kwargs_list, use_multiprocessing=n_jobs > 1, desc="Saving subregion images and masks", max_workers=n_jobs, parallel_type="process")

    sr_df = pd.concat(sr_dfs, ignore_index=True)
    path_df = pd.concat(id_dfs, ignore_index=True)

    info_str = """Subregion clustering done. The return is a dictionary with the following keys:
    - df: each row is a case, with the following columns: 
    \tID: the case id
    \timage_path: the path to the image
    \tmask_path: the path to the mask
    \tn_sr: the number of subregions in the case
    \t...
    - sr: each row is a subregion, with the following columns: 
    \tID: the case id
    \timage_path: the path to the image
    \tmask_path: the path to the mask
    \tn_sr: the number of subregions in the case
    \tsr_id: the subregion id
    \tn_sv: the number of super-voxels in the subregion
    \t...
    """
    logger.info(info_str)

    ret = edict(df=path_df, sr=sr_df)
    with open(sr_dir / "sr_cluster_results.pkl", "wb") as f:
        pickle.dump(ret, f)
    return ret

from hiomics.task.step import AbcStep
from hiomics.task.data import PathData, FeatureData

class SubregionClusteringStep(AbcStep):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "default.yaml"
        self.params = load_params(params)
        self.prep_model = None
        self.decomp_model = None
        self.cluster_model = None

    def to_kwargs(self):
        return {
            "params": self.params,
        }

    def __eq__(self, other):
        return self.params == other.params

    def run(self, step_dir, result_dir, path_data: PathData, feature_data: FeatureData, force=False, n_jobs=1, **kwargs):
        args = self.params
        prep_pkl_path = step_dir / "prep_model.pkl"
        decomp_pkl_path = step_dir / "decomp_model.pkl"
        cluster_pkl_path = step_dir / "cluster_model.pkl"
        
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

        feat_df = feature_data.df[feature_data.feature_columns].copy()
        if prep_pkl_path.exists() and not force:
            prep_model = preprocessing.sklearn_wrapper.SklearnPreprocessingWrapper.load(prep_pkl_path)
            logger.info(f"Loaded prep_model from {prep_pkl_path}")
        else:
            prep_args = args.get("preprocessing", None)
            if prep_args is None:
                prep_args = deepcopy(DEFAULT_CFG["preprocessing"])
                logger.info(f"Using default preprocessing args: {prep_args}")
            prep_model = preprocessing.get_method(prep_args["method"])(params=prep_args["params"])
            prep_model.fit(feat_df)
            prep_model.save(prep_pkl_path) 
        self.prep_model = prep_model
        norm_feat_df = pd.DataFrame(prep_model.predict(feat_df))#, columns=feat_df.columns)
        logger.debug(f"After preprocessing, norm_feat_df.shape: {norm_feat_df.shape}")

        decomp_args = args.get("decomposition", None)
        if decomp_args is None:
            logger.info("No decomposition args provided, skipping decomposition")
            self.decomp_model = None
            decomp_feat_df = norm_feat_df.copy()
        else:
            if decomp_pkl_path.exists() and not force:
                decomp_model = decomposition.sklearn_wrapper.SklearnDecompositionWrapper.load(decomp_pkl_path)
                logger.info(f"Loaded decomp_model from {decomp_pkl_path}")
            else:
                decomp_model = decomposition.get_method(decomp_args["method"])(params=decomp_args["params"])
                decomp_model.fit(norm_feat_df)
                decomp_model.save(decomp_pkl_path)
            self.decomp_model = decomp_model
            decomp_feat_df = decomp_model.predict(norm_feat_df)

        if cluster_pkl_path.exists() and not force:
            cluster_model = cluster.sklearn_wrapper.SklearnClusterWrapper.load(cluster_pkl_path)
            logger.info(f"Loaded cluster_model from {cluster_pkl_path}")
        else:
            cluster_args = args.get("cluster", None)
            if cluster_args is None:
                cluster_args = deepcopy(DEFAULT_CFG["cluster"])
                logger.info(f"Using default cluster args: {cluster_args}")
            cluster_model = cluster.get_method(cluster_args["method"])(params=cluster_args["params"])
            cluster_model.fit(decomp_feat_df)
            cluster_model.save(cluster_pkl_path)
        self.cluster_model = cluster_model
        sr_labels = cluster_model.predict(decomp_feat_df)
        logger.info(f"Subregion clustering done, {len(np.unique(sr_labels))} subregions found")

        df = feature_data.df.copy()
        df["sr_id"] = sr_labels

        new_path_data = deepcopy(path_data)
        new_path_data.set_images(path_data.new_images())
        new_path_data.set_masks(path_data.new_masks())
        new_path_data.base_dir = None

        src_images = path_data.get_images()
        src_masks = path_data.get_masks()
        dst_images = new_path_data.get_images()
        dst_masks = new_path_data.get_masks()

        kwargs_list = []
        for i, (src_img_path, src_mask_path, dst_img_path, dst_mask_path) in enumerate(zip(src_images, src_masks, dst_images, dst_masks)):
            row = path_data.df.iloc[i]
            group = df.query(f"`{path_data.id_column}` == '{row[path_data.id_column]}'")
        
            kwargs_list.append({
                "group": group,
                "image_path": src_img_path,
                "mask_path": src_mask_path,
                "out_image_path": result_dir / dst_img_path,
                "out_mask_path": result_dir / dst_mask_path,
                "__name__": f"{i}",
            })      

        parallel.worker(_image_mask_worker, kwargs_list, use_multiprocessing=n_jobs > 1, desc="Saving subregion images and masks", max_workers=n_jobs, parallel_type="process")
        new_path_data.save(result_dir)
        return new_path_data

    def save(self, step_dir, input_map, result_dir):
        tmp = {
            "step_obj": self,
            "input_map": input_map,
            "result_dir": result_dir,
        }
        with open(step_dir / "step.pkl", "wb") as f:
            pickle.dump(tmp, f)

    
if __name__ == "__main__":
    args = {}

    prep_args = args.get("preprocessing", None)
    if prep_args is None:
        prep_args = deepcopy(DEFAULT_CFG["preprocessing"])
        logger.info(f"Using default preprocessing args: {prep_args}")
    prep_model = preprocessing.get_method(prep_args["method"])(params=prep_args["params"])

    decomp_args = args.get("decomposition", None)
    if decomp_args is None:
        decomp_args = deepcopy(DEFAULT_CFG["decomposition"])
        logger.info(f"Using default decomposition args: {decomp_args}")
    decomp_model = decomposition.get_method(decomp_args["method"])(params=decomp_args["params"])

    cluster_args = args.get("cluster", None)
    if cluster_args is None:
        cluster_args = deepcopy(DEFAULT_CFG["cluster"])
        logger.info(f"Using default cluster args: {cluster_args}")
    cluster_model = cluster.get_method(cluster_args["method"])(params=cluster_args["params"])


