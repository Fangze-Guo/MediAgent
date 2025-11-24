from skimage.segmentation import slic
from copy import deepcopy
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Union, Tuple
from ..utils import io, parallel, load_params, generate_spatial_bounding_box
import SimpleITK as sitk
from pathlib import Path
import shutil
from loguru import logger
import yaml
import pickle


FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
CFG_DIR = ROOT / "configs/pre_segmentation"


def slic_worker(params: Dict[str, Any], 
                image_path: str, 
                mask_path: str, 
                max_number_of_segments: int, 
                min_pixels_per_segment: int, 
                out_image_path: str, 
                out_mask_path: str,
                ) -> Dict[str, Any]:
    try:
        params = deepcopy(params)
        params.update(dict(start_label=1, channel_axis=None))
        # image = io.as_numpy(image_path)
        # mask = io.as_numpy(mask_path)
        image_sitk = sitk.ReadImage(image_path)
        mask_sitk = sitk.ReadImage(mask_path)
        image = sitk.GetArrayFromImage(image_sitk)
        mask = sitk.GetArrayFromImage(mask_sitk)
        total_pixels = np.sum(np.where(mask > 0, 1, 0))

        if total_pixels == 0:
            n_sv = 0
            # image = np.zeros_like(image)
            mask = np.zeros_like(mask)
        else:
            """ 
            因为slic(n_segments=1)会导致空mask，所以最小只能设置为2
            """
            n_segments = total_pixels / min_pixels_per_segment
            if n_segments <= 1:
                n_segments = 1
            else:
                n_segments = min(max_number_of_segments, max(2, int(n_segments)))
            params["n_segments"] = n_segments
            # params["n_segments"] = 2
            # logger.debug(f"n_segments: {params['n_segments']}")

            roi_start, roi_end = generate_spatial_bounding_box(mask)
            image_roi = image[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]
            mask_roi = mask[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]]

            sv_mask = slic(image_roi, mask=mask_roi, **params)
            n_sv = sv_mask.max()
            if n_sv == 0:
                sv_mask = mask_roi
                n_sv = 1
                logger.warning(f"n_segments is 1, skimage's slic cannot segment, using original mask ({mask_path}) instead.")
            
            # image_roi = image_roi * np.where(sv_mask > 0, 1, 0)
            # image[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]] = image_roi
            mask[roi_start[0]:roi_end[0], roi_start[1]:roi_end[1], roi_start[2]:roi_end[2]] = sv_mask
            
        new_mask_sitk = sitk.GetImageFromArray(mask)
        new_mask_sitk.CopyInformation(mask_sitk)
        Path(out_mask_path).parent.mkdir(parents=True, exist_ok=True)
        sitk.WriteImage(new_mask_sitk, out_mask_path)
        Path(out_image_path).parent.mkdir(parents=True, exist_ok=True)
        debug_mode = False and Path.home().name in ["zhenwei", "wzt"]
        if not debug_mode:
            shutil.copy2(image_path, out_image_path)
        else:
            # logger.warning(f"ATTENTION: Using symlink!!!\n" * 10)
            if out_image_path.exists():
                import os
                os.remove(out_image_path)
            Path(out_image_path).symlink_to(image_path.resolve())
        # io.write_image_nii(image, out_image_path)
        # io.write_mask_nii(mask, out_mask_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    return dict(n_sv=n_sv, image_path=out_image_path, mask_path=out_mask_path)

def run_batch(params: Union[Dict[str, Any], str, None], 
              df: pd.DataFrame, 
              output_dir: str,
            #   max_number_of_segments: int,
            #   min_pixels_per_segment: int,
              n_jobs: int,
              ) -> pd.DataFrame:
    if params is None:
        params = CFG_DIR / "SLIC.yaml"  
        logger.info(f"Using default params for SLIC: {params}")
    params = load_params(params)
    logger.info(f"=> Params: {params}")

    if "max_number_of_segments" not in params:
        logger.error(f"max_number_of_segments is not in params")
        raise ValueError(f"max_number_of_segments is not in params")
    if "min_pixels_per_segment" not in params:
        logger.error(f"min_pixels_per_segment is not in params")
        raise ValueError(f"min_pixels_per_segment is not in params")
    max_number_of_segments = params["max_number_of_segments"]
    del params["max_number_of_segments"]
    min_pixels_per_segment = params["min_pixels_per_segment"]
    del params["min_pixels_per_segment"]

    ids = df["ID"].tolist()
    image_paths = df["image_path"].tolist()
    mask_paths = df["mask_path"].tolist()
    n = len(image_paths)

    preseg_dir = Path(output_dir) / "pre_segmentation"

    kwargs_list = []
    for i in range(n):
        kwargs_list.append(dict(
            params=params,
            image_path=image_paths[i],
            mask_path=mask_paths[i],
            max_number_of_segments=max_number_of_segments,
            min_pixels_per_segment=min_pixels_per_segment,
            out_image_path=preseg_dir / f"image/{ids[i]}_SV@IMG.nii.gz",
            out_mask_path=preseg_dir / f"mask/{ids[i]}_SV@MASK.nii.gz",
        ))

    ret = parallel.worker(slic_worker, kwargs_list, use_multiprocessing=n_jobs > 1, desc="SLIC", max_workers=n_jobs, parallel_type="process")
    
    new_df = df.copy()
    new_df["n_sv"] = [d["n_sv"] for d in ret]
    new_df["image_path"] = [d["image_path"] for d in ret]
    new_df["mask_path"] = [d["mask_path"] for d in ret]
    new_df.to_csv(preseg_dir / "sv_path.csv", index=False)

    with open(preseg_dir / "pre_segmentation.yaml", "w") as f:
        data = {
            "method": "SLIC",
            "params": params,
        }
        yaml.dump(data, f, sort_keys=False)
    return new_df


from hiomics.task.step import AbcStep
from hiomics.task.data import PathData

class PreSegmentationSLICStep(AbcStep):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "SLIC.yaml"
            logger.info(f"Using default params for SLIC: {params}")
        self.params = load_params(params)

    def to_kwargs(self):
        return {
            "params": self.params,
        }

    def __eq__(self, other):
        return self.params == other.params

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

        new_path_data = deepcopy(path_data)
        img_col = path_data.image_column
        mask_col = path_data.mask_column

        new_path_data.set_images(path_data.new_images())
        new_path_data.set_masks(path_data.new_masks())
        new_path_data.base_dir = None

        src_images = path_data.get_images()
        src_masks = path_data.get_masks()
        dst_images = new_path_data.get_images()
        dst_masks = new_path_data.get_masks()


        params = deepcopy(self.params)
        if "max_number_of_segments" not in params:
            logger.error(f"max_number_of_segments is not in params")
            raise ValueError(f"max_number_of_segments is not in params")
        if "min_pixels_per_segment" not in params:
            logger.error(f"min_pixels_per_segment is not in params")
            raise ValueError(f"min_pixels_per_segment is not in params")
        max_number_of_segments = params["max_number_of_segments"]
        del params["max_number_of_segments"]
        min_pixels_per_segment = params["min_pixels_per_segment"]
        del params["min_pixels_per_segment"]

        kwargs_list = []
        for src_img_path, src_mask_path, dst_img_path, dst_mask_path in zip(src_images, src_masks, dst_images, dst_masks):
            kwargs_list.append(dict(
                params=params,
                image_path=src_img_path,
                mask_path=src_mask_path,
                max_number_of_segments=max_number_of_segments,
                min_pixels_per_segment=min_pixels_per_segment,
                out_image_path=result_dir / dst_img_path,
                out_mask_path=result_dir / dst_mask_path,
            ))

        parallel.worker(slic_worker, kwargs_list, use_multiprocessing=n_jobs > 1, max_workers=n_jobs, desc="SLIC")
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