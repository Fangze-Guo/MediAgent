"""
图像处理工具
"""
import os
from pathlib import Path
from PIL import Image, ImageOps
from typing import Annotated
from .base_tool import BaseTool


class ImageTools(BaseTool):
    """图像处理工具类"""
    
    def register_tools(self):
        """注册图像处理工具到MCP服务器"""
        if not self.mcp_server:
            return
            
        @self.mcp_server.tool()
        def resize_image(
            input_path: Annotated[str, "输入图片路径（绝对或相对）"],
            output_path: Annotated[str, "输出图片路径"],
            width: Annotated[int, "目标宽度，像素"],
            height: Annotated[int, "目标高度，像素"],
            timeout: Annotated[int, "超时时间(秒)"] = 60
        ) -> str:
            """调整图片大小"""
            return self.resize_image_impl(input_path, output_path, width, height, timeout)

        @self.mcp_server.tool()
        def get_image_info(
            image_path: Annotated[str, "图片路径"]
        ) -> str:
            """获取图片信息"""
            return self.get_image_info_impl(image_path)
    
    def resize_image_impl(
        self,
        input_path: str,
        output_path: str,
        width: int,
        height: int,
        timeout: int = 60
    ) -> str:
        """调整图片大小"""
        try:
            self._log_operation("resize_image", input_path=input_path, output_path=output_path, width=width, height=height)
            
            # 验证输入文件
            valid, error_msg, input_file = self._validate_file_path(input_path, must_exist=True)
            if not valid:
                return self._json_response(2, "", error_msg, {"args": {"input_path": input_path}})
            
            # 验证输出路径
            valid, error_msg, output_file = self._validate_file_path(output_path, must_exist=False)
            if not valid:
                return self._json_response(2, "", error_msg, {"args": {"output_path": output_path}})
            
            # 确保输出目录存在
            valid, error_msg = self._ensure_output_dir(output_file)
            if not valid:
                return self._json_response(2, "", error_msg)
            
            # 可读性预检
            try:
                with open(input_file, "rb") as f:
                    f.read(1)
            except Exception as e:
                return self._json_response(2, "", f"无法读取文件: {e}")
            
            # 处理图片
            try:
                with Image.open(input_file) as im:
                    # 处理EXIF方向
                    im = ImageOps.exif_transpose(im)
                    # 调整大小
                    im = im.resize((width, height))
                    # 保存图片
                    im.save(output_file)
                
                result_msg = f"图片调整成功: {output_file}"
                self.log(f"[resize_image] {result_msg}")
                
                return self._json_response(
                    0, 
                    result_msg, 
                    "",
                    {
                        "input_path": str(input_file),
                        "output_path": str(output_file),
                        "original_size": Image.open(input_file).size,
                        "new_size": (width, height)
                    }
                )
                
            except Exception as e:
                error_msg = f"图片处理失败: {e}"
                self.log(f"[resize_image] ERROR: {error_msg}")
                return self._json_response(1, "", error_msg)
                
        except Exception as e:
            error_msg = f"调整图片大小异常: {e}"
            self.log(f"[resize_image] EXCEPTION: {error_msg}")
            return self._json_response(1, "", error_msg)
    
    def get_image_info_impl(
        self,
        image_path: str
    ) -> str:
        """获取图片信息"""
        try:
            self._log_operation("get_image_info", image_path=image_path)
            
            # 验证文件
            valid, error_msg, image_file = self._validate_file_path(image_path, must_exist=True)
            if not valid:
                return self._json_response(2, "", error_msg)
            
            # 获取图片信息
            with Image.open(image_file) as im:
                info = {
                    "filename": image_file.name,
                    "format": im.format,
                    "mode": im.mode,
                    "size": im.size,
                    "width": im.width,
                    "height": im.height,
                    "has_transparency": im.mode in ('RGBA', 'LA') or 'transparency' in im.info
                }
                
                # 获取文件大小
                file_size = image_file.stat().st_size
                info["file_size_bytes"] = file_size
                info["file_size_mb"] = round(file_size / (1024 * 1024), 2)
            
            result_msg = f"图片信息获取成功: {image_file.name}"
            self.log(f"[get_image_info] {result_msg}")
            
            return self._json_response(0, result_msg, "", {"image_info": info})
            
        except Exception as e:
            error_msg = f"获取图片信息失败: {e}"
            self.log(f"[get_image_info] ERROR: {error_msg}")
            return self._json_response(1, "", error_msg)
