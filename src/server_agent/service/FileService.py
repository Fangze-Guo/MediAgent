"""
文件管理服务层
处理文件相关的业务逻辑
"""
import logging
import pathlib
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import UploadFile

from constants.CommonConstants import DATASET_PATH
from src.server_agent.exceptions import ValidationError, NotFoundError, ServiceError, handle_service_exception
from src.server_agent.model import FileInfo, FileListVO

logger = logging.getLogger(__name__)


class FileService:
    """文件服务类"""

    def __init__(self):
        self.MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB（DICOM文件可能较大）
        self.ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.csv', '.dcm', '.DCM', '.nii', '.nii.gz'}

    async def getDataSetFiles(self, target_path: str) -> FileListVO:
        """
           获取数据集文件列表

           Args:
               target_path: 目标路径，相对于 DATASET_PATH 的路径

           Returns:
               FileListVO: 文件列表信息
           """
        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        fileListVO: FileListVO = await self.getFileListVO(dataset_root, target_path)
        return fileListVO

    # ==================== 上传文件 ====================

    @handle_service_exception
    async def uploadFileToData(self, file: UploadFile, target_dir: str = ".") -> FileInfo:
        """
        上传文件
        
        Args:
            file: 上传的文件
            target_dir: 目标目录
            
        Returns:
            文件信息
        """
        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        fileInfo: FileInfo = await self.uploadFile(dataset_root, file, target_dir)
        return fileInfo

    @handle_service_exception
    async def uploadMultipleFilesToData(self, files: List[UploadFile], target_dir: str = ".") -> List[FileInfo]:
        """
        批量上传文件
        
        Args:
            files: 上传的文件列表
            target_dir: 目标目录
            
        Returns:
            文件信息列表
        """
        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        uploaded_files: List[FileInfo] = []

        for file in files:
            try:
                file_info: FileInfo = await self.uploadFile(dataset_root, file, target_dir)
                uploaded_files.append(file_info)
            except Exception as e:
                # 记录单个文件上传失败，但继续处理其他文件
                logging.error(f"文件 {file.filename} 上传失败: {e}")
                continue

        return uploaded_files

    async def uploadFile(self, files_dir: pathlib.Path, file: UploadFile, target_dir: str = ".") -> FileInfo:
        """
        上传文件

        Args:
            files_dir: 文件保存的目录
            file: 要上传的文件
            target_dir: 目标子目录

        Returns:
            文件信息
        """
        # 检查文件大小
        if file.size > self.MAX_FILE_SIZE:
            raise ValidationError(
                detail=f"文件大小超过限制 ({self.MAX_FILE_SIZE // (1024 * 1024)}MB)",
                context={"file_size": file.size, "max_size": self.MAX_FILE_SIZE}
            )

        # 检查文件扩展名
        file_ext = pathlib.Path(file.filename).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                detail=f"不支持的文件类型: {file_ext}",
                context={"file_extension": file_ext, "allowed_extensions": list(self.ALLOWED_EXTENSIONS)}
            )

        target_path = self._get_safe_path(files_dir, target_dir)
        if not target_path.is_dir():
            raise ValidationError(
                detail="目标路径不是目录",
                context={"target_path": str(target_path)}
            )

        # 处理文件名冲突
        original_name = file.filename
        file_path = files_dir / original_name

        # 如果文件已存在，添加时间戳避免冲突
        if file_path.exists():
            name_without_ext = pathlib.Path(original_name).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{name_without_ext}_{timestamp}{file_ext}"
            file_path = files_dir / new_name
            original_name = new_name

        # 生成文件ID - 使用路径哈希确保唯一性，与文件列表保持一致
        file_id = f"{abs(hash(str(file_path)))}"

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 创建文件信息
        file_info: FileInfo = FileInfo(
            id=file_id,
            name=original_name,
            size=file.size,
            type=file.content_type,
            path=str(file_path.resolve()),
            modifiedTime=datetime.now().isoformat(),
            isDirectory=False
        )
        return file_info

    async def getFileListVO(self, files_dir: pathlib.Path, path: str) -> FileListVO:
        """
        获取文件列表信息

        Args:
            files_dir: 文件目录
            path: 目录路径

        Returns:
            文件列表信息
        """
        try:
            target_path = self._get_safe_path(files_dir, path)

            files: List[FileInfo] = []
            for item in target_path.iterdir():
                try:
                    stat = item.stat()
                    is_directory = item.is_dir()

                    file_id = f"{abs(hash(str(item)))}"
                    file_type = "directory" if is_directory else self._get_content_type(item.suffix)
                    relative_path = str(item.relative_to(files_dir)).replace('\\', '/')

                    file_info: FileInfo = FileInfo(
                        id=file_id,
                        name=item.name,
                        size=stat.st_size if not is_directory else 0,
                        type=file_type,
                        path=relative_path,
                        modifiedTime=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        isDirectory=is_directory
                    )
                    files.append(file_info)
                except (OSError, PermissionError):
                    continue

            # 排序：目录在前，文件在后
            files.sort(key=lambda x: (not x.isDirectory, x.name.lower()))

            # 计算路径信息
            current_path = self._get_relative_path(target_path, files_dir)
            parent_path = self._get_parent_path(target_path, files_dir)

            fileListVO: FileListVO = FileListVO(
                files=files,
                currentPath=current_path,
                parentPath=parent_path
            )

            return fileListVO

        except Exception as e:
            logger.error(f"获取输出文件列表失败: {e}")
            raise ServiceError(
                detail="获取输出文件列表失败",
                service_name="file_service",
                context={"path": path, "error": str(e)}
            )

    # ==================== 删除文件 ====================

    @handle_service_exception
    async def deleteUploadFileById(self, file_id: str) -> None:
        """
        根据ID删除上传文件

        Args:
            file_id: 文件ID
        """
        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        file_path = self._get_file_path_by_id(file_id, dataset_root)
        if file_path is None:
            raise NotFoundError(
                resource_type="file",
                resource_id=file_id,
                detail="文件不存在"
            )
        await self.deleteFile(dataset_root, file_path)

    @handle_service_exception
    async def batchDeleteUploadFilesById(self, file_ids: List[str]) -> Dict[str, Any]:
        """
        批量根据ID删除上传文件

        Args:
            file_ids: 文件ID列表

        Returns:
            删除结果统计
        """
        success_count = 0
        failed_count = 0
        failed_files = []

        for file_id in file_ids:
            try:
                await self.deleteUploadFileById(file_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                failed_files.append({
                    "fileId": file_id,
                    "error": str(e)
                })
                logger.error(f"删除文件失败 {file_id}: {e}")

        return {
            "success": failed_count == 0,
            "deletedCount": success_count,
            "failedCount": failed_count,
            "failedFiles": failed_files
        }

    async def deleteFile(self, files_dir: pathlib.Path, file_path: str) -> bool:
        """
        删除文件

        Args:
            files_dir: 文件目录
            file_path: 文件路径

        Returns:
            删除结果
        """
        target_path = self._get_safe_path(files_dir, file_path)
        if target_path.is_dir():
            # 检查目录是否为空
            if any(target_path.iterdir()):
                raise ValidationError(
                    detail="目录不为空，无法删除",
                    context={"file_path": file_path}
                )
            # 删除空目录
            target_path.rmdir()
        else:
            # 删除文件
            target_path.unlink()
        return True

    # ==================== 创建文件夹 ====================

    @handle_service_exception
    async def createFolder(self, folder_name: str, current_path: str = ".") -> None:
        """
        创建文件夹

        Args:
            folder_name: 文件夹名称
            current_path: 当前路径
        """
        if not folder_name or not folder_name.strip():
            raise ValidationError(
                detail="文件夹名称不能为空",
                context={"folderName": folder_name}
            )

        # 检查文件夹名称是否包含非法字符
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        if any(char in folder_name for char in invalid_chars):
            raise ValidationError(
                detail="文件夹名称包含非法字符",
                context={"folderName": folder_name, "invalidChars": invalid_chars}
            )

        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        target_path = self._get_safe_path(dataset_root, current_path)
        new_folder_path = target_path / folder_name

        if new_folder_path.exists():
            raise ValidationError(
                detail="文件夹已存在",
                context={"folderName": folder_name, "path": str(new_folder_path)}
            )

        new_folder_path.mkdir(parents=True, exist_ok=False)
        logger.info(f"文件夹创建成功: {new_folder_path}")

    # ==================== 🛠️工具方法 ====================

    @staticmethod
    def _get_file_path_by_id(file_id: str, files_dir: pathlib.Path) -> Optional[str]:
        """
        根据文件ID查找文件路径
        
        Args:
            file_id: 文件ID
            files_dir: 文件目录
            
        Returns:
            文件相对路径，如果未找到返回None
        """
        try:
            # 遍历目录查找匹配的文件和目录
            for item in files_dir.rglob('*'):
                # 生成ID并比较（包括文件和目录）
                generated_id = f"{abs(hash(str(item)))}"
                if generated_id == file_id:
                    return str(item.relative_to(files_dir)).replace('\\', '/')
            return None
        except Exception as e:
            logger.error(f"查找文件路径失败: {e}")
            return None

    @staticmethod
    def _get_content_type(ext: str) -> str:
        """根据文件扩展名获取内容类型"""
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.pdf': 'application/pdf',
            '.dcm': 'application/dicom',
            '.DCM': 'application/dicom',
            '.nii': 'application/nifti',
            '.nii.gz': 'application/nifti'
        }
        return content_types.get(ext.lower(), 'application/octet-stream')

    @staticmethod
    def _get_safe_path(root_dir: pathlib.Path, path: str) -> pathlib.Path:
        """获取安全的路径，防止目录遍历攻击"""
        if path == ".":
            return root_dir

        # 将正斜杠路径转换为系统路径
        system_path = path.replace('/', '\\') if '\\' in str(root_dir) else path
        target_path = root_dir / system_path
        target_path = target_path.resolve()

        # 确保路径在允许的根目录内
        try:
            target_path.relative_to(root_dir)
        except ValueError:
            raise ValidationError(
                detail="访问被拒绝",
                context={"path": path, "root_dir": str(root_dir)}
            )

        if not target_path.exists():
            raise NotFoundError(
                resource_type="path",
                resource_id=path,
                detail="路径不存在"
            )

        return target_path

    @staticmethod
    def _get_relative_path(target_path: pathlib.Path, root_dir: pathlib.Path) -> str:
        """获取相对路径"""
        try:
            current_path = str(target_path.relative_to(root_dir))
            return current_path.replace('\\', '/')
        except ValueError:
            return "."

    @staticmethod
    def _get_parent_path(target_path: pathlib.Path, root_dir: pathlib.Path) -> Optional[str]:
        """获取父目录路径"""
        try:
            parent_path = str(target_path.parent.relative_to(root_dir))
            parent_path = parent_path.replace('\\', '/')
            return parent_path if parent_path != "." else "."
        except ValueError:
            return None
