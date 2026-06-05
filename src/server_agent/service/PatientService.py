import re
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import asyncpg
from fastapi import UploadFile

from src.server_agent.exceptions import ConflictError, DatabaseError, NotFoundError, ValidationError, handle_service_exception
from src.server_agent.mapper.PatientMapper import PatientMapper


logger = logging.getLogger(__name__)
PATIENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
PATIENT_DATA_ROOT = Path("/home/fetters/project/MediAgent/src/server_new/data/patient")
CT_PHASES = {"pre", "post"}
CT_EXTENSIONS = {".nii", ".nii.gz", ".dcm", ".zip"}
PREVIEW_PLANES = {"axial", "coronal", "sagittal"}
MASK_TYPES = {
    "body-composition": "body_composition",
    "spine": "spine",
}
MASK_EXTENSIONS = {".nii", ".nii.gz"}


class PatientService:
    """Business service for the global patient dataset."""

    def __init__(self, mapper: Optional[PatientMapper] = None):
        self.mapper = mapper or PatientMapper()

    async def init(self) -> None:
        await self.mapper.init()
        PATIENT_DATA_ROOT.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        await self.mapper.close()

    @staticmethod
    def _validate_patient_id(patient_id: str) -> str:
        normalized = (patient_id or "").strip()
        if not PATIENT_ID_RE.fullmatch(normalized):
            raise ValidationError(
                detail="patient_id only supports letters, numbers, dot, underscore and hyphen",
                field="patient_id",
                context={"patient_id": patient_id},
            )
        return normalized

    @staticmethod
    def _patient_dir(patient_id: str) -> Path:
        patient_dir = (PATIENT_DATA_ROOT / patient_id).resolve()
        root = PATIENT_DATA_ROOT.resolve()
        try:
            patient_dir.relative_to(root)
        except ValueError:
            raise ValidationError(detail="invalid patient data path", field="patient_id")
        if patient_dir == root:
            raise ValidationError(detail="invalid patient data path", field="patient_id")
        return patient_dir

    @staticmethod
    def _ct_ext(filename: str) -> str:
        name = filename.lower()
        if name.endswith(".nii.gz"):
            return ".nii.gz"
        return Path(name).suffix

    @staticmethod
    def _safe_filename(filename: str, field: str = "ct_file") -> str:
        name = Path(filename or "").name.strip()
        if not name:
            raise ValidationError(detail=f"{field} filename is required", field=field)
        if "/" in name or "\\" in name:
            raise ValidationError(detail=f"invalid {field} filename", field=field)
        return name

    def _validate_phase(self, phase: str) -> str:
        clean_phase = (phase or "").strip().lower()
        if clean_phase not in CT_PHASES:
            raise ValidationError(
                detail="phase must be pre or post",
                field="phase",
                context={"phase": phase},
            )
        return clean_phase

    def _ct_dir(self, patient_id: str, phase: str) -> Path:
        patient_dir = self._patient_dir(patient_id)
        ct_dir = (patient_dir / phase / "ct").resolve()
        try:
            ct_dir.relative_to(patient_dir)
        except ValueError:
            raise ValidationError(detail="invalid ct data path", field="patient_id")
        return ct_dir

    def _ct_meta_path(self, patient_id: str, phase: str) -> Path:
        return self._ct_dir(patient_id, phase) / "meta.json"

    def _validate_preview_plane(self, plane: str) -> str:
        clean_plane = (plane or "").strip().lower()
        if clean_plane not in PREVIEW_PLANES:
            raise ValidationError(
                detail="plane must be axial, coronal, or sagittal",
                field="plane",
                context={"plane": plane},
            )
        return clean_plane

    def _validate_mask_type(self, mask_type: str) -> str:
        clean_type = (mask_type or "").strip().lower()
        if clean_type not in MASK_TYPES:
            raise ValidationError(
                detail="mask_type must be body-composition or spine",
                field="mask_type",
                context={"mask_type": mask_type},
            )
        return clean_type

    def _mask_dir(self, patient_id: str, mask_type: str, phase: str) -> Path:
        patient_dir = self._patient_dir(patient_id)
        mask_dir = (patient_dir / MASK_TYPES[mask_type] / phase / "mask").resolve()
        try:
            mask_dir.relative_to(patient_dir)
        except ValueError:
            raise ValidationError(detail="invalid mask data path", field="patient_id")
        return mask_dir

    def _mask_meta_path(self, patient_id: str, mask_type: str, phase: str) -> Path:
        return self._mask_dir(patient_id, mask_type, phase) / "meta.json"

    def _empty_ct_status(self, phase: str) -> Dict[str, Any]:
        return {
            "phase": phase,
            "status": "empty",
            "file_name": None,
            "file_size": None,
            "uploaded_at": None,
            "preview_url": None,
            "preview_planes": None,
        }

    def _empty_mask_status(self, mask_type: str, phase: str) -> Dict[str, Any]:
        return {
            "mask_type": mask_type,
            "phase": phase,
            "status": "empty",
            "file_name": None,
            "file_size": None,
            "uploaded_at": None,
            "preview_url": None,
            "preview_planes": None,
        }

    @staticmethod
    def _normalize_slice(slice_2d, window: Optional[tuple[float, float]] = None):
        import numpy as np
        from PIL import Image

        arr = np.asarray(slice_2d, dtype=np.float32)
        arr = np.nan_to_num(arr)
        if window is None:
            lo, hi = np.percentile(arr, [1, 99])
        else:
            lo, hi = window
        if hi <= lo:
            lo, hi = float(arr.min()), float(arr.max())
        if hi <= lo:
            arr = np.zeros_like(arr, dtype=np.uint8)
        else:
            arr = np.clip((arr - lo) / (hi - lo), 0, 1)
            arr = (arr * 255).astype(np.uint8)
        return Image.fromarray(arr).convert("L")

    @staticmethod
    def _ct_display_window(volume) -> tuple[float, float]:
        import numpy as np

        arr = np.asarray(volume, dtype=np.float32)
        arr = np.nan_to_num(arr)
        return float(np.min(arr)), float(np.max(arr))

    @staticmethod
    def _orient_preview_plane(axis: str, plane):
        import numpy as np

        oriented = np.asarray(plane)
        if axis in {"coronal", "sagittal"}:
            return np.flipud(oriented)
        return oriented

    @staticmethod
    def _resize_to_physical_aspect(img, axis: str, spacing, resample=None):
        from PIL import Image

        if not spacing or len(spacing) < 3:
            return img
        x_spacing, y_spacing, z_spacing = (float(spacing[0]), float(spacing[1]), float(spacing[2]))
        if axis == "axial":
            col_spacing, row_spacing = x_spacing, y_spacing
        elif axis == "coronal":
            col_spacing, row_spacing = x_spacing, z_spacing
        else:
            col_spacing, row_spacing = y_spacing, z_spacing
        if col_spacing <= 0 or row_spacing <= 0:
            return img

        width, height = img.size
        physical_ratio = (width * col_spacing) / (height * row_spacing)
        if physical_ratio <= 0:
            return img
        target_width = max(1, int(round(height * physical_ratio)))
        if target_width == width:
            return img
        return img.resize((target_width, height), resample or Image.Resampling.BILINEAR)

    @staticmethod
    def _plane_preview_path(preview_path: Path, plane: str) -> Path:
        return preview_path.with_name(f"preview_{plane}.png")

    def _make_ct_preview(self, ct_path: Path, preview_path: Path) -> bool:
        import numpy as np
        from PIL import Image, ImageDraw
        import SimpleITK as sitk

        ext = self._ct_ext(ct_path.name)
        if ext == ".zip":
            return False

        image = sitk.ReadImage(str(ct_path))
        spacing = image.GetSpacing()
        volume = sitk.GetArrayFromImage(image)
        if volume.ndim == 4:
            volume = volume[0]
        if volume.ndim == 2:
            volume = volume[np.newaxis, :, :]
        if volume.ndim != 3:
            return False

        z, y, x = volume.shape
        ct_window = self._ct_display_window(volume)
        slices = [
            ("Axial", "axial", volume[z // 2, :, :]),
            ("Coronal", "coronal", volume[:, y // 2, :]),
            ("Sagittal", "sagittal", volume[:, :, x // 2]),
        ]
        panel_width = 420
        image_height = 380
        panel_height = 430
        gap = 12

        panels = []
        for label, axis, arr in slices:
            img = self._normalize_slice(self._orient_preview_plane(axis, arr), ct_window)
            img = self._resize_to_physical_aspect(img, axis, spacing)
            img.convert("RGB").save(self._plane_preview_path(preview_path, axis))
            img.thumbnail((panel_width - 24, image_height))
            canvas = Image.new("RGB", (panel_width, panel_height), "#0b0f19")
            left = (panel_width - img.width) // 2
            top = (image_height - img.height) // 2
            canvas.paste(img.convert("RGB"), (left, top))
            draw = ImageDraw.Draw(canvas)
            draw.text((14, image_height + 18), label, fill="#e5e7eb")
            panels.append(canvas)

        combined = Image.new("RGB", (panel_width * 3 + gap * 2, panel_height), "#111827")
        for index, panel in enumerate(panels):
            combined.paste(panel, (index * (panel_width + gap), 0))
        combined.save(preview_path)
        return True

    def _make_mask_preview(self, mask_path: Path, preview_path: Path, patient_id: str, phase: str) -> bool:
        import numpy as np
        from PIL import Image, ImageDraw
        import SimpleITK as sitk

        image = sitk.ReadImage(str(mask_path))
        mask_spacing = image.GetSpacing()
        volume = sitk.GetArrayFromImage(image)
        if volume.ndim == 4:
            volume = volume[0]
        if volume.ndim == 2:
            volume = volume[np.newaxis, :, :]
        if volume.ndim != 3:
            return False

        mask = np.asarray(volume)
        nonzero = mask != 0
        if not np.any(nonzero):
            return False

        label_values = np.unique(mask[nonzero])
        if (
            len(label_values) > 64
            or np.any(label_values < 0)
            or not np.all(np.isclose(label_values, np.round(label_values)))
        ):
            raise ValidationError(
                detail="Mask file must be a discrete label map, not a CT/intensity image",
                field="mask_file",
                context={
                    "label_count": int(len(label_values)),
                    "min_value": float(np.min(label_values)),
                    "max_value": float(np.max(label_values)),
                },
            )

        ct_data = self._find_reference_ct_volume(patient_id, phase)
        ct_volume = ct_data[0] if ct_data is not None else None
        ct_spacing = ct_data[1] if ct_data is not None else None
        display_spacing = ct_spacing or mask_spacing

        def center_index(size: int) -> int:
            return max(0, size // 2)

        def map_index(index: int, source_size: int, target_size: int) -> int:
            if source_size <= 1 or target_size <= 1:
                return 0
            return int(round(index * (target_size - 1) / (source_size - 1)))

        if ct_volume is not None:
            ct_z, ct_y, ct_x = ct_volume.shape
            ct_z_idx = center_index(ct_z)
            ct_y_idx = center_index(ct_y)
            ct_x_idx = center_index(ct_x)
            z_idx = map_index(ct_z_idx, ct_z, mask.shape[0])
            y_idx = map_index(ct_y_idx, ct_y, mask.shape[1])
            x_idx = map_index(ct_x_idx, ct_x, mask.shape[2])
            ct_window = self._ct_display_window(ct_volume)
        else:
            z_idx = center_index(mask.shape[0])
            y_idx = center_index(mask.shape[1])
            x_idx = center_index(mask.shape[2])
            ct_z_idx = ct_y_idx = ct_x_idx = 0
            ct_window = None

        def ct_slice(axis: str):
            if ct_volume is None:
                return None
            try:
                if axis == "axial":
                    return ct_volume[ct_z_idx, :, :]
                if axis == "coronal":
                    return ct_volume[:, ct_y_idx, :]
                return ct_volume[:, :, ct_x_idx]
            except Exception as exc:
                logger.warning(
                    "Failed to slice reference CT for mask preview: patient=%s phase=%s axis=%s error=%s",
                    patient_id,
                    phase,
                    axis,
                    exc,
                )
                return None

        slices = [
            ("Axial", "axial", mask[z_idx, :, :], ct_slice("axial")),
            ("Coronal", "coronal", mask[:, y_idx, :], ct_slice("coronal")),
            ("Sagittal", "sagittal", mask[:, :, x_idx], ct_slice("sagittal")),
        ]
        palette = np.array([
            [255, 0, 0],
            [0, 255, 0],
            [0, 0, 255],
            [255, 255, 0],
            [0, 255, 255],
            [255, 0, 255],
            [255, 255, 255],
            [0, 0, 255],
            [180, 110, 40],
            [220, 190, 130],
            [0, 220, 220],
            [80, 60, 200],
            [0, 150, 150],
            [0, 150, 80],
            [230, 170, 130],
            [90, 80, 210],
            [210, 120, 210],
            [220, 120, 90],
            [170, 50, 40],
            [255, 255, 255],
        ], dtype=np.uint8)

        panel_width = 420
        image_height = 380
        panel_height = 430
        gap = 12

        panels = []
        for label, axis, arr, ct_arr in slices:
            arr = self._orient_preview_plane(axis, arr)
            if ct_arr is not None:
                ct_arr = self._orient_preview_plane(axis, ct_arr)
            h, w = arr.shape
            colored = np.zeros((h, w, 3), dtype=np.uint8)
            labels = [v for v in np.unique(arr) if v != 0]
            for value in labels:
                palette_index = (int(value) - 1) % len(palette)
                colored[arr == value] = palette[palette_index]

            if ct_arr is not None:
                base_img = self._normalize_slice(ct_arr, ct_window).convert("RGB")
                if base_img.size != (w, h):
                    base_img = base_img.resize((w, h), Image.Resampling.BILINEAR)
                base = np.asarray(base_img, dtype=np.uint8)
                overlay = base.copy()
                mask_pixels = arr != 0
                overlay[mask_pixels] = (
                    0.5 * base[mask_pixels] + 0.5 * colored[mask_pixels]
                ).astype(np.uint8)
                img = Image.fromarray(overlay, mode="RGB").convert("RGBA")
            else:
                alpha = np.where(arr != 0, 230, 0).astype(np.uint8)
                rgba = np.dstack([colored, alpha])
                img = Image.fromarray(rgba, mode="RGBA")
            img = self._resize_to_physical_aspect(img, axis, display_spacing)
            img.convert("RGB").save(self._plane_preview_path(preview_path, axis))
            img.thumbnail((panel_width - 24, image_height))

            canvas = Image.new("RGBA", (panel_width, panel_height), "#0b0f19")
            left = (panel_width - img.width) // 2
            top = (image_height - img.height) // 2
            canvas.alpha_composite(img, (left, top))
            draw = ImageDraw.Draw(canvas)
            draw.text((14, image_height + 18), f"{label} mask", fill="#e5e7eb")
            panels.append(canvas.convert("RGB"))

        combined = Image.new("RGB", (panel_width * 3 + gap * 2, panel_height), "#111827")
        for index, panel in enumerate(panels):
            combined.paste(panel, (index * (panel_width + gap), 0))
        combined.save(preview_path)
        return True

    def _find_reference_ct_volume(self, patient_id: str, phase: str) -> Any:
        import SimpleITK as sitk

        meta_path = self._ct_meta_path(patient_id, phase)
        if not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        file_name = meta.get("file_name")
        if not file_name:
            return None
        ct_path = self._ct_dir(patient_id, phase) / Path(file_name).name
        if not ct_path.is_file() or self._ct_ext(ct_path.name) == ".zip":
            return None
        try:
            image = sitk.ReadImage(str(ct_path))
            volume = sitk.GetArrayFromImage(image)
            if volume.ndim == 4:
                volume = volume[0]
            if volume.ndim == 2:
                import numpy as np
                volume = volume[np.newaxis, :, :]
            return volume, image.GetSpacing()
        except Exception:
            return None
        return None

    @staticmethod
    def _clean_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(data)
        for key, value in list(cleaned.items()):
            if isinstance(value, str):
                value = value.strip()
                cleaned[key] = value or None
        if cleaned.get("name") is not None:
            cleaned["name"] = str(cleaned["name"]).strip()
        return cleaned

    @handle_service_exception
    async def create_patient(self, payload: Dict[str, Any]):
        data = self._clean_payload(payload)
        data["patient_id"] = self._validate_patient_id(data.get("patient_id", ""))
        if not data.get("name"):
            raise ValidationError(detail="name is required", field="name")

        try:
            patient = await self.mapper.create_patient(data)
        except asyncpg.UniqueViolationError:
            raise ConflictError(
                detail="patient_id already exists",
                context={"patient_id": data["patient_id"]},
            )
        except Exception as exc:
            raise DatabaseError(
                detail="failed to create patient",
                operation="create_patient",
                context={"error": str(exc)},
            )

        patient_dir = self._patient_dir(patient.patient_id)
        try:
            patient_dir.mkdir(parents=True, exist_ok=False)
        except Exception as exc:
            await self.mapper.delete_patient(patient.patient_id)
            raise DatabaseError(
                detail="failed to create patient data directory",
                operation="create_patient_directory",
                context={"patient_id": patient.patient_id, "path": str(patient_dir), "error": str(exc)},
            )
        return patient

    @handle_service_exception
    async def list_patients(self, keyword: Optional[str], page: int, size: int) -> Dict[str, Any]:
        if page < 1:
            raise ValidationError(detail="page must be greater than 0", field="page")
        if size < 1 or size > 200:
            raise ValidationError(detail="size must be between 1 and 200", field="size")

        clean_keyword = keyword.strip() if keyword else None
        total = await self.mapper.count_patients(clean_keyword)
        items = await self.mapper.list_patients(clean_keyword, size, (page - 1) * size)
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
        }

    @handle_service_exception
    async def get_patient(self, patient_id: str):
        clean_id = self._validate_patient_id(patient_id)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)
        return patient

    @handle_service_exception
    async def get_ct_status(self, patient_id: str, phase: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        meta_path = self._ct_meta_path(clean_id, clean_phase)
        if not meta_path.is_file():
            return self._empty_ct_status(clean_phase)
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return self._empty_ct_status(clean_phase)
        return {
            **self._empty_ct_status(clean_phase),
            **{k: data.get(k) for k in ("phase", "status", "file_name", "file_size", "uploaded_at", "preview_url", "preview_planes")},
        }

    @handle_service_exception
    async def get_mask_status(self, patient_id: str, mask_type: str, phase: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        meta_path = self._mask_meta_path(clean_id, clean_type, clean_phase)
        if not meta_path.is_file():
            return self._empty_mask_status(clean_type, clean_phase)
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return self._empty_mask_status(clean_type, clean_phase)
        return {
            **self._empty_mask_status(clean_type, clean_phase),
            **{k: data.get(k) for k in ("mask_type", "phase", "status", "file_name", "file_size", "uploaded_at", "preview_url", "preview_planes")},
        }

    @handle_service_exception
    async def upload_ct_file(self, patient_id: str, phase: str, ct_file: UploadFile) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        file_name = self._safe_filename(ct_file.filename or "")
        ext = self._ct_ext(file_name)
        if ext not in CT_EXTENSIONS:
            raise ValidationError(
                detail="CT file only supports .nii, .nii.gz, .dcm, or .zip",
                field="ct_file",
                context={"filename": file_name},
            )

        ct_dir = self._ct_dir(clean_id, clean_phase)
        if ct_dir.exists():
            shutil.rmtree(ct_dir)
        ct_dir.mkdir(parents=True, exist_ok=True)

        file_path = ct_dir / file_name
        size = 0
        try:
            with file_path.open("wb") as out_file:
                while True:
                    chunk = await ct_file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    out_file.write(chunk)
        finally:
            await ct_file.close()

        if size <= 0:
            shutil.rmtree(ct_dir, ignore_errors=True)
            raise ValidationError(detail="ct_file is empty", field="ct_file")

        meta = {
            "phase": clean_phase,
            "status": "ready",
            "file_name": file_name,
            "file_size": size,
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "preview_url": None,
            "preview_planes": None,
        }
        preview_path = ct_dir / "preview.png"
        try:
            if self._make_ct_preview(file_path, preview_path):
                meta["preview_url"] = f"/patients/{clean_id}/ct/{clean_phase}/preview"
                meta["preview_planes"] = {
                    plane: f"/patients/{clean_id}/ct/{clean_phase}/preview/{plane}"
                    for plane in ("axial", "coronal", "sagittal")
                }
        except Exception as exc:
            logger.exception(
                "Failed to generate CT preview: patient=%s phase=%s file=%s error=%s",
                clean_id,
                clean_phase,
                file_name,
                exc,
            )
            meta["preview_url"] = None

        self._ct_meta_path(clean_id, clean_phase).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return meta

    @handle_service_exception
    async def upload_mask_file(self, patient_id: str, mask_type: str, phase: str, mask_file: UploadFile) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        file_name = self._safe_filename(mask_file.filename or "", field="mask_file")
        ext = self._ct_ext(file_name)
        if ext not in MASK_EXTENSIONS:
            raise ValidationError(
                detail="Mask file only supports .nii or .nii.gz",
                field="mask_file",
                context={"filename": file_name},
            )

        mask_dir = self._mask_dir(clean_id, clean_type, clean_phase)
        if mask_dir.exists():
            shutil.rmtree(mask_dir)
        mask_dir.mkdir(parents=True, exist_ok=True)

        file_path = mask_dir / file_name
        size = 0
        try:
            with file_path.open("wb") as out_file:
                while True:
                    chunk = await mask_file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    out_file.write(chunk)
        finally:
            await mask_file.close()

        if size <= 0:
            shutil.rmtree(mask_dir, ignore_errors=True)
            raise ValidationError(detail="mask_file is empty", field="mask_file")

        meta = {
            "mask_type": clean_type,
            "phase": clean_phase,
            "status": "ready",
            "file_name": file_name,
            "file_size": size,
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "preview_url": None,
            "preview_planes": None,
        }
        preview_path = mask_dir / "preview.png"
        try:
            if self._make_mask_preview(file_path, preview_path, clean_id, clean_phase):
                meta["preview_url"] = f"/patients/{clean_id}/mask/{clean_type}/{clean_phase}/preview"
                meta["preview_planes"] = {
                    plane: f"/patients/{clean_id}/mask/{clean_type}/{clean_phase}/preview/{plane}"
                    for plane in ("axial", "coronal", "sagittal")
                }
        except ValidationError:
            shutil.rmtree(mask_dir, ignore_errors=True)
            raise
        except Exception as exc:
            logger.exception(
                "Failed to generate mask preview: patient=%s mask_type=%s phase=%s file=%s error=%s",
                clean_id,
                clean_type,
                clean_phase,
                file_name,
                exc,
            )
            meta["preview_url"] = None

        self._mask_meta_path(clean_id, clean_type, clean_phase).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return meta

    @handle_service_exception
    async def get_ct_preview_path(self, patient_id: str, phase: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        preview_path = self._ct_dir(clean_id, clean_phase) / "preview.png"
        if not preview_path.is_file():
            raise NotFoundError(resource_type="ct_preview", resource_id=f"{clean_id}:{clean_phase}")
        return preview_path

    @handle_service_exception
    async def get_ct_preview_plane_path(self, patient_id: str, phase: str, plane: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        clean_plane = self._validate_preview_plane(plane)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        preview_path = self._plane_preview_path(self._ct_dir(clean_id, clean_phase) / "preview.png", clean_plane)
        if not preview_path.is_file():
            raise NotFoundError(resource_type="ct_preview", resource_id=f"{clean_id}:{clean_phase}:{clean_plane}")
        return preview_path

    @handle_service_exception
    async def get_mask_preview_path(self, patient_id: str, mask_type: str, phase: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        preview_path = self._mask_dir(clean_id, clean_type, clean_phase) / "preview.png"
        if not preview_path.is_file():
            raise NotFoundError(resource_type="mask_preview", resource_id=f"{clean_id}:{clean_type}:{clean_phase}")
        return preview_path

    @handle_service_exception
    async def get_mask_preview_plane_path(self, patient_id: str, mask_type: str, phase: str, plane: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        clean_plane = self._validate_preview_plane(plane)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        preview_path = self._plane_preview_path(self._mask_dir(clean_id, clean_type, clean_phase) / "preview.png", clean_plane)
        if not preview_path.is_file():
            raise NotFoundError(resource_type="mask_preview", resource_id=f"{clean_id}:{clean_type}:{clean_phase}:{clean_plane}")
        return preview_path

    @handle_service_exception
    async def delete_ct_data(self, patient_id: str, phase: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        ct_dir = self._ct_dir(clean_id, clean_phase)
        if ct_dir.exists():
            shutil.rmtree(ct_dir)
        return self._empty_ct_status(clean_phase)

    @handle_service_exception
    async def delete_mask_data(self, patient_id: str, mask_type: str, phase: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        mask_dir = self._mask_dir(clean_id, clean_type, clean_phase)
        if mask_dir.exists():
            shutil.rmtree(mask_dir)
        return self._empty_mask_status(clean_type, clean_phase)

    @handle_service_exception
    async def update_patient(self, patient_id: str, payload: Dict[str, Any]):
        clean_id = self._validate_patient_id(patient_id)
        data = self._clean_payload(payload)
        if "name" in data and not data["name"]:
            raise ValidationError(detail="name cannot be empty", field="name")
        patient = await self.mapper.update_patient(clean_id, data)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)
        return patient

    @handle_service_exception
    async def delete_patient(self, patient_id: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        existing = await self.mapper.get_patient(clean_id)
        if not existing:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        deleted = await self.mapper.delete_patient(clean_id)
        if not deleted:
            raise DatabaseError(
                detail="failed to delete patient",
                operation="delete_patient",
                context={"patient_id": clean_id},
            )

        patient_dir = self._patient_dir(clean_id)
        if patient_dir.exists():
            shutil.rmtree(patient_dir)

        return {"patient_id": clean_id, "directory_deleted": not patient_dir.exists()}
