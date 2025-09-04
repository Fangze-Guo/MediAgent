# main.py
import asyncio, os
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from agent import MCPAgent

app = FastAPI(title="MediAgent Backend")

agent = MCPAgent()
_init_lock = asyncio.Lock()
_initialized = False

class ChatReq(BaseModel):
    conversation_id: str
    message: str
    history: list[dict] = []

class ChatResp(BaseModel):
    conversation_id: str
    answer: str
    tool_calls: list = []

class ToolReq(BaseModel):
    name: str
    args: dict

@app.on_event("startup")
async def startup():
    global _initialized
    async with _init_lock:
        if not _initialized:
            await agent.init_tools()
            _initialized = True

@app.get("/tools")
async def list_tools():
    if not _initialized:
        await startup()
    return {"tools": agent.tools}

@app.post("/refresh-tools")
async def refresh_tools():
    await agent.init_tools()
    return {"ok": True, "count": len(agent.tools)}

@app.post("/chat", response_model=ChatResp)
async def chat(req: ChatReq):
    if not _initialized:
        await startup()

    msgs = [{"role": "system", "content": "你可以在需要时调用可用工具来完成任务，工具返回JSON，请先解析后用中文总结关键结果。"}]
    msgs += req.history
    msgs += [{"role": "user", "content": req.message}]

    result = await agent.chat(msgs)
    return ChatResp(conversation_id=req.conversation_id, answer=result["content"], tool_calls=result["tool_calls"])

# === 直连工具：绕过 LLM，快速排障 ===
@app.post("/call-tool")
async def call_tool(req: ToolReq):
    if not _initialized:
        await startup()
    names = [t["function"]["name"] for t in agent.tools if "function" in t]
    if req.name not in names:
        raise HTTPException(404, f"tool not found: {req.name}")
    # 内部方法，直接调用 MCP 工具
    result = await agent._call_tool(req.name, req.args)
    return {"ok": True, "result": result}

# === 健康检查 ===
@app.get("/healthz")
async def healthz():
    base_url = os.getenv("BASE_URL", "http://localhost:1234/v1")
    model = os.getenv("MODEL", "unknown")
    mcp_py = "unknown"
    try:
        # 从 tools_server 日志里已经能看到 sys.executable；这里简单带回当前进程信息
        import sys
        mcp_py = sys.executable
    except Exception:
        pass
    if not _initialized:
        await startup()
    return {
        "status": "ok",
        "model": model,
        "lm_server": base_url,
        "tools_count": len(agent.tools),
        "python": mcp_py,
    }

# === 自测：生成、缩放、校验（本地磁盘） ===
@app.get("/selftest")
async def selftest():
    import pathlib
    from PIL import Image
    root = pathlib.Path("../..")
    inp = root / "selftest_in.jpg"
    outp = root / "selftest_out.jpg"
    Image.new("RGB", (320, 200), (180, 200, 240)).save(inp)
    # 直连工具调用
    res = await agent._call_tool("resize_image", {
        "input_path": str(inp.resolve()),
        "output_path": str(outp.resolve()),
        "width": 128,
        "height": 128,
        "timeout": 30
    })
    return {"ok": True, "result": res}
