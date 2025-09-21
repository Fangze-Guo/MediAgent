"""
聊天服务层
处理聊天相关的业务逻辑
"""
import json
import logging
from typing import List, Dict, Any, AsyncGenerator

from src.server_agent.exceptions import handle_service_exception
from src.server_agent.model.entity import ChatInfo

logger = logging.getLogger(__name__)


class ChatService:
    """聊天服务类"""

    def __init__(self, agent):
        self.agent = agent

    @handle_service_exception
    async def chat(self, conversation_id: str, message: str, history: List[Dict[str, Any]]) -> ChatInfo:
        """
        普通聊天服务
        
        Args:
            conversation_id: 会话ID
            message: 用户消息
            history: 历史消息

        Returns:
            聊天响应结果
        """
        # 构建消息列表
        msgs = [{"role": "system",
                 "content": "你可以在需要时调用可用工具来完成任务，工具返回JSON，请先解析后用中文总结关键结果。"}]
        msgs += history
        msgs += [{"role": "user", "content": message}]
        # 调用AI聊天
        chatInfo: ChatInfo = await self.agent.chat(msgs)
        return chatInfo

    @handle_service_exception
    async def chat_stream(self, conversation_id: str, message: str, history: List[Dict[str, Any]],
                          files: List[Any] = None,
                          assistant_type: str = "general") -> AsyncGenerator[str, None]:
        """
        流式聊天服务

        Args:
            conversation_id: 会话ID
            message: 用户消息
            history: 历史消息
            files: 关联文件列表
            assistant_type: 助手类型

        Yields:
            Server-Sent Events 格式的流式数据
        """

        try:
            # 构建系统消息
            system_content = self._build_system_content(files, assistant_type)

            # 构建消息列表
            msgs = [{"role": "system", "content": system_content}]
            msgs += history
            msgs += [{"role": "user", "content": message}]

            # 发送开始信号
            yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"

            # 流式获取AI回复
            try:
                async for chunk in self.agent.chat_stream(msgs):
                    if chunk and isinstance(chunk, dict) and 'type' in chunk:
                        if chunk['type'] == 'content':
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                        elif chunk['type'] == 'tool_call':
                            yield f"data: {json.dumps({'type': 'tool_call', 'tool': chunk['tool']}, ensure_ascii=False)}\n\n"
                        elif chunk['type'] == 'complete':
                            yield f"data: {json.dumps({'type': 'complete', 'tool_calls': chunk.get('tool_calls', [])}, ensure_ascii=False)}\n\n"
                            break
                    else:
                        logger.warning(f"收到无效的chunk: {chunk}")
                        continue
                
                # 确保总是发送结束信号
                yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"
                
            except Exception as stream_error:
                logger.error(f"流式处理错误: {stream_error}")
                yield f"data: {json.dumps({'type': 'error', 'error': f'流式处理错误: {str(stream_error)}'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"流式聊天服务错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"

    def _build_system_content(self, files: List[Any] = None, assistant_type: str = "general") -> str:
        """
        构建系统消息内容

        Args:
            files: 文件列表
            assistant_type: 助手类型 (medical, data, document, general)

        Returns:
            系统消息内容
        """
        # 根据助手类型和文件类型确定系统提示词
        system_content = self._get_system_prompt_by_type(assistant_type, files)

        # 如果有文件，添加文件信息到系统消息
        if files:
            logger.info(f"处理 {len(files)} 个文件")
            system_content += f"\n\n可用文件："

            for i, file in enumerate(files):
                logger.debug(f"文件 {i}: {type(file)} - {file}")

                # 处理字典格式的文件对象
                if isinstance(file, dict):
                    file_name = file.get('originalName', file.get('name', '未知文件'))
                    file_type = file.get('type', '')
                    file_path = file.get('path', '')
                else:
                    # 处理对象格式的文件
                    file_name = getattr(file, 'originalName', getattr(file, 'name', '未知文件'))
                    file_type = getattr(file, 'type', '')
                    file_path = getattr(file, 'path', '')

                if file_type.startswith('image/'):
                    system_content += f"\n- {file_name} → {file_path}"
                elif 'csv' in file_type:
                    system_content += f"\n- {file_name} → {file_path}"
                else:
                    system_content += f"\n- {file_name} → {file_path}"

            system_content += f"\n\n注意：调用工具时使用完整路径，不要使用原始文件名。"

        return system_content

    def _get_system_prompt_by_type(self, assistant_type: str, files: List[Any] = None) -> str:
        """
        根据助手类型获取系统提示词

        Args:
            assistant_type: 助手类型
            files: 文件列表

        Returns:
            系统提示词
        """
        # 检查文件类型以确定是否需要特殊处理
        has_medical_files = self._has_medical_files(files)

        if assistant_type == "medical" or has_medical_files:
            return self._get_medical_system_prompt()
        elif assistant_type == "data":
            return self._get_data_analysis_system_prompt()
        elif assistant_type == "document":
            return self._get_document_system_prompt()
        else:
            return self._get_general_system_prompt()

    def _has_medical_files(self, files: List[Any] = None) -> bool:
        """检查是否有医学图像文件"""
        if not files:
            return False

        for file in files:
            file_name = ""
            if isinstance(file, dict):
                file_name = file.get('originalName', file.get('name', ''))
            else:
                file_name = getattr(file, 'originalName', getattr(file, 'name', ''))

            if any(ext in file_name.lower() for ext in ['.dcm', '.dicom', '.nii', '.nii.gz']):
                return True
        return False

    def _get_medical_system_prompt(self) -> str:
        """医学图像处理专家系统提示词"""
        return """你是一位专业的医学图像处理专家，专门负责DICOM到NII格式转换。你具备以下专业知识：
    
    **专业背景：**
    - 深度理解DICOM (Digital Imaging and Communications in Medicine) 格式规范
    - 精通NIfTI (Neuroimaging Informatics Technology Initiative) 格式标准
    - 熟悉SimpleITK库的医学图像处理技术
    - 具备丰富的医学图像转换经验
    
    **技术能力：**
    - DICOM序列读取和解析
    - NII格式转换和质量保证
    - 空间信息保持（体素间距、图像方向、原点）
    - 元数据保留和验证
    - 批量处理和错误处理
    
    **服务原则：**
    1. 提供专业、详细的技术解释
    2. 根据用户需求推荐最佳转换策略
    3. 解释转换过程中的技术细节
    4. 提供质量优化建议
    5. 主动调用相关工具完成处理任务
    
    **重要规则：**
    - 当需要调用工具时，请直接调用，不要输出思考过程
    - 工具返回JSON格式，请解析后用中文总结关键结果
    - 回复要专业、详细，体现医学图像处理专家的水平
    - 主动提供技术建议和最佳实践
    
    **输出目录规则：**
    - 所有处理结果默认保存到 output 目录中
    - 当用户要求处理文件时，自动将输出路径设置为 output/ 目录
    - 如果用户没有指定具体输出文件名，使用有意义的默认名称
    - 确保输出目录存在，如果不存在则自动创建"""

    def _get_data_analysis_system_prompt(self) -> str:
        """数据分析专家系统提示词"""
        return """你是一位专业的数据分析专家，擅长数据清洗、分析和可视化。你具备以下专业知识：
    
    **专业背景：**
    - 精通Python数据科学栈（pandas, numpy, matplotlib, seaborn）
    - 熟悉统计分析和机器学习算法
    - 具备丰富的数据可视化经验
    - 了解各种数据格式和数据库操作
    
    **技术能力：**
    - 数据清洗和预处理
    - 统计分析和技术指标计算
    - 数据可视化（图表、仪表板）
    - 异常检测和数据质量评估
    - 报告生成和结果解释
    
    **服务原则：**
    1. 提供清晰的数据分析结果
    2. 解释分析方法和统计意义
    3. 提供可视化建议
    4. 主动调用相关工具完成分析任务
    
    **重要规则：**
    - 当需要调用工具时，请直接调用，不要输出思考过程
    - 工具返回JSON格式，请解析后用中文总结关键结果
    - 回复要专业、准确，体现数据分析专家的水平"""

    def _get_document_system_prompt(self) -> str:
        """文档处理专家系统提示词"""
        return """你是一位专业的文档处理专家，擅长各种文档格式的解析和处理。你具备以下专业知识：
    
    **专业背景：**
    - 精通PDF、Word、Excel等文档格式处理
    - 熟悉OCR技术和文本提取
    - 具备丰富的文档分析经验
    - 了解文档结构化和信息提取
    
    **技术能力：**
    - 文档格式转换
    - 文本提取和结构化
    - OCR文字识别
    - 文档内容分析
    - 批量文档处理
    
    **服务原则：**
    1. 提供准确的文档处理结果
    2. 解释处理方法和质量评估
    3. 提供格式转换建议
    4. 主动调用相关工具完成处理任务
    
    **重要规则：**
    - 当需要调用工具时，请直接调用，不要输出思考过程
    - 工具返回JSON格式，请解析后用中文总结关键结果
    - 回复要专业、准确，体现文档处理专家的水平"""

    def _get_general_system_prompt(self) -> str:
        """通用助手系统提示词"""
        return """你是一个智能助手，可以调用工具来帮助用户完成任务。
    
    **重要规则：**
    1. 当需要调用工具时，请直接调用，不要输出<think>标签或思考过程
    2. 工具返回JSON格式，请解析后用中文总结关键结果
    3. 回复要简洁明了，避免冗余的思考过程
    4. 根据用户需求主动推荐合适的工具"""
