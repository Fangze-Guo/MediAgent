from ..utils import io, parallel, load_params, create_object
from hiomics.task.step import AbcStep
from hiomics.task.data import PathData
import pickle
from loguru import logger
from pathlib import Path
from copy import deepcopy

import numpy as np
import monai
# from monai.data import set_track_meta
# set_track_meta(False)
import gc


def run_transform(src_image_path, src_mask_path, dst_image_path, dst_mask_path, trans):
    parser = monai.bundle.ConfigParser(trans)
    args = parser.get_parsed_content()
    trans = args["transform"]

    # gc.collect()
    # logger.info(f"1: Run transform: {src_image_path}")
    data = {
        "image": src_image_path,
        "mask": src_mask_path,
    }
    new_data = trans(data)
    # logger.info("2: Transform done")
    io.write_image_nii(new_data["image"], dst_image_path)
    io.write_mask_nii(new_data["mask"], dst_mask_path)
    # logger.info("3: Write done")


class MonaiStep(AbcStep):
    def __init__(self, params):
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

        # parser = monai.bundle.ConfigParser(self.params)
        # args = parser.get_parsed_content()
        # transform = args["transform"]

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
        kwargs_list = []
        for src_img_path, src_mask_path, dst_img_path, dst_mask_path in zip(src_images, src_masks, dst_images, dst_masks):
            kwargs_list.append({
                "src_image_path": src_img_path,
                "src_mask_path": src_mask_path,
                "dst_image_path": result_dir / dst_img_path,
                "dst_mask_path": result_dir / dst_mask_path,
                "trans": deepcopy(self.params),
            })

        parallel.worker(run_transform, kwargs_list, use_multiprocessing=n_jobs > 1, max_workers=n_jobs, desc="MONAI transform")
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