# agent.py
import os, json, asyncio
from typing import Any
from openai import AsyncOpenAI
import httpx  # 用于更精细地捕获底层 HTTP 异常
from mcp_client import load_all_clients

BASE_URL = os.getenv("BASE_URL", "http://localhost:1234/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "not-needed")
MODEL = os.getenv("MODEL", "qwen2.5-7b-instruct")
#读取.env中指定的环境变量，若不存在则使用默认值

# === 可按需调整的超时/重试策略（集中配置更清晰） ===
LLM_REQUEST_TIMEOUT_SEC = 60          # 单次 LLM 请求的总超时（上层保护）
LLM_CLIENT_TIMEOUT_SEC = 60           # AsyncOpenAI 内部 httpx 的超时
TOOL_CALL_OUTER_TIMEOUT_SEC = 360     # 对 MCP 工具调用再套一层总超时，防止卡住

class MCPAgent:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=BASE_URL,
            api_key=OPENAI_API_KEY,
            timeout=LLM_CLIENT_TIMEOUT_SEC,    # 负责和LLM直接对话，将用户的输入格式化传入给LLM，将LLM的格式化输出解析为具体行为，如回复直接传给用户，调用工具则进行调用
            # max_retries=0,  # 如需禁用 SDK 的自动重试可打开
        )
        self.mcp_clients = []  # MCP 工具服连接池。它让你的 Agent 能够同时管理多台 MCP 服务器，统一发现工具，并把每次工具调用路由到正确的那台服务器
        self.tools = []  # OpenAI tools schema
        self._tool_map = {}  # name -> mcp_client
        #动态维护工具列表和工具到服务器的映射，但是目前没有做重名工具的处理，后续有需要可能需要添加命名空间的功能

    async def init_tools(self):
        self.mcp_clients = await load_all_clients()
        self.tools.clear()
        self._tool_map.clear()
        # 汇总所有 MCP 服务器的工具
        for mc in self.mcp_clients:
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
                })  # 把 MCP 的工具描述（t["name"] / t["description"] / t["input_schema"]）转换为 OpenAI 工具列表（self.tools）——这样模型才能用 tool_calls 方式“请求调用”这些工具
                self._tool_map[name] = mc

    async def _call_tool(self, name: str, arguments_json: str | dict[str, Any]) -> str:
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

    async def chat(self, messages: list[dict], max_iters=5) -> dict:
        """
        messages: [{"role":"user","content":"..."}] 累积历史
        返回：{"role":"assistant","content":"...", "tool_calls":[...]}
        """
        #处理一轮对话，要实现上下文功能还需要外部控制
        #一轮对话内模型可能多次调用工具，这边属于LLM和agent之间的内部行为，直到LLM不再调用工具才认为已经可以向用户返回结果了
        tool_calls_log = []

        # 若当前没有任何工具（例如 init_tools 失败），仍允许纯 LLM 对话
        for _ in range(max_iters):
            # —— 用 asyncio.wait_for 给整次 LLM 推理包一层保护超时 ——
            try:
                resp = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        tools=self.tools,           # 工具列表在这边暴露给模型
                        tool_choice="auto",
                        temperature=0.2,
                    ),
                    timeout=LLM_REQUEST_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                # 返回一个清晰可见的文本给前端/用户
                return {"role": "assistant", "content": "(LLM 超时未响应，请稍后重试)", "tool_calls": tool_calls_log}
            except httpx.HTTPError as e:
                # 捕获底层网络错误（连接失败、读超时、TLS 等）
                return {"role": "assistant", "content": f"(LLM 调用失败：{e})", "tool_calls": tool_calls_log}
            except Exception as e:
                # 其他非预期异常兜底
                return {"role": "assistant", "content": f"(LLM 异常：{e})", "tool_calls": tool_calls_log}

            # —— 解析模型输出（严格防御：choices 为空/无 message 等情况） ——
            if not resp.choices:
                return {"role": "assistant", "content": "(LLM 无可用结果)", "tool_calls": tool_calls_log}
            choice = resp.choices[0]
            msg = getattr(choice, "message", None)
            if msg is None:
                return {"role": "assistant", "content": "(LLM 响应格式异常：缺少 message)", "tool_calls": tool_calls_log}

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
                return {"role": "assistant", "content": (msg.content or ""), "tool_calls": tool_calls_log}

        # 超过迭代上限也返回（避免死循环）
        return {"role": "assistant", "content": "(对话达到最大迭代次数)", "tool_calls": tool_calls_log}
