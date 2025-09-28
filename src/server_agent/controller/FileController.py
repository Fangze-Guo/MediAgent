"""
文件管理API控制器 - 简化版，只管理数据集文件
"""

from typing import List

from fastapi import UploadFile, File, Form

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.model import DeleteFileRequest, CreateFolderRequest, BatchDeleteFilesRequest, FileInfo, FileListVO
from src.server_agent.service import FileService
from .base import BaseController


class FileController(BaseController):
    """文件控制器 - 管理数据集文件操作"""

    def __init__(self):
        super().__init__(prefix="/files", tags=[["文件管理"]])
        self.fileService = FileService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.get("/dataset")
        async def getDataSetFiles(target_path: str = ".") -> BaseResponse[FileListVO]:
            """获取数据集文件列表"""
            fileListVO: FileListVO = await self.fileService.getDataSetFiles(target_path)
            return ResultUtils.success(fileListVO)

        @self.router.post("/upload")
        async def uploadFile(
                file: UploadFile = File(...),
                target_dir: str = Form(".")
        ) -> BaseResponse[FileInfo]:
            """上传文件到数据集"""
            fileInfo: FileInfo = await self.fileService.uploadFileToData(file, target_dir)
            return ResultUtils.success(fileInfo)

        @self.router.post("/upload-multiple")
        async def uploadMultipleFiles(
                files: List[UploadFile] = File(...),
                target_dir: str = Form(".")
        ) -> BaseResponse[List[FileInfo]]:
            """批量上传文件到数据集"""
            uploaded_files: List[FileInfo] = await self.fileService.uploadMultipleFilesToData(files, target_dir)
            return ResultUtils.success(uploaded_files)

        @self.router.post("/delete")
        async def deleteFile(request: DeleteFileRequest) -> BaseResponse[None]:
            """删除文件"""
            await self.fileService.deleteUploadFileById(request.fileId)
            return ResultUtils.success(None)

        @self.router.post("/batch-delete")
        async def batchDeleteFiles(request: BatchDeleteFilesRequest) -> BaseResponse[dict]:
            """批量删除文件"""
            result = await self.fileService.batchDeleteUploadFilesById(request.fileIds)
            return ResultUtils.success(result)

        @self.router.post("/create-folder")
        async def createFolder(request: CreateFolderRequest) -> BaseResponse[None]:
            """创建文件夹"""
            await self.fileService.createFolder(request.folderName, request.currentPath)
            return ResultUtils.success(None)
