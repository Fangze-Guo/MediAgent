from typing import Optional

from pydantic import BaseModel, Field


class PatientCreateRequest(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    sex: Optional[str] = Field(default=None, max_length=20)
    age: Optional[int] = Field(default=None, ge=0, le=130)
    phone: Optional[str] = Field(default=None, max_length=64)
    height_cm: Optional[float] = Field(default=None, ge=0, le=300)
    smoking_status: Optional[str] = Field(default=None, max_length=64)
    pathology_type: Optional[str] = Field(default=None, max_length=128)
    pd_l1_status: Optional[str] = Field(default=None, max_length=128)


class PatientUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sex: Optional[str] = Field(default=None, max_length=20)
    age: Optional[int] = Field(default=None, ge=0, le=130)
    phone: Optional[str] = Field(default=None, max_length=64)
    height_cm: Optional[float] = Field(default=None, ge=0, le=300)
    smoking_status: Optional[str] = Field(default=None, max_length=64)
    pathology_type: Optional[str] = Field(default=None, max_length=128)
    pd_l1_status: Optional[str] = Field(default=None, max_length=128)
