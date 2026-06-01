"""
文件管理API控制器 - 简化版，只管理数据集文件
"""

from typing import Iterator, List
import io
import pathlib
import queue
import threading
from urllib.parse import quote
import zipfile

from fastapi import UploadFile, File, Form, Depends, Header, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.model import DeleteFileRequest, CreateFolderRequest, BatchDeleteFilesRequest, RenameFileRequest, FileInfo, FileListVO, UserVO
from src.server_agent.service import FileService, UserService
from src.server_agent.service.OssService import OssService
from src.server_agent.exceptions import AuthenticationError, ValidationError
from src.server_agent.constants.CommonConstants import DATASET_PATH
from .base import BaseController


class PresignRequest(BaseModel):
    conversation_id: str
    filename: str
    content_type: str


class _ZipStreamWriter(io.RawIOBase):
    """将 zipfile 产生的数据块转交给 StreamingResponse。"""

    def __init__(self, chunks: queue.Queue, stopped: threading.Event):
        self.chunks = chunks
        self.stopped = stopped
        self.offset = 0

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def tell(self) -> int:
        return self.offset

    def write(self, data: bytes) -> int:
        if not data:
            return 0
        while not self.stopped.is_set():
            try:
                self.chunks.put(data, timeout=0.5)
                self.offset += len(data)
                return len(data)
            except queue.Full:
                continue
        raise BrokenPipeError("download cancelled")


class FileController(BaseController):
    """文件控制器 - 管理数据集文件操作"""

    def __init__(self):
        super().__init__(prefix="/files", tags=[["文件管理"]])
        self.fileService = FileService()
        self.userService = UserService()
        self.ossService = OssService()
        self._register_routes()

    def _register_routes(self):
        """注册所有路由"""

        @self.router.post("/chat/presign")
        async def getChatImagePresignUrl(
            body: PresignRequest,
            userVO: UserVO = Depends(self._get_current_user),
        ) -> BaseResponse[dict]:
            """生成聊天图片 OSS 预签名上传 URL（前端直传）"""
            result = self.ossService.generate_presign_url(
                user_id=str(userVO.uid),
                conversation_id=body.conversation_id,
                filename=body.filename,
                content_type=body.content_type,
            )
            return ResultUtils.success(result)

        @self.router.get("/serve/{file_id:path}")
        async def serveFile(
            file_id: str,
            download: bool = Query(False, description="是否强制下载文件"),
        ):
            """提供文件下载/预览接口"""
            try:
                # 获取文件完整路径 - file_id 是相对于 DATASET_PATH 的路径
                # 例如: "public/image.png" 或 "private/user123/dataset/photo.jpg"
                dataset_root = pathlib.Path(DATASET_PATH)
                file_path = dataset_root / file_id
                
                # 安全检查：防止路径遍历攻击
                try:
                    file_path = file_path.resolve()
                    root = dataset_root.resolve()
                    if not str(file_path).startswith(str(root)):
                        return ResultUtils.error(403, "Access denied")
                except Exception:
                    return ResultUtils.error(403, "Invalid path")
                
                # 检查文件是否存在
                if not file_path.exists() or not file_path.is_file():
                    return ResultUtils.error(404, "File not found")
                
                # 判断是否可在浏览器内联预览
                import mimetypes as _mt
                content_type, _ = _mt.guess_type(str(file_path))
                if content_type is None:
                    content_type = "application/octet-stream"

                INLINE_TYPES = {
                    "application/pdf",
                    "text/plain",
                    "text/html",
                    "text/markdown",
                    "text/csv",
                    "image/jpeg",
                    "image/png",
                    "image/gif",
                    "image/webp",
                    "image/svg+xml",
                }

                if download:
                    return FileResponse(
                        path=file_path,
                        filename=file_path.name,
                        media_type=content_type,
                    )
                elif content_type in INLINE_TYPES:
                    return FileResponse(
                        path=file_path,
                        media_type=content_type,
                        headers={"Content-Disposition": "inline"},
                    )
                else:
                    return FileResponse(
                        path=file_path,
                        filename=file_path.name,
                        media_type=content_type,
                    )
            except Exception as e:
                return ResultUtils.error(500, f"Error serving file: {str(e)}")

        @self.router.post("/archive")
        async def downloadArchive(
            file_ids: List[str] = Form(...),
            token: str = Form(...),
            archive_name: str = Form("dataset-download.zip"),
        ) -> StreamingResponse:
            """将选中的文件和目录打包为 ZIP，并以流式响应下载。"""
            userVO = await self.userService.get_user_by_token(token)
            if not userVO:
                raise AuthenticationError(detail="Invalid token")

            targets = self._resolve_archive_targets(file_ids, userVO)
            archive_name = pathlib.Path(archive_name).name
            if not archive_name.lower().endswith(".zip"):
                archive_name = f"{archive_name}.zip"
            headers = {
                "Content-Disposition": (
                    'attachment; filename="dataset-download.zip"; '
                    f"filename*=UTF-8''{quote(archive_name)}"
                ),
                "Cache-Control": "no-store",
            }
            return StreamingResponse(
                self._stream_zip(targets),
                media_type="application/zip",
                headers=headers,
            )

        @self.router.get("/dataset")
        async def getDataSetFiles(
            target_path: str = ".",
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[FileListVO]:
            """获取数据集文件列表"""
            fileListVO: FileListVO = await self.fileService.getDataSetFiles(target_path, userVO.uid, userVO.role)
            return ResultUtils.success(fileListVO)

        @self.router.get("/task")
        async def getTaskFiles(
            target_path: str = ".",
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[FileListVO]:
            """获取任务文件列表"""
            fileListVO: FileListVO = await self.fileService.getTaskFiles(target_path, userVO.uid, userVO.role)
            return ResultUtils.success(fileListVO)

        @self.router.post("/upload")
        async def uploadFile(
                file: UploadFile = File(...),
                target_dir: str = Form("."),
                userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[FileInfo]:
            """上传文件到数据集"""
            try:
                fileInfo: FileInfo = await self.fileService.uploadFileToData(file, target_dir, userVO.uid, userVO.role)
                return ResultUtils.success(fileInfo)
            except Exception as e:
                # 捕获所有异常并返回详细错误信息
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"文件上传失败: {error_message}")

        @self.router.post("/upload-multiple")
        async def uploadMultipleFiles(
                files: List[UploadFile] = File(...),
                target_dir: str = Form("."),
                userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[List[FileInfo]]:
            """批量上传文件到数据集"""
            try:
                uploaded_files: List[FileInfo] = await self.fileService.uploadMultipleFilesToData(files, target_dir, userVO.uid, userVO.role)
                return ResultUtils.success(uploaded_files)
            except Exception as e:
                # 捕获所有异常并返回详细错误信息
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"批量上传失败: {error_message}")

        @self.router.post("/delete")
        async def deleteFile(
            request: DeleteFileRequest,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[None]:
            """删除文件"""
            try:
                await self.fileService.deleteUploadFileById(request.fileId, userVO.uid, userVO.role)
                return ResultUtils.success(None)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"删除失败: {error_message}")

        @self.router.post("/batch-delete")
        async def batchDeleteFiles(
            request: BatchDeleteFilesRequest,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[dict]:
            """批量删除文件"""
            try:
                result = await self.fileService.batchDeleteUploadFilesById(request.fileIds, userVO.uid, userVO.role)
                return ResultUtils.success(result)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"批量删除失败: {error_message}")

        @self.router.post("/create-folder")
        async def createFolder(request: CreateFolderRequest) -> BaseResponse[None]:
            """创建文件夹"""
            await self.fileService.createFolder(request.folderName, request.currentPath)
            return ResultUtils.success(None)

        @self.router.post("/rename")
        async def renameFile(
            request: RenameFileRequest,
            userVO: UserVO = Depends(self._get_current_user)
        ) -> BaseResponse[FileInfo]:
            """重命名文件或文件夹"""
            try:
                fileInfo: FileInfo = await self.fileService.renameUploadFileById(
                    request.fileId, request.newName, userVO.uid, userVO.role
                )
                return ResultUtils.success(fileInfo)
            except Exception as e:
                error_message = str(e)
                if hasattr(e, 'detail'):
                    error_message = e.detail
                return ResultUtils.error(400, f"重命名失败: {error_message}")

    # ==================== 工具方法 ====================

    @staticmethod
    def _resolve_archive_targets(file_ids: List[str], userVO: UserVO) -> List[pathlib.Path]:
        dataset_root = pathlib.Path(DATASET_PATH).resolve()
        targets = []

        for file_id in dict.fromkeys(file_ids):
            target = (dataset_root / file_id).resolve()
            try:
                relative_path = target.relative_to(dataset_root)
            except ValueError:
                raise ValidationError(detail="访问被拒绝", context={"path": file_id})

            if not target.exists():
                raise ValidationError(detail="文件或目录不存在", context={"path": file_id})

            parts = relative_path.parts
            if userVO.role != "admin":
                is_public = len(parts) >= 1 and parts[0] == "public"
                is_own_private = (
                    len(parts) >= 2
                    and parts[0] == "private"
                    and parts[1] == str(userVO.uid)
                )
                if not is_public and not is_own_private:
                    raise ValidationError(detail="无权下载该文件或目录", context={"path": file_id})

            targets.append(target)

        if not targets:
            raise ValidationError(detail="请选择要下载的文件或目录")
        return targets

    @staticmethod
    def _stream_zip(targets: List[pathlib.Path]) -> Iterator[bytes]:
        chunks: queue.Queue = queue.Queue(maxsize=16)
        stopped = threading.Event()
        completed = object()

        def produce_zip():
            writer = _ZipStreamWriter(chunks, stopped)
            try:
                with zipfile.ZipFile(writer, "w", compression=zipfile.ZIP_STORED) as archive:
                    for target in targets:
                        if target.is_symlink():
                            continue
                        if target.is_file():
                            archive.write(target, arcname=target.name)
                            continue

                        wrote_entry = False
                        for child in target.rglob("*"):
                            if child.is_symlink():
                                continue
                            archive_name = pathlib.Path(target.name) / child.relative_to(target)
                            if child.is_dir():
                                archive.writestr(f"{archive_name.as_posix()}/", "")
                            elif child.is_file():
                                archive.write(child, arcname=archive_name.as_posix())
                            wrote_entry = True
                        if not wrote_entry:
                            archive.writestr(f"{target.name}/", "")
            except BrokenPipeError:
                pass
            finally:
                if not stopped.is_set():
                    chunks.put(completed)

        threading.Thread(target=produce_zip, daemon=True).start()
        try:
            while True:
                chunk = chunks.get()
                if chunk is completed:
                    break
                yield chunk
        finally:
            stopped.set()

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
