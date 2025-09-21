from pathlib import Path
import SimpleITK as sitk

from script import dcm_dir, og_dir


def read_dicom_series(series_directory: Path) -> sitk.Image:
    reader = sitk.ImageSeriesReader()
    series_ids = reader.GetGDCMSeriesIDs(str(series_directory))
    if not series_ids:
        raise FileNotFoundError(f"No DICOM series found in {series_directory}")

    # Pick the series with the most files if multiple exist in the folder
    best_file_names = []
    for series_id in series_ids:
        file_names = reader.GetGDCMSeriesFileNames(str(series_directory), series_id)
        if len(file_names) > len(best_file_names):
            best_file_names = file_names

    reader.SetFileNames(best_file_names)
    image = reader.Execute()
    return image


for patient_dir in dcm_dir.iterdir():
    if not patient_dir.is_dir():
        continue

    c0_dir = patient_dir / "C0"
    c2_dir = patient_dir / "C2"
    if not c0_dir.exists() or not c2_dir.exists():
        continue

    c0_img_sitk = read_dicom_series(c0_dir)
    c2_img_sitk = read_dicom_series(c2_dir)

    dst_dir = og_dir / patient_dir.name
    dst_dir.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(c0_img_sitk, str(dst_dir / "C0.nii.gz"))
    sitk.WriteImage(c2_img_sitk, str(dst_dir / "C2.nii.gz"))

    print(f"{patient_dir.name} C0 size: {c0_img_sitk.GetSize()}, spacing: {c0_img_sitk.GetSpacing()}")
    print(f"{patient_dir.name} C2 size: {c2_img_sitk.GetSize()}, spacing: {c2_img_sitk.GetSpacing()}")