"""
文件系统沙箱 - 限制文件访问在项目目录内
"""
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FileSystemSandbox:
    """文件系统沙箱，限制文件访问在项目目录内"""
    
    def __init__(self, base_dir: Path):
        """
        初始化沙箱
        
        Args:
            base_dir: 项目根目录（绝对路径）
        """
        # 确保 base_dir 是绝对路径并解析所有符号链接
        self.base_dir = base_dir.resolve()
        
        if not self.base_dir.is_absolute():
            raise ValueError(f"base_dir 必须是绝对路径: {base_dir}")
        
        logger.info(f"初始化文件系统沙箱: base_dir={self.base_dir}")
    
    def validate_path(self, path: str | Path) -> bool:
        """
        验证路径是否在项目目录内
        
        Args:
            path: 要验证的路径（可以是相对路径或绝对路径）
        
        Returns:
            True 如果路径在项目目录内，False 否则
        """
        try:
            # 转换为 Path 对象
            target_path = Path(path)
            
            # 如果是相对路径，相对于 base_dir 解析
            if not target_path.is_absolute():
                target_path = self.base_dir / target_path
            
            # 解析所有符号链接和 .. 路径
            # 注意：resolve() 会解析符号链接，这正是我们需要的
            # 如果路径不存在，resolve() 仍会规范化路径
            try:
                resolved_path = target_path.resolve()
            except (OSError, RuntimeError) as e:
                # 路径解析失败（例如循环符号链接）
                logger.warning(f"路径解析失败: {path}, 错误: {e}")
                return False
            
            # 检查解析后的路径是否在 base_dir 内
            # 使用 is_relative_to (Python 3.9+) 或手动检查
            try:
                # Python 3.9+
                is_inside = resolved_path.is_relative_to(self.base_dir)
            except AttributeError:
                # Python 3.8 及以下，手动检查
                try:
                    resolved_path.relative_to(self.base_dir)
                    is_inside = True
                except ValueError:
                    is_inside = False
            
            if not is_inside:
                logger.warning(
                    f"路径访问被拒绝: {path} -> {resolved_path} "
                    f"(不在 {self.base_dir} 内)"
                )
                return False
            
            logger.debug(f"路径验证通过: {path} -> {resolved_path}")
            return True
            
        except Exception as e:
            logger.error(f"路径验证异常: {path}, 错误: {e}")
            return False
    
    def safe_read(self, path: str | Path) -> Optional[bytes]:
        """
        安全读取文件
        
        Args:
            path: 文件路径
        
        Returns:
            文件内容，如果路径不合法或读取失败则返回 None
        """
        if not self.validate_path(path):
            logger.error(f"拒绝读取文件: {path} (路径不在项目目录内)")
            return None
        
        try:
            target_path = Path(path)
            if not target_path.is_absolute():
                target_path = self.base_dir / target_path
            
            resolved_path = target_path.resolve()
            
            with open(resolved_path, 'rb') as f:
                content = f.read()
            
            logger.info(f"成功读取文件: {resolved_path}")
            return content
            
        except Exception as e:
            logger.error(f"读取文件失败: {path}, 错误: {e}")
            return None
    
    def safe_write(self, path: str | Path, content: bytes) -> bool:
        """
        安全写入文件
        
        Args:
            path: 文件路径
            content: 文件内容
        
        Returns:
            True 如果写入成功，False 否则
        """
        if not self.validate_path(path):
            logger.error(f"拒绝写入文件: {path} (路径不在项目目录内)")
            return False
        
        try:
            target_path = Path(path)
            if not target_path.is_absolute():
                target_path = self.base_dir / target_path
            
            resolved_path = target_path.resolve()
            
            # 确保父目录存在
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(resolved_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"成功写入文件: {resolved_path}")
            return True
            
        except Exception as e:
            logger.error(f"写入文件失败: {path}, 错误: {e}")
            return False
