"""
文件管理API控制器 - 统一管理所有文件操作
"""

from fastapi import UploadFile, File, Form

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.model import DeleteFileRequest, CreateFolderRequest, BatchDeleteFilesRequest, FileInfo, FileListVO
from src.server_agent.service import FileService
from .base import BaseController


# ==================== 主控制器 ====================

class FileController(BaseController):
    """统一文件控制器 - 管理所有文件操作"""

    def __init__(self):
        super().__init__(prefix="/files", tags=[["文件管理"]])
        self.fileService = FileService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        # ==================== 已上传文件路由 ====================

        @self.router.post("/upload")
        async def uploadFileToData(
                file: UploadFile = File(...),
                target_dir: str = Form(".")
        ) -> BaseResponse[FileInfo]:
            """上传文件接口"""
            file: FileInfo = await self.fileService.uploadFileToData(file, target_dir)
            return ResultUtils.success(file)

        @self.router.get("")
        async def listFiles(path: str = ".") -> BaseResponse[FileListVO]:
            """获取已上传文件列表"""
            fileListVO: FileListVO = await self.fileService.getUploadFils(path)
            return ResultUtils.success(fileListVO)

        @self.router.post("/delete")
        async def deleteFile(request: DeleteFileRequest) -> BaseResponse[None]:
            """删除单个文件"""
            await self.fileService.deleteUploadFileById(request.fileId)
            return ResultUtils.success(None)

        @self.router.post("/create-folder")
        async def createFolder(request: CreateFolderRequest) -> BaseResponse[None]:
            """创建文件夹"""
            await self.fileService.createFolder(request.folderName, request.currentPath)
            return ResultUtils.success(None)

        @self.router.post("/batch-delete")
        async def batchDeleteFiles(request: BatchDeleteFilesRequest) -> BaseResponse[dict]:
            """批量删除文件"""
            result = await self.fileService.batchDeleteUploadFilesById(request.fileIds)
            return ResultUtils.success(result)

        # ==================== 本地文件路由 ====================

        @self.router.get("/local")
        async def listLocalFiles(path: str = ".") -> BaseResponse[FileListVO]:
            """获取本地文件列表"""
            localFileListVO: FileListVO = await self.fileService.getLocalFiles(path)
            return ResultUtils.success(localFileListVO)

        @self.router.post("/local/upload")
        async def uploadFileToLocal(
                file: UploadFile = File(...),
                target_dir: str = Form(".")
        ) -> BaseResponse[FileInfo]:
            """上传文件到指定本地目录"""
            file: FileInfo = await self.fileService.uploadFileToLocal(file, target_dir)
            return ResultUtils.success(file)

        @self.router.post("/local/delete")
        async def delete_local_file(file_path: str = Form(...)) -> BaseResponse[None]:
            """删除本地文件"""
            await self.fileService.deleteLocalFile(file_path)
            return ResultUtils.success(None)

        # ==================== 输出文件路由 ====================

        @self.router.get("/output")
        async def list_output_files(path: str = ".") -> BaseResponse[FileListVO]:
            """获取输出文件列表"""
            outputFileListVO: FileListVO = await self.fileService.getOutputFiles(path)
            return ResultUtils.success(outputFileListVO)

        @self.router.post("/output/upload")
        async def uploadFileToOutput(
                file: UploadFile = File(...),
                target_dir: str = Form(".")
        ) -> BaseResponse[FileInfo]:
            """上传文件到指定输出目录"""
            file: FileInfo = await self.fileService.uploadFileToOutput(file, target_dir)
            return ResultUtils.success(file)

        @self.router.post("/output/delete")
        async def delete_output_file(file_path: str = Form(...)) -> BaseResponse[None]:
            """删除输出文件"""
            await self.fileService.deleteOutputFile(file_path)
            return ResultUtils.success(None)
