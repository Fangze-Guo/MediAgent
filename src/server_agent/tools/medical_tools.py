"""
医学图像处理工具
支持完整的医学图像处理流程：DICOM -> NII -> Registration -> nnUNet -> N4 -> Resample -> Normalization
"""
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP

from .base_tool import BaseTool

# 尝试导入进度控制器
try:
    from ..controller.progress_controller import create_progress_task, update_task_progress
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    try:
        from src.server_agent.controller.progress_controller import create_progress_task, update_task_progress
    except ImportError:
        # 如果都失败了，创建简单的替代函数
        def create_progress_task(task_id: str, message: str):
            print(f"[{task_id}] {message}")


        def update_task_progress(task_id: str, progress: int, status: str, message: str):
            print(f"[{task_id}] {progress}% - {status}: {message}")

# 导入医学图像处理管道
try:
    from ..script.medical_pipeline import (
        MedicalImagePipeline,
        ProcessingStep,
        StepStatus,
        medical_process_patient,
        medical_process_all_patients,
        medical_get_patient_status,
        medical_get_all_patients_status
    )
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    try:
        from src.server_agent.script.medical_pipeline import (
            MedicalImagePipeline,
            ProcessingStep,
            StepStatus,
            medical_process_patient,
            medical_process_all_patients,
            medical_get_patient_status,
            medical_get_all_patients_status
        )
    except ImportError:
        # 如果都失败了，创建简单的替代函数
        def medical_process_patient(patient_id: str, data_root: str, steps: List[str] = None) -> Dict[str, Any]:
            return {"error": "医学图像处理管道未正确导入"}


        def medical_process_all_patients(data_root: str, steps: List[str] = None) -> Dict[str, Any]:
            return {"error": "医学图像处理管道未正确导入"}


        def medical_get_patient_status(patient_id: str, data_root: str) -> Dict[str, Any]:
            return {"error": "医学图像处理管道未正确导入"}


        def medical_get_all_patients_status(data_root: str) -> Dict[str, Any]:
            return {"error": "医学图像处理管道未正确导入"}


class MedicalTools(BaseTool):
    """医学图像处理工具类 - 支持完整的处理流程"""

    def __init__(self, mcp_server: FastMCP = None):
        super().__init__(mcp_server)
        self.pipeline_cache: Dict[str, MedicalImagePipeline] = {}

    def register_tools(self):
        """注册工具"""
        if not self.mcp_server:
            return

        # 完整医学图像处理流程工具
        @self.mcp_server.tool()
        def process_medical_images(
                data_root: str,
                patient_id: Optional[str] = None,
                steps: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """
            执行完整的医学图像处理流程
            
            支持的处理步骤：
            - dicom_to_nii: DICOM转NII格式
            - registration: 图像配准
            - nnunet_segmentation: nnUNet分割
            - n4_correction: N4偏置场校正
            - resample: 重采样
            - normalization: 归一化
            
            Args:
                data_root: 数据根目录路径（包含0_DICOM等子目录）
                patient_id: 患者ID，如果为None则处理所有患者
                steps: 要执行的处理步骤列表，如果为None则执行所有步骤
                
            Returns:
                处理结果字典，包含成功/失败状态和详细信息
            """
            task_id = str(uuid.uuid4())
            create_progress_task(task_id, f"开始医学图像处理流程")

            try:
                # 处理相对路径，转换为绝对路径
                data_root_path = Path(data_root)
                if not data_root_path.is_absolute():
                    # 如果是相对路径，尝试几种可能的路径
                    possible_paths = [
                        Path("src/server_agent/data"),  # 从项目根目录
                        Path("data"),  # 从当前工作目录
                        Path("../data"),  # 从上级目录
                    ]
                    
                    for possible_path in possible_paths:
                        if possible_path.exists():
                            data_root_path = possible_path
                            break
                    else:
                        # 如果都找不到，使用默认路径
                        data_root_path = Path("src/server_agent/data")
                
                # 确保路径存在
                if not data_root_path.exists():
                    return {
                        "success": False,
                        "error": f"数据目录不存在: {data_root_path}",
                        "task_id": task_id,
                        "suggested_paths": [str(p) for p in possible_paths if p.exists()]
                    }
                
                if patient_id:
                    # 处理单个患者
                    result = medical_process_patient(patient_id, str(data_root_path), steps)
                    update_task_progress(task_id, 100, "completed", f"患者 {patient_id} 处理完成")
                else:
                    # 处理所有患者
                    result = medical_process_all_patients(str(data_root_path), steps)
                    update_task_progress(task_id, 100, "completed", f"所有患者处理完成")

                return result

            except Exception as e:
                update_task_progress(task_id, 0, "failed", f"处理失败: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "task_id": task_id
                }

        # 获取患者状态工具
        @self.mcp_server.tool()
        def get_patient_status(
                data_root: str,
                patient_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            获取患者处理状态
            
            Args:
                data_root: 数据根目录路径
                patient_id: 患者ID，如果为None则获取所有患者状态
                
            Returns:
                患者状态信息
            """
            try:
                # 处理相对路径，转换为绝对路径
                data_root_path = Path(data_root)
                if not data_root_path.is_absolute():
                    possible_paths = [
                        Path("src/server_agent/data"),
                        Path("data"),
                        Path("../data"),
                    ]
                    
                    for possible_path in possible_paths:
                        if possible_path.exists():
                            data_root_path = possible_path
                            break
                    else:
                        data_root_path = Path("src/server_agent/data")
                
                if patient_id:
                    return medical_get_patient_status(patient_id, str(data_root_path))
                else:
                    return medical_get_all_patients_status(str(data_root_path))
            except Exception as e:
                return {
                    "error": str(e),
                    "success": False
                }

        # 单步骤处理工具
        @self.mcp_server.tool()
        def process_single_step(
                data_root: str,
                patient_id: str,
                step: str
        ) -> Dict[str, Any]:
            """
            执行单个处理步骤
            
            Args:
                data_root: 数据根目录路径
                patient_id: 患者ID
                step: 处理步骤名称
                
            Returns:
                步骤执行结果
            """
            task_id = str(uuid.uuid4())
            create_progress_task(task_id, f"开始执行步骤: {step}")

            try:
                # 处理相对路径，转换为绝对路径
                data_root_path = Path(data_root)
                if not data_root_path.is_absolute():
                    possible_paths = [
                        Path("src/server_agent/data"),
                        Path("data"),
                        Path("../data"),
                    ]
                    
                    for possible_path in possible_paths:
                        if possible_path.exists():
                            data_root_path = possible_path
                            break
                    else:
                        data_root_path = Path("src/server_agent/data")
                
                result = medical_process_patient(patient_id, str(data_root_path), [step])
                update_task_progress(task_id, 100, "completed", f"步骤 {step} 执行完成")
                return result
            except Exception as e:
                update_task_progress(task_id, 0, "failed", f"步骤 {step} 执行失败: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "task_id": task_id
                }

        # 获取可用处理步骤工具
        @self.mcp_server.tool()
        def get_available_steps() -> List[str]:
            """
            获取可用的处理步骤列表
            
            Returns:
                处理步骤名称列表
            """
            try:
                return [step.value for step in ProcessingStep]
            except Exception as e:
                return [f"error: {str(e)}"]

        # 获取数据目录结构工具
        @self.mcp_server.tool()
        def get_data_structure(data_root: str) -> Dict[str, Any]:
            """
            获取数据目录结构信息
            
            Args:
                data_root: 数据根目录路径
                
            Returns:
                目录结构信息
            """
            try:
                # 处理相对路径，转换为绝对路径
                data_root_path = Path(data_root)
                if not data_root_path.is_absolute():
                    possible_paths = [
                        Path("src/server_agent/data"),
                        Path("data"),
                        Path("../data"),
                    ]
                    
                    for possible_path in possible_paths:
                        if possible_path.exists():
                            data_root_path = possible_path
                            break
                    else:
                        data_root_path = Path("src/server_agent/data")
                
                structure = {}

                # 检查各个处理阶段的目录
                stages = {
                    "0_DICOM": "原始DICOM数据",
                    "1_NII": "NII格式数据",
                    "2_Reg": "配准后数据",
                    "3_N4": "N4校正后数据",
                    "4_Res": "重采样后数据",
                    "5_Norm": "归一化后数据"
                }

                for stage, description in stages.items():
                    stage_path = data_root_path / stage
                    structure[stage] = {
                        "path": str(stage_path),
                        "exists": stage_path.exists(),
                        "description": description,
                        "patient_count": 0
                    }

                    if stage_path.exists():
                        # 统计患者数量
                        patient_dirs = [d for d in stage_path.iterdir() if d.is_dir()]
                        structure[stage]["patient_count"] = len(patient_dirs)
                        structure[stage]["patients"] = [d.name for d in patient_dirs]

                return {
                    "success": True,
                    "data_root": str(data_root_path),
                    "structure": structure
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
