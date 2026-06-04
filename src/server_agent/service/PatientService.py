import re
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import asyncpg
from fastapi import UploadFile

from src.server_agent.exceptions import ConflictError, DatabaseError, NotFoundError, ValidationError, handle_service_exception
from src.server_agent.mapper.PatientMapper import PatientMapper


PATIENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
PATIENT_DATA_ROOT = Path("/home/fetters/project/MediAgent/src/server_new/data/patient")
CT_PHASES = {"pre", "post"}
CT_EXTENSIONS = {".nii", ".nii.gz", ".dcm", ".zip"}


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
    def _safe_filename(filename: str) -> str:
        name = Path(filename or "").name.strip()
        if not name:
            raise ValidationError(detail="ct_file filename is required", field="ct_file")
        if "/" in name or "\\" in name:
            raise ValidationError(detail="invalid ct_file filename", field="ct_file")
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

    def _empty_ct_status(self, phase: str) -> Dict[str, Any]:
        return {
            "phase": phase,
            "status": "empty",
            "file_name": None,
            "file_size": None,
            "uploaded_at": None,
            "preview_url": None,
        }

    @staticmethod
    def _normalize_slice(slice_2d):
        import numpy as np
        from PIL import Image

        arr = np.asarray(slice_2d, dtype=np.float32)
        arr = np.nan_to_num(arr)
        lo, hi = np.percentile(arr, [1, 99])
        if hi <= lo:
            lo, hi = float(arr.min()), float(arr.max())
        if hi <= lo:
            arr = np.zeros_like(arr, dtype=np.uint8)
        else:
            arr = np.clip((arr - lo) / (hi - lo), 0, 1)
            arr = (arr * 255).astype(np.uint8)
        return Image.fromarray(arr).convert("L")

    def _make_ct_preview(self, ct_path: Path, preview_path: Path) -> bool:
        import numpy as np
        from PIL import Image, ImageDraw
        import SimpleITK as sitk

        ext = self._ct_ext(ct_path.name)
        if ext == ".zip":
            return False

        image = sitk.ReadImage(str(ct_path))
        volume = sitk.GetArrayFromImage(image)
        if volume.ndim == 4:
            volume = volume[0]
        if volume.ndim == 2:
            volume = volume[np.newaxis, :, :]
        if volume.ndim != 3:
            return False

        z, y, x = volume.shape
        slices = [
            ("Axial", volume[z // 2, :, :]),
            ("Coronal", volume[:, y // 2, :]),
            ("Sagittal", volume[:, :, x // 2]),
        ]
        panels = []
        for label, arr in slices:
            img = self._normalize_slice(arr)
            img.thumbnail((320, 320))
            canvas = Image.new("RGB", (340, 372), "#0b0f19")
            left = (340 - img.width) // 2
            top = (320 - img.height) // 2
            canvas.paste(img.convert("RGB"), (left, top))
            draw = ImageDraw.Draw(canvas)
            draw.text((14, 342), label, fill="#e5e7eb")
            panels.append(canvas)

        combined = Image.new("RGB", (340 * 3 + 24, 372), "#111827")
        for index, panel in enumerate(panels):
            combined.paste(panel, (index * (340 + 12), 0))
        combined.save(preview_path)
        return True

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
            **{k: data.get(k) for k in ("phase", "status", "file_name", "file_size", "uploaded_at", "preview_url")},
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
        }
        preview_path = ct_dir / "preview.png"
        try:
            if self._make_ct_preview(file_path, preview_path):
                meta["preview_url"] = f"/patients/{clean_id}/ct/{clean_phase}/preview"
        except Exception:
            meta["preview_url"] = None

        self._ct_meta_path(clean_id, clean_phase).write_text(
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
