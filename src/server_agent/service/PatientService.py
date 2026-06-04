import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import asyncpg

from src.server_agent.exceptions import ConflictError, DatabaseError, NotFoundError, ValidationError, handle_service_exception
from src.server_agent.mapper.PatientMapper import PatientMapper


PATIENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
PATIENT_DATA_ROOT = Path("/home/fetters/project/MediAgent/src/server_new/data/patient")


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
