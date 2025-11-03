"""
数据集管理API控制器
"""

from typing import List

from fastapi import UploadFile, File, Form, Depends, Header

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.model.entity.DatasetInfo import DatasetInfo
from src.server_agent.model.dto.dataset import CreateDatasetRequest, UpdateDatasetRequest
from src.server_agent.model.vo.DatasetVO import DatasetVO
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service.DatasetService import DatasetService
from src.server_agent.service.UserService import UserService
from src.server_agent.exceptions import AuthenticationError
from .base import BaseController


class DatasetController(BaseController):
    """数据集控制器"""

    def __init__(self):
        super().__init__(prefix="/dataset", tags=["数据集管理"])
        self.dataset_service = DatasetService()
        self.user_service = UserService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.post("/create")
        async def create_dataset(
            request: CreateDatasetRequest,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[DatasetVO]:
            """创建数据集"""
            try:
                # 构建DatasetInfo
                dataset_info = DatasetInfo(
                    dataset_name=request.dataset_name,
                    case_count=request.case_count,
                    clinical_data_desc=request.clinical_data_desc,
                    text_data_desc=request.text_data_desc,
                    imaging_data_desc=request.imaging_data_desc,
                    pathology_data_desc=request.pathology_data_desc,
                    genomics_data_desc=request.genomics_data_desc,
                    annotation_desc=request.annotation_desc,
                    notes=request.notes,
                    user_id=userVO.uid
                )
                
                dataset_vo = await self.dataset_service.create_dataset(dataset_info)
                return ResultUtils.success(dataset_vo)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"创建数据集失败: {error_message}")

        @self.router.get("/list")
        async def get_datasets(
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[List[DatasetVO]]:
            """获取用户的数据集列表"""
            try:
                datasets = await self.dataset_service.get_user_datasets(userVO.uid, userVO.role)
                return ResultUtils.success(datasets)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"获取数据集列表失败: {error_message}")

        @self.router.get("/{dataset_id}")
        async def get_dataset(
            dataset_id: int,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[DatasetVO]:
            """获取数据集详情"""
            try:
                dataset = await self.dataset_service.get_dataset_by_id(dataset_id, userVO.uid, userVO.role)
                return ResultUtils.success(dataset)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"获取数据集失败: {error_message}")

        @self.router.put("/update")
        async def update_dataset(
            request: UpdateDatasetRequest,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[DatasetVO]:
            """更新数据集信息"""
            try:
                # 构建更新数据字典（只包含非None的字段）
                update_data = {
                    k: v for k, v in request.model_dump().items() 
                    if v is not None and k != 'id'
                }
                
                dataset = await self.dataset_service.update_dataset(
                    request.id, 
                    update_data, 
                    userVO.uid, 
                    userVO.role
                )
                return ResultUtils.success(dataset)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"更新数据集失败: {error_message}")

        @self.router.delete("/{dataset_id}")
        async def delete_dataset(
            dataset_id: int,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[None]:
            """删除数据集"""
            try:
                await self.dataset_service.delete_dataset(dataset_id, userVO.uid, userVO.role)
                return ResultUtils.success(None)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"删除数据集失败: {error_message}")

        @self.router.post("/{dataset_id}/upload")
        async def upload_files_to_dataset(
            dataset_id: int,
            files: List[UploadFile] = File(...),
            file_paths: str = Form(None),
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            """上传文件到数据集"""
            try:
                import json
                import logging
                
                # 解析文件路径信息
                paths_list = None
                if file_paths:
                    try:
                        paths_list = json.loads(file_paths)
                        logging.info(f"接收到 {len(paths_list)} 个文件路径")
                        # 打印前5个路径作为示例
                        for i, path in enumerate(paths_list[:5]):
                            logging.info(f"  路径 {i+1}: {path}")
                    except json.JSONDecodeError:
                        logging.warning("无法解析文件路径JSON，将使用原文件名")
                
                result = await self.dataset_service.upload_files_to_dataset(
                    dataset_id, 
                    files, 
                    userVO.uid, 
                    userVO.role,
                    paths_list
                )
                return ResultUtils.success(result)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"上传文件失败: {error_message}")

        @self.router.post("/{dataset_id}/upload-description")
        async def upload_description_file(
            dataset_id: int,
            file: UploadFile = File(...),
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            """上传数据集描述文件（CSV）"""
            try:
                result = await self.dataset_service.upload_description_file(
                    dataset_id,
                    file,
                    userVO.uid,
                    userVO.role
                )
                return ResultUtils.success(result)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"上传描述文件失败: {error_message}")

    # ==================== 工具方法 ====================

    async def _get_current_user(self, authorization: str = Header(None)) -> UserVO:
        """根据token获取用户信息的依赖函数"""
        if not authorization:
            raise AuthenticationError(
                detail="Missing authorization header",
                context={"header": "Authorization"}
            )

        # 支持多种格式：Bearer token 或直接 token
        if authorization.startswith("Bearer "):
            token = authorization[7:]  # 移除 "Bearer " 前缀
        else:
            token = authorization  # 直接使用 token

        userVO: UserVO = await self.user_service.get_user_by_token(token)
        if not userVO:
            raise AuthenticationError(
                detail="Invalid token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return userVO

