# main.py
import asyncio, os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from agent import MCPAgent
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MediAgent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

#各项功能以及内部需要等待IO的调用等都要写成协程，防止阻塞整个服务器
@app.on_event("startup")
async def startup():
    global _initialized
    async with _init_lock:#进入一个 异步锁（_init_lock = asyncio.Lock() 通常在模块顶层创建）。作用：避免竞态——如果有多个并发路径可能触发初始化（例如你在路由里也做了“懒加载兜底”），只有第一个协程能进入临界区，其它协程会等待；等初始化完成再放行。
        if not _initialized:#双保险。即使多个并发都到达这里，只有第一个会执行真正的初始化；后面进来的看到标记已置位，就直接跳过
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
    try:
        if not _initialized:
            await startup()
        msgs = [{"role": "system", "content": "你可以在需要时调用可用工具来完成任务，工具返回JSON，请先解析后用中文总结关键结果。"}]
        msgs += req.history
        msgs += [{"role": "user", "content": req.message}]
        result = await agent.chat(msgs)
        return ChatResp(conversation_id=req.conversation_id, answer=result["content"], tool_calls=result["tool_calls"])
    except Exception as e:
        print(f"/chat 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"聊天服务错误: {str(e)}")

@app.post("/chat/stream")
async def chat_stream(req: ChatReq):
    """流式聊天接口，支持实时输出"""
    try:
        if not _initialized:
            await startup()
        
        msgs = [{"role": "system", "content": "你可以在需要时调用可用工具来完成任务，工具返回JSON，请先解析后用中文总结关键结果。"}]
        msgs += req.history
        msgs += [{"role": "user", "content": req.message}]
        
        async def generate():
            try:
                # 发送开始信号
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': req.conversation_id}, ensure_ascii=False)}\n\n"
                
                # 流式获取AI回复
                async for chunk in agent.chat_stream(msgs):
                    if chunk['type'] == 'content':
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif chunk['type'] == 'tool_call':
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': chunk['tool']}, ensure_ascii=False)}\n\n"
                    elif chunk['type'] == 'complete':
                        yield f"data: {json.dumps({'type': 'complete', 'tool_calls': chunk.get('tool_calls', [])}, ensure_ascii=False)}\n\n"
                        break
                
            except Exception as e:
                print(f"流式聊天错误: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",  # ← 改成 SSE 正确类型
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # ← 反向代理(如Nginx)禁缓冲，避免卡流
            },
        )


    except Exception as e:
        print(f"/chat/stream 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"流式聊天服务错误: {str(e)}")

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
