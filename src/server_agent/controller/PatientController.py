from fastapi import Depends, Query

from src.server_agent.common import BaseResponse, ResultUtils
from src.server_agent.dependencies import get_current_user
from src.server_agent.model.dto.patient import PatientCreateRequest, PatientUpdateRequest
from src.server_agent.model.entity.PatientInfo import PatientInfo
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service.PatientService import PatientService

from .base import BaseController


class PatientController(BaseController):
    """Global patient dataset controller."""

    def __init__(self):
        super().__init__(prefix="/patients", tags=["患者数据集"])
        self.service = PatientService()
        self._register_routes()

    def _register_routes(self):
        @self.router.post("")
        async def create_patient(
            request: PatientCreateRequest,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[PatientInfo]:
            patient = await self.service.create_patient(request.model_dump())
            return ResultUtils.success(patient)

        @self.router.get("")
        async def list_patients(
            keyword: str | None = Query(default=None),
            page: int = Query(default=1, ge=1),
            size: int = Query(default=20, ge=1, le=200),
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            result = await self.service.list_patients(keyword, page, size)
            return ResultUtils.success(result)

        @self.router.get("/{patient_id}")
        async def get_patient(
            patient_id: str,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[PatientInfo]:
            patient = await self.service.get_patient(patient_id)
            return ResultUtils.success(patient)

        @self.router.put("/{patient_id}")
        async def update_patient(
            patient_id: str,
            request: PatientUpdateRequest,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[PatientInfo]:
            patient = await self.service.update_patient(
                patient_id,
                request.model_dump(exclude_unset=True),
            )
            return ResultUtils.success(patient)

        @self.router.delete("/{patient_id}")
        async def delete_patient(
            patient_id: str,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            result = await self.service.delete_patient(patient_id)
            return ResultUtils.success(result)
