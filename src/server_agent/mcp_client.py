# mcp_client.py
import os, shlex, asyncio
from typing import List, Dict, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from constants.EnvConfig import MCP_SERVERS


class MCPClient:
    def __init__(self, launch_cmd: str):
        """
        launch_cmd 示例：
        - "python tools_server.py"
        - 或 "node dist/server.js"
        """
        self.launch_cmd = launch_cmd
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None#这边的session仍然还是一个空对象，ClientSession只是一个类型提示，后续才完成session的初始化

    async def __aenter__(self):
        parts = shlex.split(self.launch_cmd, posix=(os.name != "nt"))
        params = StdioServerParameters(command=parts[0], args=parts[1:], env=None)
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(params))
        stdio, write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        await self.exit_stack.aclose()

    async def list_tools(self) -> List[Dict[str, Any]]:
        assert self.session is not None
        resp = await self.session.list_tools()
        tools = []
        for t in resp.tools:
            tools.append({
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema  # 直接可喂给 LLM 的 tools schema
            })
        return tools

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        assert self.session is not None
        result = await self.session.call_tool(name, args)
        # 规范化返回
        return {
            "content": [c.model_dump() for c in result.content] if hasattr(result, "content") else result
        }

async def load_all_clients() -> List[MCPClient]:
    servers = MCP_SERVERS.split(";")
    clients = []
    for s in servers:
        c = MCPClient(s.strip())
        await c.__aenter__()
        clients.append(c)
    return clients
