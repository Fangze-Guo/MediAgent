"""
聊天相关API控制器
"""
from typing import List, Dict, Any
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .base import BaseController
from ..service import ChatService


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
        self.chat_service = ChatService(self.agent)
        self._register_routes()
    
    def _register_routes(self):
        """注册路由"""
        
        @self.router.post("", response_model=ChatResp)
        async def chat(req: ChatReq):
            """普通聊天接口"""
            await self.ensure_initialized()
            result = await self.chat_service.chat(
                conversation_id=req.conversation_id,
                message=req.message,
                history=req.history,
                files=req.files
            )
            return ChatResp(**result)
        
        @self.router.post("/stream")
        async def chat_stream(req: ChatReq):
            """流式聊天接口，支持实时输出"""
            await self.ensure_initialized()
            
            async def generate():
                async for chunk in self.chat_service.chat_stream(
                    conversation_id=req.conversation_id,
                    message=req.message,
                    history=req.history,
                    files=req.files
                ):
                    yield chunk
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
