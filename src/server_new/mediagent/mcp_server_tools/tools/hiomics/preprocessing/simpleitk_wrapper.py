import SimpleITK as sitk
from pathlib import Path
from ..utils import io, parallel, load_params
from copy import deepcopy
from loguru import logger
from hiomics.preprocessing import CFG_DIR
import pickle
import shutil
import traceback


from hiomics.task.step import AbcStep
from hiomics.task.data import PathData


# def resample(in_path, out_path, out_spacing=[1.0, 1.0, 1.0], is_mask = False):
#     image_3d = sitk.ReadImage(str(in_path))
#     if image_3d.GetSpacing() == out_spacing:
#         shutil.copy(in_path, out_path)
#         return

#     # image_3d is simpleitk
#     if isinstance(image_3d, sitk.Image):
#         original_spacing = image_3d.GetSpacing()
#         original_size = image_3d.GetSize()

#         # out_size = [
#         #     int(np.round(original_size[0] * (original_spacing[0] / out_spacing[0]))),
#         #     int(np.round(original_size[1] * (original_spacing[1] / out_spacing[1]))),
#         #     int(np.round(original_size[2] * (original_spacing[2] / out_spacing[2])))
#         # ]
#         # 上述也可以直接用下面这句简写
#         out_size = [int(round(osz*ospc/nspc)) for osz,ospc,nspc in zip(original_size, original_spacing, out_spacing)]
#         #print(itk_image.GetDirection(),itk_image.GetOrigin())
#         resample = sitk.ResampleImageFilter()
#         resample.SetOutputSpacing(out_spacing)
#         resample.SetSize(out_size)
#         resample.SetOutputDirection(image_3d.GetDirection())
#         resample.SetOutputOrigin(image_3d.GetOrigin())
#         resample.SetTransform(sitk.Transform())
#         # resample.SetDefaultPixelValue(itk_image.GetPixelIDValue())

#         if is_mask: # 如果是mask图像，就选择sitkNearestNeighbor这种插值
#             resample.SetInterpolator(sitk.sitkNearestNeighbor)
#         else: # 如果是普通图像，就采用sitkBSpline插值法
#             resample.SetInterpolator(sitk.sitkBSpline)

#         resampled_image = resample.Execute(image_3d)
#         resampled_image = sitk.DICOMOrient(resampled_image, "LPS")
#         resampled_image.SetOrigin((0.0, 0.0, 0.0))
#         resampled_image.SetDirection((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))
#         # print(resampled_image.GetDirection())
#         Path(out_path).parent.mkdir(parents=True, exist_ok=True)
#         sitk.WriteImage(resampled_image, str(out_path))
#         # return resampled_image
#     else:
#         raise NotImplementedError

def resample(in_path, out_path, out_spacing=[1.0, 1.0, 1.0], is_mask = False):
    image_3d = sitk.ReadImage(str(in_path))

    """ 1. spacing """
    original_size = image_3d.GetSize()
    original_spacing = image_3d.GetSpacing()
    same_spacing = True
    for i in range(len(original_spacing)):
        if original_spacing[i] != out_spacing[i]:
            same_spacing = False
            break
    if not same_spacing:
        out_size = [int(round(osz*ospc/nspc)) for osz,ospc,nspc in zip(original_size, original_spacing, out_spacing)]
        resample_filter = sitk.ResampleImageFilter()
        resample_filter.SetOutputSpacing(out_spacing)
        resample_filter.SetSize(out_size)
        resample_filter.SetOutputDirection(image_3d.GetDirection())
        resample_filter.SetOutputOrigin(image_3d.GetOrigin())
        resample_filter.SetTransform(sitk.Transform())
        # resample.SetDefaultPixelValue(itk_image.GetPixelIDValue())

        if is_mask: # 如果是mask图像，就选择sitkNearestNeighbor这种插值
            resample_filter.SetInterpolator(sitk.sitkNearestNeighbor)
        else: # 如果是普通图像，就采用sitkBSpline插值法
            resample_filter.SetInterpolator(sitk.sitkBSpline)

        image_3d = resample_filter.Execute(image_3d)

    """ 2. direction """
    original_direction = image_3d.GetDirection()
    out_direction = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    same_direction = True
    for i in range(len(original_direction)):
        if original_direction[i] != out_direction[i]:
            same_direction = False
            break
    image_3d = sitk.DICOMOrient(image_3d, "LPS")
    image_3d.SetDirection(out_direction)

    """ 3. origin """
    original_origin = image_3d.GetOrigin()
    out_origin = (0.0, 0.0, 0.0)
    same_origin = True
    for i in range(len(original_origin)):
        if original_origin[i] != out_origin[i]:
            same_origin = False
    image_3d.SetOrigin(out_origin)

    """ 4. write """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(image_3d, str(out_path))



class ResampleStep(AbcStep):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "Resampler.yaml"
            logger.info(f"Using default params for Resampler: {params}")
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
        kwargs_list = []
        for src_img_path, src_mask_path, dst_img_path, dst_mask_path in zip(src_images, src_masks, dst_images, dst_masks):
            kwargs_list.append({
                "in_path": src_img_path,
                "out_path": result_dir / dst_img_path,
                "out_spacing": self.params["spacing"],
                "is_mask": False,
            })
            kwargs_list.append({
                "in_path": src_mask_path,
                "out_path": result_dir / dst_mask_path,
                "out_spacing": self.params["spacing"],
                "is_mask": True,
            })

        parallel.worker(resample, kwargs_list, use_multiprocessing=n_jobs > 1, max_workers=n_jobs, desc="Resampling")
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

def N4(src_image_path, src_mask_path, dst_image_path, dst_mask_path, kernel_radius=None):
    try:
        image = sitk.Cast(sitk.ReadImage(str(src_image_path)), sitk.sitkFloat32)
        mask = sitk.Cast(sitk.ReadImage(str(src_mask_path)), sitk.sitkUInt8)
        if kernel_radius:
            mask = sitk.Cast(sitk.BinaryDilate(mask, kernelRadius=kernel_radius, foregroundValue=1, backgroundValue=0), sitk.sitkUInt8)

        n4_corrector = sitk.N4BiasFieldCorrectionImageFilter()
        res = n4_corrector.Execute(image, mask)

        Path(dst_image_path).parent.mkdir(parents=True, exist_ok=True)
        sitk.WriteImage(res, str(dst_image_path))

        Path(dst_mask_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_mask_path, dst_mask_path)
    except Exception as e:
        logger.error(traceback.format_exc())
        raise e
    
class N4Step(AbcStep):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "N4.yaml"
            logger.info(f"Using default params for Resampler: {params}")
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
        kwargs_list = []
        for src_img_path, src_mask_path, dst_img_path, dst_mask_path in zip(src_images, src_masks, dst_images, dst_masks):
            kwargs_list.append({
                "src_image_path": src_img_path,
                "src_mask_path": src_mask_path,
                "dst_image_path": result_dir / dst_img_path,
                "dst_mask_path": result_dir / dst_mask_path,
                "kernel_radius": self.params["kernel_radius"],
            })

        parallel.worker(N4, kwargs_list, use_multiprocessing=n_jobs > 1, max_workers=n_jobs, desc="N4")
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

def normalize(src_image_path, src_mask_path, dst_image_path, dst_mask_path, scale=1):
    try:
        image = sitk.ReadImage(str(src_image_path))
        normalized = sitk.Normalize(image)
        
        # Apply scale factor
        if scale != 1:
            normalized = normalized * scale
        
        Path(dst_image_path).parent.mkdir(parents=True, exist_ok=True)
        sitk.WriteImage(normalized, str(dst_image_path))
        
        Path(dst_mask_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_mask_path, dst_mask_path)
    except Exception as e:
        logger.error(traceback.format_exc())
        raise e

class NormalizeStep(AbcStep):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "Normalize.yaml"
            logger.info(f"Using default params for Normalize: {params}")
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
        kwargs_list = []
        for src_img_path, src_mask_path, dst_img_path, dst_mask_path in zip(src_images, src_masks, dst_images, dst_masks):
            kwargs_list.append({
                "src_image_path": src_img_path,
                "src_mask_path": src_mask_path,
                "dst_image_path": result_dir / dst_img_path,
                "dst_mask_path": result_dir / dst_mask_path,
                "scale": self.params.get("scale", 1),
            })

        parallel.worker(normalize, kwargs_list, use_multiprocessing=n_jobs > 1, max_workers=n_jobs, desc="Normalize")
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

