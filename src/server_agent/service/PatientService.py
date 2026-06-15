import re
import asyncio
import csv
import json
import logging
import shutil
import threading
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import asyncpg
from fastapi import UploadFile

from src.server_agent.exceptions import ConflictError, DatabaseError, NotFoundError, ValidationError, handle_service_exception
from src.server_agent.mapper.PatientMapper import PatientMapper
from src.server_agent.mapper.paths import in_data


logger = logging.getLogger(__name__)
PATIENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
PATIENT_DATA_ROOT = in_data("patient")
PATIENT_INFO_FILENAME = "patient_info.json"
LEGACY_PATIENT_INFO_FILENAMES = ("info.json", "patient.json")
CT_PHASES = {"pre", "post"}
CT_EXTENSIONS = {".nii", ".nii.gz", ".dcm", ".zip"}
PREVIEW_PLANES = {"axial", "coronal", "sagittal"}
MASK_TYPES = {
    "body-composition": "body_composition",
    "spine": "spine",
    "lung": "lung",
    "tumor": "tumor",
}
MASK_EXTENSIONS = {".nii", ".nii.gz"}
BODY_COMPOSITION_METRIC_EXTENSIONS = {".csv", ".xlsx"}
BODY_COMPOSITION_TYPE_EXTENSIONS = {".json"}
VOLUME_CACHE: Dict[str, Dict[str, Any]] = {}
SLICE_CACHE_WARMUPS: set[str] = set()
SLICE_CACHE_WARMUP_LOCK = threading.Lock()


class PatientService:
    """Business service for the global patient dataset."""

    def __init__(self, mapper: Optional[PatientMapper] = None):
        self.mapper = mapper or PatientMapper()

    async def init(self) -> None:
        await self.mapper.init()
        PATIENT_DATA_ROOT.mkdir(parents=True, exist_ok=True)
        await self.sync_patient_info_files()

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
    def _patient_info_path(patient_id: str) -> Path:
        return PatientService._patient_dir(patient_id) / PATIENT_INFO_FILENAME

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
                detail="mask_type must be body-composition, spine, lung, or tumor",
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

    def _body_composition_metrics_dir(self, patient_id: str, phase: str) -> Path:
        patient_dir = self._patient_dir(patient_id)
        metrics_dir = (patient_dir / "body_composition_metrics" / phase / "table").resolve()
        try:
            metrics_dir.relative_to(patient_dir)
        except ValueError:
            raise ValidationError(detail="invalid body composition metrics path", field="patient_id")
        return metrics_dir

    def _body_composition_type_dir(self, patient_id: str) -> Path:
        patient_dir = self._patient_dir(patient_id)
        type_dir = (patient_dir / "body_composition_type" / "classification").resolve()
        try:
            type_dir.relative_to(patient_dir)
        except ValueError:
            raise ValidationError(detail="invalid body composition type path", field="patient_id")
        return type_dir

    def _standard_result_file_path(self, patient_id: str, file_path: str) -> Path:
        patient_dir = self._patient_dir(patient_id)
        if not file_path or Path(file_path).is_absolute():
            raise ValidationError(detail="invalid result file path", field="file_path")
        target = (patient_dir / file_path).resolve()
        try:
            relative = target.relative_to(patient_dir)
        except ValueError:
            raise ValidationError(detail="invalid result file path", field="file_path")
        if not relative.parts or relative.parts[0] not in {"body_composition_metrics", "body_composition_type"}:
            raise ValidationError(detail="unsupported result file path", field="file_path")
        if not target.is_file():
            raise NotFoundError(resource_type="patient_result_file", resource_id=file_path)
        return target

    def _empty_ct_status(self, phase: str) -> Dict[str, Any]:
        return {
            "phase": phase,
            "status": "empty",
            "file_name": None,
            "file_size": None,
            "uploaded_at": None,
            "preview_updated_at": None,
            "preview_url": None,
            "preview_planes": None,
            "display_window": None,
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

    @staticmethod
    def _report_dir(patient_id: str) -> Path:
        return PatientService._patient_dir(patient_id) / "reports"

    def _read_cached_volume(self, image_path: Path) -> Optional[Dict[str, Any]]:
        import numpy as np
        import SimpleITK as sitk

        if not image_path.is_file() or self._ct_ext(image_path.name) == ".zip":
            return None
        stat = image_path.stat()
        cache_key = str(image_path)
        cached = VOLUME_CACHE.get(cache_key)
        if cached and cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size:
            return cached
        image = sitk.ReadImage(str(image_path))
        volume = sitk.GetArrayFromImage(image)
        if volume.ndim == 4:
            volume = volume[0]
        if volume.ndim == 2:
            volume = volume[np.newaxis, :, :]
        if volume.ndim != 3:
            return None
        cached = {
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "volume": volume,
            "spacing": image.GetSpacing(),
            "window": self._ct_display_window(volume),
        }
        VOLUME_CACHE[cache_key] = cached
        return cached

    @staticmethod
    def _slice_count(shape, plane: str) -> int:
        if plane == "axial":
            return int(shape[0])
        if plane == "coronal":
            return int(shape[1])
        return int(shape[2])

    @staticmethod
    def _slice_plane(volume, plane: str, index: int):
        if plane == "axial":
            return volume[index, :, :]
        if plane == "coronal":
            return volume[:, index, :]
        return volume[:, :, index]

    def _mask_palette(self):
        import numpy as np

        return np.array([
            [255, 0, 0],
            [0, 255, 0],
            [0, 0, 255],
            [255, 255, 0],
            [0, 255, 255],
            [255, 0, 255],
            [255, 239, 213],
            [0, 0, 205],
            [205, 133, 63],
            [210, 180, 140],
            [102, 205, 170],
            [0, 0, 128],
            [0, 139, 139],
            [46, 139, 87],
            [255, 228, 225],
            [106, 90, 205],
            [221, 160, 221],
            [233, 150, 122],
            [165, 42, 42],
            [255, 250, 250],
        ], dtype=np.uint8)

    def _render_slice_png(self, ct_path: Path, output_path: Path, plane: str, index: int, mask_path: Optional[Path] = None) -> Path:
        import numpy as np
        from PIL import Image

        ct_data = self._read_cached_volume(ct_path)
        if not ct_data:
            raise NotFoundError(resource_type="ct_file", resource_id=ct_path.name)
        ct_volume = ct_data["volume"]
        plane_count = self._slice_count(ct_volume.shape, plane)
        clean_index = max(0, min(int(index), plane_count - 1))
        ct_arr = self._orient_preview_plane(plane, self._slice_plane(ct_volume, plane, clean_index))
        base_img = self._normalize_slice(ct_arr, ct_data["window"]).convert("RGB")

        if mask_path is not None and mask_path.is_file():
            mask_data = self._read_cached_volume(mask_path)
            if mask_data:
                mask_volume = mask_data["volume"]
                mask_index = max(0, min(
                    self._slice_count(mask_volume.shape, plane) - 1,
                    int(round(clean_index * (self._slice_count(mask_volume.shape, plane) - 1) / max(1, plane_count - 1))),
                ))
                mask_arr = self._orient_preview_plane(plane, self._slice_plane(mask_volume, plane, mask_index))
                colored = np.zeros((*mask_arr.shape, 3), dtype=np.uint8)
                palette = self._mask_palette()
                for value in [v for v in np.unique(mask_arr) if v != 0]:
                    colored[mask_arr == value] = palette[(int(value) - 1) % len(palette)]
                color_img = Image.fromarray(colored, mode="RGB")
                mask_alpha = Image.fromarray(np.where(mask_arr != 0, 128, 0).astype(np.uint8), mode="L")
                if color_img.size != base_img.size:
                    color_img = color_img.resize(base_img.size, Image.Resampling.NEAREST)
                    mask_alpha = mask_alpha.resize(base_img.size, Image.Resampling.NEAREST)
                base_img = Image.composite(color_img, base_img, mask_alpha)

        base_img = self._resize_to_physical_aspect(base_img, plane, ct_data["spacing"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(f".{output_path.name}.{threading.get_ident()}.tmp")
        base_img.save(temp_path, format="PNG")
        temp_path.replace(output_path)
        return output_path

    def _slice_cache_path(self, base_dir: Path, plane: str, index: int, overlay: bool = False) -> Path:
        prefix = "overlay" if overlay else "ct"
        return base_dir / "slice_cache" / f"{prefix}_{plane}_{index}.png"

    @staticmethod
    def _volume_cache_path(base_dir: Path, name: str) -> Path:
        return base_dir / "volume_cache" / name

    @staticmethod
    def _write_array_atomic(array, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(f".{output_path.name}.{threading.get_ident()}.tmp")
        array.tofile(temp_path)
        temp_path.replace(output_path)
        return output_path

    def _ct_uint8_volume_path(self, ct_path: Path, output_path: Path) -> Path:
        import numpy as np

        ct_data = self._read_cached_volume(ct_path)
        if not ct_data:
            raise NotFoundError(resource_type="ct_file", resource_id=ct_path.name)
        volume = np.asarray(ct_data["volume"], dtype=np.float32)
        expected_size = int(volume.size)
        if output_path.is_file() and output_path.stat().st_size == expected_size:
            return output_path
        lo, hi = ct_data["window"]
        if hi <= lo:
            normalized = np.zeros(volume.shape, dtype=np.uint8)
        else:
            normalized = np.clip((volume - lo) / (hi - lo), 0, 1)
            normalized = (normalized * 255).astype(np.uint8)
        return self._write_array_atomic(np.ascontiguousarray(normalized), output_path)

    def _mask_uint8_volume_path(self, mask_path: Path, output_path: Path) -> Path:
        import numpy as np

        mask_data = self._read_cached_volume(mask_path)
        if not mask_data:
            raise NotFoundError(resource_type="mask_file", resource_id=mask_path.name)
        volume = np.asarray(mask_data["volume"])
        expected_size = int(volume.size)
        if output_path.is_file() and output_path.stat().st_size == expected_size:
            return output_path
        labels = np.clip(np.rint(volume), 0, 255).astype(np.uint8)
        return self._write_array_atomic(np.ascontiguousarray(labels), output_path)

    @staticmethod
    def _center_first_indices(count: int):
        if count <= 0:
            return
        center = count // 2
        yield center
        for offset in range(1, max(center + 1, count - center)):
            left = center - offset
            right = center + offset
            if left >= 0:
                yield left
            if right < count:
                yield right

    @staticmethod
    def _source_matches(path: Optional[Path], mtime: Optional[float], size: Optional[int]) -> bool:
        if path is None:
            return True
        if not path.is_file():
            return False
        stat = path.stat()
        return stat.st_mtime == mtime and stat.st_size == size

    def _warm_slice_cache(
        self,
        ct_path: Path,
        base_dir: Path,
        overlay: bool = False,
        mask_path: Optional[Path] = None,
        ct_mtime: Optional[float] = None,
        ct_size: Optional[int] = None,
        mask_mtime: Optional[float] = None,
        mask_size: Optional[int] = None,
    ) -> None:
        if not self._source_matches(ct_path, ct_mtime, ct_size) or not self._source_matches(mask_path, mask_mtime, mask_size):
            return
        ct_data = self._read_cached_volume(ct_path)
        if not ct_data:
            return
        shape = ct_data["volume"].shape
        for plane in ("axial", "coronal", "sagittal"):
            count = self._slice_count(shape, plane)
            for index in self._center_first_indices(count):
                if not self._source_matches(ct_path, ct_mtime, ct_size) or not self._source_matches(mask_path, mask_mtime, mask_size):
                    return
                slice_path = self._slice_cache_path(base_dir, plane, index, overlay=overlay)
                if slice_path.is_file():
                    continue
                self._render_slice_png(ct_path, slice_path, plane, index, mask_path=mask_path)

    def _run_slice_cache_warmup(
        self,
        key: str,
        ct_path: Path,
        base_dir: Path,
        overlay: bool = False,
        mask_path: Optional[Path] = None,
        ct_mtime: Optional[float] = None,
        ct_size: Optional[int] = None,
        mask_mtime: Optional[float] = None,
        mask_size: Optional[int] = None,
    ) -> None:
        try:
            self._warm_slice_cache(
                ct_path,
                base_dir,
                overlay=overlay,
                mask_path=mask_path,
                ct_mtime=ct_mtime,
                ct_size=ct_size,
                mask_mtime=mask_mtime,
                mask_size=mask_size,
            )
        except Exception as exc:
            logger.exception("Failed to warm slice cache: key=%s error=%s", key, exc)
        finally:
            with SLICE_CACHE_WARMUP_LOCK:
                SLICE_CACHE_WARMUPS.discard(key)

    def _schedule_slice_cache_warmup(self, key: str, ct_path: Path, base_dir: Path, overlay: bool = False, mask_path: Optional[Path] = None) -> None:
        ct_stat = ct_path.stat()
        mask_stat = mask_path.stat() if mask_path is not None and mask_path.is_file() else None
        with SLICE_CACHE_WARMUP_LOCK:
            if key in SLICE_CACHE_WARMUPS:
                return
            SLICE_CACHE_WARMUPS.add(key)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(asyncio.to_thread(
                self._run_slice_cache_warmup,
                key,
                ct_path,
                base_dir,
                overlay,
                mask_path,
                ct_stat.st_mtime,
                ct_stat.st_size,
                mask_stat.st_mtime if mask_stat else None,
                mask_stat.st_size if mask_stat else None,
            ))
        except RuntimeError:
            self._run_slice_cache_warmup(
                key,
                ct_path,
                base_dir,
                overlay=overlay,
                mask_path=mask_path,
                ct_mtime=ct_stat.st_mtime,
                ct_size=ct_stat.st_size,
                mask_mtime=mask_stat.st_mtime if mask_stat else None,
                mask_size=mask_stat.st_size if mask_stat else None,
            )

    @staticmethod
    def _uploaded_file_from_meta(meta_path: Path, base_dir: Path) -> Optional[Path]:
        if not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            file_name = meta.get("file_name")
        except Exception:
            return None
        if not file_name:
            return None
        file_path = base_dir / Path(file_name).name
        return file_path if file_path.is_file() else None

    def _schedule_related_mask_warmups(self, patient_id: str, phase: str, ct_path: Path) -> None:
        for mask_type in MASK_TYPES:
            mask_dir = self._mask_dir(patient_id, mask_type, phase)
            mask_path = self._uploaded_file_from_meta(self._mask_meta_path(patient_id, mask_type, phase), mask_dir)
            if not mask_path:
                continue
            key = f"mask:{patient_id}:{mask_type}:{phase}:{ct_path.stat().st_mtime}:{mask_path.stat().st_mtime}"
            self._schedule_slice_cache_warmup(key, ct_path, mask_dir, overlay=True, mask_path=mask_path)

    @staticmethod
    def _font(size: int, bold: bool = False):
        from PIL import ImageFont

        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
        for path in candidates:
            if Path(path).is_file():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    @staticmethod
    def _draw_text(draw, xy, text: str, font, fill="#111827", anchor=None):
        safe_text = str(text or "-")
        try:
            draw.text(xy, safe_text, font=font, fill=fill, anchor=anchor)
        except UnicodeEncodeError:
            draw.text(xy, safe_text.encode("ascii", "ignore").decode("ascii") or "-", font=font, fill=fill, anchor=anchor)

    @staticmethod
    def _text_width(draw, text: str, font) -> int:
        bbox = draw.textbbox((0, 0), str(text), font=font)
        return int(bbox[2] - bbox[0])

    def _wrap_text(self, draw, text: str, font, max_width: int):
        words = str(text or "-").split()
        if not words:
            return ["-"]
        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if self._text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _collect_preview_images(self, base_preview: Path, label: str):
        images = []
        for plane in ("axial", "coronal", "sagittal"):
            plane_path = self._plane_preview_path(base_preview, plane)
            if plane_path.is_file():
                images.append((f"{label} {plane.title()}", plane_path))
        if not images and base_preview.is_file():
            images.append((label, base_preview))
        return images

    def _report_patient_fields(self, patient) -> list[tuple[str, str]]:
        fields = [
            ("Name", patient.name),
            ("Examination ID", patient.patient_id),
            ("Phone number", patient.phone),
        ]
        return [(label, str(value)) for label, value in fields if value not in (None, "")]

    def _report_clinical_fields(self, patient) -> list[tuple[str, str]]:
        fields = [
            ("Sex", patient.sex),
            ("Age", patient.age),
            ("Height", f"{patient.height_cm:g} cm" if patient.height_cm is not None else None),
            ("Smoking status", patient.smoking_status),
            ("Pathology type", patient.pathology_type),
            ("PD-L1 status", patient.pd_l1_status),
        ]
        return [(label, str(value)) for label, value in fields if value not in (None, "")]

    def _draw_section_label(self, draw, x: int, y: int, text: str):
        font = self._font(18, bold=True)
        width = max(180, self._text_width(draw, text, font) + 52)
        draw.rounded_rectangle((x, y, x + width, y + 34), radius=17, outline="#111827", width=2, fill="#ffffff")
        self._draw_text(draw, (x + width / 2, y + 17), text, font, anchor="mm")
        return y + 54

    def _draw_info_grid(self, draw, x: int, y: int, width: int, fields: list[tuple[str, str]], columns: int):
        if not fields:
            return y
        font_label = self._font(16, bold=True)
        font_value = self._font(16)
        gap = 2
        cell_w = (width - gap * (columns - 1)) // columns
        row_h = 68
        for index, (label, value) in enumerate(fields):
            row = index // columns
            col = index % columns
            left = x + col * (cell_w + gap)
            top = y + row * (row_h + gap)
            draw.rectangle((left, top, left + cell_w, top + row_h), fill="#eef0f2")
            self._draw_text(draw, (left + cell_w / 2, top + 20), f"{label}:", font_label, anchor="mm")
            lines = self._wrap_text(draw, value, font_value, cell_w - 16)[:2]
            first_y = top + 43 if len(lines) == 1 else top + 37
            for line_index, line in enumerate(lines):
                self._draw_text(draw, (left + cell_w / 2, first_y + line_index * 18), line, font_value, anchor="mm")
        rows = (len(fields) + columns - 1) // columns
        return y + rows * row_h + (rows - 1) * gap + 38

    def _draw_image_grid(self, page, draw, x: int, y: int, width: int, images: list[tuple[str, Path]], columns: int = 3):
        from PIL import Image

        if not images:
            return y
        font = self._font(13)
        gap = 20
        cell_w = (width - gap * (columns - 1)) // columns
        img_h = 190
        caption_h = 24
        for index, (label, path) in enumerate(images):
            row = index // columns
            col = index % columns
            left = x + col * (cell_w + gap)
            top = y + row * (img_h + caption_h + 28)
            try:
                img = Image.open(path).convert("RGB")
            except Exception:
                continue
            img.thumbnail((cell_w, img_h), Image.Resampling.LANCZOS)
            box_left = left + (cell_w - img.width) // 2
            box_top = top + (img_h - img.height) // 2
            page.paste(img, (box_left, box_top))
            self._draw_text(draw, (left + cell_w / 2, top + img_h + 14), label, font, fill="#374151", anchor="mm")
        rows = (len(images) + columns - 1) // columns
        return y + rows * (img_h + caption_h + 28) + 20

    def _build_report_sections(self, patient_id: str):
        sections = []
        ct_images = []
        for phase in ("pre", "post"):
            ct_preview = self._ct_dir(patient_id, phase) / "preview.png"
            ct_images.extend(self._collect_preview_images(ct_preview, f"{phase.upper()} CT"))
        if ct_images:
            sections.append(("CT examination", ct_images))

        body_images = []
        spine_images = []
        lung_images = []
        tumor_images = []
        for phase in ("pre", "post"):
            body_preview = self._mask_dir(patient_id, "body-composition", phase) / "preview.png"
            body_images.extend(self._collect_preview_images(body_preview, f"{phase.upper()} Body composition"))
            spine_preview = self._mask_dir(patient_id, "spine", phase) / "preview.png"
            spine_images.extend(self._collect_preview_images(spine_preview, f"{phase.upper()} Spine"))
            lung_preview = self._mask_dir(patient_id, "lung", phase) / "preview.png"
            lung_images.extend(self._collect_preview_images(lung_preview, f"{phase.upper()} Lung"))
            tumor_preview = self._mask_dir(patient_id, "tumor", phase) / "preview.png"
            tumor_images.extend(self._collect_preview_images(tumor_preview, f"{phase.upper()} Tumor"))
        if body_images:
            sections.append(("Body composition", body_images))
        if spine_images:
            sections.append(("Spine", spine_images))
        if lung_images:
            sections.append(("Lung", lung_images))
        if tumor_images:
            sections.append(("Tumor", tumor_images))
        return sections

    def _generate_patient_report_pdf(self, patient, output_path: Path) -> Path:
        from PIL import Image, ImageDraw

        page_w, page_h = 1240, 1754
        margin_x = 76
        content_w = page_w - margin_x * 2
        pages = []
        page = Image.new("RGB", (page_w, page_h), "#f5fbfc")
        draw = ImageDraw.Draw(page)

        title_font = self._font(34, bold=True)
        subtitle_font = self._font(14)
        draw.rectangle((0, 0, page_w, 150), fill="#ffffff")
        self._draw_text(draw, (page_w / 2, 64), "Human metabolic health research", title_font, anchor="mm")
        self._draw_text(draw, (page_w / 2, 106), "examination CT report", title_font, anchor="mm")
        draw.line((0, 150, page_w, 150), fill="#111827", width=2)
        self._draw_text(draw, (page_w - margin_x, 132), datetime.now().strftime("%Y-%m-%d %H:%M"), subtitle_font, fill="#6b7280", anchor="ra")

        y = 210
        basic_fields = self._report_patient_fields(patient)
        if basic_fields:
            y = self._draw_section_label(draw, 30, y, "Basic information")
            y = self._draw_info_grid(draw, margin_x, y, content_w, basic_fields, min(3, max(1, len(basic_fields))))

        clinical_fields = self._report_clinical_fields(patient)
        if clinical_fields:
            y = self._draw_section_label(draw, 30, y, "Clinical information")
            y = self._draw_info_grid(draw, margin_x, y, content_w, clinical_fields, min(6, max(1, len(clinical_fields))))

        for title, images in self._build_report_sections(patient.patient_id):
            required_rows = (len(images) + 2) // 3
            required_height = 58 + required_rows * 242 + 30
            if y + required_height > page_h - 80:
                pages.append(page)
                page = Image.new("RGB", (page_w, page_h), "#f5fbfc")
                draw = ImageDraw.Draw(page)
                y = 80
            y = self._draw_section_label(draw, 30, y, title)
            y = self._draw_image_grid(page, draw, margin_x, y, content_w, images, columns=3)

        if y < page_h - 120:
            note_font = self._font(13)
            self._draw_text(draw, (margin_x, page_h - 56), "Generated from uploaded patient data. Missing data sections are omitted.", note_font, fill="#6b7280")
        pages.append(page)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        first, rest = pages[0], pages[1:]
        first.save(output_path, "PDF", resolution=150.0, save_all=True, append_images=rest)
        return output_path

    def _make_ct_preview(self, ct_path: Path, preview_path: Path, tumor_mask_path: Optional[Path] = None) -> bool:
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
        center = {"axial": z // 2, "coronal": y // 2, "sagittal": x // 2}
        focus_source = "center"

        if tumor_mask_path is not None and tumor_mask_path.is_file():
            try:
                mask_image = sitk.ReadImage(str(tumor_mask_path))
                mask_volume = sitk.GetArrayFromImage(mask_image)
                if mask_volume.ndim == 4:
                    mask_volume = mask_volume[0]
                if mask_volume.ndim == 2:
                    mask_volume = mask_volume[np.newaxis, :, :]
                mask = np.asarray(mask_volume)
                nonzero = np.argwhere(mask != 0)
                if mask.ndim == 3 and len(nonzero) > 0:
                    mask_center = np.rint(nonzero.mean(axis=0)).astype(int)

                    def map_index(index: int, source_size: int, target_size: int) -> int:
                        if source_size <= 1 or target_size <= 1:
                            return 0
                        return int(round(index * (target_size - 1) / (source_size - 1)))

                    center = {
                        "axial": max(0, min(z - 1, map_index(int(mask_center[0]), mask.shape[0], z))),
                        "coronal": max(0, min(y - 1, map_index(int(mask_center[1]), mask.shape[1], y))),
                        "sagittal": max(0, min(x - 1, map_index(int(mask_center[2]), mask.shape[2], x))),
                    }
                    focus_source = "tumor"
            except Exception as exc:
                logger.warning("Failed to use tumor mask for CT preview focus: path=%s error=%s", tumor_mask_path, exc)

        slices = [
            ("Axial", "axial", volume[center["axial"], :, :]),
            ("Coronal", "coronal", volume[:, center["coronal"], :]),
            ("Sagittal", "sagittal", volume[:, :, center["sagittal"]]),
        ]
        panel_width = 420
        image_height = 380
        panel_height = 430
        gap = 12

        panels = []
        for label, axis, arr in slices:
            oriented_arr = self._orient_preview_plane(axis, arr)
            img = self._normalize_slice(oriented_arr, ct_window).convert("RGB")
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
        return {
            "window": {"min": ct_window[0], "max": ct_window[1]},
            "shape": {"x": x, "y": y, "z": z},
            "spacing": {"x": spacing[0], "y": spacing[1], "z": spacing[2]},
            "slice_counts": {"axial": z, "coronal": y, "sagittal": x},
            "center": center,
            "focus_source": focus_source,
        }

    def _tumor_mask_file_path(self, patient_id: str, phase: str) -> Optional[Path]:
        tumor_dir = self._mask_dir(patient_id, "tumor", phase)
        return self._uploaded_file_from_meta(self._mask_meta_path(patient_id, "tumor", phase), tumor_dir)

    def _write_ct_preview_metadata(self, patient_id: str, phase: str, ct_path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
        preview_path = self._ct_dir(patient_id, phase) / "preview.png"
        tumor_mask_path = self._tumor_mask_file_path(patient_id, phase)
        preview = self._make_ct_preview(ct_path, preview_path, tumor_mask_path=tumor_mask_path)
        if preview:
            meta["preview_url"] = f"/patients/{patient_id}/ct/{phase}/preview"
            meta["preview_planes"] = {
                plane: f"/patients/{patient_id}/ct/{phase}/preview/{plane}"
                for plane in ("axial", "coronal", "sagittal")
            }
            meta["display_window"] = preview.get("window") if isinstance(preview, dict) else None
            meta["preview_updated_at"] = datetime.now().isoformat(timespec="seconds")
            meta["viewer_metadata"] = {
                key: preview.get(key)
                for key in ("shape", "spacing", "slice_counts", "center", "window", "focus_source")
                if isinstance(preview, dict)
            }
        return meta

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

        def map_index(index: int, source_size: int, target_size: int) -> int:
            if source_size <= 1 or target_size <= 1:
                return 0
            return int(round(index * (target_size - 1) / (source_size - 1)))

        mask_center = np.rint(np.argwhere(nonzero).mean(axis=0)).astype(int)
        z_idx = max(0, min(mask.shape[0] - 1, int(mask_center[0])))
        y_idx = max(0, min(mask.shape[1] - 1, int(mask_center[1])))
        x_idx = max(0, min(mask.shape[2] - 1, int(mask_center[2])))

        if ct_volume is not None:
            ct_z, ct_y, ct_x = ct_volume.shape
            ct_z_idx = max(0, min(ct_z - 1, map_index(z_idx, mask.shape[0], ct_z)))
            ct_y_idx = max(0, min(ct_y - 1, map_index(y_idx, mask.shape[1], ct_y)))
            ct_x_idx = max(0, min(ct_x - 1, map_index(x_idx, mask.shape[2], ct_x)))
            ct_window = self._ct_display_window(ct_volume)
        else:
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

    @staticmethod
    def _patient_file_payload(patient) -> Dict[str, Any]:
        return {
            "name": patient.name,
            "sex": patient.sex,
            "age": patient.age,
            "phone": patient.phone,
            "height_cm": patient.height_cm,
            "smoking_status": patient.smoking_status,
            "pathology_type": patient.pathology_type,
            "pd_l1_status": patient.pd_l1_status,
        }

    @staticmethod
    def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _write_patient_info_file(self, patient) -> Path:
        info_path = self._patient_info_path(patient.patient_id)
        self._write_json_atomic(info_path, self._patient_file_payload(patient))
        return info_path

    @staticmethod
    def _parse_file_datetime(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def _read_patient_info_payload(self, patient_dir: Path) -> Optional[Dict[str, Any]]:
        candidates = [patient_dir / PATIENT_INFO_FILENAME]
        candidates.extend(patient_dir / name for name in LEGACY_PATIENT_INFO_FILENAMES)
        for info_path in candidates:
            if not info_path.is_file():
                continue
            try:
                raw = json.loads(info_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to read patient info file: path=%s error=%s", info_path, exc)
                return None
            patient_data = raw.get("patient") if isinstance(raw, dict) else None
            if not isinstance(patient_data, dict) and isinstance(raw, dict):
                patient_data = raw
            if isinstance(patient_data, dict):
                patient_data = dict(patient_data)
                patient_data["_info_file_mtime"] = datetime.fromtimestamp(info_path.stat().st_mtime).isoformat()
                return patient_data
        return None

    def _patient_payload_from_dir(self, patient_dir: Path) -> Optional[Dict[str, Any]]:
        try:
            clean_id = self._validate_patient_id(patient_dir.name)
        except ValidationError:
            logger.warning("Skipping invalid patient directory name: %s", patient_dir)
            return None

        file_payload = self._read_patient_info_payload(patient_dir) or {}
        data = self._clean_payload(file_payload)
        data["patient_id"] = clean_id
        if not data.get("name"):
            data["name"] = clean_id
        try:
            if data.get("age") is not None:
                data["age"] = int(data["age"])
            if data.get("height_cm") is not None:
                data["height_cm"] = float(data["height_cm"])
        except (TypeError, ValueError):
            logger.warning("Skipping patient info file with invalid numeric fields: %s", patient_dir)
            return None

        allowed_fields = {
            "patient_id",
            "name",
            "sex",
            "age",
            "phone",
            "height_cm",
            "smoking_status",
            "pathology_type",
            "pd_l1_status",
            "_info_file_mtime",
        }
        return {key: value for key, value in data.items() if key in allowed_fields}

    @staticmethod
    def _patient_data_differs(patient, data: Dict[str, Any]) -> bool:
        fields = (
            "name",
            "sex",
            "age",
            "phone",
            "height_cm",
            "smoking_status",
            "pathology_type",
            "pd_l1_status",
        )
        for field in fields:
            if field not in data:
                continue
            current = getattr(patient, field)
            incoming = data[field]
            if field == "height_cm" and current is not None and incoming is not None:
                if float(current) != float(incoming):
                    return True
            elif current != incoming:
                return True
        return False

    @handle_service_exception
    async def sync_patient_info_files(self) -> Dict[str, int]:
        db_patients = await self.mapper.list_all_patients()
        db_by_patient_id = {patient.patient_id: patient for patient in db_patients}
        stats = {
            "files_written": 0,
            "db_created_or_updated": 0,
            "directories_seen": 0,
        }

        for patient in db_patients:
            self._patient_dir(patient.patient_id).mkdir(parents=True, exist_ok=True)

        for patient_dir in PATIENT_DATA_ROOT.iterdir():
            if not patient_dir.is_dir():
                continue
            stats["directories_seen"] += 1
            data = self._patient_payload_from_dir(patient_dir)
            if data is None:
                continue

            db_patient = db_by_patient_id.get(data["patient_id"])
            info_file_mtime = self._parse_file_datetime(data.get("_info_file_mtime"))
            has_file_change = (
                info_file_mtime is not None
                and db_patient is not None
                and info_file_mtime > db_patient.updated_at
                and self._patient_data_differs(db_patient, data)
            )
            if db_patient is None or has_file_change:
                data.pop("_info_file_mtime", None)
                patient = await self.mapper.upsert_patient(data)
                db_by_patient_id[patient.patient_id] = patient
                stats["db_created_or_updated"] += 1

        for patient in await self.mapper.list_all_patients():
            self._write_patient_info_file(patient)
            stats["files_written"] += 1

        return stats

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
            patient_dir.mkdir(parents=True, exist_ok=True)
            self._write_patient_info_file(patient)
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

    def _agent_outputs_dir(self, patient_id: str) -> Path:
        output_dir = (self._patient_dir(patient_id) / "agent_outputs").resolve()
        try:
            output_dir.relative_to(self._patient_dir(patient_id))
        except ValueError:
            raise ValidationError(detail="invalid agent output path", field="patient_id")
        return output_dir

    def _agent_output_file_path(self, patient_id: str, file_path: str) -> Path:
        output_root = self._agent_outputs_dir(patient_id)
        if not file_path or Path(file_path).is_absolute():
            raise ValidationError(detail="invalid output file path", field="file_path")
        target = (output_root / file_path).resolve()
        try:
            target.relative_to(output_root)
        except ValueError:
            raise ValidationError(detail="invalid output file path", field="file_path")
        if not target.is_file():
            raise NotFoundError(resource_type="patient_output_file", resource_id=file_path)
        return target

    @handle_service_exception
    async def list_agent_output_files(self, patient_id: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        output_root = self._agent_outputs_dir(clean_id)
        output_root.mkdir(parents=True, exist_ok=True)
        files = []
        for path in sorted(output_root.rglob("*")):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(output_root)
            except ValueError:
                continue
            if "_internal" in relative.parts:
                continue
            relative_path = relative.as_posix()
            stat = path.stat()
            media_type, _ = mimetypes.guess_type(path.name)
            files.append({
                "path": relative_path,
                "name": path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "media_type": media_type or "application/octet-stream",
                "download_url": f"/patients/{clean_id}/outputs/serve/{relative_path}",
            })
        return {
            "patient_id": clean_id,
            "output_root": str(output_root),
            "files": files,
        }

    @handle_service_exception
    async def get_agent_output_file_path(self, patient_id: str, file_path: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)
        return self._agent_output_file_path(clean_id, file_path)

    @staticmethod
    def _read_json_file(path: Path) -> dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _parse_iso_datetime(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _manifest_sort_time(self, manifest_path: Path, manifest: dict) -> float:
        for key in ("finished_at", "updated_at", "started_at"):
            parsed = self._parse_iso_datetime(manifest.get(key))
            if parsed is not None:
                return parsed.timestamp()
        try:
            return manifest_path.stat().st_mtime
        except OSError:
            return 0.0

    def _safe_manifest_output_path(self, run_dir: Path, rel_path: str) -> Optional[Path]:
        candidate = Path(rel_path)
        output_path = candidate if candidate.is_absolute() else run_dir / candidate
        output_path = output_path.resolve()
        try:
            relative = output_path.relative_to(run_dir.resolve())
        except ValueError:
            return None
        if "_internal" in relative.parts:
            return None
        return output_path if output_path.is_file() else None

    def _latest_agent_output_by_role(
        self,
        patient_id: str,
        skill_id: str,
        role: str,
        phase: Optional[str] = None,
    ) -> Optional[Path]:
        output_root = self._agent_outputs_dir(patient_id)
        best: tuple[float, Path] | None = None
        for manifest_path in sorted(output_root.glob(f"*/steps/{skill_id}/manifest.json")):
            manifest = self._read_json_file(manifest_path)
            if manifest.get("status") != "success":
                continue
            run_dir_value = manifest.get("run_dir")
            run_dir = Path(run_dir_value).resolve() if isinstance(run_dir_value, str) else manifest_path.parent.resolve()
            timestamp = self._manifest_sort_time(manifest_path, manifest)
            for output in manifest.get("outputs") or []:
                if not isinstance(output, dict):
                    continue
                if output.get("role") != role:
                    continue
                if phase is None:
                    if output.get("phase") is not None:
                        continue
                elif output.get("phase") != phase:
                    continue
                rel_path = output.get("path")
                if not isinstance(rel_path, str):
                    continue
                output_path = self._safe_manifest_output_path(run_dir, rel_path)
                if output_path is None:
                    continue
                if best is None or timestamp > best[0]:
                    best = (timestamp, output_path)
        return best[1] if best else None

    @staticmethod
    def _first_file_with_ext(base_dir: Path, extensions: set[str]) -> Optional[Path]:
        if not base_dir.is_dir():
            return None
        for path in sorted(base_dir.iterdir()):
            if not path.is_file():
                continue
            name = path.name.lower()
            if any(name.endswith(ext) for ext in extensions):
                return path
        return None

    def _standard_result_file_payload(self, patient_id: str, path: Optional[Path], source: str) -> Optional[dict]:
        if path is None or not path.is_file():
            return None
        if source == "agent_output":
            output_root = self._agent_outputs_dir(patient_id)
            relative_path = path.resolve().relative_to(output_root.resolve()).as_posix()
            download_url = f"/patients/{patient_id}/outputs/serve/{relative_path}"
        else:
            patient_dir = self._patient_dir(patient_id)
            relative_path = path.resolve().relative_to(patient_dir.resolve()).as_posix()
            download_url = f"/patients/{patient_id}/body-composition-results/serve/{relative_path}"
        stat = path.stat()
        media_type, _ = mimetypes.guess_type(path.name)
        return {
            "path": str(path),
            "relative_path": relative_path,
            "name": path.name,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "media_type": media_type or "application/octet-stream",
            "download_url": download_url,
            "source": source,
        }

    @staticmethod
    def _find_numeric_column(row: dict[str, str], explicit_names: list[str], required_tokens: list[str]) -> Optional[float]:
        for name in explicit_names:
            value = row.get(name)
            if value not in (None, ""):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
        tokens = [token.lower() for token in required_tokens]
        for key, value in row.items():
            if value in (None, ""):
                continue
            key_lower = key.lower()
            if all(token in key_lower for token in tokens):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
        return None

    def _summarize_metrics_csv(self, csv_path: Optional[Path], height_cm: Optional[float]) -> Optional[dict]:
        if csv_path is None or not csv_path.is_file():
            return None
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle), None)
        except Exception:
            return None
        if not row:
            return None

        muscle = self._find_numeric_column(row, ["SMVI", "标签1-骨骼肌-Muscle (cm³)"], ["标签1", "muscle", "cm"])
        vat = self._find_numeric_column(row, ["VAVI", "VFVI", "标签3-内脏脂肪-VAT (cm³)"], ["标签3", "vat", "cm"])
        sat = self._find_numeric_column(row, ["SAVI", "标签4-皮下脂肪-SAT (cm³)"], ["标签4", "sat", "cm"])
        summary = {
            "file_name": row.get("文件名"),
            "muscle_cm3": muscle,
            "vat_cm3": vat,
            "sat_cm3": sat,
            "thoracic_start": row.get("胸椎起始"),
            "thoracic_end": row.get("胸椎结束"),
        }
        if height_cm:
            height_m2 = (float(height_cm) / 100.0) ** 2
            if height_m2 > 0:
                summary.update({
                    "smvi": muscle / height_m2 if muscle is not None else None,
                    "vavi": vat / height_m2 if vat is not None else None,
                    "savi": sat / height_m2 if sat is not None else None,
                })
        return summary

    def _summarize_type_json(self, json_path: Optional[Path]) -> Optional[dict]:
        if json_path is None or not json_path.is_file():
            return None
        payload = self._read_json_file(json_path)
        classification = payload.get("classification") if isinstance(payload.get("classification"), dict) else payload
        metric_results = classification.get("metric_results") if isinstance(classification, dict) else None
        if not isinstance(metric_results, dict):
            return None
        return {
            "status": classification.get("status"),
            "message": classification.get("message"),
            "metric_results": metric_results,
        }

    def _resolve_body_composition_metric_files(self, patient_id: str, phase: str) -> dict:
        metrics_dir = self._body_composition_metrics_dir(patient_id, phase)
        csv_path = self._first_file_with_ext(metrics_dir, {".csv"})
        xlsx_path = self._first_file_with_ext(metrics_dir, {".xlsx"})
        csv_source = "standard"
        xlsx_source = "standard"
        if csv_path is None:
            csv_path = self._latest_agent_output_by_role(patient_id, "ct_bodycomp_metrics_thoracic", "metrics_table", phase)
            csv_source = "agent_output"
        if xlsx_path is None:
            xlsx_path = self._latest_agent_output_by_role(patient_id, "ct_bodycomp_metrics_thoracic", "metrics_report", phase)
            xlsx_source = "agent_output"
        return {
            "csv": self._standard_result_file_payload(patient_id, csv_path, csv_source),
            "xlsx": self._standard_result_file_payload(patient_id, xlsx_path, xlsx_source),
        }

    def _resolve_body_composition_type_file(self, patient_id: str) -> tuple[Optional[Path], str]:
        type_dir = self._body_composition_type_dir(patient_id)
        json_path = self._first_file_with_ext(type_dir, {".json"})
        if json_path is not None:
            return json_path, "standard"
        json_path = self._latest_agent_output_by_role(
            patient_id,
            "ct_body_composition_type_classifier",
            "body_composition_type_classification",
            None,
        )
        return json_path, "agent_output"

    @handle_service_exception
    async def get_body_composition_results(self, patient_id: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        height_cm = getattr(patient, "height_cm", None)
        pre_files = self._resolve_body_composition_metric_files(clean_id, "pre")
        post_files = self._resolve_body_composition_metric_files(clean_id, "post")
        type_path, type_source = self._resolve_body_composition_type_file(clean_id)
        type_file = self._standard_result_file_payload(clean_id, type_path, type_source)

        return {
            "patient_id": clean_id,
            "standard_roots": {
                "metrics": str(self._patient_dir(clean_id) / "body_composition_metrics"),
                "type_classification": str(self._patient_dir(clean_id) / "body_composition_type"),
            },
            "metrics": {
                "pre": {
                    **pre_files,
                    "summary": self._summarize_metrics_csv(Path(pre_files["csv"]["path"]) if pre_files.get("csv") else None, height_cm),
                },
                "post": {
                    **post_files,
                    "summary": self._summarize_metrics_csv(Path(post_files["csv"]["path"]) if post_files.get("csv") else None, height_cm),
                },
            },
            "type_classification": {
                "json": type_file,
                "summary": self._summarize_type_json(Path(type_file["path"]) if type_file else None),
            },
        }

    @handle_service_exception
    async def upload_body_composition_metric_file(self, patient_id: str, phase: str, result_file: UploadFile) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        file_name = self._safe_filename(result_file.filename or "", field="result_file")
        ext = ".xlsx" if file_name.lower().endswith(".xlsx") else Path(file_name.lower()).suffix
        if ext not in BODY_COMPOSITION_METRIC_EXTENSIONS:
            raise ValidationError(detail="Metric file only supports .csv or .xlsx", field="result_file")

        target_dir = self._body_composition_metrics_dir(clean_id, clean_phase)
        target_dir.mkdir(parents=True, exist_ok=True)
        for old_file in target_dir.glob(f"*{ext}"):
            old_file.unlink(missing_ok=True)
        file_path = target_dir / file_name
        size = 0
        try:
            with file_path.open("wb") as out_file:
                while True:
                    chunk = await result_file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    out_file.write(chunk)
        finally:
            await result_file.close()
        if size <= 0:
            file_path.unlink(missing_ok=True)
            raise ValidationError(detail="result_file is empty", field="result_file")
        return await self.get_body_composition_results(clean_id)

    @handle_service_exception
    async def upload_body_composition_type_file(self, patient_id: str, result_file: UploadFile) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        file_name = self._safe_filename(result_file.filename or "", field="result_file")
        if Path(file_name.lower()).suffix not in BODY_COMPOSITION_TYPE_EXTENSIONS:
            raise ValidationError(detail="Type classification file only supports .json", field="result_file")
        target_dir = self._body_composition_type_dir(clean_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        for old_file in target_dir.glob("*.json"):
            old_file.unlink(missing_ok=True)
        file_path = target_dir / file_name
        size = 0
        try:
            with file_path.open("wb") as out_file:
                while True:
                    chunk = await result_file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    out_file.write(chunk)
        finally:
            await result_file.close()
        if size <= 0:
            file_path.unlink(missing_ok=True)
            raise ValidationError(detail="result_file is empty", field="result_file")
        if not self._read_json_file(file_path):
            file_path.unlink(missing_ok=True)
            raise ValidationError(detail="result_file must be a JSON object", field="result_file")
        return await self.get_body_composition_results(clean_id)

    @handle_service_exception
    async def get_body_composition_result_file_path(self, patient_id: str, file_path: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)
        return self._standard_result_file_path(clean_id, file_path)

    @handle_service_exception
    async def export_patient_report(self, patient_id: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)
        report_path = self._report_dir(clean_id) / f"{clean_id}_ct_report.pdf"
        return self._generate_patient_report_pdf(patient, report_path)

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
            **{k: data.get(k) for k in ("phase", "status", "file_name", "file_size", "uploaded_at", "preview_updated_at", "preview_url", "preview_planes", "display_window")},
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
            "preview_updated_at": None,
            "preview_url": None,
            "preview_planes": None,
            "display_window": None,
            "viewer_metadata": None,
        }
        try:
            self._write_ct_preview_metadata(clean_id, clean_phase, file_path, meta)
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
        warmup_key = f"ct:{clean_id}:{clean_phase}:{file_path.stat().st_mtime}:{size}"
        self._schedule_slice_cache_warmup(warmup_key, file_path, ct_dir)
        self._schedule_related_mask_warmups(clean_id, clean_phase, file_path)
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
        ct_dir = self._ct_dir(clean_id, clean_phase)
        ct_path = self._uploaded_file_from_meta(self._ct_meta_path(clean_id, clean_phase), ct_dir)
        if ct_path:
            warmup_key = f"mask:{clean_id}:{clean_type}:{clean_phase}:{ct_path.stat().st_mtime}:{file_path.stat().st_mtime}"
            self._schedule_slice_cache_warmup(warmup_key, ct_path, mask_dir, overlay=True, mask_path=file_path)
            if clean_type == "tumor":
                ct_meta_path = self._ct_meta_path(clean_id, clean_phase)
                try:
                    ct_meta = json.loads(ct_meta_path.read_text(encoding="utf-8")) if ct_meta_path.is_file() else {}
                    self._write_ct_preview_metadata(clean_id, clean_phase, ct_path, ct_meta)
                    ct_meta_path.write_text(
                        json.dumps(ct_meta, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception as exc:
                    logger.exception(
                        "Failed to refresh CT preview with tumor mask: patient=%s phase=%s error=%s",
                        clean_id,
                        clean_phase,
                        exc,
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
    async def get_ct_file_path(self, patient_id: str, phase: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        meta_path = self._ct_meta_path(clean_id, clean_phase)
        if not meta_path.is_file():
            raise NotFoundError(resource_type="ct_file", resource_id=f"{clean_id}:{clean_phase}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        file_name = meta.get("file_name")
        if not file_name:
            raise NotFoundError(resource_type="ct_file", resource_id=f"{clean_id}:{clean_phase}")
        file_path = self._ct_dir(clean_id, clean_phase) / Path(file_name).name
        if not file_path.is_file():
            raise NotFoundError(resource_type="ct_file", resource_id=f"{clean_id}:{clean_phase}")
        return file_path

    @handle_service_exception
    async def get_ct_viewer_metadata(self, patient_id: str, phase: str) -> Dict[str, Any]:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        meta_path = self._ct_meta_path(clean_id, clean_phase)
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                metadata = meta.get("viewer_metadata")
                if metadata and metadata.get("slice_counts") and metadata.get("center"):
                    if "display_window" not in metadata and metadata.get("window"):
                        metadata["display_window"] = metadata["window"]
                    return metadata
            except Exception:
                pass
        ct_path = await self.get_ct_file_path(clean_id, clean_phase)
        ct_data = self._read_cached_volume(ct_path)
        if not ct_data:
            raise NotFoundError(resource_type="ct_file", resource_id=f"{clean_id}:{clean_phase}")
        z, y, x = ct_data["volume"].shape
        window_min, window_max = ct_data["window"]
        return {
            "shape": {"x": x, "y": y, "z": z},
            "spacing": {"x": ct_data["spacing"][0], "y": ct_data["spacing"][1], "z": ct_data["spacing"][2]},
            "slice_counts": {"axial": z, "coronal": y, "sagittal": x},
            "center": {"axial": z // 2, "coronal": y // 2, "sagittal": x // 2},
            "display_window": {"min": window_min, "max": window_max},
        }

    @handle_service_exception
    async def get_ct_slice_path(self, patient_id: str, phase: str, plane: str, index: int) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        clean_plane = self._validate_preview_plane(plane)
        ct_path = await self.get_ct_file_path(clean_id, clean_phase)
        ct_data = self._read_cached_volume(ct_path)
        if not ct_data:
            raise NotFoundError(resource_type="ct_file", resource_id=f"{clean_id}:{clean_phase}")
        clean_index = max(0, min(int(index), self._slice_count(ct_data["volume"].shape, clean_plane) - 1))
        slice_path = self._slice_cache_path(self._ct_dir(clean_id, clean_phase), clean_plane, clean_index)
        if not slice_path.is_file():
            self._render_slice_png(ct_path, slice_path, clean_plane, clean_index)
        return slice_path

    @handle_service_exception
    async def get_ct_volume_data_path(self, patient_id: str, phase: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_phase = self._validate_phase(phase)
        ct_path = await self.get_ct_file_path(clean_id, clean_phase)
        return self._ct_uint8_volume_path(
            ct_path,
            self._volume_cache_path(self._ct_dir(clean_id, clean_phase), "ct_uint8.raw"),
        )

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
    async def get_mask_file_path(self, patient_id: str, mask_type: str, phase: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        patient = await self.mapper.get_patient(clean_id)
        if not patient:
            raise NotFoundError(resource_type="patient", resource_id=clean_id)

        meta_path = self._mask_meta_path(clean_id, clean_type, clean_phase)
        if not meta_path.is_file():
            raise NotFoundError(resource_type="mask_file", resource_id=f"{clean_id}:{clean_type}:{clean_phase}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        file_name = meta.get("file_name")
        if not file_name:
            raise NotFoundError(resource_type="mask_file", resource_id=f"{clean_id}:{clean_type}:{clean_phase}")
        file_path = self._mask_dir(clean_id, clean_type, clean_phase) / Path(file_name).name
        if not file_path.is_file():
            raise NotFoundError(resource_type="mask_file", resource_id=f"{clean_id}:{clean_type}:{clean_phase}")
        return file_path

    @handle_service_exception
    async def get_mask_slice_path(self, patient_id: str, mask_type: str, phase: str, plane: str, index: int) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        clean_plane = self._validate_preview_plane(plane)
        ct_path = await self.get_ct_file_path(clean_id, clean_phase)
        mask_path = await self.get_mask_file_path(clean_id, clean_type, clean_phase)
        ct_data = self._read_cached_volume(ct_path)
        if not ct_data:
            raise NotFoundError(resource_type="ct_file", resource_id=f"{clean_id}:{clean_phase}")
        clean_index = max(0, min(int(index), self._slice_count(ct_data["volume"].shape, clean_plane) - 1))
        slice_path = self._slice_cache_path(self._mask_dir(clean_id, clean_type, clean_phase), clean_plane, clean_index, overlay=True)
        if not slice_path.is_file():
            self._render_slice_png(ct_path, slice_path, clean_plane, clean_index, mask_path=mask_path)
        return slice_path

    @handle_service_exception
    async def get_mask_volume_data_path(self, patient_id: str, mask_type: str, phase: str) -> Path:
        clean_id = self._validate_patient_id(patient_id)
        clean_type = self._validate_mask_type(mask_type)
        clean_phase = self._validate_phase(phase)
        mask_path = await self.get_mask_file_path(clean_id, clean_type, clean_phase)
        return self._mask_uint8_volume_path(
            mask_path,
            self._volume_cache_path(self._mask_dir(clean_id, clean_type, clean_phase), "mask_uint8.raw"),
        )

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
        if clean_type == "tumor":
            ct_dir = self._ct_dir(clean_id, clean_phase)
            ct_path = self._uploaded_file_from_meta(self._ct_meta_path(clean_id, clean_phase), ct_dir)
            if ct_path:
                ct_meta_path = self._ct_meta_path(clean_id, clean_phase)
                try:
                    ct_meta = json.loads(ct_meta_path.read_text(encoding="utf-8")) if ct_meta_path.is_file() else {}
                    self._write_ct_preview_metadata(clean_id, clean_phase, ct_path, ct_meta)
                    ct_meta_path.write_text(
                        json.dumps(ct_meta, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception as exc:
                    logger.exception(
                        "Failed to refresh CT preview after deleting tumor mask: patient=%s phase=%s error=%s",
                        clean_id,
                        clean_phase,
                        exc,
                    )
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
        self._write_patient_info_file(patient)
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
