"""
最简单的医学图像处理工具
只实现核心的DICOM到NII转换功能
"""
import json
import time
import uuid
from pathlib import Path
import SimpleITK as sitk
from mcp.server.fastmcp import FastMCP
from .base_tool import BaseTool
from ..controller.progress_controller import create_progress_task, update_task_progress


class MedicalTools(BaseTool):
    """最简单的医学图像处理工具类"""
    
    def __init__(self, mcp_server: FastMCP = None):
        super().__init__(mcp_server)
    
    def register_tools(self):
        """注册工具"""
        if not self.mcp_server:
            return
        
        # 单序列DICOM转换工具
        @self.mcp_server.tool()
        async def convert_dicom_series(
            dicom_directory: str,
            output_file: str,
            compression: bool = True
        ) -> str:
            """
            将单个DICOM序列转换为NII文件
            
            适用于：单个患者的单个序列转换
            输入：包含DICOM文件的目录
            输出：单个NII文件
            
            Args:
                dicom_directory: DICOM文件目录路径
                output_file: 输出NII文件路径（包含文件名）
                compression: 是否压缩输出文件
                
            Returns:
                JSON格式的处理结果
            """
            return await self._convert_single_series(
                dicom_directory, output_file, compression
            )
        
        # 多患者批量转换工具
        @self.mcp_server.tool()
        async def batch_convert_patients(
            patients_directory: str,
            output_directory: str,
            compression: bool = True
        ) -> str:
            """
            批量转换多个患者的DICOM数据
            
            适用于：多患者批量处理，自动识别C0/C2序列
            输入：包含多个患者文件夹的目录
            输出：按患者组织的NII文件
            
            Args:
                patients_directory: 患者文件夹目录（每个子文件夹为一个患者）
                output_directory: 输出目录
                compression: 是否压缩输出文件
                
            Returns:
                JSON格式的处理结果
            """
            return await self._batch_convert_patients(
                patients_directory, output_directory, compression
            )
    
    async def _convert_single_series(
        self, 
        dicom_dir: str, 
        output_file: str, 
        compression: bool = True
    ) -> str:
        """转换单个DICOM序列"""
        task_id = str(uuid.uuid4())
        create_progress_task(task_id, "开始单序列DICOM转换")
        
        try:
            # 步骤1: 验证输入目录
            update_task_progress(task_id, 10, "验证输入目录", "检查DICOM目录是否存在")
            dicom_path = Path(dicom_dir)
            if not dicom_path.exists() or not dicom_path.is_dir():
                update_task_progress(task_id, 100, "转换失败", f"DICOM目录不存在: {dicom_dir}")
                return self._json_response(400, stderr=f"DICOM目录不存在: {dicom_dir}")
            
            # 步骤2: 准备输出文件
            update_task_progress(task_id, 20, "准备输出文件", "设置输出文件路径和扩展名")
            output_path = Path(output_file)
            if compression and not output_path.suffix.endswith('.gz'):
                output_path = output_path.with_suffix(output_path.suffix + '.gz')
            elif not compression and output_path.suffix == '.gz':
                output_path = output_path.with_suffix('')
            
            # 创建输出目录
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 步骤3: 读取DICOM序列
            update_task_progress(task_id, 40, "读取DICOM序列", "正在读取DICOM文件...")
            image = self._read_dicom_series(dicom_path)
            
            # 步骤4: 写入NII文件
            update_task_progress(task_id, 70, "写入NII文件", "正在保存NII格式文件...")
            sitk.WriteImage(image, str(output_path))
            
            # 步骤5: 获取图像信息
            update_task_progress(task_id, 90, "获取图像信息", "正在分析图像属性...")
            size = image.GetSize()
            spacing = image.GetSpacing()
            
            # 步骤6: 完成
            update_task_progress(task_id, 100, "转换完成", f"成功转换DICOM序列到NII格式: {output_path}")
            
            result_info = {
                "output_file": str(output_path),
                "image_size": list(size),
                "spacing": list(spacing),
                "compression": compression,
                "series_type": "single",
                "task_id": task_id
            }
            
            return self._json_response(
                200, 
                stdout=f"成功转换DICOM序列到NII格式: {output_path}",
                extra=result_info
            )
            
        except Exception as e:
            update_task_progress(task_id, 100, "转换失败", f"转换过程中发生错误: {str(e)}")
            return self._json_response(500, stderr=f"转换过程中发生错误: {str(e)}")
    
    async def _batch_convert_patients(
        self,
        patients_dir: str,
        output_dir: str,
        compression: bool = True
    ) -> str:
        """批量转换多患者DICOM数据"""
        task_id = str(uuid.uuid4())
        create_progress_task(task_id, "开始多患者批量转换")
        
        try:
            # 步骤1: 验证患者目录
            update_task_progress(task_id, 5, "验证患者目录", "检查患者目录是否存在")
            patients_path = Path(patients_dir)
            output_path = Path(output_dir)
            
            if not patients_path.exists() or not patients_path.is_dir():
                update_task_progress(task_id, 100, "转换失败", f"患者目录不存在: {patients_dir}")
                return self._json_response(400, stderr=f"患者目录不存在: {patients_dir}")
            
            # 创建输出目录
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 步骤2: 查找所有患者目录
            update_task_progress(task_id, 10, "扫描患者目录", "正在查找所有患者文件夹...")
            patient_dirs = [d for d in patients_path.iterdir() if d.is_dir()]
            if not patient_dirs:
                update_task_progress(task_id, 100, "转换失败", "未找到患者目录")
                return self._json_response(400, stderr="未找到患者目录")
            
            results = []
            processed_count = 0
            total_patients = len(patient_dirs)
            
            # 步骤3: 批量处理患者
            for i, patient_dir in enumerate(patient_dirs):
                try:
                    progress = int(10 + (i / total_patients) * 80)
                    update_task_progress(task_id, progress, f"处理患者 {i+1}/{total_patients}", f"正在处理患者: {patient_dir.name}")
                    
                    # 查找C0和C2目录
                    c0_dir = patient_dir / "C0"
                    c2_dir = patient_dir / "C2"
                    
                    if not c0_dir.exists() or not c2_dir.exists():
                        results.append({
                            "patient_id": patient_dir.name,
                            "status": "skipped",
                            "error": "缺少C0或C2目录"
                        })
                        continue
                    
                    # 创建患者输出目录
                    patient_output_dir = output_path / patient_dir.name
                    patient_output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 转换C0序列
                    c0_image = self._read_dicom_series(c0_dir)
                    c0_output = patient_output_dir / ("C0.nii.gz" if compression else "C0.nii")
                    sitk.WriteImage(c0_image, str(c0_output))
                    
                    # 转换C2序列
                    c2_image = self._read_dicom_series(c2_dir)
                    c2_output = patient_output_dir / ("C2.nii.gz" if compression else "C2.nii")
                    sitk.WriteImage(c2_image, str(c2_output))
                    
                    result = {
                        "patient_id": patient_dir.name,
                        "c0_file": str(c0_output),
                        "c2_file": str(c2_output),
                        "c0_size": list(c0_image.GetSize()),
                        "c2_size": list(c2_image.GetSize()),
                        "c0_spacing": list(c0_image.GetSpacing()),
                        "c2_spacing": list(c2_image.GetSpacing()),
                        "status": "success"
                    }
                    results.append(result)
                    processed_count += 1
                    
                except Exception as e:
                    # 记录失败的患者
                    results.append({
                        "patient_id": patient_dir.name,
                        "status": "failed",
                        "error": str(e)
                    })
            
            # 步骤4: 完成
            update_task_progress(task_id, 100, "批量转换完成", f"成功处理{processed_count}个患者，共{total_patients}个患者目录")
            
            return self._json_response(
                200,
                stdout=f"批量转换完成，成功处理{processed_count}个患者，共{total_patients}个患者目录",
                extra={
                    "results": results,
                    "total_patients": total_patients,
                    "successful": processed_count,
                    "failed": total_patients - processed_count,
                    "series_type": "batch",
                    "task_id": task_id
                }
            )
            
        except Exception as e:
            update_task_progress(task_id, 100, "批量转换失败", f"批量转换过程中发生错误: {str(e)}")
            return self._json_response(500, stderr=f"批量转换过程中发生错误: {str(e)}")
    
    def _read_dicom_series(self, series_directory: Path) -> sitk.Image:
        """读取DICOM序列 - 使用你提供的代码"""
        reader = sitk.ImageSeriesReader()
        series_ids = reader.GetGDCMSeriesIDs(str(series_directory))
        
        if not series_ids:
            raise FileNotFoundError(f"No DICOM series found in {series_directory}")
        
        # 选择文件最多的序列
        best_file_names = []
        for series_id in series_ids:
            file_names = reader.GetGDCMSeriesFileNames(str(series_directory), series_id)
            if len(file_names) > len(best_file_names):
                best_file_names = file_names
        
        reader.SetFileNames(best_file_names)
        image = reader.Execute()
        return image
