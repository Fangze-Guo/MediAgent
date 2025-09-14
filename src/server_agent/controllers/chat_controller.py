"""
聊天相关API控制器
"""
from typing import List, Dict, Any
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from .base import BaseController


class ChatReq(BaseModel):
    conversation_id: str
    message: str
    history: List[Dict[str, Any]] = []
    files: List[Any] = []  # 这里应该是FileInfo类型，但为了避免循环导入暂时用List[Any]


class ChatResp(BaseModel):
    conversation_id: str
    answer: str
    tool_calls: List[Any] = []


class ChatController(BaseController):
    """聊天控制器"""
    
    def __init__(self):
        super().__init__(prefix="/chat", tags=["聊天"])
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.post("", response_model=ChatResp)
        async def chat(req: ChatReq):
            """普通聊天接口"""
            try:
                await self.ensure_initialized()
                
                msgs = [{"role": "system",
                         "content": "你可以在需要时调用可用工具来完成任务，工具返回JSON，请先解析后用中文总结关键结果。"}]
                msgs += req.history
                msgs += [{"role": "user", "content": req.message}]
                
                result = await self.agent.chat(msgs)
                return ChatResp(
                    conversation_id=req.conversation_id, 
                    answer=result["content"], 
                    tool_calls=result["tool_calls"]
                )
            except Exception as e:
                print(f"/chat 调用失败: {e}")
                raise HTTPException(status_code=500, detail=f"聊天服务错误: {str(e)}")
        
        @self.router.post("/stream")
        async def chat_stream(req: ChatReq):
            """流式聊天接口，支持实时输出"""
            try:
                await self.ensure_initialized()

                # 构建系统消息，包含文件信息
                system_content = "你是一个智能助手，可以调用工具来帮助用户完成任务。\n\n重要规则：\n1. 当需要调用工具时，请直接调用，不要输出<think>标签或思考过程\n2. 工具返回JSON格式，请解析后用中文总结关键结果\n3. 回复要简洁明了，避免冗余的思考过程"

                # 如果有文件，添加文件信息到系统消息
                if req.files:
                    system_content += f"\n\n可用文件："
                    for file in req.files:
                        if hasattr(file, 'type') and file.type.startswith('image/'):
                            system_content += f"\n- {file.originalName} → {file.path}"
                        elif hasattr(file, 'type') and 'csv' in file.type:
                            system_content += f"\n- {file.originalName} → {file.path}"
                        else:
                            system_content += f"\n- {file.originalName} → {file.path}"

                    system_content += f"\n\n注意：调用工具时使用完整路径，不要使用原始文件名。"

                msgs = [{"role": "system", "content": system_content}]
                msgs += req.history
                msgs += [{"role": "user", "content": req.message}]

                async def generate():
                    try:
                        # 发送开始信号
                        yield f"data: {json.dumps({'type': 'start', 'conversation_id': req.conversation_id}, ensure_ascii=False)}\n\n"

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
                        print(f"流式聊天错误: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )

            except Exception as e:
                print(f"/chat/stream 调用失败: {e}")
                raise HTTPException(status_code=500, detail=f"流式聊天服务错误: {str(e)}")
