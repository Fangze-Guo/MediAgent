"""
文件管理API控制器 - 统一管理所有文件操作
"""
from typing import List, Optional

from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.server_agent.service import FileService
from .base import BaseController


# ==================== 数据模型 ====================

class FileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str
    path: str
    modifiedTime: str
    isDirectory: bool


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
    currentPath: str
    parentPath: Optional[str] = None


class CreateFolderRequest(BaseModel):
    folderName: str
    currentPath: str = "."


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
        self.file_service = FileService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        # ==================== 已上传文件路由 ====================

        @self.router.post("/upload", response_model=FileUploadResp)
        async def upload_file(file: UploadFile = File(...)):
            """上传文件接口"""
            result = await self.file_service.upload_file(file)
            return FileUploadResp(**result)

        @self.router.get("", response_model=FileListResp)
        async def list_files(path: str = "."):
            """获取已上传文件列表"""
            result = await self.file_service.get_files_list(path)
            return FileListResp(**result)

        @self.router.post("/delete", response_model=DeleteFileResp)
        async def delete_file(req: DeleteFileReq):
            """删除单个文件"""
            result = await self.file_service.delete_file(req.fileId)
            return DeleteFileResp(**result)

        @self.router.post("/batch-delete", response_model=BatchDeleteFilesResp)
        async def batch_delete_files(req: BatchDeleteFilesReq):
            """批量删除文件"""
            result = await self.file_service.batch_delete_files(req.fileIds)
            return BatchDeleteFilesResp(**result)

        @self.router.post("/download", response_model=DownloadFileResp)
        async def download_file(req: DownloadFileReq):
            """获取文件下载URL"""
            result = await self.file_service.get_download_url(req.fileId)
            return DownloadFileResp(**result)

        @self.router.get("/serve/{file_id}")
        async def serve_file(file_id: str):
            """提供文件下载服务"""
            file_path, content_type = await self.file_service.serve_file(file_id)
            return FileResponse(
                path=str(file_path),
                media_type=content_type,
                filename=file_path.name
            )

        # ==================== 本地文件路由 ====================

        @self.router.get("/local", response_model=LocalFileListResp)
        async def list_local_files(path: str = "."):
            """获取本地文件列表"""
            result = await self.file_service.browse_local_files(path)
            return LocalFileListResp(**result)

        @self.router.post("/local/upload")
        async def upload_to_local_directory(
                file: UploadFile = File(...),
                target_dir: str = Form(".")
        ):
            """上传文件到指定本地目录"""
            return await self.file_service.upload_to_local_directory(file, target_dir)

        @self.router.post("/local/delete")
        async def delete_local_file(file_path: str = Form(...)):
            """删除本地文件"""
            return await self.file_service.delete_local_file(file_path)

        @self.router.get("/local/serve")
        async def serve_local_file(path: str):
            """提供本地文件下载服务"""
            file_path, content_type = await self.file_service.serve_local_file(path)
            return FileResponse(
                path=str(file_path),
                media_type=content_type,
                filename=file_path.name
            )

        # ==================== 输出文件路由 ====================

        @self.router.get("/output", response_model=OutputFileListResp)
        async def list_output_files(path: str = "."):
            """获取输出文件列表"""
            result = await self.file_service.browse_output_files(path)
            return OutputFileListResp(**result)

        @self.router.post("/output/upload")
        async def upload_to_output_directory(
                file: UploadFile = File(...),
                target_dir: str = Form(".")
        ):
            """上传文件到指定输出目录"""
            return await self.file_service.upload_to_output_directory(file, target_dir)

        @self.router.post("/output/delete")
        async def delete_output_file(file_path: str = Form(...)):
            """删除输出文件"""
            return await self.file_service.delete_output_file(file_path)

        @self.router.get("/output/serve")
        async def serve_output_file(path: str):
            """提供输出文件下载服务"""
            file_path, content_type = await self.file_service.serve_output_file(path)
            return FileResponse(
                path=str(file_path),
                media_type=content_type,
                filename=file_path.name
            )

        @self.router.post("/create-folder")
        async def create_folder(request: CreateFolderRequest):
            """创建文件夹"""
            return await self.file_service.create_folder(request.folderName, request.currentPath)
