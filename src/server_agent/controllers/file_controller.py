"""
文件管理API控制器
"""
import pathlib
import shutil
from datetime import datetime
from fastapi import HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .base import BaseController


class FileInfo(BaseModel):
    id: str
    originalName: str
    size: int
    type: str
    path: str
    uploadTime: str


class FileUploadResp(BaseModel):
    success: bool
    file: FileInfo = None
    error: str = None


class FileListResp(BaseModel):
    files: list[FileInfo]


class DeleteFileReq(BaseModel):
    fileId: str


class DeleteFileResp(BaseModel):
    success: bool
    error: str = None


class BatchDeleteFilesReq(BaseModel):
    fileIds: list[str]


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


class FileController(BaseController):
    """文件控制器"""
    
    def __init__(self):
        super().__init__(prefix="/files", tags=["文件管理"])
        
        # 文件上传配置
        self.UPLOAD_DIR = pathlib.Path("uploads")
        self.UPLOAD_DIR.mkdir(exist_ok=True)
        self.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        self.ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.csv'}
        
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
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
    
    def get_content_type(self, ext: str) -> str:
        """根据文件扩展名获取内容类型"""
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.csv': 'text/csv'
        }
        return content_types.get(ext.lower(), 'application/octet-stream')
    
    def find_file_by_id(self, file_id: str) -> pathlib.Path:
        """根据文件ID查找文件路径"""
        for file_path in self.UPLOAD_DIR.iterdir():
            if file_path.is_file() and file_path.stem == file_id:
                return file_path
        return None
