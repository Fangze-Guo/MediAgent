import os
import argparse
import SimpleITK as sitk
import numpy as np
parser = argparse.ArgumentParser()
parser.add_argument('--task', type=str,
                    default='B') # B breast/T tumor
parser.add_argument('--dicom_path', type=str,
                    default='')
parser.add_argument('--model_seg_input_path', type=str,
                    default='')
parser.add_argument('--model_seg_output_path', type=str,
                    default='')
args = parser.parse_args()

def read_write_dicom(dicom_dir_path):
    reader = sitk.ImageSeriesReader()
    img_name = reader.GetGDCMSeriesFileNames(dicom_dir_path)
    tag = sitk.ReadImage(img_name[0])
    id = tag.GetMetaData('0010|0020')
    reader.SetFileNames(img_name)
    image = reader.Execute()
    image_array = sitk.GetArrayFromImage(image)
    image_out = sitk.GetImageFromArray(image_array)
    image_out.SetOrigin(image.GetOrigin())
    image_out.SetSpacing(image.GetSpacing())
    image_out.SetDirection(image.GetDirection())
    return image_out, id

def delete_all_files(directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

def resample_image(itk_image, out_spacing=[1.0, 1.0, 1.0]):
    original_spacing = itk_image.GetSpacing()
    original_size = itk_image.GetSize()
    out_size = [
        int(np.round(original_size[0] * original_spacing[0] / out_spacing[0])),
        int(np.round(original_size[1] * original_spacing[1] / out_spacing[1])),
        int(np.round(original_size[2] * original_spacing[2] / out_spacing[2]))
    ]
    resample = sitk.ResampleImageFilter()
    resample.SetOutputSpacing(out_spacing)
    resample.SetSize(out_size)
    resample.SetOutputDirection(itk_image.GetDirection())
    resample.SetOutputOrigin(itk_image.GetOrigin())
    resample.SetTransform(sitk.Transform())
    resample.SetDefaultPixelValue(itk_image.GetPixelIDValue())
    resample.SetInterpolator(sitk.sitkNearestNeighbor)
    return resample.Execute(itk_image)


if not os.path.exists(args.model_seg_input_path):
    os.makedirs(args.model_seg_input_path)
elif len(os.listdir(args.model_seg_input_path))!=0:
    delete_all_files(args.model_seg_input_path)
if not os.path.exists(args.model_seg_output_path):
    os.makedirs(args.model_seg_output_path)
elif len(os.listdir(args.model_seg_output_path))!=0:
    delete_all_files(args.model_seg_output_path)
file_list = os.listdir(args.dicom_path)
file_list.sort()
fail_resample_list = []
for file in file_list:
    print(file)
    try:
        img, _ = read_write_dicom(os.path.join(args.dicom_path, file))
        img_resample = resample_image(img)
        sitk.WriteImage(img_resample, os.path.join(args.model_seg_input_path, file + '_0000.nii.gz'))
        print(f"{file} is resampled!")
    except:
        print(f"Wrong with {file}!")
        fail_resample_list.append(file)
        continue
if len(fail_resample_list) != 0:
    print(f'Cases failed to resample: {fail_resample_list}')
if args.task == 'B':
    task = 52
    fold = 4
elif args.task == 'T':
    task = 88
    fold = 0
os.system(
    f"nnUNet_predict -i {args.model_seg_input_path}/ -o {args.model_seg_output_path} -t {task} -m 3d_fullres -f {fold}")
