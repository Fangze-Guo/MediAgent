"""
聊天服务层
处理聊天相关的业务逻辑
"""
from typing import List, Dict, Any, AsyncGenerator
import json
import logging

from src.server_agent.exceptions import ServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class ChatService:
    """聊天服务类"""
    
    def __init__(self, agent):
        self.agent = agent
    
    @handle_service_exception
    async def chat(self, conversation_id: str, message: str, history: List[Dict[str, Any]], files: List[Any] = None) -> Dict[str, Any]:
        """
        普通聊天服务
        
        Args:
            conversation_id: 会话ID
            message: 用户消息
            history: 历史消息
            files: 关联文件列表
            
        Returns:
            聊天响应结果
        """
        try:
            # 构建消息列表
            msgs = [{"role": "system",
                     "content": "你可以在需要时调用可用工具来完成任务，工具返回JSON，请先解析后用中文总结关键结果。"}]
            msgs += history
            msgs += [{"role": "user", "content": message}]
            
            # 调用AI聊天
            result = await self.agent.chat(msgs)
            
            return {
                "conversation_id": conversation_id,
                "answer": result["content"],
                "tool_calls": result["tool_calls"]
            }
            
        except Exception as e:
            logger.error(f"聊天服务错误: {e}")
            raise ServiceError(
                detail="聊天服务错误",
                service_name="chat_service",
                context={"conversation_id": conversation_id, "error": str(e)}
            )
    
    @handle_service_exception
    async def chat_stream(self, conversation_id: str, message: str, history: List[Dict[str, Any]], files: List[Any] = None) -> AsyncGenerator[str, None]:
        """
        流式聊天服务
        
        Args:
            conversation_id: 会话ID
            message: 用户消息
            history: 历史消息
            files: 关联文件列表
            
        Yields:
            Server-Sent Events 格式的流式数据
        """
        try:
            # 构建系统消息
            system_content = self._build_system_content(files)
            
            # 构建消息列表
            msgs = [{"role": "system", "content": system_content}]
            msgs += history
            msgs += [{"role": "user", "content": message}]
            
            # 发送开始信号
            yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            
            # 流式获取AI回复
            async for chunk in self.agent.chat_stream(msgs):
                if chunk['type'] == 'content':
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                elif chunk['type'] == 'tool_call':
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': chunk['tool']}, ensure_ascii=False)}\n\n"
                elif chunk['type'] == 'complete':
                    yield f"data: {json.dumps({'type': 'complete', 'tool_calls': chunk.get('tool_calls', [])}, ensure_ascii=False)}\n\n"
                    break
                    
        except Exception as e:
            logger.error(f"流式聊天服务错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
    
    def _build_system_content(self, files: List[Any] = None) -> str:
        """
        构建系统消息内容
        
        Args:
            files: 文件列表
            
        Returns:
            系统消息内容
        """
        system_content = "你是一个智能助手，可以调用工具来帮助用户完成任务。\n\n重要规则：\n1. 当需要调用工具时，请直接调用，不要输出<think>标签或思考过程\n2. 工具返回JSON格式，请解析后用中文总结关键结果\n3. 回复要简洁明了，避免冗余的思考过程"
        
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
