# mcp_client.py
import os
import shlex
from contextlib import AsyncExitStack
from typing import List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.server_agent.constants.EnvConfig import MCP_SERVERS


class MCPClient:
    def __init__(self, launch_cmd: str):
        """
        launch_cmd 示例：
        - "python tools_server.py"
        - 或 "node dist/server.js"
        """
        self.launch_cmd = launch_cmd
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def __aenter__(self):
        """
        启动 MCP 工具服务器并建立客户端连接
        """
        parts = shlex.split(self.launch_cmd, posix=(os.name != "nt"))

        # 设置工作目录为项目根目录
        import pathlib
        project_root = pathlib.Path(__file__).parent.parent.parent

        # 修改命令，使用绝对路径
        if len(parts) > 1 and parts[1] and not pathlib.Path(parts[1]).is_absolute():
            parts[1] = str(project_root / parts[1])

        print(f"启动MCP服务器: {' '.join(parts)}")
        print(f"工作目录: {project_root}")

        params = StdioServerParameters(
            command=parts[0],
            args=parts[1:],
            env=None
        )
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
    """
    异步加载所有MCP客户端

    该函数根据配置加载多个MCP服务器客户端，支持默认配置和自定义配置。
    如果某个客户端加载失败，会记录错误信息但不会中断其他客户端的加载。

    Returns:
        List[MCPClient]: 成功加载的MCP客户端列表
    """
    # 获取项目根目录
    import pathlib
    project_root = pathlib.Path(__file__).parent.parent.parent
    tools_server_path = project_root / "src" / "server_agent" / "tools_server.py"

    # 如果没有配置MCP_SERVERS或配置无效，使用默认配置
    if not MCP_SERVERS or not MCP_SERVERS.strip():
        servers = [f"python {tools_server_path}"]
    else:
        servers = MCP_SERVERS.split(";")
        print(f"servers: {servers}")
        # 检查并修复路径
        fixed_servers = []
        for s in servers:
            print(f"检查路径: {s}")
            s = s.strip()
            if s and "tools_server.py" in s:
                # 如果路径中包含tools_server.py，使用绝对路径
                fixed_servers.append(f"python {tools_server_path}")
            elif s:
                fixed_servers.append(s)
        servers = fixed_servers

    print(f"MCP服务器配置: {servers}")

    clients = []
    for s in servers:
        try:
            c = MCPClient(s.strip())
            await c.__aenter__()
            clients.append(c)
            print(f"成功加载MCP客户端: {s}")
        except Exception as e:
            print(f"Failed to load MCP client '{s}': {e}")
            # 继续加载其他客户端，不因为一个失败而停止
            continue
    return clients
