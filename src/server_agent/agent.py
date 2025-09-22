import asyncio
import json
from typing import Any, List

import httpx  # 用于更精细地捕获底层 HTTP 异常
from openai import AsyncOpenAI

from src.server_agent.constants.EnvConfig import BASE_URL, API_KEY, MODEL
from src.server_agent.mcp_client import load_all_clients
from src.server_agent.model.entity import ToolCallInfo, ChatInfo

# === 可按需调整的超时/重试策略（集中配置更清晰） ===
LLM_REQUEST_TIMEOUT_SEC = 60  # 单次 LLM 请求的总超时（上层保护）
LLM_CLIENT_TIMEOUT_SEC = 60  # AsyncOpenAI 内部 httpx 的超时
TOOL_CALL_OUTER_TIMEOUT_SEC = 360  # 对 MCP 工具调用再套一层总超时，防止卡住


class MCPAgent:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=BASE_URL,
            api_key=API_KEY,
            timeout=LLM_CLIENT_TIMEOUT_SEC,  # 负责和LLM直接对话，将用户的输入格式化传入给LLM，将LLM的格式化输出解析为具体行为，如回复直接传给用户，调用工具则进行调用
            # max_retries=0,  # 如需禁用 SDK 的自动重试可打开
        )
        self.mcp_clients = []  # MCP 工具服连接池。它让你的 Agent 能够同时管理多台 MCP 服务器，统一发现工具，并把每次工具调用路由到正确的那台服务器
        self.tools = []  # OpenAI tools schema
        self._tool_map = {}  # name -> mcp_client
        # 动态维护工具列表和工具到服务器的映射，但是目前没有做重名工具的处理，后续有需要可能需要添加命名空间的功能

    async def init_tools(self):
        """
        初始化所有 MCP 工具，加载所有 MCP 客户端并获取其工具列表。

        该方法会异步加载所有可用的 MCP 客户端，并从每个客户端获取工具列表，
        然后将其转换为 OpenAI 兼容的工具格式，供模型调用。

        工具信息将被存储在以下属性中：
        - self.tools: OpenAI 格式的工具列表，用于模型调用
        - self._tool_map: 工具名称到 MCP 客户端的映射，用于后续调用
        - self.mcp_clients: 所有已加载的 MCP 客户端列表

        如果加载失败或没有可用客户端，将清空工具列表并使用纯 LLM 模式。
        """
        try:
            self.mcp_clients = await load_all_clients()
            self.tools.clear()
            self._tool_map.clear()

            if not self.mcp_clients:
                print("警告: 没有可用的MCP客户端，将使用纯LLM模式")
                return

            # 汇总所有 MCP 服务器的工具
            for mc in self.mcp_clients:
                try:
                    tl = await mc.list_tools()
                    for t in tl:
                        name = t["name"]
                        # 如需防止不同服务器重名工具冲突，这里可引入命名空间（如 f"{mc.server_name}.{name}"）
                        self.tools.append({
                            "type": "function",
                            "function": {
                                "name": name,
                                "description": t["description"],
                                "parameters": t["input_schema"]  # 直接使用
                            }
                        })  # 把 MCP 的工具描述（t["name"] / t["description"] / t["input_schema"]）转换为 OpenAI 工具列表（self.tools）——这样模型才能用 tool_calls 方式"请求调用"这些工具
                        self._tool_map[name] = mc
                    print(f"从MCP客户端加载了 {len(tl)} 个工具")
                except Exception as e:
                    print(f"MCP客户端工具加载失败: {e}")
                    continue

            print(f"总共加载了 {len(self.tools)} 个工具")
            for tool in self.tools:
                print(f"工具: {tool['function']['name']}")

        except Exception as e:
            print(f"MCP工具初始化失败: {e}")
            print("将使用纯LLM模式（无工具）")
            self.mcp_clients = []
            self.tools = []
            self._tool_map = {}

    async def _call_tool(self, name: str, arguments_json: str | dict[str, Any]) -> str:
        """
        调用指定名称的工具，并返回结构化的结果字符串。

        参数:
            name: 工具名称，用于在工具映射中查找对应的MCP客户端
            arguments_json: 工具调用参数，可以是JSON字符串或字典格式

        返回值:
            str: 工具调用结果的JSON字符串，包含成功结果或错误信息
        """
        # —— 解析参数 & 路由到对应的 MCP 客户端 ——
        args = json.loads(arguments_json) if isinstance(arguments_json, str) else (arguments_json or {})
        mc = self._tool_map.get(name)
        if mc is None:
            # 约定：把工具的“结构化结果JSON字符串”返回给模型（这里返回一个规范化的错误对象）
            return json.dumps(
                {"error": "tool_not_found", "name": name, "detail": f"tool '{name}' not registered"},
                ensure_ascii=False
            )

        # —— 对 MCP 调用再套一层总超时，避免底层异常时无限等待（scripts 里也有自己的 timeout） ——
        try:
            result = await asyncio.wait_for(mc.call_tool(name, args), timeout=TOOL_CALL_OUTER_TIMEOUT_SEC)
            # 约定：把工具的“结构化结果JSON字符串”返回给模型
            return json.dumps(result, ensure_ascii=False, default=str)
        except asyncio.TimeoutError:
            return json.dumps(
                {"error": "tool_timeout", "name": name, "timeout": TOOL_CALL_OUTER_TIMEOUT_SEC, "args": args},
                ensure_ascii=False
            )
        except Exception as e:
            # 兜底异常，保证回灌到模型时是 JSON 字符串而不是直接抛异常
            return json.dumps(
                {"error": "tool_exception", "name": name, "detail": str(e), "args": args},
                ensure_ascii=False
            )

    async def chat(self, messages: list[dict], max_iters=5) -> ChatInfo:
        """
        执行一轮对话交互，支持工具调用和多轮内部迭代。

        参数:
            messages (list[dict]): 包含历史对话消息的列表，每条消息格式为 {"role": "...", "content": "..."}。
                                   通常由用户发起，例如 [{"role": "user", "content": "你好"}]。
            max_iters (int): 最大工具调用迭代次数，防止无限循环调用，默认值为 5。

        返回:
            ChatInfo: 模型最终的回复内容，格式为 {"role": "assistant", "content": "...", "tool_calls": [...]}。
                      如果发生错误或超时，也会返回对应的提示信息。
        """
        # 处理一轮对话，要实现上下文功能还需要外部控制
        # 一轮对话内模型可能多次调用工具，这边属于LLM和agent之间的内部行为，直到LLM不再调用工具才认为已经可以向用户返回结果了
        tool_calls_log: List[ToolCallInfo] = []

        # 若当前没有任何工具（例如 init_tools 失败），仍允许纯 LLM 对话
        for _ in range(max_iters):
            # —— 用 asyncio.wait_for 给整次 LLM 推理包一层保护超时 ——
            try:
                # 构建请求参数，只有当有工具时才包含tools参数
                request_params = {
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.2,
                }

                # 只有当工具列表不为空时才添加tools参数
                if self.tools:
                    request_params["tools"] = self.tools
                    request_params["tool_choice"] = "auto"
                    print(f"使用工具模式，工具数量: {len(self.tools)}")
                else:
                    print("使用纯LLM模式（无工具）")

                resp = await asyncio.wait_for(
                    self.client.chat.completions.create(**request_params),
                    timeout=LLM_REQUEST_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                # 返回一个清晰可见的文本给前端/用户
                return ChatInfo(role="assistant", content="(LLM 调用超时)", tool_calls=tool_calls_log)
            except httpx.HTTPError as e:
                # 捕获底层网络错误（连接失败、读超时、TLS 等）
                return ChatInfo(role="assistant", content="(LLM 底层网络异常)", tool_calls=tool_calls_log)
            except Exception as e:
                # 其他非预期异常兜底
                return ChatInfo(role="assistant", content="(LLM 响应异常)", tool_calls=tool_calls_log)

            # —— 解析模型输出（严格防御：choices 为空/无 message 等情况） ——
            if not resp.choices:
                return ChatInfo(role="assistant", content="(LLM 无可用结果)", tool_calls=tool_calls_log)
            choice = resp.choices[0]
            msg = getattr(choice, "message", None)
            if msg is None:
                return ChatInfo(role="assistant", content="(LLM 响应格式异常：缺少 message)", tool_calls=tool_calls_log)
            if getattr(msg, "tool_calls", None):
                # 模型要求调用工具（可能一次或多次）
                for tc in msg.tool_calls:
                    name = tc.function.name
                    arguments = tc.function.arguments or "{}"
                    tool_result = await self._call_tool(name, arguments)
                    tool_calls_log.append({"name": name, "arguments": arguments, "result": tool_result})
                    # 把工具结果回灌给模型
                    messages.append({
                        "role": "assistant",
                        "tool_calls": [tc.model_dump()]  # 保留记录
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result
                    })
                continue
            else:
                # 没有更多工具调用，返回最终答案
                return ChatInfo("assistant", content=(msg.content or ""), tool_calls=tool_calls_log)

        # 超过迭代上限也返回（避免死循环）
        return {"role": "assistant", "content": "(对话达到最大迭代次数)", "tool_calls": tool_calls_log}

    async def chat_stream(self, messages: list[dict], max_iters=5):
        """
        流式聊天方法，逐步返回AI回复内容。支持工具调用与纯LLM对话模式。

        参数:
            messages (list[dict]): 聊天历史消息列表，格式如 [{"role": "user", "content": "..."}]。
            max_iters (int): 最大迭代次数，用于限制工具调用的循环次数，默认为5次。

        返回:
            异步生成器，产生字典对象，包含以下几种类型：
                - {"type": "content", "content": "..."}：模型逐步输出的内容片段。
                - {"type": "tool_call", "tool": "..."}：表示调用某个工具。
                - {"type": "complete", "tool_calls": [...]}：表示对话完成，并附带所有工具调用日志。
        """
        tool_calls_log = []

        # 若当前没有任何工具（例如 init_tools 失败），仍允许纯 LLM 对话
        for _ in range(max_iters):
            try:
                # 构建请求参数
                request_params = {
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.1,  # 降低温度，减少随机性
                    "stream": True  # 启用流式输出
                }

                # 只有当工具列表不为空时才添加tools参数
                if self.tools:
                    request_params["tools"] = self.tools
                    request_params["tool_choice"] = "auto"
                    print(f"流式聊天使用工具模式，工具数量: {len(self.tools)}")
                else:
                    print("流式聊天使用纯LLM模式（无工具）")

                # 使用流式API调用
                stream = await self.client.chat.completions.create(**request_params)

                assistant_message = {"role": "assistant", "content": "", "tool_calls": []}
                current_tool_calls = []

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta

                        # 处理内容流
                        if delta.content:
                            assistant_message["content"] += delta.content
                            yield {"type": "content", "content": delta.content}

                        # 处理工具调用
                        if delta.tool_calls:
                            for tool_call in delta.tool_calls:
                                if tool_call.index is not None:
                                    # 确保工具调用列表足够长
                                    while len(current_tool_calls) <= tool_call.index:
                                        current_tool_calls.append({
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""}
                                        })

                                    tc = current_tool_calls[tool_call.index]
                                    if tool_call.id:
                                        tc["id"] = tool_call.id
                                    if tool_call.function:
                                        if tool_call.function.name:
                                            tc["function"]["name"] = tool_call.function.name
                                        if tool_call.function.arguments:
                                            tc["function"]["arguments"] += tool_call.function.arguments

                # 处理工具调用
                if current_tool_calls:
                    assistant_message["tool_calls"] = current_tool_calls
                    messages.append(assistant_message)

                    for tc in current_tool_calls:
                        name = tc["function"]["name"]
                        arguments = tc["function"]["arguments"] or "{}"

                        yield {"type": "tool_call", "tool": name}

                        tool_result = await self._call_tool(name, arguments)
                        tool_calls_log.append({"name": name, "arguments": arguments, "result": tool_result})

                        # 把工具结果回灌给模型
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_result
                        })
                    continue
                else:
                    # 没有工具调用，返回最终答案
                    yield {"type": "complete", "tool_calls": tool_calls_log}
                    return

            except asyncio.TimeoutError:
                yield {"type": "content", "content": "(LLM 超时未响应，请稍后重试)"}
                yield {"type": "complete", "tool_calls": tool_calls_log}
                return
            except Exception as e:
                yield {"type": "content", "content": f"(LLM 异常：{e})"}
                yield {"type": "complete", "tool_calls": tool_calls_log}
                return

        # 超过迭代上限
        yield {"type": "content", "content": "(对话达到最大迭代次数)"}
        yield {"type": "complete", "tool_calls": tool_calls_log}
