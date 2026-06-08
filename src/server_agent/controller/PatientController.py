from fastapi import Depends, File, Query, UploadFile
from fastapi.responses import FileResponse

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

        @self.router.post("/sync")
        async def sync_patients(
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            result = await self.service.sync_patient_info_files()
            return ResultUtils.success(result)

        @self.router.get("/{patient_id}")
        async def get_patient(
            patient_id: str,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[PatientInfo]:
            patient = await self.service.get_patient(patient_id)
            return ResultUtils.success(patient)

        @self.router.get("/{patient_id}/report")
        async def export_patient_report(
            patient_id: str,
            current_user: UserVO = Depends(get_current_user),
        ):
            report_path = await self.service.export_patient_report(patient_id)
            return FileResponse(
                path=report_path,
                media_type="application/pdf",
                filename=report_path.name,
                headers={
                    "Content-Disposition": f'attachment; filename="{report_path.name}"',
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        @self.router.get("/{patient_id}/ct/{phase}")
        async def get_ct_status(
            patient_id: str,
            phase: str,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            status = await self.service.get_ct_status(patient_id, phase)
            return ResultUtils.success(status)

        @self.router.get("/{patient_id}/mask/{mask_type}/{phase}")
        async def get_mask_status(
            patient_id: str,
            mask_type: str,
            phase: str,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            status = await self.service.get_mask_status(patient_id, mask_type, phase)
            return ResultUtils.success(status)

        @self.router.post("/{patient_id}/ct/{phase}")
        async def upload_ct_file(
            patient_id: str,
            phase: str,
            ct_file: UploadFile = File(...),
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            status = await self.service.upload_ct_file(patient_id, phase, ct_file)
            return ResultUtils.success(status)

        @self.router.post("/{patient_id}/mask/{mask_type}/{phase}")
        async def upload_mask_file(
            patient_id: str,
            mask_type: str,
            phase: str,
            mask_file: UploadFile = File(...),
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            status = await self.service.upload_mask_file(patient_id, mask_type, phase, mask_file)
            return ResultUtils.success(status)

        @self.router.get("/{patient_id}/ct/{phase}/preview")
        async def get_ct_preview(
            patient_id: str,
            phase: str,
        ):
            preview_path = await self.service.get_ct_preview_path(patient_id, phase)
            return FileResponse(
                path=preview_path,
                media_type="image/png",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        @self.router.get("/{patient_id}/ct/{phase}/preview/{plane}")
        async def get_ct_preview_plane(
            patient_id: str,
            phase: str,
            plane: str,
        ):
            preview_path = await self.service.get_ct_preview_plane_path(patient_id, phase, plane)
            return FileResponse(
                path=preview_path,
                media_type="image/png",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        @self.router.get("/{patient_id}/ct/{phase}/file")
        async def get_ct_file(
            patient_id: str,
            phase: str,
        ):
            file_path = await self.service.get_ct_file_path(patient_id, phase)
            return FileResponse(
                path=file_path,
                media_type="application/nifti",
                filename=file_path.name,
                headers={
                    "Content-Disposition": f'inline; filename="{file_path.name}"',
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        @self.router.get("/{patient_id}/ct/{phase}/viewer-metadata")
        async def get_ct_viewer_metadata(
            patient_id: str,
            phase: str,
        ) -> BaseResponse[dict]:
            metadata = await self.service.get_ct_viewer_metadata(patient_id, phase)
            return ResultUtils.success(metadata)

        @self.router.get("/{patient_id}/ct/{phase}/slice/{plane}/{index}")
        async def get_ct_slice(
            patient_id: str,
            phase: str,
            plane: str,
            index: int,
        ):
            slice_path = await self.service.get_ct_slice_path(patient_id, phase, plane, index)
            return FileResponse(
                path=slice_path,
                media_type="image/png",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "public, max-age=31536000",
                },
            )

        @self.router.get("/{patient_id}/ct/{phase}/volume")
        async def get_ct_volume(
            patient_id: str,
            phase: str,
        ):
            volume_path = await self.service.get_ct_volume_data_path(patient_id, phase)
            return FileResponse(
                path=volume_path,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "public, max-age=31536000",
                    "X-Volume-Dtype": "uint8",
                },
            )

        @self.router.get("/{patient_id}/mask/{mask_type}/{phase}/preview")
        async def get_mask_preview(
            patient_id: str,
            mask_type: str,
            phase: str,
        ):
            preview_path = await self.service.get_mask_preview_path(patient_id, mask_type, phase)
            return FileResponse(
                path=preview_path,
                media_type="image/png",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        @self.router.get("/{patient_id}/mask/{mask_type}/{phase}/file")
        async def get_mask_file(
            patient_id: str,
            mask_type: str,
            phase: str,
        ):
            file_path = await self.service.get_mask_file_path(patient_id, mask_type, phase)
            return FileResponse(
                path=file_path,
                media_type="application/nifti",
                filename=file_path.name,
                headers={
                    "Content-Disposition": f'inline; filename="{file_path.name}"',
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        @self.router.get("/{patient_id}/mask/{mask_type}/{phase}/slice/{plane}/{index}")
        async def get_mask_slice(
            patient_id: str,
            mask_type: str,
            phase: str,
            plane: str,
            index: int,
        ):
            slice_path = await self.service.get_mask_slice_path(patient_id, mask_type, phase, plane, index)
            return FileResponse(
                path=slice_path,
                media_type="image/png",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "public, max-age=31536000",
                },
            )

        @self.router.get("/{patient_id}/mask/{mask_type}/{phase}/volume")
        async def get_mask_volume(
            patient_id: str,
            mask_type: str,
            phase: str,
        ):
            volume_path = await self.service.get_mask_volume_data_path(patient_id, mask_type, phase)
            return FileResponse(
                path=volume_path,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "public, max-age=31536000",
                    "X-Volume-Dtype": "uint8",
                },
            )

        @self.router.get("/{patient_id}/mask/{mask_type}/{phase}/preview/{plane}")
        async def get_mask_preview_plane(
            patient_id: str,
            mask_type: str,
            phase: str,
            plane: str,
        ):
            preview_path = await self.service.get_mask_preview_plane_path(patient_id, mask_type, phase, plane)
            return FileResponse(
                path=preview_path,
                media_type="image/png",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        @self.router.delete("/{patient_id}/ct/{phase}")
        async def delete_ct_data(
            patient_id: str,
            phase: str,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            status = await self.service.delete_ct_data(patient_id, phase)
            return ResultUtils.success(status)

        @self.router.delete("/{patient_id}/mask/{mask_type}/{phase}")
        async def delete_mask_data(
            patient_id: str,
            mask_type: str,
            phase: str,
            current_user: UserVO = Depends(get_current_user),
        ) -> BaseResponse[dict]:
            status = await self.service.delete_mask_data(patient_id, mask_type, phase)
            return ResultUtils.success(status)

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
