"""
数据集管理服务层
处理数据集相关的业务逻辑
"""

import logging
import pathlib
import shutil
from typing import List

from constants.CommonConstants import DATASET_PATH
from fastapi import UploadFile

from src.server_agent.exceptions import (
    NotFoundError,
    ServiceError,
    ValidationError,
    handle_service_exception,
)
from src.server_agent.mapper.DatasetMapper import DatasetMapper
from src.server_agent.mapper.paths import get_db_path
from src.server_agent.model.entity.DatasetInfo import DatasetInfo
from src.server_agent.model.vo.DatasetVO import DatasetVO
from src.server_agent.service.FileService import FileService

logger = logging.getLogger(__name__)


class DatasetService:
    """数据集服务类"""

    def __init__(self):
        self.dataset_mapper = DatasetMapper(get_db_path())
        self.file_service = FileService()

    @handle_service_exception
    async def create_dataset(self, dataset_info: DatasetInfo) -> DatasetVO:
        """
        创建数据集

        Args:
            dataset_info: 数据集信息

        Returns:
            创建的数据集VO
        """
        # 检查数据集名称是否已存在
        existing = await self.dataset_mapper.get_dataset_by_name_and_user(
            dataset_info.dataset_name, dataset_info.user_id
        )
        if existing:
            raise ValidationError(
                detail=f"数据集 '{dataset_info.dataset_name}' 已存在",
                context={"dataset_name": dataset_info.dataset_name},
            )

        # 验证数据集名称
        if not dataset_info.dataset_name or len(dataset_info.dataset_name.strip()) == 0:
            raise ValidationError(
                detail="数据集名称不能为空",
                context={"dataset_name": dataset_info.dataset_name},
            )

        # 创建数据集文件夹 - 新路径格式：private/{user_id}/dataset/{dataset_name}
        dataset_folder = (
            pathlib.Path(DATASET_PATH)
            / f"private/{dataset_info.user_id}/dataset"
            / dataset_info.dataset_name
        )
        try:
            dataset_folder.mkdir(parents=True, exist_ok=False)
            logger.info(f"Created dataset folder: {dataset_folder}")
        except FileExistsError:
            raise ValidationError(
                detail="数据集文件夹已存在", context={"folder": str(dataset_folder)}
            )
        except Exception as e:
            raise ServiceError(
                detail="创建数据集文件夹失败",
                context={"error": str(e), "folder": str(dataset_folder)},
            )

        # 设置数据路径
        dataset_info.data_path = f"private/{dataset_info.user_id}/dataset/{dataset_info.dataset_name}"

        # 保存数据集信息到数据库
        dataset_id = await self.dataset_mapper.create_dataset(dataset_info)
        dataset_info.id = dataset_id

        return DatasetVO(**dataset_info.model_dump())

    @handle_service_exception
    async def get_dataset_by_id(
        self, dataset_id: int, user_id: int, role: str = "user"
    ) -> DatasetVO:
        """
        根据ID获取数据集

        Args:
            dataset_id: 数据集ID
            user_id: 用户ID
            role: 用户角色

        Returns:
            数据集VO
        """
        dataset = await self.dataset_mapper.get_dataset_by_id(dataset_id)

        if not dataset:
            raise NotFoundError(
                detail="数据集不存在", context={"dataset_id": dataset_id}
            )

        # 权限检查：普通用户只能查看自己的数据集
        if role != "admin" and dataset.user_id != user_id:
            raise ValidationError(
                detail="无权访问该数据集",
                context={"dataset_id": dataset_id, "user_id": user_id},
            )

        return DatasetVO(**dataset.model_dump())

    @handle_service_exception
    async def get_user_datasets(
        self, user_id: int, role: str = "user"
    ) -> List[DatasetVO]:
        """
        获取用户的所有数据集

        Args:
            user_id: 用户ID
            role: 用户角色

        Returns:
            数据集列表
        """
        if role == "admin":
            # 管理员可以查看所有数据集
            datasets = await self.dataset_mapper.get_all_datasets()
        else:
            # 普通用户只能查看自己的数据集
            datasets = await self.dataset_mapper.get_datasets_by_user(user_id)

        return [DatasetVO(**dataset.model_dump()) for dataset in datasets]

    @handle_service_exception
    async def update_dataset(
        self, dataset_id: int, update_data: dict, user_id: int, role: str = "user"
    ) -> DatasetVO:
        """
        更新数据集信息

        Args:
            dataset_id: 数据集ID
            update_data: 更新数据
            user_id: 用户ID
            role: 用户角色

        Returns:
            更新后的数据集VO
        """
        # 获取数据集
        dataset = await self.dataset_mapper.get_dataset_by_id(dataset_id)

        if not dataset:
            raise NotFoundError(
                detail="数据集不存在", context={"dataset_id": dataset_id}
            )

        # 权限检查：普通用户只能更新自己的数据集
        if role != "admin" and dataset.user_id != user_id:
            raise ValidationError(
                detail="无权修改该数据集",
                context={"dataset_id": dataset_id, "user_id": user_id},
            )

        # 如果要更新数据集名称，需要重命名文件夹
        if (
            "dataset_name" in update_data
            and update_data["dataset_name"] != dataset.dataset_name
        ):
            old_folder = (
                pathlib.Path(DATASET_PATH)
                / f"private/{dataset.user_id}/dataset"
                / dataset.dataset_name
            )
            new_folder = (
                pathlib.Path(DATASET_PATH)
                / f"private/{dataset.user_id}/dataset"
                / update_data["dataset_name"]
            )

            if new_folder.exists():
                raise ValidationError(
                    detail=f"数据集名称 '{update_data['dataset_name']}' 已被使用",
                    context={"new_name": update_data["dataset_name"]},
                )

            try:
                old_folder.rename(new_folder)
                # 更新 data_path
                update_data["data_path"] = f"private/{dataset.user_id}/dataset/{update_data['dataset_name']}"
                logger.info(f"Renamed dataset folder from {old_folder} to {new_folder}")
            except Exception as e:
                raise ServiceError(
                    detail="重命名数据集文件夹失败", context={"error": str(e)}
                )

        # 更新数据库
        await self.dataset_mapper.update_dataset(dataset_id, update_data)

        # 获取更新后的数据集
        updated_dataset = await self.dataset_mapper.get_dataset_by_id(dataset_id)
        return DatasetVO(**updated_dataset.model_dump())

    @handle_service_exception
    async def delete_dataset(
        self, dataset_id: int, user_id: int, role: str = "user"
    ) -> bool:
        """
        删除数据集

        Args:
            dataset_id: 数据集ID
            user_id: 用户ID
            role: 用户角色

        Returns:
            是否删除成功
        """
        # 获取数据集
        dataset = await self.dataset_mapper.get_dataset_by_id(dataset_id)

        if not dataset:
            raise NotFoundError(
                detail="数据集不存在", context={"dataset_id": dataset_id}
            )

        # 权限检查：普通用户只能删除自己的数据集
        if role != "admin" and dataset.user_id != user_id:
            raise ValidationError(
                detail="无权删除该数据集",
                context={"dataset_id": dataset_id, "user_id": user_id},
            )

        # 删除数据集文件夹
        dataset_folder = (
            pathlib.Path(DATASET_PATH)
            / f"private/{dataset.user_id}/dataset"
            / dataset.dataset_name
        )
        try:
            if dataset_folder.exists():
                shutil.rmtree(dataset_folder)
                logger.info(f"Deleted dataset folder: {dataset_folder}")
        except Exception as e:
            logger.error(f"Failed to delete dataset folder: {e}")
            # 即使文件夹删除失败，也继续删除数据库记录

        # 删除数据库记录
        await self.dataset_mapper.delete_dataset(dataset_id)

        return True

    @handle_service_exception
    async def upload_files_to_dataset(
        self, dataset_id: int, files: List[UploadFile], user_id: int, role: str = "user"
    ) -> dict:
        """
        上传文件到数据集

        Args:
            dataset_id: 数据集ID
            files: 文件列表
            user_id: 用户ID
            role: 用户角色

        Returns:
            上传结果
        """
        # 调试日志
        logger.info(f"收到上传请求 - 数据集ID: {dataset_id}, 文件数量: {len(files)}")
        for i, file in enumerate(files):
            logger.info(f"文件 {i+1}: {file.filename}, 大小: {file.size}")
        
        # 获取数据集
        dataset = await self.dataset_mapper.get_dataset_by_id(dataset_id)

        if not dataset:
            raise NotFoundError(
                detail="数据集不存在", context={"dataset_id": dataset_id}
            )

        # 权限检查
        if role != "admin" and dataset.user_id != user_id:
            raise ValidationError(
                detail="无权上传文件到该数据集",
                context={"dataset_id": dataset_id, "user_id": user_id},
            )

        # 构建目标路径 - 新路径格式
        target_dir = f"private/{dataset.user_id}/dataset/{dataset.dataset_name}"

        # 上传文件
        uploaded_files = await self.file_service.uploadMultipleFilesToData(
            files, target_dir, user_id, role
        )

        # 更新案例数量（假设每个文件是一个案例）
        new_case_count = dataset.case_count + len(uploaded_files)
        await self.dataset_mapper.update_case_count(dataset_id, new_case_count)
        
        # 更新 has_data 和 data_path
        update_data = {
            "has_data": 1,
            "data_path": target_dir
        }
        await self.dataset_mapper.update_dataset(dataset_id, update_data)

        return {
            "uploaded_count": len(uploaded_files),
            "total_case_count": new_case_count,
            "files": uploaded_files,
        }

    @handle_service_exception
    async def upload_description_file(
        self, dataset_id: int, file: UploadFile, user_id: int, role: str = "user"
    ) -> dict:
        """
        上传数据集描述文件（CSV）

        Args:
            dataset_id: 数据集ID
            file: CSV描述文件
            user_id: 用户ID
            role: 用户角色

        Returns:
            上传结果
        """
        # 获取数据集
        dataset = await self.dataset_mapper.get_dataset_by_id(dataset_id)

        if not dataset:
            raise NotFoundError(
                detail="数据集不存在", context={"dataset_id": dataset_id}
            )

        # 权限检查
        if role != "admin" and dataset.user_id != user_id:
            raise ValidationError(
                detail="无权上传文件到该数据集",
                context={"dataset_id": dataset_id, "user_id": user_id},
            )

        # 验证文件类型
        if not file.filename.endswith('.csv'):
            raise ValidationError(
                detail="只支持上传 CSV 格式的描述文件",
                context={"filename": file.filename}
            )

        # 构建目标路径：private/{user_id}/dataset/{dataset_name}/{dataset_id}.csv
        target_dir = pathlib.Path(DATASET_PATH) / f"private/{dataset.user_id}/dataset/{dataset.dataset_name}"
        target_file = target_dir / f"{dataset_id}.csv"

        # 确保目录存在
        target_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        try:
            content = await file.read()
            with open(target_file, 'wb') as f:
                f.write(content)
            logger.info(f"Uploaded description file: {target_file}")
        except Exception as e:
            raise ServiceError(
                detail="保存描述文件失败",
                context={"error": str(e), "file": str(target_file)}
            )

        # 更新数据库：设置 has_description_file=1 和 description_file_path
        description_file_path = f"private/{dataset.user_id}/dataset/{dataset.dataset_name}/{dataset_id}.csv"
        update_data = {
            "has_description_file": 1,
            "description_file_path": description_file_path
        }
        await self.dataset_mapper.update_dataset(dataset_id, update_data)

        return {
            "message": "描述文件上传成功",
            "file_path": description_file_path
        }
