from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PatientInfo(BaseModel):
    id: int
    patient_id: str
    name: str
    sex: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    height_cm: Optional[float] = None
    smoking_status: Optional[str] = None
    pathology_type: Optional[str] = None
    pd_l1_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
