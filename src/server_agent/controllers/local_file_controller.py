"""
本地文件浏览API控制器
"""
import pathlib
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel

from .base import BaseController


class LocalFileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str
    path: str
    modifiedTime: str
    isDirectory: bool


class LocalFileListResp(BaseModel):
    files: list[LocalFileInfo]
    currentPath: str
    parentPath: str = None


class LocalFileController(BaseController):
    """本地文件控制器"""
    
    def __init__(self):
        super().__init__(prefix="/local-files", tags=["本地文件"])
        
        # 本地文件浏览配置
        self.LOCAL_FILES_DIR = pathlib.Path(".")  # 当前目录，可以根据需要修改
        
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.get("", response_model=LocalFileListResp)
        async def list_local_files(path: str = "."):
            """获取本地文件列表"""
            try:
                # 确保路径安全，防止目录遍历攻击
                target_path = self.LOCAL_FILES_DIR / path
                target_path = target_path.resolve()
                
                # 确保路径在允许的根目录内
                root_path = self.LOCAL_FILES_DIR.resolve()
                try:
                    target_path.relative_to(root_path)
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
                        file_id = f"local_{hash(str(item))}"
                        
                        # 获取文件类型
                        if is_directory:
                            file_type = "directory"
                        else:
                            file_type = self.get_content_type(item.suffix)
                        
                        file_info = LocalFileInfo(
                            id=file_id,
                            name=item.name,
                            size=stat.st_size if not is_directory else 0,
                            type=file_type,
                            path=str(item.resolve()),
                            modifiedTime=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            isDirectory=is_directory
                        )
                        files.append(file_info)
                    except (OSError, PermissionError):
                        # 跳过无法访问的文件
                        continue
                
                # 按类型和名称排序：目录在前，文件在后
                files.sort(key=lambda x: (not x.isDirectory, x.name.lower()))
                
                # 计算父目录路径
                parent_path = None
                if target_path != self.LOCAL_FILES_DIR:
                    parent_path = str(target_path.parent.relative_to(self.LOCAL_FILES_DIR))
                    if parent_path == ".":
                        parent_path = None
                
                return LocalFileListResp(
                    files=files,
                    currentPath=str(target_path.relative_to(self.LOCAL_FILES_DIR)),
                    parentPath=parent_path
                )
                
            except Exception as e:
                print(f"获取本地文件列表失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取本地文件列表失败: {str(e)}")
        
        @self.router.get("/serve")
        async def serve_local_file(path: str):
            """提供本地文件下载服务"""
            try:
                # 确保路径安全
                target_path = self.LOCAL_FILES_DIR / path
                target_path = target_path.resolve()
                
                # 确保路径在允许的根目录内
                root_path = self.LOCAL_FILES_DIR.resolve()
                try:
                    target_path.relative_to(root_path)
                except ValueError:
                    raise HTTPException(status_code=403, detail="访问被拒绝")
                
                if not target_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")
                
                if target_path.is_dir():
                    raise HTTPException(status_code=400, detail="路径是目录，不是文件")
                
                # 获取文件内容类型
                content_type = self.get_content_type(target_path.suffix)
                
                # 返回文件内容
                from fastapi.responses import FileResponse
                return FileResponse(
                    path=str(target_path),
                    media_type=content_type,
                    filename=target_path.name
                )
                
            except Exception as e:
                print(f"本地文件下载失败: {e}")
                raise HTTPException(status_code=500, detail=f"本地文件下载失败: {str(e)}")
    
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
