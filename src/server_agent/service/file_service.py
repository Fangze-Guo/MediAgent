"""
文件管理服务层
处理文件相关的业务逻辑
"""
import pathlib
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
import logging

from fastapi import UploadFile
from src.server_agent.exceptions import ValidationError, NotFoundError, ServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class FileService:
    """文件服务类"""
    
    def __init__(self):
        # 文件上传配置
        self.UPLOAD_DIR = pathlib.Path("data")
        self.UPLOAD_DIR.mkdir(exist_ok=True)
        self.MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB（DICOM文件可能较大）
        self.ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.csv', '.dcm', '.DCM', '.nii', '.nii.gz'}
        
        # 本地文件浏览配置
        self.LOCAL_FILES_DIR = pathlib.Path(".").resolve()
        
        # 输出文件浏览配置
        self.OUTPUT_FILES_DIR = pathlib.Path("output").resolve()
        self.OUTPUT_FILES_DIR.mkdir(exist_ok=True)
    
    @handle_service_exception
    async def upload_file(self, file: UploadFile) -> Dict[str, Any]:
        """
        上传文件
        
        Args:
            file: 上传的文件
            
        Returns:
            上传结果
        """
        try:
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
            
            # 处理文件名冲突
            original_name = file.filename
            file_path = self.UPLOAD_DIR / original_name
            
            if file_path.exists():
                name_without_ext = pathlib.Path(original_name).stem
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"{name_without_ext}_{timestamp}{file_ext}"
                file_path = self.UPLOAD_DIR / new_name
                original_name = new_name
            
            # 生成文件ID
            file_id = pathlib.Path(original_name).stem
            
            # 保存文件
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # 创建文件信息
            file_info = {
                "id": file_id,
                "originalName": original_name,
                "size": file.size,
                "type": file.content_type,
                "path": str(file_path.resolve()),
                "uploadTime": datetime.now().isoformat()
            }
            
            return {"success": True, "file": file_info}
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            raise ServiceError(
                detail="文件上传失败",
                service_name="file_service",
                context={"filename": file.filename, "error": str(e)}
            )
    
    @handle_service_exception
    async def get_files_list(self) -> Dict[str, Any]:
        """
        获取data目录中的所有文件列表（包括已上传和已存在的文件）
        
        Returns:
            文件列表
        """
        try:
            files = []
            
            # 递归遍历data目录
            for file_path in self.UPLOAD_DIR.rglob("*"):
                if file_path.is_file():
                    # 计算相对路径
                    relative_path = str(file_path.relative_to(self.UPLOAD_DIR)).replace('\\', '/')
                    
                    # 生成唯一ID
                    file_id = f"data_{abs(hash(str(file_path)))}"
                    
                    stat = file_path.stat()
                    file_info = {
                        "id": file_id,
                        "originalName": file_path.name,
                        "size": stat.st_size,
                        "type": self._get_content_type(file_path.suffix),
                        "path": relative_path,
                        "uploadTime": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    }
                    files.append(file_info)
            
            # 按修改时间排序（最新的在前）
            files.sort(key=lambda x: x["uploadTime"], reverse=True)
            
            return {"files": files}
            
        except Exception as e:
            logger.error(f"获取文件列表失败: {e}")
            raise ServiceError(
                detail="获取文件列表失败",
                service_name="file_service",
                context={"error": str(e)}
            )
    
    @handle_service_exception
    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        """
        删除文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            删除结果
        """
        try:
            file_path = self._find_file_by_id(file_id)
            if not file_path:
                raise NotFoundError(
                    resource_type="file",
                    resource_id=file_id,
                    detail=f"文件不存在: {file_id}"
                )
            
            file_path.unlink()
            return {"success": True}
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            raise ServiceError(
                detail="删除文件失败",
                service_name="file_service",
                context={"file_id": file_id, "error": str(e)}
            )
    
    @handle_service_exception
    async def batch_delete_files(self, file_ids: List[str]) -> Dict[str, Any]:
        """
        批量删除文件
        
        Args:
            file_ids: 文件ID列表
            
        Returns:
            批量删除结果
        """
        try:
            deleted_count = 0
            errors = []
            
            for file_id in file_ids:
                try:
                    file_path = self._find_file_by_id(file_id)
                    if file_path and file_path.exists():
                        file_path.unlink()
                        deleted_count += 1
                    else:
                        errors.append(f"文件不存在: {file_id}")
                except Exception as e:
                    errors.append(f"删除文件 {file_id} 失败: {str(e)}")
            
            if errors:
                return {
                    "success": False,
                    "deletedCount": deleted_count,
                    "error": f"部分文件删除失败: {'; '.join(errors)}"
                }
            
            return {
                "success": True,
                "deletedCount": deleted_count
            }
            
        except Exception as e:
            logger.error(f"批量删除文件失败: {e}")
            raise ServiceError(
                detail="批量删除文件失败",
                service_name="file_service",
                context={"file_ids": file_ids, "error": str(e)}
            )
    
    @handle_service_exception
    async def get_download_url(self, file_id: str) -> Dict[str, Any]:
        """
        获取文件下载URL
        
        Args:
            file_id: 文件ID
            
        Returns:
            下载URL信息
        """
        try:
            file_path = self._find_file_by_id(file_id)
            if not file_path or not file_path.exists():
                raise NotFoundError(
                    resource_type="file",
                    resource_id=file_id,
                    detail=f"文件不存在: {file_id}"
                )
            
            download_url = f"/files/serve/{file_id}"
            return {
                "success": True,
                "downloadUrl": download_url
            }
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"获取下载URL失败: {e}")
            raise ServiceError(
                detail="获取下载URL失败",
                service_name="file_service",
                context={"file_id": file_id, "error": str(e)}
            )
    
    @handle_service_exception
    async def serve_file(self, file_id: str) -> Tuple[pathlib.Path, str]:
        """
        提供文件下载服务
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件路径和内容类型
        """
        try:
            file_path = self._find_file_by_id(file_id)
            if not file_path or not file_path.exists():
                raise NotFoundError(
                    resource_type="file",
                    resource_id=file_id,
                    detail="文件不存在"
                )
            
            content_type = self._get_content_type(file_path.suffix)
            return file_path, content_type
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"文件下载失败: {e}")
            raise ServiceError(
                detail="文件下载失败",
                service_name="file_service",
                context={"file_id": file_id, "error": str(e)}
            )
    
    @handle_service_exception
    async def browse_local_files(self, path: str = ".") -> Dict[str, Any]:
        """
        浏览本地文件
        
        Args:
            path: 目录路径
            
        Returns:
            文件列表信息
        """
        try:
            target_path = self._get_safe_path(self.LOCAL_FILES_DIR, path)
            
            files = []
            for item in target_path.iterdir():
                try:
                    stat = item.stat()
                    is_directory = item.is_dir()
                    
                    file_id = f"local_{abs(hash(str(item)))}"
                    file_type = "directory" if is_directory else self._get_content_type(item.suffix)
                    relative_path = str(item.relative_to(self.LOCAL_FILES_DIR)).replace('\\', '/')
                    
                    file_info = {
                        "id": file_id,
                        "name": item.name,
                        "size": stat.st_size if not is_directory else 0,
                        "type": file_type,
                        "path": relative_path,
                        "modifiedTime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "isDirectory": is_directory
                    }
                    files.append(file_info)
                except (OSError, PermissionError):
                    continue
            
            # 排序：目录在前，文件在后
            files.sort(key=lambda x: (not x["isDirectory"], x["name"].lower()))
            
            # 计算路径信息
            current_path = self._get_relative_path(target_path, self.LOCAL_FILES_DIR)
            parent_path = self._get_parent_path(target_path, self.LOCAL_FILES_DIR)
            
            return {
                "files": files,
                "currentPath": current_path,
                "parentPath": parent_path
            }
            
        except Exception as e:
            logger.error(f"获取本地文件列表失败: {e}")
            raise ServiceError(
                detail="获取本地文件列表失败",
                service_name="file_service",
                context={"path": path, "error": str(e)}
            )
    
    @handle_service_exception
    async def upload_to_local_directory(self, file: UploadFile, target_dir: str = ".") -> Dict[str, Any]:
        """
        上传文件到本地目录
        
        Args:
            file: 上传的文件
            target_dir: 目标目录
            
        Returns:
            上传结果
        """
        try:
            target_path = self._get_safe_path(self.LOCAL_FILES_DIR, target_dir)
            
            if not target_path.is_dir():
                raise ValidationError(
                    detail="目标路径不是目录",
                    context={"target_path": str(target_path)}
                )
            
            # 保存文件
            file_path = target_path / file.filename
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # 计算相对路径
            relative_path = str(file_path.relative_to(self.LOCAL_FILES_DIR)).replace('\\', '/')
            
            return {
                "success": True,
                "message": f"文件已上传到 {target_dir}",
                "file": {
                    "name": file.filename,
                    "path": relative_path,
                    "size": len(content)
                }
            }
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"上传文件到本地目录失败: {e}")
            raise ServiceError(
                detail="上传失败",
                service_name="file_service",
                context={"filename": file.filename, "target_dir": target_dir, "error": str(e)}
            )
    
    @handle_service_exception
    async def delete_local_file(self, file_path: str) -> Dict[str, Any]:
        """
        删除本地文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            删除结果
        """
        try:
            target_path = self._get_safe_path(self.LOCAL_FILES_DIR, file_path)
            
            if target_path.is_dir():
                raise ValidationError(
                    detail="不能删除目录",
                    context={"file_path": file_path}
                )
            
            target_path.unlink()
            return {
                "success": True,
                "message": f"文件 {file_path} 已删除"
            }
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"删除本地文件失败: {e}")
            raise ServiceError(
                detail="删除失败",
                service_name="file_service",
                context={"file_path": file_path, "error": str(e)}
            )
    
    @handle_service_exception
    async def serve_local_file(self, path: str) -> Tuple[pathlib.Path, str]:
        """
        提供本地文件下载服务
        
        Args:
            path: 文件路径
            
        Returns:
            文件路径和内容类型
        """
        try:
            target_path = self._get_safe_path(self.LOCAL_FILES_DIR, path)
            
            if target_path.is_dir():
                raise ValidationError(
                    detail="路径是目录，不是文件",
                    context={"path": path}
                )
            
            content_type = self._get_content_type(target_path.suffix)
            return target_path, content_type
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"本地文件下载失败: {e}")
            raise ServiceError(
                detail="本地文件下载失败",
                service_name="file_service",
                context={"path": path, "error": str(e)}
            )
    
    @handle_service_exception
    async def browse_output_files(self, path: str = ".") -> Dict[str, Any]:
        """
        浏览输出文件
        
        Args:
            path: 目录路径
            
        Returns:
            文件列表信息
        """
        try:
            target_path = self._get_safe_path(self.OUTPUT_FILES_DIR, path)
            
            files = []
            for item in target_path.iterdir():
                try:
                    stat = item.stat()
                    is_directory = item.is_dir()
                    
                    file_id = f"output_{abs(hash(str(item)))}"
                    file_type = "directory" if is_directory else self._get_content_type(item.suffix)
                    relative_path = str(item.relative_to(self.OUTPUT_FILES_DIR)).replace('\\', '/')
                    
                    file_info = {
                        "id": file_id,
                        "name": item.name,
                        "size": stat.st_size if not is_directory else 0,
                        "type": file_type,
                        "path": relative_path,
                        "modifiedTime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "isDirectory": is_directory
                    }
                    files.append(file_info)
                except (OSError, PermissionError):
                    continue
            
            # 排序：目录在前，文件在后
            files.sort(key=lambda x: (not x["isDirectory"], x["name"].lower()))
            
            # 计算路径信息
            current_path = self._get_relative_path(target_path, self.OUTPUT_FILES_DIR)
            parent_path = self._get_parent_path(target_path, self.OUTPUT_FILES_DIR)
            
            return {
                "files": files,
                "currentPath": current_path,
                "parentPath": parent_path
            }
            
        except Exception as e:
            logger.error(f"获取输出文件列表失败: {e}")
            raise ServiceError(
                detail="获取输出文件列表失败",
                service_name="file_service",
                context={"path": path, "error": str(e)}
            )
    
    @handle_service_exception
    async def upload_to_output_directory(self, file: UploadFile, target_dir: str = ".") -> Dict[str, Any]:
        """
        上传文件到输出目录
        
        Args:
            file: 上传的文件
            target_dir: 目标目录
            
        Returns:
            上传结果
        """
        try:
            target_path = self._get_safe_path(self.OUTPUT_FILES_DIR, target_dir)
            
            if not target_path.is_dir():
                raise ValidationError(
                    detail="目标路径不是目录",
                    context={"target_path": str(target_path)}
                )
            
            # 保存文件
            file_path = target_path / file.filename
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # 计算相对路径
            relative_path = str(file_path.relative_to(self.OUTPUT_FILES_DIR)).replace('\\', '/')
            
            return {
                "success": True,
                "message": f"文件已上传到输出目录 {target_dir}",
                "file": {
                    "name": file.filename,
                    "path": relative_path,
                    "size": len(content)
                }
            }
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"上传文件到输出目录失败: {e}")
            raise ServiceError(
                detail="上传失败",
                service_name="file_service",
                context={"filename": file.filename, "target_dir": target_dir, "error": str(e)}
            )
    
    @handle_service_exception
    async def delete_output_file(self, file_path: str) -> Dict[str, Any]:
        """
        删除输出文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            删除结果
        """
        try:
            target_path = self._get_safe_path(self.OUTPUT_FILES_DIR, file_path)
            
            if target_path.is_dir():
                raise ValidationError(
                    detail="不能删除目录",
                    context={"file_path": file_path}
                )
            
            target_path.unlink()
            return {
                "success": True,
                "message": f"输出文件 {file_path} 已删除"
            }
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"删除输出文件失败: {e}")
            raise ServiceError(
                detail="删除失败",
                service_name="file_service",
                context={"file_path": file_path, "error": str(e)}
            )
    
    @handle_service_exception
    async def serve_output_file(self, path: str) -> Tuple[pathlib.Path, str]:
        """
        提供输出文件下载服务
        
        Args:
            path: 文件路径
            
        Returns:
            文件路径和内容类型
        """
        try:
            target_path = self._get_safe_path(self.OUTPUT_FILES_DIR, path)
            
            if target_path.is_dir():
                raise ValidationError(
                    detail="路径是目录，不是文件",
                    context={"path": path}
                )
            
            content_type = self._get_content_type(target_path.suffix)
            return target_path, content_type
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"输出文件下载失败: {e}")
            raise ServiceError(
                detail="输出文件下载失败",
                service_name="file_service",
                context={"path": path, "error": str(e)}
            )
    
    # ==================== 工具方法 ====================
    
    def _get_content_type(self, ext: str) -> str:
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
    
    def _find_file_by_id(self, file_id: str) -> Optional[pathlib.Path]:
        """根据文件ID查找文件路径"""
        # 如果是新的ID格式（data_开头），通过hash查找
        if file_id.startswith("data_"):
            for file_path in self.UPLOAD_DIR.rglob("*"):
                if file_path.is_file():
                    if f"data_{abs(hash(str(file_path)))}" == file_id:
                        return file_path
        else:
            # 兼容旧的ID格式（文件名stem）
            for file_path in self.UPLOAD_DIR.iterdir():
                if file_path.is_file() and file_path.stem == file_id:
                    return file_path
        return None
    
    def _get_safe_path(self, root_dir: pathlib.Path, path: str) -> pathlib.Path:
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
    
    def _get_relative_path(self, target_path: pathlib.Path, root_dir: pathlib.Path) -> str:
        """获取相对路径"""
        try:
            current_path = str(target_path.relative_to(root_dir))
            return current_path.replace('\\', '/')
        except ValueError:
            return "."
    
    def _get_parent_path(self, target_path: pathlib.Path, root_dir: pathlib.Path) -> Optional[str]:
        """获取父目录路径"""
        try:
            parent_path = str(target_path.parent.relative_to(root_dir))
            parent_path = parent_path.replace('\\', '/')
            return parent_path if parent_path != "." else "."
        except ValueError:
            return None
