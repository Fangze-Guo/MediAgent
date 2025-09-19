"""
聊天相关API控制器
"""
from typing import List, Dict, Any

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .base import BaseController
from src.server_agent.service import ChatService
from src.server_agent.model import ChatRequest


class ChatResp(BaseModel):
    conversation_id: str
    answer: str
    tool_calls: List[Any] = []


class ChatController(BaseController):
    """聊天控制器"""

    def __init__(self):
        super().__init__(prefix="/chat", tags=["聊天"])
        self.chatService = ChatService(self.agent)
        self._register_routes()

    def _register_routes(self):
        """注册路由"""

        @self.router.post("")
        async def chat(request: ChatRequest):
            """普通聊天接口"""
            await self.ensure_initialized()
            result = await self.chatService.chat(
                conversation_id=request.conversation_id,
                message=request.message,
                history=request.history,
                files=request.files,
                assistant_type=request.assistant_type
            )
            return ChatResp(**result)

        @self.router.post("/stream")
        async def chat_stream(req: ChatReq):
            """流式聊天接口，支持实时输出"""
            await self.ensure_initialized()

            async def generate():
                async for chunk in self.chatService.chat_stream(
                        conversation_id=req.conversation_id,
                        message=req.message,
                        history=req.history,
                        files=req.files,
                        assistant_type=req.assistant_type
                ):
                    yield chunk

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                },
            )
