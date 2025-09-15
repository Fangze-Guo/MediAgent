"""
文件管理API控制器 - 统一管理所有文件操作
"""
import pathlib
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .base import BaseController


# ==================== 数据模型 ====================

class FileInfo(BaseModel):
    id: str
    originalName: str
    size: int
    type: str
    path: str
    uploadTime: str


class LocalFileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str
    path: str
    modifiedTime: str
    isDirectory: bool


class OutputFileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str
    path: str
    modifiedTime: str
    isDirectory: bool


# ==================== 响应模型 ====================

class FileUploadResp(BaseModel):
    success: bool
    file: FileInfo = None
    error: str = None


class FileListResp(BaseModel):
    files: List[FileInfo]


class LocalFileListResp(BaseModel):
    files: List[LocalFileInfo]
    currentPath: str
    parentPath: Optional[str] = None


class OutputFileListResp(BaseModel):
    files: List[OutputFileInfo]
    currentPath: str
    parentPath: Optional[str] = None


class DeleteFileReq(BaseModel):
    fileId: str


class DeleteFileResp(BaseModel):
    success: bool
    error: str = None


class BatchDeleteFilesReq(BaseModel):
    fileIds: List[str]


class BatchDeleteFilesResp(BaseModel):
    success: bool
    deletedCount: int
    error: str = None


class DownloadFileReq(BaseModel):
    fileId: str


class DownloadFileResp(BaseModel):
    success: bool
    downloadUrl: str = None
    error: str = None


# ==================== 主控制器 ====================

class FileController(BaseController):
    """统一文件控制器 - 管理所有文件操作"""

    def __init__(self):
        super().__init__(prefix="/files", tags=["文件管理"])

        # 文件上传配置
        self.UPLOAD_DIR = pathlib.Path("uploads")
        self.UPLOAD_DIR.mkdir(exist_ok=True)
        self.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        self.ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.csv'}

        # 本地文件浏览配置
        self.LOCAL_FILES_DIR = pathlib.Path(".").resolve()  # 当前目录的绝对路径

        # 输出文件浏览配置
        self.OUTPUT_FILES_DIR = pathlib.Path("output").resolve()  # 输出目录的绝对路径
        self.OUTPUT_FILES_DIR.mkdir(exist_ok=True)

        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        # ==================== 已上传文件路由 ====================

        @self.router.post("/upload", response_model=FileUploadResp)
        async def upload_file(file: UploadFile = File(...)):
            """上传文件接口"""
            try:
                # 检查文件大小
                if file.size > self.MAX_FILE_SIZE:
                    return FileUploadResp(
                        success=False,
                        file=None,
                        error=f"文件大小超过限制 ({self.MAX_FILE_SIZE // (1024 * 1024)}MB)"
                    )

                # 检查文件扩展名
                file_ext = pathlib.Path(file.filename).suffix.lower()
                if file_ext not in self.ALLOWED_EXTENSIONS:
                    return FileUploadResp(
                        success=False,
                        file=None,
                        error=f"不支持的文件类型: {file_ext}"
                    )

                # 使用原始文件名，如果文件已存在则添加时间戳
                original_name = file.filename
                file_path = self.UPLOAD_DIR / original_name

                # 如果文件已存在，添加时间戳避免冲突
                if file_path.exists():
                    name_without_ext = pathlib.Path(original_name).stem
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    new_name = f"{name_without_ext}_{timestamp}{file_ext}"
                    file_path = self.UPLOAD_DIR / new_name
                    original_name = new_name

                # 使用文件名作为ID（去掉扩展名）
                file_id = pathlib.Path(original_name).stem

                # 保存文件
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # 创建文件信息
                file_info = FileInfo(
                    id=file_id,
                    originalName=original_name,
                    size=file.size,
                    type=file.content_type,
                    path=str(file_path.resolve()),
                    uploadTime=datetime.now().isoformat()
                )

                return FileUploadResp(success=True, file=file_info)

            except Exception as e:
                print(f"文件上传失败: {e}")
                return FileUploadResp(
                    success=False,
                    file=None,
                    error=f"文件上传失败: {str(e)}"
                )

        @self.router.get("", response_model=FileListResp)
        async def list_files():
            """获取已上传文件列表"""
            try:
                files = []
                for file_path in self.UPLOAD_DIR.iterdir():
                    if file_path.is_file():
                        # 从文件名提取ID
                        file_id = file_path.stem
                        file_ext = file_path.suffix

                        # 获取文件信息
                        stat = file_path.stat()
                        file_info = FileInfo(
                            id=file_id,
                            originalName=f"{file_id}{file_ext}",
                            size=stat.st_size,
                            type=self.get_content_type(file_ext),
                            path=str(file_path.resolve()),
                            uploadTime=datetime.fromtimestamp(stat.st_mtime).isoformat()
                        )
                        files.append(file_info)

                return FileListResp(files=files)

            except Exception as e:
                print(f"获取文件列表失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

        @self.router.post("/delete", response_model=DeleteFileResp)
        async def delete_file(req: DeleteFileReq):
            """删除单个文件"""
            try:
                file_path = self.find_file_by_id(req.fileId)
                if not file_path:
                    return DeleteFileResp(
                        success=False,
                        error=f"文件不存在: {req.fileId}"
                    )

                # 删除文件
                file_path.unlink()

                return DeleteFileResp(success=True)

            except Exception as e:
                print(f"删除文件失败: {e}")
                return DeleteFileResp(
                    success=False,
                    error=f"删除文件失败: {str(e)}"
                )

        @self.router.post("/batch-delete", response_model=BatchDeleteFilesResp)
        async def batch_delete_files(req: BatchDeleteFilesReq):
            """批量删除文件"""
            try:
                deleted_count = 0
                errors = []

                for file_id in req.fileIds:
                    try:
                        file_path = self.find_file_by_id(file_id)
                        if file_path and file_path.exists():
                            file_path.unlink()
                            deleted_count += 1
                        else:
                            errors.append(f"文件不存在: {file_id}")
                    except Exception as e:
                        errors.append(f"删除文件 {file_id} 失败: {str(e)}")

                if errors:
                    return BatchDeleteFilesResp(
                        success=False,
                        deletedCount=deleted_count,
                        error=f"部分文件删除失败: {'; '.join(errors)}"
                    )

                return BatchDeleteFilesResp(
                    success=True,
                    deletedCount=deleted_count
                )

            except Exception as e:
                print(f"批量删除文件失败: {e}")
                return BatchDeleteFilesResp(
                    success=False,
                    deletedCount=0,
                    error=f"批量删除文件失败: {str(e)}"
                )

        @self.router.post("/download", response_model=DownloadFileResp)
        async def download_file(req: DownloadFileReq):
            """获取文件下载URL"""
            try:
                file_path = self.find_file_by_id(req.fileId)
                if not file_path or not file_path.exists():
                    return DownloadFileResp(
                        success=False,
                        error=f"文件不存在: {req.fileId}"
                    )

                # 生成下载URL
                download_url = f"/files/serve/{req.fileId}"

                return DownloadFileResp(
                    success=True,
                    downloadUrl=download_url
                )

            except Exception as e:
                print(f"获取下载URL失败: {e}")
                return DownloadFileResp(
                    success=False,
                    error=f"获取下载URL失败: {str(e)}"
                )

        @self.router.get("/serve/{file_id}")
        async def serve_file(file_id: str):
            """提供文件下载服务"""
            try:
                file_path = self.find_file_by_id(file_id)
                if not file_path or not file_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")

                # 获取文件内容类型
                content_type = self.get_content_type(file_path.suffix)

                # 返回文件内容
                return FileResponse(
                    path=str(file_path),
                    media_type=content_type,
                    filename=file_path.name
                )

            except Exception as e:
                print(f"文件下载失败: {e}")
                raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")

        # ==================== 本地文件路由 ====================

        @self.router.get("/local", response_model=LocalFileListResp)
        async def list_local_files(path: str = "."):
            """获取本地文件列表"""
            try:
                print(f"请求路径: {path}")
                print(f"本地文件目录: {self.LOCAL_FILES_DIR}")

                # 确保路径安全，防止目录遍历攻击
                if path == ".":
                    target_path = self.LOCAL_FILES_DIR
                else:
                    target_path = self.LOCAL_FILES_DIR / path
                    target_path = target_path.resolve()
                
                print(f"目标路径: {target_path}")
                print(f"根目录: {self.LOCAL_FILES_DIR}")

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.LOCAL_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="路径不存在")

                if not target_path.is_dir():
                    raise HTTPException(status_code=400, detail="路径不是目录")

                files = []
                for item in target_path.iterdir():
                    try:
                        stat = item.stat()
                        is_directory = item.is_dir()

                        # 生成唯一ID
                        file_id = f"local_{abs(hash(str(item)))}"

                        # 获取文件类型
                        if is_directory:
                            file_type = "directory"
                        else:
                            file_type = self.get_content_type(item.suffix)

                        # 计算相对于根目录的路径，统一使用正斜杠
                        relative_path = str(item.relative_to(self.LOCAL_FILES_DIR)).replace('\\', '/')
                        
                        file_info = LocalFileInfo(
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
                        # 跳过无法访问的文件
                        continue

                # 按类型和名称排序：目录在前，文件在后
                files.sort(key=lambda x: (not x.isDirectory, x.name.lower()))

                # 计算当前路径
                try:
                    current_path = str(target_path.relative_to(self.LOCAL_FILES_DIR))
                    # 统一使用正斜杠作为路径分隔符
                    current_path = current_path.replace('\\', '/')
                    if current_path == ".":
                        current_path = "."
                except ValueError:
                    # 如果当前路径就是根目录
                    current_path = "."

                # 计算父目录路径
                parent_path = None
                if current_path != ".":
                    try:
                        parent_path = str(target_path.parent.relative_to(self.LOCAL_FILES_DIR))
                        # 统一使用正斜杠作为路径分隔符
                        parent_path = parent_path.replace('\\', '/')
                        # 如果父目录是根目录，设置为"."，而不是None
                        if parent_path == ".":
                            parent_path = "."
                    except ValueError:
                        # 如果父目录不在根目录内，设置为None
                        parent_path = None
                
                return LocalFileListResp(
                    files=files,
                    currentPath=current_path,
                    parentPath=parent_path
                )

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"获取本地文件列表失败: {e}")
                print(f"详细错误信息: {error_details}")
                raise HTTPException(status_code=500, detail=f"获取本地文件列表失败: {str(e)}")

        @self.router.post("/local/upload")
        async def upload_to_local_directory(
            file: UploadFile = File(...),
            target_dir: str = Form(".")
        ):
            """上传文件到指定本地目录"""
            try:
                print(f"收到上传请求: 文件={file.filename}, 目标目录={target_dir}")
                # 确保目标目录安全
                if target_dir == ".":
                    target_path = self.LOCAL_FILES_DIR
                else:
                    # 将正斜杠路径转换为系统路径
                    system_path = target_dir.replace('/', '\\') if '\\' in str(self.LOCAL_FILES_DIR) else target_dir
                    target_path = self.LOCAL_FILES_DIR / system_path
                    target_path = target_path.resolve()

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.LOCAL_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="目标目录不存在")

                if not target_path.is_dir():
                    raise HTTPException(status_code=400, detail="目标路径不是目录")

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

            except Exception as e:
                print(f"上传文件到本地目录失败: {e}")
                raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

        @self.router.post("/local/delete")
        async def delete_local_file(file_path: str = Form(...)):
            """删除本地文件"""
            try:
                print(f"收到删除请求: 文件路径={file_path}")
                # 将正斜杠路径转换为系统路径
                system_path = file_path.replace('/', '\\') if '\\' in str(self.LOCAL_FILES_DIR) else file_path
                
                # 确保路径安全
                target_path = self.LOCAL_FILES_DIR / system_path
                target_path = target_path.resolve()

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.LOCAL_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")

                if target_path.is_dir():
                    raise HTTPException(status_code=400, detail="不能删除目录")

                # 删除文件
                target_path.unlink()

                return {
                    "success": True,
                    "message": f"文件 {file_path} 已删除"
                }

            except Exception as e:
                print(f"删除本地文件失败: {e}")
                raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

        @self.router.get("/local/serve")
        async def serve_local_file(path: str):
            """提供本地文件下载服务"""
            try:
                # 将正斜杠路径转换为系统路径
                system_path = path.replace('/', '\\') if '\\' in str(self.LOCAL_FILES_DIR) else path
                
                # 确保路径安全
                target_path = self.LOCAL_FILES_DIR / system_path
                target_path = target_path.resolve()

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.LOCAL_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")

                if target_path.is_dir():
                    raise HTTPException(status_code=400, detail="路径是目录，不是文件")

                # 获取文件内容类型
                content_type = self.get_content_type(target_path.suffix)

                # 返回文件内容
                return FileResponse(
                    path=str(target_path),
                    media_type=content_type,
                    filename=target_path.name
                )

            except Exception as e:
                print(f"本地文件下载失败: {e}")
                raise HTTPException(status_code=500, detail=f"本地文件下载失败: {str(e)}")

        # ==================== 输出文件路由 ====================

        @self.router.get("/output", response_model=OutputFileListResp)
        async def list_output_files(path: str = "."):
            """获取输出文件列表"""
            try:
                print(f"请求输出文件路径: {path}")
                print(f"输出文件目录: {self.OUTPUT_FILES_DIR}")

                # 确保路径安全，防止目录遍历攻击
                if path == ".":
                    target_path = self.OUTPUT_FILES_DIR
                else:
                    # 将正斜杠路径转换为系统路径
                    system_path = path.replace('/', '\\') if '\\' in str(self.OUTPUT_FILES_DIR) else path
                    target_path = self.OUTPUT_FILES_DIR / system_path
                    target_path = target_path.resolve()
                
                print(f"目标路径: {target_path}")
                print(f"根目录: {self.OUTPUT_FILES_DIR}")

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.OUTPUT_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="路径不存在")

                if not target_path.is_dir():
                    raise HTTPException(status_code=400, detail="路径不是目录")

                files = []
                for item in target_path.iterdir():
                    try:
                        stat = item.stat()
                        is_directory = item.is_dir()

                        # 生成唯一ID
                        file_id = f"output_{abs(hash(str(item)))}"

                        # 获取文件类型
                        if is_directory:
                            file_type = "directory"
                        else:
                            file_type = self.get_content_type(item.suffix)

                        # 计算相对于根目录的路径，统一使用正斜杠
                        relative_path = str(item.relative_to(self.OUTPUT_FILES_DIR)).replace('\\', '/')
                        
                        file_info = OutputFileInfo(
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
                        # 跳过无法访问的文件
                        continue

                # 按类型和名称排序：目录在前，文件在后
                files.sort(key=lambda x: (not x.isDirectory, x.name.lower()))

                # 计算当前路径
                try:
                    current_path = str(target_path.relative_to(self.OUTPUT_FILES_DIR))
                    # 统一使用正斜杠作为路径分隔符
                    current_path = current_path.replace('\\', '/')
                    if current_path == ".":
                        current_path = "."
                except ValueError:
                    # 如果当前路径就是根目录
                    current_path = "."

                # 计算父目录路径
                parent_path = None
                if current_path != ".":
                    try:
                        parent_path = str(target_path.parent.relative_to(self.OUTPUT_FILES_DIR))
                        # 统一使用正斜杠作为路径分隔符
                        parent_path = parent_path.replace('\\', '/')
                        # 如果父目录是根目录，设置为"."，而不是None
                        if parent_path == ".":
                            parent_path = "."
                    except ValueError:
                        # 如果父目录不在根目录内，设置为None
                        parent_path = None
                
                return OutputFileListResp(
                    files=files,
                    currentPath=current_path,
                    parentPath=parent_path
                )

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"获取输出文件列表失败: {e}")
                print(f"详细错误信息: {error_details}")
                raise HTTPException(status_code=500, detail=f"获取输出文件列表失败: {str(e)}")

        @self.router.post("/output/upload")
        async def upload_to_output_directory(
            file: UploadFile = File(...),
            target_dir: str = Form(".")
        ):
            """上传文件到指定输出目录"""
            try:
                print(f"收到输出文件上传请求: 文件={file.filename}, 目标目录={target_dir}")
                # 确保目标目录安全
                if target_dir == ".":
                    target_path = self.OUTPUT_FILES_DIR
                else:
                    # 将正斜杠路径转换为系统路径
                    system_path = target_dir.replace('/', '\\') if '\\' in str(self.OUTPUT_FILES_DIR) else target_dir
                    target_path = self.OUTPUT_FILES_DIR / system_path
                    target_path = target_path.resolve()

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.OUTPUT_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="目标目录不存在")

                if not target_path.is_dir():
                    raise HTTPException(status_code=400, detail="目标路径不是目录")

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

            except Exception as e:
                print(f"上传文件到输出目录失败: {e}")
                raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

        @self.router.post("/output/delete")
        async def delete_output_file(file_path: str = Form(...)):
            """删除输出文件"""
            try:
                print(f"收到删除输出文件请求: 文件路径={file_path}")
                # 将正斜杠路径转换为系统路径
                system_path = file_path.replace('/', '\\') if '\\' in str(self.OUTPUT_FILES_DIR) else file_path
                
                # 确保路径安全
                target_path = self.OUTPUT_FILES_DIR / system_path
                target_path = target_path.resolve()

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.OUTPUT_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")

                if target_path.is_dir():
                    raise HTTPException(status_code=400, detail="不能删除目录")

                # 删除文件
                target_path.unlink()

                return {
                    "success": True,
                    "message": f"输出文件 {file_path} 已删除"
                }

            except Exception as e:
                print(f"删除输出文件失败: {e}")
                raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

        @self.router.get("/output/serve")
        async def serve_output_file(path: str):
            """提供输出文件下载服务"""
            try:
                # 将正斜杠路径转换为系统路径
                system_path = path.replace('/', '\\') if '\\' in str(self.OUTPUT_FILES_DIR) else path
                
                # 确保路径安全
                target_path = self.OUTPUT_FILES_DIR / system_path
                target_path = target_path.resolve()

                # 确保路径在允许的根目录内
                try:
                    target_path.relative_to(self.OUTPUT_FILES_DIR)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")

                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")

                if target_path.is_dir():
                    raise HTTPException(status_code=400, detail="路径是目录，不是文件")

                # 获取文件内容类型
                content_type = self.get_content_type(target_path.suffix)

                # 返回文件内容
                return FileResponse(
                    path=str(target_path),
                    media_type=content_type,
                    filename=target_path.name
                )

            except Exception as e:
                print(f"输出文件下载失败: {e}")
                raise HTTPException(status_code=500, detail=f"输出文件下载失败: {str(e)}")

    # ==================== 工具方法 ====================

    def get_content_type(self, ext: str) -> str:
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
            '.pdf': 'application/pdf'
        }
        return content_types.get(ext.lower(), 'application/octet-stream')

    def find_file_by_id(self, file_id: str) -> pathlib.Path:
        """根据文件ID查找文件路径"""
        for file_path in self.UPLOAD_DIR.iterdir():
            if file_path.is_file() and file_path.stem == file_id:
                return file_path
        return None