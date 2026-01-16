from typing import List

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.server_agent.common import BaseResponse, ResultUtils
from src.server_agent.service.clinical_tools.MedicalConsultationService import MedicalConsultationService
from ..base import BaseController


class ChatMessage(BaseModel):
    role: str  # "user" 或 "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    message: str  # 当前消息


class MedicalConsultationController(BaseController):
    def __init__(self):
        super().__init__(prefix="/medical-consultation", tags=["医学咨询"])
        self.service = MedicalConsultationService()
        self._register_routes()

    def _register_routes(self):
        @self.router.post("/taking")
        async def taking(request: ChatRequest) -> StreamingResponse:
            """流式对话接口，支持消息历史"""
            # 转换消息格式
            messages_dict = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            
            # 调用 Service 的流式方法
            async def generate_stream():
                async for chunk in self.service.stream_chat(messages_dict, request.message):
                    yield chunk
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.router.post("/taking/sync")
        async def taking_sync(request: ChatRequest) -> BaseResponse[str]:
            """同步对话接口（用于接口文档测试）"""
            try:
                # 转换消息格式
                messages_dict = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.messages
                ]
                
                # 调用 Service 的同步方法
                response_content = await self.service.chat(messages_dict, request.message)
                return ResultUtils.success(response_content)
            except Exception as e:
                return ResultUtils.error(500, f"对话失败: {str(e)}")
