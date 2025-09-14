"""
本地文件浏览API控制器
"""
import pathlib
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, UploadFile, File
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
    files: List[LocalFileInfo]
    currentPath: str
    parentPath: Optional[str] = None


class LocalFileController(BaseController):
    """本地文件控制器"""

    def __init__(self):
        super().__init__(prefix="/local-files", tags=["本地文件"])

        # 本地文件浏览配置
        self.LOCAL_FILES_DIR = pathlib.Path(".").resolve()  # 当前目录的绝对路径

        self._register_routes()

    def _register_routes(self):
        """注册路由"""

        @self.router.get("", response_model=LocalFileListResp)
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

        @self.router.post("/upload")
        async def upload_to_local_directory(
            file: UploadFile = File(...),
            target_dir: str = "."
        ):
            """上传文件到指定本地目录"""
            try:
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

        @self.router.post("/delete")
        async def delete_local_file(file_path: str):
            """删除本地文件"""
            try:
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

        @self.router.get("/serve")
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
