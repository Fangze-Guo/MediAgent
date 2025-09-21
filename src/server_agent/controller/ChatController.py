"""
聊天相关API控制器
"""
from __future__ import annotations

import json
from typing import List, Any

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.server_agent.common import ResultUtils, BaseResponse
from src.server_agent.model import ChatRequest
from src.server_agent.model.entity.ChatInfo import ChatInfo
from src.server_agent.service import ChatService
from .base import BaseController


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
        async def chat(request: ChatRequest) -> "BaseResponse[ChatInfo]":
            """普通聊天接口"""
            await self.ensure_initialized()
            chatInfo: ChatInfo = await self.chatService.chat(
                conversation_id=request.conversation_id,
                message=request.message,
                history=request.history,
                files=request.files,
                assistant_type=request.assistant_type
            )
            return ResultUtils.success(chatInfo)

        @self.router.post("/stream")
        async def chat_stream(request: ChatRequest):
            """流式聊天接口，支持实时输出"""
            await self.ensure_initialized()

            async def generate():
                try:
                    async for chunk in self.chatService.chat_stream(
                            conversation_id=request.conversation_id,
                            message=request.message,
                            history=request.history,
                            files=request.files,
                            assistant_type=request.assistant_type
                    ):
                        yield chunk
                except Exception as e:
                    # 确保在异常情况下也发送结束信号
                    yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"

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
