"""
医学咨询服务类
处理医学咨询相关的业务逻辑
"""

import json
import os
from typing import AsyncGenerator, List

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from src.server_agent.exceptions import handle_service_exception


class MedicalConsultationService:
    """医学咨询服务类"""

    def __init__(self, model: ChatOpenAI = None):
        """
        初始化服务

        Args:
            model: LangChain 聊天模型实例，如果为 None 则使用默认配置
        """
        if model is None:
            self.model = ChatOpenAI(
                model="Baichuan-M3",
                api_key=os.getenv("BAICHUAN_API_KEY"),
                base_url=os.getenv("BAICHUAN_BASE_URL"),
                streaming=True,
            )
        else:
            self.model = model

    @handle_service_exception
    async def stream_chat(
        self, messages: List[dict], current_message: str
    ) -> AsyncGenerator[str, None]:
        """
        流式对话方法

        Args:
            messages: 历史消息列表，格式为 [{"role": "user|assistant", "content": "..."}]
            current_message: 当前用户消息

        Yields:
            SSE 格式的 JSON 字符串，每个 chunk 都使用 BaseResponse 格式
        """
        from src.server_agent.common import ResultUtils

        # 转换消息格式为 LangChain 格式
        langchain_messages = []
        for message in messages:
            if message.get("role") == "user":
                langchain_messages.append(
                    HumanMessage(content=message.get("content", ""))
                )
            elif message.get("role") == "assistant":
                langchain_messages.append(AIMessage(content=message.get("content", "")))

        # 添加当前消息
        langchain_messages.append(HumanMessage(content=current_message))

        try:
            full_content = ""
            # 使用异步流式方法
            async for chunk in self.model.astream(langchain_messages):
                if chunk.content:
                    full_content += chunk.content
                    # 使用 ResultUtils 格式包装每个 chunk
                    response = ResultUtils.success(
                        {
                            "content": chunk.content,
                            "full_content": full_content,
                            "done": False,
                        }
                    )
                    # 转换为 JSON 并发送 SSE 格式
                    data = json.dumps(
                        {
                            "code": response.code,
                            "data": response.data,
                            "message": response.message,
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {data}\n\n"

            # 发送最终完成响应
            final_response = ResultUtils.success(
                {"content": "", "full_content": full_content, "done": True}
            )
            final_data = json.dumps(
                {
                    "code": final_response.code,
                    "data": final_response.data,
                    "message": final_response.message,
                },
                ensure_ascii=False,
            )
            yield f"data: {final_data}\n\n"
        except Exception as e:
            # 发送错误响应（使用 ResultUtils 格式）
            error_response = ResultUtils.error(500, f"流式输出失败: {str(e)}")
            error_data = json.dumps(
                {
                    "code": error_response.code,
                    "data": error_response.data,
                    "message": error_response.message,
                },
                ensure_ascii=False,
            )
            yield f"data: {error_data}\n\n"

    @handle_service_exception
    async def chat(self, messages: List[dict], current_message: str) -> str:
        """
        同步对话方法（用于非流式场景）

        Args:
            messages: 历史消息列表
            current_message: 当前用户消息

        Returns:
            AI 回复内容
        """
        # 转换消息格式为 LangChain 格式
        langchain_messages = []
        for message in messages:
            if message.get("role") == "user":
                langchain_messages.append(
                    HumanMessage(content=message.get("content", ""))
                )
            elif message.get("role") == "assistant":
                langchain_messages.append(AIMessage(content=message.get("content", "")))

        # 添加当前消息
        langchain_messages.append(HumanMessage(content=current_message))

        # 非流式调用
        response = await self.model.ainvoke(langchain_messages)
        return response.content
