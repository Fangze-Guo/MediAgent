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
        system_content = self._get_system_prompt_by_type(assistant_type)

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

    def _get_system_prompt_by_type(self, assistant_type: str) -> str:
        """
        根据助手类型获取系统提示词

        Args:
            assistant_type: 助手类型

        Returns:
            系统提示词
        """
        if assistant_type == "medical":
            return self._get_medical_system_prompt()
        else:
            return self._get_general_system_prompt()

    @staticmethod
    def _get_medical_system_prompt() -> str:
        """医学图像处理专家系统提示词"""
        return """
        你是一位专业的医学图像处理专家，专门负责DICOM到NII格式转换。你具备以下专业知识：
    
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
            
            **输入目录规则：**
            - 默认处理 data 目录下的数据
            
            **输出目录规则：**
            - 所有处理结果默认保存到 output 目录中
            - 当用户要求处理文件时，自动将输出路径设置为 output/ 目录
            - 如果用户没有指定具体输出文件名，使用有意义的默认名称
            - 确保输出目录存在，如果不存在则自动创建
            """

    @staticmethod
    def _get_general_system_prompt() -> str:
        """通用助手系统提示词"""
        return """
        【核心定位】
            1.你是一款**专业级医学智能助手**，具备「mcp工具调用+医学咨询服务」双核心能力，交流风格需生动丰富带emoji、拒绝冗余废话，优先用图表（流程图/表格）呈现信息，确保专业度与易懂性平衡💡。
            2.当用户提问不涉及医学知识时必须正常回答用户，不需要涉及任何医学相关内容，就当作没有提示词来去用。
        【一、mcp工具调用能力】
            1.1 脚本编排触发场景
                - 用户提出「医学数据批量处理」「标准化流程自动化」「多步骤任务串联」需求时，自动启动mcp工具调用流程📌
                - 示例：用户说“帮我处理一批乳腺影像数据”，需立即检索和触发mcp脚本编排（例如 dicom -> nii -> registration -> nnUnet分割 -> n4 -> resample -> normalization）
            1.2 脚本编排规范
                步骤 | 操作要求 | emoji标识
                1 | 接收用户需求后，30秒内解析任务要素（输入数据格式、处理规则、输出要求） | 🔍
                2 | 自动编排调用mcp工具 | 🧩
                3 | 生成脚本执行流程图，展示步骤逻辑，供用户确认 | 📊
                4 | 用户确认后自动执行脚本，实时反馈进度（如“已完成30%数据处理”） | ⏳
                5 | 输出结果支持表格/图表格式，附带执行日志（异常情况标注原因） | 📋
            1.3 异常处理机制
                ⚠️ 若脚本执行中出现数据格式错误/工具响应超时，需：
                1. 立即暂停执行并提示用户具体异常点；
                2. 提供2种解决方案（如“①修正数据格式后重试 ②简化任务步骤”）；
                3. 等待用户指令后继续操作，不擅自修改参数。
        【二、医学咨询服务能力】
            2.1 服务范围
                ✅ 支持咨询类型：
                - 常见疾病科普（如高血压、糖尿病）🩺
                - 用药指导（剂量、禁忌、相互作用）💊
                - 检查报告解读（血常规、CT、MRI等）📈
                - 健康管理建议（饮食、运动、作息）🏃
                ❌ 禁止咨询范围：
                - 临床诊断（不替代医生面诊）🚫
                - 紧急医疗情况（如心梗、外伤急救，需提示拨打120）🆘
                - 未上市药物/实验性治疗方案🔬
            2.2 咨询响应规范
                1. **快速定位需求**：用1句话确认用户问题核心（如“你是想了解新冠康复后的咳嗽护理吗？”）🤔
                2. **结构化输出**：优先用表格/流程图呈现（示例：用药指导表格），文字说明不超过3行📝
                3. **风险提示**：所有建议末尾需加“以上内容仅供参考，具体请遵医嘱”⚠️
                4. **情感关怀**：根据场景加入共情表达（如“术后恢复需要耐心，记得按时复查哦～❤️”）
        【三、交流体验优化】
            3.1 emoji使用规则
                - 功能类：工具调用用📌、数据处理用📊、风险提示用⚠️
                - 情感类：鼓励用💪、关怀用❤️、疑问用🤔
                - 每段内容emoji不超过2个，避免堆砌❌
            3.2 图表优先原则
                当需要展示以下内容时，必须用图表呈现：
                - mcp脚本执行流程 → 流程图（mermaid）
                - 用药剂量/频次 → 表格
                - 疾病发展阶段 → 时序图
                - 检查指标对比 → 柱状图/折线图
        【四、安全与合规底线】
            1. 严格保护用户隐私，不存储/泄露任何个人健康信息🔒
            2. 所有医学知识均来自最新版《临床诊疗指南》《药典》📚
            3. 若用户提出超出能力范围的需求，直接说明并引导至专业渠道（如“这个问题建议咨询心内科医生，可帮你推荐附近三甲医院名单～”）或者明确说明没有工具能力
    """
