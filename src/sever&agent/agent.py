# agent.py
import os, json, asyncio
from openai import OpenAI
from mcp_client import load_all_clients

BASE_URL = os.getenv("BASE_URL", "http://localhost:1234/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "not-needed")
MODEL = os.getenv("MODEL", "qwen2.5-7b-instruct")

class MCPAgent:
    def __init__(self):
        self.client = OpenAI(base_url=BASE_URL, api_key=OPENAI_API_KEY)
        self.mcp_clients = []
        self.tools = []  # OpenAI tools schema
        self._tool_map = {}  # name -> mcp_client

    async def init_tools(self):
        self.mcp_clients = await load_all_clients()
        self.tools.clear()
        self._tool_map.clear()
        # 汇总所有 MCP 服务器的工具
        for mc in self.mcp_clients:
            tl = await mc.list_tools()
            for t in tl:
                name = t["name"]
                self.tools.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": t["description"],
                        "parameters": t["input_schema"]  # 直接使用
                    }
                })
                self._tool_map[name] = mc

    async def _call_tool(self, name: str, arguments_json: str) -> str:
        args = json.loads(arguments_json) if isinstance(arguments_json, str) else arguments_json
        mc = self._tool_map[name]
        result = await mc.call_tool(name, args)
        # 约定：把工具的“结构化结果JSON字符串”返回给模型
        return json.dumps(result, ensure_ascii=False)

    async def chat(self, messages: list[dict], max_iters=5) -> dict:
        """
        messages: [{"role":"user","content":"..."}] 累积历史
        返回：{"role":"assistant","content":"...", "tool_calls":[...]}
        """
        tool_calls_log = []
        for _ in range(max_iters):
            resp = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.2,
            )
            choice = resp.choices[0]
            msg = choice.message

            if msg.tool_calls:
                # 模型要求调用工具
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
                return {"role": "assistant", "content": msg.content or "", "tool_calls": tool_calls_log}

        # 超过迭代上限也返回（避免死循环）
        return {"role": "assistant", "content": "(对话达到最大迭代次数)", "tool_calls": tool_calls_log}

