"""
文件管理API控制器 - 简化版，只管理数据集文件
"""

from typing import List

from fastapi import UploadFile, File, Form, Depends, Header
from fastapi.responses import StreamingResponse

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.model import DeleteFileRequest, CreateFolderRequest, BatchDeleteFilesRequest, FileInfo, FileListVO, UserVO
from src.server_agent.service import FileService, UserService
from src.server_agent.exceptions import AuthenticationError
from .base import BaseController


class FileController(BaseController):
    """文件控制器 - 管理数据集文件操作"""

    def __init__(self):
        super().__init__(prefix="/files", tags=[["文件管理"]])
        self.fileService = FileService()
        self.userService = UserService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.get("/dataset")
        async def getDataSetFiles(
            target_path: str = ".",
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[FileListVO]:
            """获取数据集文件列表"""
            fileListVO: FileListVO = await self.fileService.getDataSetFiles(target_path, userVO.uid)
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

        userVO: UserVO = await self.userService.get_user_by_token(token)
        if not userVO:
            raise AuthenticationError(
                detail="Invalid token",
                context={"token": token[:10] + "..." if len(token) > 10 else token}
            )
        return userVO
