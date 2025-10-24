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

    async def getDataSetFiles(self, target_path: str, user_id: int = None, role: str = 'user') -> FileListVO:
        """
           获取数据集文件列表

           Args:
               target_path: 目标路径，相对于 DATASET_PATH 的路径
               user_id: 当前用户ID，用于过滤private文件夹内容
               role: 用户角色（'user' 或 'admin'）

           Returns:
               FileListVO: 文件列表信息
           """
        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        fileListVO: FileListVO = await self.getFileListVO(dataset_root, target_path, user_id, role)
        return fileListVO


    # ==================== 上传文件 ====================

    @handle_service_exception
    async def uploadFileToData(self, file: UploadFile, target_dir: str = ".", user_id: int = None, role: str = 'user') -> FileInfo:
        """
        上传文件
        
        Args:
            file: 上传的文件
            target_dir: 目标目录
            user_id: 当前用户ID，用于权限检查
            role: 用户角色（'user' 或 'admin'）
            
        Returns:
            文件信息
        """
        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        fileInfo: FileInfo = await self.uploadFile(dataset_root, file, target_dir, user_id, role)
        return fileInfo


    @handle_service_exception
    async def uploadMultipleFilesToData(self, files: List[UploadFile], target_dir: str = ".", user_id: int = None, role: str = 'user') -> List[FileInfo]:
        """
        批量上传文件
        
        Args:
            files: 上传的文件列表
            target_dir: 目标目录
            user_id: 当前用户ID，用于权限检查
            role: 用户角色（'user' 或 'admin'）
            
        Returns:
            文件信息列表
        """
        # 将DATASET_PATH转换为pathlib.Path对象
        dataset_root = pathlib.Path(DATASET_PATH)
        uploaded_files: List[FileInfo] = []

        for file in files:
            try:
                file_info: FileInfo = await self.uploadFile(dataset_root, file, target_dir, user_id, role)
                uploaded_files.append(file_info)
            except Exception as e:
                # 记录单个文件上传失败，但继续处理其他文件
                logging.error(f"文件 {file.filename} 上传失败: {e}")
                continue

        return uploaded_files

    async def uploadFile(self, files_dir: pathlib.Path, file: UploadFile, target_dir: str = ".", user_id: int = None, role: str = 'user') -> FileInfo:
        """
        上传文件

        Args:
            files_dir: 文件保存的目录
            file: 要上传的文件
            target_dir: 目标子目录
            user_id: 当前用户ID，用于权限检查
            role: 用户角色（'user' 或 'admin'）

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
        
        # 权限检查：验证用户是否有权限上传到目标目录
        self._check_write_permission(target_path, files_dir, user_id, role)

        # 处理文件名冲突
        original_name = file.filename
        file_path = target_path / original_name

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
        # 计算相对于根目录的路径用于前端显示
        relative_path = str(file_path.relative_to(files_dir)).replace('\\', '/')
        
        file_info: FileInfo = FileInfo(
            id=file_id,
            name=original_name,
            size=file.size,
            type=file.content_type,
            path=relative_path,
            modifiedTime=datetime.now().isoformat(),
            isDirectory=False
        )
        return file_info

    async def getFileListVO(self, files_dir: pathlib.Path, path: str, user_id: int = None, role: str = 'user') -> FileListVO:
        """
        获取文件列表信息

        Args:
            files_dir: 文件目录
            path: 目录路径
            user_id: 当前用户ID，用于过滤private文件夹内容
            role: 用户角色（'user' 或 'admin'）

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

                    # 检查是否需要过滤private文件夹下的内容（管理员不过滤）
                    if self._should_filter_item(item, files_dir, user_id, role):
                        continue

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
    async def deleteUploadFileById(self, file_id: str, user_id: int = None, role: str = 'user') -> None:
        """
        根据ID删除上传文件

        Args:
            file_id: 文件ID
            user_id: 当前用户ID
            role: 用户角色
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
        await self.deleteFile(dataset_root, file_path, user_id, role)

    @handle_service_exception
    async def batchDeleteUploadFilesById(self, file_ids: List[str], user_id: int = None, role: str = 'user') -> Dict[str, Any]:
        """
        批量根据ID删除上传文件

        Args:
            file_ids: 文件ID列表
            user_id: 当前用户ID
            role: 用户角色

        Returns:
            删除结果统计
        """
        success_count = 0
        failed_count = 0
        failed_files = []

        for file_id in file_ids:
            try:
                await self.deleteUploadFileById(file_id, user_id, role)
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

    async def deleteFile(self, files_dir: pathlib.Path, file_path: str, user_id: int = None, role: str = 'user') -> bool:
        """
        删除文件或目录（支持递归删除非空目录）

        Args:
            files_dir: 文件目录
            file_path: 文件路径
            user_id: 当前用户ID
            role: 用户角色

        Returns:
            删除结果
        """
        import shutil
        
        target_path = self._get_safe_path(files_dir, file_path)
        
        # 权限检查：验证用户是否有权限删除
        self._check_delete_permission(target_path, files_dir, user_id, role)
        
        if target_path.is_dir():
            # 递归删除整个目录（包括所有子文件和子目录）
            shutil.rmtree(target_path)
            logger.info(f"成功删除目录: {target_path}")
        else:
            # 删除文件
            target_path.unlink()
            logger.info(f"成功删除文件: {target_path}")
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
    def _check_delete_permission(target_path: pathlib.Path, files_dir: pathlib.Path, user_id: int = None, role: str = 'user'):
        """
        检查用户是否有权限删除文件/文件夹
        
        权限规则：
        1. 禁止删除 private 和 public 根目录
        2. 管理员(admin)：可以删除除根目录外的所有文件
        3. 普通用户(user)：
           - public目录：只读，禁止删除
           - private目录：只能删除自己ID的文件夹下的内容
        
        Args:
            target_path: 目标路径
            files_dir: 文件根目录
            user_id: 当前用户ID
            role: 用户角色（'user' 或 'admin'）
            
        Raises:
            ValidationError: 当用户没有删除权限时
        """
        from src.server_agent.exceptions import ValidationError
        
        if user_id is None:
            raise ValidationError(
                detail="用户未认证，无法删除文件",
                context={"target_path": str(target_path)}
            )
        
        # 获取相对路径
        try:
            relative_path = str(target_path.relative_to(files_dir)).replace('\\', '/')
        except ValueError:
            raise ValidationError(
                detail="非法的目标路径",
                context={"target_path": str(target_path), "files_dir": str(files_dir)}
            )
        
        path_parts = relative_path.split('/')
        
        # 禁止删除 private 和 public 根目录（管理员也不行）
        if len(path_parts) == 1 and path_parts[0] in ['private', 'public']:
            raise ValidationError(
                detail=f"禁止删除 {path_parts[0]} 根目录",
                context={"relative_path": relative_path}
            )
        
        # 管理员可以删除其他所有文件（除了根目录）
        if role == 'admin':
            logger.info(f"管理员用户 {user_id} 删除文件: {relative_path}")
            return
        
        # 普通用户权限检查
        # 检查是否在public目录下
        if len(path_parts) >= 1 and path_parts[0] == 'public':
            raise ValidationError(
                detail="public目录为只读目录，普通用户不能删除文件",
                context={"relative_path": relative_path}
            )
        
        # 检查是否在private目录下
        if len(path_parts) >= 2 and path_parts[0] == 'private':
            # 检查是否是当前用户的目录
            folder_name = path_parts[1]
            try:
                folder_user_id = int(folder_name)
                if folder_user_id != user_id:
                    raise ValidationError(
                        detail="无权限删除其他用户的私有文件",
                        context={"user_id": user_id, "target_user_id": folder_user_id}
                    )
            except ValueError:
                raise ValidationError(
                    detail="private目录下的文件夹名必须是用户ID",
                    context={"folder_name": folder_name}
                )
        else:
            # 其他目录不允许普通用户删除
            raise ValidationError(
                detail="只能删除 private/{用户ID}/ 目录下的文件",
                context={"relative_path": relative_path}
            )

    @staticmethod
    def _check_write_permission(target_path: pathlib.Path, files_dir: pathlib.Path, user_id: int = None, role: str = 'user'):
        """
        检查用户是否有权限写入目标目录
        
        权限规则：
        1. 管理员(admin)：可以写入任何目录（包括public和所有private目录）
        2. 普通用户(user)：
           - public目录：只读，禁止写入
           - private目录：只能写入自己ID的文件夹
        
        Args:
            target_path: 目标路径
            files_dir: 文件根目录
            user_id: 当前用户ID
            role: 用户角色（'user' 或 'admin'）
            
        Raises:
            ValidationError: 当用户没有写入权限时
        """
        from src.server_agent.exceptions import ValidationError
        
        if user_id is None:
            raise ValidationError(
                detail="用户未认证，无法上传文件",
                context={"target_path": str(target_path)}
            )
        
        # 管理员拥有所有权限，跳过权限检查
        if role == 'admin':
            logger.info(f"管理员用户 {user_id} 上传文件到 {target_path}")
            return
        
        # 获取相对路径
        try:
            relative_path = str(target_path.relative_to(files_dir)).replace('\\', '/')
        except ValueError:
            raise ValidationError(
                detail="非法的目标路径",
                context={"target_path": str(target_path), "files_dir": str(files_dir)}
            )
        
        # 根目录不允许直接上传
        if relative_path == '.':
            raise ValidationError(
                detail="不能直接上传到根目录，请选择public或private目录",
                context={"relative_path": relative_path}
            )
        
        path_parts = relative_path.split('/')
        
        # 检查是否在public目录下
        if len(path_parts) >= 1 and path_parts[0] == 'public':
            raise ValidationError(
                detail="public目录为只读目录，普通用户不能上传文件",
                context={"relative_path": relative_path}
            )
        
        # 检查是否在private目录下
        if len(path_parts) >= 1 and path_parts[0] == 'private':
            # 必须指定到具体用户ID的目录或其子目录
            if len(path_parts) < 2:
                raise ValidationError(
                    detail="请指定要上传到private下的具体用户文件夹",
                    context={"relative_path": relative_path}
                )
            
            # 检查是否是当前用户的目录
            folder_name = path_parts[1]
            try:
                folder_user_id = int(folder_name)
                if folder_user_id != user_id:
                    raise ValidationError(
                        detail="无权限上传到其他用户的私有目录",
                        context={"user_id": user_id, "target_user_id": folder_user_id}
                    )
            except ValueError:
                raise ValidationError(
                    detail="private目录下的文件夹名必须是用户ID",
                    context={"folder_name": folder_name}
                )
        else:
            # 其他目录也不允许上传
            raise ValidationError(
                detail="只能上传到private/{用户ID}/目录下",
                context={"relative_path": relative_path}
            )

    @staticmethod
    def _should_filter_item(item: pathlib.Path, files_dir: pathlib.Path, user_id: int = None, role: str = 'user') -> bool:
        """
        检查是否应该过滤掉某个文件或文件夹
        
        Args:
            item: 当前文件或文件夹路径
            files_dir: 文件根目录
            user_id: 当前用户ID
            role: 用户角色（'user' 或 'admin'）
            
        Returns:
            bool: True表示应该过滤掉，False表示不过滤
        """
        try:
            # 管理员可以看到所有文件和文件夹
            if role == 'admin':
                return False
                
            # 如果没有提供用户ID，不进行过滤
            if user_id is None:
                return False
                
            # 获取相对路径
            relative_path = str(item.relative_to(files_dir)).replace('\\', '/')
            path_parts = relative_path.split('/')
            
            # 检查是否在private目录下
            if len(path_parts) >= 2 and path_parts[0] == 'private':
                # 如果当前项就是private目录的直接子目录（用户文件夹）
                if len(path_parts) == 2:
                    # 检查文件夹名是否与当前用户ID匹配
                    folder_name = path_parts[1]
                    # 如果文件夹名不是当前用户的ID，则过滤掉
                    try:
                        folder_user_id = int(folder_name)
                        return folder_user_id != user_id
                    except ValueError:
                        # 如果文件夹名不是数字，也过滤掉（按照用户ID命名的约定）
                        return True
                        
            return False
        except Exception as e:
            logger.error(f"过滤文件项时发生错误: {e}")
            return False

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
